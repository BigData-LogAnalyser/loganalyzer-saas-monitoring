"""Recherche des logs indexés dans Elasticsearch."""

import os
import re
from datetime import datetime, timezone

from elasticsearch import Elasticsearch
from elastic_transport import TransportError
from elasticsearch.exceptions import ApiError
from flask import Blueprint, current_app, jsonify, render_template, request


if __package__:
    from .search_history import record_search
else:
    from search_history import record_search


PAGE_SIZE = 50
MAX_PAGE = 200

LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

SORT_FIELDS = {
    "date": "@timestamp",
    "level": "log.level",
    "service": "service.name",
}

ALLOWED_PARAMETERS = {
    "q", "general", "level", "service", "start", "end",
    "sort", "order", "page", "upload_id",
}

DATE_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d{1,3})?(?:Z|[+-]\d{2}:\d{2})"
)

SERVICE_PATTERN = re.compile(r"[a-z][a-z0-9-]{0,63}")


class InvalidFilter(ValueError):
    def __init__(self, field, message):
        super().__init__(message)
        self.field = field


def parse_date(value, field):
    if not value:
        return None

    if not DATE_PATTERN.fullmatch(value):
        raise InvalidFilter(
            field,
            "Utilisez une date ISO 8601 avec fuseau, "
            "par exemple 2026-11-04T10:00:00Z.",
        )

    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
        offset_seconds = abs(result.utcoffset().total_seconds())

        if offset_seconds > 14 * 3600:
            raise ValueError("Fuseau hors limites.")

        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise InvalidFilter(field, "Date ou fuseau invalide.") from None


def parse_parameters(args):
    unknown = set(args) - ALLOWED_PARAMETERS

    if unknown:
        raise InvalidFilter(
            sorted(unknown)[0],
            "Paramètre de recherche inconnu.",
        )

    for field in args:
        if len(args.getlist(field)) != 1:
            raise InvalidFilter(
                field,
                "Ce paramètre ne doit être fourni qu'une seule fois.",
            )

    values = {
        field: args.get(field, "").strip()
        for field in ALLOWED_PARAMETERS
    }

    values["upload_id"] = values["upload_id"].lower()

    if values["upload_id"] and not re.fullmatch(
        r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}",
        values["upload_id"],
    ):
        raise InvalidFilter(
            "upload_id", "Identifiant d’import invalide."
        )

    if len(values["q"]) > 500:
        raise InvalidFilter("q", "Le texte est limité à 500 caractères.")

    if len(values["general"]) > 500:
        raise InvalidFilter(
            "general", "La recherche générale est limitée à 500 caractères."
        )

    if len(values["general"].split()) > 10:
        raise InvalidFilter(
            "general", "La recherche générale est limitée à 10 termes."
        )

    if values["level"] and values["level"] not in LEVELS:
        raise InvalidFilter(
            "level",
            "Niveaux acceptés : DEBUG, INFO, WARNING, ERROR, CRITICAL.",
        )

    if (
        values["service"]
        and not SERVICE_PATTERN.fullmatch(values["service"])
    ):
        raise InvalidFilter(
            "service",
            "Service invalide : 1 à 64 caractères, "
            "lettres minuscules, chiffres et tirets ; "
            "le premier caractère doit être une lettre.",
        )

    sort = values["sort"] or "date"
    order = values["order"] or "desc"
    page_text = values["page"] or "1"

    if sort not in SORT_FIELDS:
        raise InvalidFilter(
            "sort", "Tris acceptés : date, level, service."
        )

    if order not in {"asc", "desc"}:
        raise InvalidFilter(
            "order", "Ordres acceptés : asc, desc."
        )

    if not re.fullmatch(r"[1-9][0-9]{0,2}", page_text):
        raise InvalidFilter(
            "page", f"La page doit être comprise entre 1 et {MAX_PAGE}."
        )

    page = int(page_text)

    if page > MAX_PAGE:
        raise InvalidFilter(
            "page",
            "La navigation est limitée à 10 000 résultats. "
            "Précisez les filtres pour réduire la recherche.",
        )

    start = parse_date(values["start"], "start")
    end = parse_date(values["end"], "end")

    if start and end and start > end:
        raise InvalidFilter(
            "end",
            "La fin de période doit être postérieure ou égale au début.",
        )

    return {
        "q": values["q"],
        "general": values["general"],
        "upload_id": values["upload_id"],
        "level": values["level"],
        "service": values["service"],
        "start": (
            start.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            if start else None
        ),
        "end": (
            end.isoformat(timespec="milliseconds").replace("+00:00", "Z")
            if end else None
        ),
        "sort": sort,
        "order": order,
        "page": page,
    }



