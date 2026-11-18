"""Lecture des résultats confirmés dans Elasticsearch et des rejets."""

import json
from itertools import islice
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


class ResultReadError(RuntimeError):
    pass


def read_rejections(path, upload_id):
    """Retourner un rejet par ligne source, sans compter les répétitions."""
    rows = {}

    try:
        source = Path(path).open("rb")
    except FileNotFoundError:
        return rows

    with source:
        for raw in source:
            # Une écriture en cours sera relue au prochain contrôle.
            if not raw.endswith(b"\n"):
                break

            try:
                row = json.loads(raw)
            except (ValueError, UnicodeDecodeError) as error:
                raise ResultReadError(
                    "Fichier de rejets illisible."
                ) from error

            if not isinstance(row, dict):
                raise ResultReadError("Structure de rejet incorrecte.")

            if row.get("upload_id") != upload_id:
                continue

            number = row.get("source_line")
            errors = row.get("errors")

            if (
                type(number) is not int or number < 1
                or row.get("failure_kind") not in {"data", "technical"}
                or not isinstance(row.get("raw"), str)
                or not isinstance(errors, list) or not errors
                or any(
                    not isinstance(item, dict)
                    or not isinstance(item.get("code"), str)
                    or not isinstance(item.get("message"), str)
                    for item in errors
                )
            ):
                raise ResultReadError("Diagnostic de rejet incomplet.")

            if number in rows and rows[number] != row:
                raise ResultReadError(
                    "Résultats contradictoires pour une ligne."
                )

            rows[number] = row

    return rows


def search_results(es_url, body):
    request = Request(
        es_url.rstrip("/")
        + "/loganalyzer-logs-*/_search?allow_no_indices=true",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=10) as response:
            return json.load(response)
    except (URLError, OSError, ValueError) as error:
        raise ResultReadError(
            "Impossible de vérifier les résultats dans Elasticsearch."
        ) from error


def read_indexed_lines(es_url, upload_id, source_lines):
    """Vérifier les identifiants attendus par lots de 500 événements."""
    indexed = set()
    iterator = iter(source_lines)

    while True:
        batch = list(islice(iterator, 500))

        if not batch:
            return indexed

        expected = {
            f"{upload_id}:{number}": number
            for number in batch
        }

        result = search_results(es_url, {
            "size": 501,
            "track_total_hits": True,
            "_source": ["event.id", "loganalyzer"],
            "query": {
                "bool": {
                    "filter": [
                        {"term": {"loganalyzer.upload_id": upload_id}},
                        {"terms": {"event.id": list(expected)}},
                    ]
                }
            },
        })

        try:
            if result["timed_out"] or result["_shards"]["failed"]:
                raise ResultReadError(
                    "Recherche Elasticsearch incomplète."
                )

            total = result["hits"]["total"]
            hits = result["hits"]["hits"]

            if (
                total["relation"] != "eq"
                or total["value"] != len(hits)
                or len(hits) > len(expected)
            ):
                raise ResultReadError("Bilan Elasticsearch incohérent.")

            for hit in hits:
                source = hit["_source"]
                event_id = source["event"]["id"]
                context = source["loganalyzer"]
                number = context["source_line"]

                if (
                    event_id not in expected
                    or hit["_id"] != event_id
                    or context["upload_id"] != upload_id
                    or type(number) is not int
                    or number != expected[event_id]
                    or number in indexed
                ):
                    raise ResultReadError(
                        "Identité de document incohérente."
                    )

                indexed.add(number)

        except (KeyError, TypeError, AttributeError) as error:
            raise ResultReadError(
                "Réponse Elasticsearch incorrecte."
            ) from error