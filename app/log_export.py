"""Export CSV des résultats d'une recherche."""

import csv
import io
from datetime import datetime, timezone

from elasticsearch.exceptions import ApiError
from elastic_transport import TransportError
from flask import Blueprint, Response, current_app, request

if __package__:
    from .log_actions import elasticsearch_client, json_error
    from .search import InvalidFilter, build_query, build_sort, parse_parameters
else:
    from log_actions import elasticsearch_client, json_error
    from search import InvalidFilter, build_query, build_sort, parse_parameters


EXPORT_MAX_ROWS = 10000
EXPORT_MAX_BYTES = 20 * 1024 * 1024

CSV_COLUMNS = (
    "_index",
    "_id",
    "@timestamp",
    "log.level",
    "service.name",
    "message",
    "event.dataset",
    "event.kind",
    "event.action",
    "event.duration",
    "event.ingested",
    "event.id",
    "http.request.method",
    "http.request.id",
    "http.response.status_code",
    "url.path",
    "user.id",
    "organization.id",
    "error.code",
    "error.message",
    "saas.feature",
    "saas.database.query_name",
    "log.file.path",
    "loganalyzer.upload_id",
    "loganalyzer.source_line",
    "loganalyzer.original_filename",
    "loganalyzer.schema_version",
    "ecs.version",
)


def document_value(document, field):
    value = document

    for part in field.split("."):
        if not isinstance(value, dict):
            return ""
        value = value.get(part)

    return "" if value is None else value


def csv_value(value):
    # Évite qu'un message soit interprété comme formule par un tableur.
    if isinstance(value, str):
        stripped = value.lstrip()
        if stripped.startswith(("=", "+", "-", "@")) or value.startswith(
            ("\t", "\r", "\n")
        ):
            return "'" + value
    return value


def csv_line(values):
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(values)
    return buffer.getvalue().encode("utf-8")


def register_log_export(app):
    exports = Blueprint("log_export", __name__)

    @exports.get("/api/v1/logs/export")
    def export_logs():
        if "page" in request.args:
            return json_error(
                "INVALID_FILTER",
                "L'export porte sur tous les résultats filtrés. "
                "Ne fournissez pas de paramètre page.",
                400,
            )

        try:
            parameters = parse_parameters(request.args)
        except InvalidFilter as error:
            response = json_error("INVALID_FILTER", str(error), 400)
            response.get_json()
            # Ajouter le nom du paramètre incorrect dans la réponse.
            from flask import jsonify
            response = jsonify(error={
                "code": "INVALID_FILTER",
                "field": error.field,
                "message": str(error),
            })
            response.status_code = 400
            response.headers["Cache-Control"] = "no-store"
            return response

        try:
            with elasticsearch_client() as client:
                result = client.search(
                    index="loganalyzer-logs-*",
                    query=build_query(parameters),
                    sort=build_sort(parameters),
                    size=EXPORT_MAX_ROWS,
                    source_includes=[
                        field for field in CSV_COLUMNS
                        if field not in {"_index", "_id"}
                    ],
                    track_total_hits=True,
                    allow_no_indices=True,
                    allow_partial_search_results=False,
                    timeout="10s",
                )

            if (
                result.get("timed_out")
                or result.get("_shards", {}).get("failed", 0)
            ):
                raise RuntimeError("Résultat Elasticsearch incomplet.")

            total = result["hits"]["total"]["value"]
            hits = result["hits"]["hits"]

            if total > EXPORT_MAX_ROWS:
                return json_error(
                    "EXPORT_LIMIT",
                    f"La recherche contient {total} logs. "
                    f"La limite est de {EXPORT_MAX_ROWS}. "
                    "Précisez les filtres avant d'exporter.",
                    422,
                )

            if len(hits) != total:
                raise RuntimeError("Export incomplet.")

        except (ApiError, TransportError, RuntimeError):
            current_app.logger.exception("Échec de préparation de l'export")
            return json_error(
                "EXPORT_UNAVAILABLE",
                "L'export est temporairement indisponible.",
                503,
            )

        # BOM UTF-8 puis en-tête : même une recherche vide produit un CSV lisible.
        output = bytearray(b"\xef\xbb\xbf")
        output.extend(csv_line(CSV_COLUMNS))

        for hit in hits:
            values = []

            for field in CSV_COLUMNS:
                if field in {"_index", "_id"}:
                    value = hit[field]
                else:
                    value = document_value(hit["_source"], field)

                values.append(csv_value(value))

            row = csv_line(values)

            if len(output) + len(row) > EXPORT_MAX_BYTES:
                return json_error(
                    "EXPORT_SIZE_LIMIT",
                    "Le fichier CSV dépasse 20 Mio. "
                    "Précisez les filtres avant d'exporter.",
                    422,
                )

            output.extend(row)

        filename = datetime.now(timezone.utc).strftime(
            "loganalyzer-export-%Y%m%dT%H%M%SZ.csv"
        )

        response = Response(
            bytes(output),
            content_type="text/csv; charset=utf-8",
        )
        response.headers["Content-Disposition"] = (
            f'attachment; filename="{filename}"'
        )
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Export-Count"] = str(total)
        response.headers["X-Export-Limit"] = str(EXPORT_MAX_ROWS)
        return response

    app.register_blueprint(exports)