def build_general_query(value):
    terms = []

    for word in value.split():
        # *, ? et \ saisis par l'utilisateur restent des caractères littéraux.
        escaped = (
            word.replace("\\", "\\\\")
            .replace("*", "\\*")
            .replace("?", "\\?")
        )

        terms.append({
            "bool": {
                "should": [
                    {
                        "wildcard": {
                            "loganalyzer.search_values": {
                                "value": f"*{escaped}*",
                                "case_insensitive": True,
                            }
                        }
                    },
                    {
                        "match": {
                            "loganalyzer.search_text": {
                                "query": word,
                                "operator": "and",
                                "fuzziness": "AUTO",
                                "prefix_length": 0,
                                "max_expansions": 50,
                            }
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        })

    return {"bool": {"must": terms}}


def build_query(parameters):
    filters = []

    if parameters.get("upload_id"):
        filters.append({
            "term": {
                "loganalyzer.upload_id": parameters["upload_id"]
            }
        })

    if parameters["level"]:
        filters.append({"term": {"log.level": parameters["level"]}})

    if parameters["service"]:
        filters.append({"term": {"service.name": parameters["service"]}})

    period = {}

    if parameters["start"]:
        period["gte"] = parameters["start"]

    if parameters["end"]:
        period["lte"] = parameters["end"]

    if period:
        filters.append({"range": {"@timestamp": period}})

    must = []

    if parameters["q"]:
        must.append({
            "multi_match": {
                "query": parameters["q"],
                "fields": ["message", "error.message"],
                "type": "cross_fields",
                "operator": "and",
            }
        })

    if parameters["general"]:
        must.append(build_general_query(parameters["general"]))

    return {"bool": {"must": must, "filter": filters}}


def build_sort(parameters):
    primary = SORT_FIELDS[parameters["sort"]]
    result = [{primary: {"order": parameters["order"]}}]

    if primary != "@timestamp":
        result.append({"@timestamp": {"order": "desc"}})

    # Départage les événements qui ont la même valeur de tri.
    result.append({"event.id": {"order": "asc"}})
    return result


def register_search(app):
    search = Blueprint("search", __name__)

    @search.get("/logs")
    def search_page():
        return render_template("search.html")

    @search.get("/api/v1/logs")
    def search_logs():
        try:
            parameters = parse_parameters(request.args)
        except InvalidFilter as error:
            return jsonify(error={
                "code": "INVALID_FILTER",
                "field": error.field,
                "message": str(error),
            }), 400

        executed_at = datetime.now(timezone.utc)

        host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
        port = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
        url = os.environ.get(
            "ELASTICSEARCH_URL", f"http://{host}:{port}"
        )

        try:
            with Elasticsearch(
                url,
                request_timeout=10,
                max_retries=0,
            ) as client:
                result = client.search(
                    index="loganalyzer-logs-*",
                    query=build_query(parameters),
                    sort=build_sort(parameters),
                    from_=(parameters["page"] - 1) * PAGE_SIZE,
                    size=PAGE_SIZE,
                    track_total_hits=True,
                    allow_no_indices=True,
                    allow_partial_search_results=False,
                    timeout="5s",
                )

            if (
                result.get("timed_out")
                or result.get("_shards", {}).get("failed", 0)
            ):
                raise RuntimeError("Résultat Elasticsearch incomplet.")

        except (ApiError, TransportError, RuntimeError):
            current_app.logger.exception(
                "Échec de la recherche Elasticsearch"
            )
            return jsonify(error={
                "code": "SEARCH_UNAVAILABLE",
                "message": (
                    "La recherche est temporairement indisponible. "
                    "Réessayez dans quelques instants."
                ),
            }), 503

        total = result["hits"]["total"]["value"]
        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE
        accessible_pages = min(total_pages, MAX_PAGE)

        items = [
            {
                "id": hit["_id"],
                "index": hit["_index"],
                "document": hit["_source"],
            }
            for hit in result["hits"]["hits"]
        ]

        history_status = record_search(parameters, total, executed_at)

        response = jsonify(
            history=history_status,
            items=items,
            total=total,
            page=parameters["page"],
            page_size=PAGE_SIZE,
            total_pages=total_pages,
            accessible_pages=accessible_pages,
            pagination_limited=total_pages > MAX_PAGE,
            has_previous=parameters["page"] > 1,
            has_next=parameters["page"] < accessible_pages,
            filters=parameters,
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    app.register_blueprint(search)
