#!/usr/bin/env python3
"""SCRUM-18 : validation HTTP -> tracker -> Logstash -> Elasticsearch.

À lancer dans un conteneur webapp avec les samples et le dossier de bilan
montés. Chaque exécution crée ses propres imports et conserve les preuves.
"""

import argparse
from collections import Counter
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import sys
import time
import traceback
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import uuid4


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def utcnow():
    return datetime.now(timezone.utc)


def json_default(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    raise TypeError(f"Valeur non sérialisable : {type(value).__name__}")


def http_json(url, data=None, content_type="application/json"):
    request = Request(
        url,
        data=data,
        headers={"Content-Type": content_type},
        method="GET" if data is None else "POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.loads(error.read())


def check_reference_documents(documents, targets, metadata, extension, since):
    first = 2 if extension == "csv" else 1
    by_line = {}
    for hit in documents:
        source = hit["_source"]
        number = source["loganalyzer"]["source_line"]
        require(number not in by_line, "Numéro de ligne indexé plusieurs fois.")
        by_line[number] = hit

    require(
        set(by_line) == set(range(first, first + len(targets))),
        "Les numéros de ligne indexés ne correspondent pas aux références.",
    )

    for offset, target in enumerate(targets):
        number = first + offset
        hit = by_line[number]
        actual = deepcopy(hit["_source"])
        expected = deepcopy(target)
        event_id = f'{metadata["upload_id"]}:{number}'

        require(hit["_id"] == event_id, "Identifiant Elasticsearch incorrect.")
        ingested = actual["event"].pop("ingested")
        receipt = datetime.fromisoformat(ingested.replace("Z", "+00:00"))
        require(receipt.utcoffset() == timedelta(0), "Date de réception non UTC.")
        require(
            since - timedelta(seconds=5) <= receipt <= utcnow() + timedelta(seconds=5),
            "Date de réception hors de la période de ce test.",
        )
        expected["event"].pop("ingested", None)
        expected["event"]["id"] = event_id
        expected["loganalyzer"]["upload_id"] = metadata["upload_id"]
        expected["loganalyzer"]["source_line"] = number
        expected["loganalyzer"]["original_filename"] = metadata["original_filename"]
        expected["log"]["file"]["path"] = str(
            Path("/uploads") / metadata["source_relative_path"]
        )
        require(
            actual == expected,
            f"Document de la ligne {number} différent de la cible : "
            + json.dumps({"attendu": expected, "obtenu": actual}, ensure_ascii=False),
        )


class ValidationSuite:
    def __init__(self, args, database):
        self.args = args
        self.database = database
        self.samples = Path(args.samples)
        self.expected = json.loads(
            (self.samples / "attendus.json").read_text(encoding="utf-8")
        )
        self.targets = [
            json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((self.samples / "cibles").glob("*.json"))
        ]
        require(len(self.targets) == 4, "Quatre documents cibles sont attendus.")
        self.run_id = utcnow().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
        output = Path(args.output)
        output.mkdir(parents=True, exist_ok=True)
        self.output = output / f"bilan-{self.run_id}.json"
        self.report = {
            "ticket": "SCRUM-18",
            "run_id": self.run_id,
            "started_at": utcnow(),
            "python_version": platform.python_version(),
            "scope": "Uploads HTTP réels, imports confirmés et comparaison aux références.",
            "processing_error_test": "À réaliser séparément ; non couvert par ce script.",
            "cases": [],
        }
        reference_files = [self.samples / "attendus.json"] + sorted(
            (self.samples / "cibles").glob("*.json")
        )
        self.report["references_sha256"] = {
            str(path.relative_to(self.samples)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in reference_files
        }
        self.current = None
        self.es_url = "http://{}:{}".format(
            os.environ["ELASTICSEARCH_HOST"], os.environ["ELASTICSEARCH_PORT"]
        )
        self.save()

    def save(self):
        temporary = self.output.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(self.report, ensure_ascii=False, indent=2, default=json_default) + "\n",
            encoding="utf-8",
        )
        temporary.replace(self.output)

    def api(self, path, data=None, content_type="application/json"):
        return http_json(self.args.api_url.rstrip("/") + path, data, content_type)

    def documents(self, field, value):
        status, result = http_json(
            self.es_url + "/loganalyzer-logs-*/_search?allow_no_indices=true",
            json.dumps({
                "size": 1000,
                "track_total_hits": True,
                "query": {"term": {field: value}},
            }).encode("utf-8"),
        )
        require(status == 200, f"Recherche Elasticsearch refusée : {result}")
        require(not result["timed_out"], "Recherche Elasticsearch expirée.")
        require(result["_shards"]["failed"] == 0, "Recherche Elasticsearch incomplète.")
        hits = result["hits"]["hits"]
        total = result["hits"]["total"]
        require(
            total["relation"] == "eq" and total["value"] == len(hits),
            "Résultats Elasticsearch incomplets ou trop nombreux pour ce test.",
        )
        return hits

    def preview(self, path):
        content = path.read_bytes()
        filename = f"scrum18-{self.run_id}-{self.current['name']}{path.suffix}"
        boundary = "boundary-" + uuid4().hex
        payload = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        status, result = self.api(
            "/api/imports/preview", payload, f"multipart/form-data; boundary={boundary}"
        )
        self.current.update({
            "source": str(path.relative_to(self.samples)),
            "source_sha256": hashlib.sha256(content).hexdigest(),
            "original_filename": filename,
            "preview_http_status": status,
            "preview_response": result,
        })
        self.save()
        return status, result

    def wait_for_import(self, upload_id):
        deadline = time.monotonic() + self.args.timeout
        states = []
        while True:
            status, result = self.api(f"/api/imports/{upload_id}")
            require(status == 200, f"Consultation du suivi impossible : {result}")
            row = result["import_record"]
            self.current["import_record"] = row
            if not states or states[-1]["status"] != row["status"]:
                states.append({"status": row["status"], "observed_at": utcnow()})
                print(f"  {self.current['name']} : {row['status']}", flush=True)
            self.current["observed_states"] = states
            self.save()
            if row["status"] in {"TERMINE", "PARTIEL", "ECHEC"}:
                return row
            require(time.monotonic() < deadline, f"Import {upload_id} toujours en cours après le délai de test.")
            time.sleep(1)

    def accepted(self, path, expected, indexed, rejected, final_status, compare_targets=False):
        since = utcnow()
        status, preview = self.preview(path)
        require(status == 201 and preview["preview"]["can_confirm"], "Aperçu valide refusé.")
        upload_id = preview["upload_id"]
        self.current["upload_id"] = upload_id
        self.save()
        status, confirmation = self.api(f"/api/imports/{upload_id}/confirm", b"")
        self.current["confirmation_response"] = confirmation
        require(status in {200, 201}, f"Confirmation refusée : {confirmation}")
        status, repeated = self.api(f"/api/imports/{upload_id}/confirm", b"")
        require(status == 200 and repeated["upload_id"] == upload_id, "Nouvelle confirmation non idempotente.")
        row = self.wait_for_import(upload_id)
        require(row["status"] == final_status, f"État final inattendu : {row}")
        for field, value in (
            ("expected_count", expected), ("indexed_count", indexed),
            ("rejected_count", rejected), ("progress_percent", 100),
        ):
            require(row[field] == value, f"{field} : attendu {value}, obtenu {row[field]}.")
        require(row["reading_complete"] is True, "Fin de lecture non confirmée.")
        require(row["error"] is None, f"Erreur technique inattendue : {row['error']}")
        require(expected == indexed + rejected, "Bilan attendu incohérent.")
        metadata = self.database.imports.find_one({"_id": upload_id})
        require(metadata is not None, "Métadonnées MongoDB absentes.")
        require(
            metadata["original_filename"] == row["original_filename"] == self.current["original_filename"],
            "Nom du fichier importé incorrect.",
        )
        for field in ("status", "expected_count", "indexed_count", "rejected_count"):
            require(metadata[field] == row[field], f"Désaccord API/MongoDB sur {field}.")
        original = Path(os.environ.get("UPLOAD_DIR", "/app/uploads")) / metadata["source_relative_path"]
        require(original.read_bytes() == path.read_bytes(), "Le fichier original conservé a changé.")
        require(metadata["source_sha256"] == self.current["source_sha256"], "Empreinte MongoDB incorrecte.")
        documents = self.documents("loganalyzer.upload_id", upload_id)
        self.current["indexed_documents"] = documents
        require(len(documents) == indexed, "Le nombre réellement indexé diffère du bilan.")
        for hit in documents:
            source = hit["_source"]
            number = source["loganalyzer"]["source_line"]
            require(hit["_id"] == source["event"]["id"] == f"{upload_id}:{number}", "Identité de document incorrecte.")
            require(source["event"].get("ingested"), "Date de réception absente.")
        status, diagnostics = self.api(f"/api/imports/{upload_id}/rejections?limit=100")
        require(status == 200 and not diagnostics["has_more"], "Lecture des diagnostics incomplète.")
        self.current["diagnostics"] = diagnostics["items"]
        require(len(diagnostics["items"]) == rejected, "Nombre de diagnostics inattendu.")
        stored = list(self.database.import_rejections.find({"upload_id": upload_id}))
        require(len(stored) == rejected, "Nombre de rejets MongoDB incorrect.")
        require(
            {r["source_line"] for r in stored} == {r["source_line"] for r in diagnostics["items"]},
            "Les lignes rejetées diffèrent entre MongoDB et l'API.",
        )
        for saved in stored:
            public = next(r for r in diagnostics["items"] if r["source_line"] == saved["source_line"])
            require(saved["_id"] == f"{upload_id}:{saved['source_line']}", "Identité du rejet MongoDB incorrecte.")
            for field in ("raw", "errors", "failure_kind"):
                require(saved[field] == public[field], f"Diagnostic MongoDB/API différent : {field}.")
        if compare_targets:
            check_reference_documents(documents, self.targets, metadata, path.suffix[1:], since)
            counts = Counter(hit["_source"]["event"]["dataset"] for hit in documents)
            require(dict(counts) == self.expected["valides"]["dataset_counts"], "Répartition des familles incorrecte.")
        else:
            require(preview["preview"]["preview_count"] == self.expected["mixte"]["apercu_valide"], "Aperçu mixte incorrect.")
            require(
                {hit["_source"]["loganalyzer"]["source_line"] for hit in documents}
                == set(range(1, self.expected["mixte"]["apercu_valide"] + 1)),
                "Les lignes indexées du fichier mixte ne sont pas les dix premières.",
            )
            actual_lines = {row["source_line"] for row in diagnostics["items"]}
            require(actual_lines == set(self.expected["mixte"]["lignes_rejetees"]), "Lignes rejetées du fichier mixte incorrectes.")
            raw_lines = path.read_bytes().split(b"\n")
            for diagnostic in diagnostics["items"]:
                number = diagnostic["source_line"]
                require(diagnostic["failure_kind"] == "data", "Erreur technique confondue avec rejet de données.")
                raw = raw_lines[number - 1].removesuffix(b"\r").decode("utf-8")
                require(diagnostic["raw"] == raw, "Contenu original du rejet altéré.")
                require(diagnostic["errors"], "Motif du rejet absent.")

    def refused(self, path, semantic=False, code=None):
        status, result = self.preview(path)
        require(status == 422, f"Le fichier invalide n'a pas été refusé : HTTP {status}.")
        require("upload_id" not in result, "Un fichier invalide ne doit pas être confirmable.")
        require(result["preview"]["can_confirm"] is False, "Confirmation autorisée malgré les erreurs.")
        errors = result["preview"]["errors"]
        if semantic:
            line_key = "ligne_csv" if path.suffix == ".csv" else "ligne_jsonl_txt"
            expected = {(r[line_key], r["code"], r["field"]) for r in self.expected["invalides_semantiques"]}
            actual = {(r["source_line"], r["code"], r["field"]) for r in errors}
            require(expected <= actual, "Les diagnostics sémantiques attendus ne sont pas tous présents.")
        else:
            require(code in {r["code"] for r in errors}, f"Code attendu absent : {code}.")
        filename = self.current["original_filename"]
        require(self.database.imports.count_documents({"original_filename": filename}) == 0, "Import créé malgré le refus.")
        require(not self.documents("loganalyzer.original_filename", filename), "Événements indexés malgré le refus.")

    def run_case(self, name, function):
        self.current = {"name": name, "started_at": utcnow(), "result": "EN_COURS"}
        self.report["cases"].append(self.current)
        self.save()
        print(f"TEST : {name}", flush=True)
        try:
            function()
            self.current["result"] = "OK"
            print(f"OK : {name}", flush=True)
        except Exception as error:
            self.current["result"] = "ECHEC"
            self.current["error"] = str(error)
            self.current["traceback"] = traceback.format_exc()
            print(f"ECHEC : {name} — {error}", flush=True)
        finally:
            self.current["finished_at"] = utcnow()
            self.save()

    def run(self):
        status, health = self.api("/health")
        require(status == 200 and health["status"] == "ok", "Flask n'est pas disponible.")
        count = self.expected["valides"]["evenements_par_fichier"]
        for extension in ("csv", "jsonl", "txt"):
            self.run_case(f"valide-{extension}", lambda ext=extension: self.accepted(
                self.samples / "valides" / f"logs.{ext}", count, count, 0, "TERMINE", True
            ))
        for extension in ("csv", "jsonl", "txt"):
            self.run_case(f"invalide-{extension}", lambda ext=extension: self.refused(
                self.samples / "invalides" / f"logs.{ext}", semantic=True
            ))
        for filename, code in self.expected["structure"].items():
            self.run_case(f"structure-{Path(filename).stem}", lambda name=filename, expected_code=code: self.refused(
                self.samples / "invalides" / name, code=expected_code
            ))
        mixed = self.expected["mixte"]
        self.run_case("mixte-jsonl", lambda: self.accepted(
            self.samples / "mixte.jsonl", mixed["attendus"], mixed["indexes"],
            mixed["rejetes"], mixed["etat"],
        ))
        failures = sum(case["result"] != "OK" for case in self.report["cases"])
        self.report.update({
            "finished_at": utcnow(),
            "passed": len(self.report["cases"]) - failures,
            "failed": failures,
            "result": "ECHEC" if failures else "OK",
        })
        self.save()
        print(f"Bilan : {self.report['passed']} scénarios réussis, {failures} en échec.", flush=True)
        print(f"Résultats enregistrés : {self.output}", flush=True)
        return 1 if failures else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-url", default="http://webapp:8000")
    parser.add_argument("--samples", default="/samples")
    parser.add_argument("--output", default="/results")
    parser.add_argument("--timeout", type=float, default=240)
    args = parser.parse_args()
    require(args.timeout > 0, "Le délai doit être positif.")
    from pymongo import MongoClient
    with MongoClient(
        host=os.environ["MONGODB_HOST"], port=int(os.environ["MONGODB_PORT"]),
        serverSelectionTimeoutMS=5000, connectTimeoutMS=5000, socketTimeoutMS=10000,
    ) as client:
        client.admin.command("ping")
        database = client[os.environ.get("MONGODB_DATABASE", "loganalyzer")]
        return ValidationSuite(args, database).run()


if __name__ == "__main__":
    sys.exit(main())
