"""Indicateurs du dashboard : Elasticsearch et suivi MongoDB."""

import os
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from elasticsearch import Elasticsearch
from elastic_transport import TransportError
from elasticsearch.exceptions import ApiError
from flask import Blueprint, current_app, jsonify, render_template, request
from pymongo.errors import PyMongoError

if __package__:
    from .search import InvalidFilter, SERVICE_PATTERN, parse_date
    from .validation import BUSINESS_PAIRS
else:
    from search import InvalidFilter, SERVICE_PATTERN, parse_date
    from validation import BUSINESS_PAIRS


TIMEZONE = "Africa/Tunis"
NS_PER_MS = 1_000_000
GROUP_PAGE_SIZE = 500
MAX_GROUP_PAGES = 200

PARAMETERS = {"start", "end", "service", "organization"}


def iso(value):
    return value.astimezone(timezone.utc).isoformat(
        timespec="milliseconds"
    ).replace("+00:00", "Z")


def parse_stats_parameters(args, now):
    unknown = set(args) - PARAMETERS

    if unknown:
        raise InvalidFilter(
            sorted(unknown)[0], "Paramètre de statistiques inconnu."
        )

    for field in args:
        if len(args.getlist(field)) != 1:
            raise InvalidFilter(
                field, "Ce paramètre ne doit être fourni qu'une seule fois."
            )

    values = {
        field: args.get(field, "").strip()
        for field in PARAMETERS
    }

    service = values["service"]
    organization = values["organization"]

    if service and not SERVICE_PATTERN.fullmatch(service):
        raise InvalidFilter("service", "Nom de service invalide.")

    if (
        len(organization) > 128
        or any(ord(char) < 32 or ord(char) == 127 for char in organization)
    ):
        raise InvalidFilter(
            "organization",
            "Organisation invalide : 128 caractères maximum, sans contrôle.",
        )

    end = parse_date(values["end"], "end") or now
    start = parse_date(values["start"], "start") or (
        end - timedelta(hours=24)
    )

    if start >= end:
        raise InvalidFilter(
            "end", "La fin doit être strictement postérieure au début."
        )

    return {
        "start": iso(start),
        "end": iso(end),
        "service": service,
        "organization": organization,
    }


def query_with(filters):
    return {"bool": {"filter": filters}}


def checked_search(client, index, **kwargs):
    result = client.search(
        index=index,
        size=0,
        allow_no_indices=True,
        allow_partial_search_results=False,
        timeout="5s",
        **kwargs,
    )

    if (
        result.get("timed_out")
        or result.get("_shards", {}).get("failed", 0)
    ):
        raise RuntimeError("Agrégation Elasticsearch incomplète.")

    return result


def grouped(client, index, filters, sources, aggregations=None):
    """Parcourt tous les groupes, sans approximation de cardinalité."""
    after = None

    for _ in range(MAX_GROUP_PAGES):
        composite = {
            "size": GROUP_PAGE_SIZE,
            "sources": sources,
        }

        if after is not None:
            composite["after"] = after

        groups = {"composite": composite}

        if aggregations:
            groups["aggs"] = aggregations

        result = checked_search(
            client,
            index,
            query=query_with(filters),
            aggs={"groups": groups},
        )

        page = result["aggregations"]["groups"]
        buckets = page["buckets"]

        yield from buckets

        next_after = page.get("after_key")

        if not buckets or next_after is None:
            return

        if next_after == after:
            raise RuntimeError("Pagination des agrégations bloquée.")

        after = next_after

    raise RuntimeError("Nombre maximal de groupes dépassé.")


def collect_stats(
    client,
    parameters,
    now,
    sql_threshold_ms,
    index="loganalyzer-logs-*",
):
    common = []

    if parameters["service"]:
        common.append({
            "term": {"service.name": parameters["service"]}
        })

    if parameters["organization"]:
        common.append({
            "term": {"organization.id": parameters["organization"]}
        })

    period = common + [{
        "range": {
            "@timestamp": {
                "gte": parameters["start"],
                "lt": parameters["end"],
            }
        }
    }]

    local_now = now.astimezone(ZoneInfo(TIMEZONE))
    day_start = local_now.replace(
        hour=0, minute=0, second=0, microsecond=0
    )
    day_end = day_start + timedelta(days=1)

    slow_sql = period + [
        {"term": {"event.dataset": "saas.database"}},
        {"range": {
            "event.duration": {
                "gt": sql_threshold_ms * NS_PER_MS
            }
        }},
    ]

    summary = checked_search(
        client,
        index,
        query=query_with(common),
        track_total_hits=True,
        aggs={
            "today": {
                "filter": {
                    "range": {
                        "@timestamp": {
                            "gte": iso(day_start),
                            "lt": iso(day_end),
                        }
                    }
                }
            },
            "errors": {
                "filter": query_with(period + [{
                    "terms": {"log.level": ["ERROR", "CRITICAL"]}
                }])
            },
            "slow_sql": {
                "filter": query_with(slow_sql),
                "aggs": {
                    "executions": {
                        "top_hits": {
                            "size": 10,
                            "sort": [
                                {"event.duration": "desc"},
                                {"@timestamp": "desc"},
                                {"event.id": "asc"},
                            ],
                            "_source": [
                                "@timestamp",
                                "service.name",
                                "saas.database.query_name",
                                "event.duration",
                            ],
                        }
                    }
                },
            },
        },
    )

    latency = []

    for bucket in grouped(
        client,
        index,
        period + [
            {"term": {"event.dataset": "saas.http"}},
            {"range": {"event.duration": {"gte": 0}}},
            {"exists": {"field": "url.path"}},
        ],
        [{"endpoint": {"terms": {"field": "url.path"}}}],
        {"duration": {"avg": {"field": "event.duration"}}},
    ):
        latency.append({
            "endpoint": bucket["key"]["endpoint"],
            "request_count": bucket["doc_count"],
            "average_ms": bucket["duration"]["value"] / NS_PER_MS,
        })

    http_rates = []

    for bucket in grouped(
        client,
        index,
        period + [
            {"term": {"event.dataset": "saas.http"}},
            {"range": {
                "http.response.status_code": {"gte": 100, "lte": 599}
            }},
        ],
        [{"service": {"terms": {"field": "service.name"}}}],
        {"errors": {
            "filter": {
                "range": {
                    "http.response.status_code": {"gte": 500, "lte": 599}
                }
            }
        }},
    ):
        count = bucket["doc_count"]
        errors = bucket["errors"]["doc_count"]

        http_rates.append({
            "service": bucket["key"]["service"],
            "response_count": count,
            "error_count": errors,
            "error_rate_percent": 100 * errors / count,
        })

    active_users = sum(
        1
        for _ in grouped(
            client,
            index,
            period + [
                {"terms": {
                    "event.dataset": ["saas.http", "saas.business"]
                }},
                {"exists": {"field": "user.id"}},
                {"bool": {
                    "must_not": [{"term": {"user.id": ""}}]
                }},
            ],
            [{"user": {"terms": {"field": "user.id"}}}],
        )
    )

    admissible_actions = [
        query_with([
            {"term": {"event.action": action}},
            {"term": {"saas.feature": feature}},
        ])
        for action, feature in sorted(BUSINESS_PAIRS)
    ]

    features = [
        {
            "feature": bucket["key"]["feature"],
            "usage_count": bucket["doc_count"],
        }
        for bucket in grouped(
            client,
            index,
            period + [
                {"term": {"event.dataset": "saas.business"}},
                {"bool": {
                    "should": admissible_actions,
                    "minimum_should_match": 1,
                }},
            ],
            [{"feature": {"terms": {"field": "saas.feature"}}}],
        )
    ]

    features.sort(
        key=lambda row: (-row["usage_count"], row["feature"])
    )

    aggregations = summary["aggregations"]
    sql = aggregations["slow_sql"]

    slowest = []

    for hit in sql["executions"]["hits"]["hits"]:
        document = hit["_source"]

        slowest.append({
            "id": hit["_id"],
            "index": hit["_index"],
            "timestamp": document.get("@timestamp"),
            "service": document.get("service", {}).get("name"),
            "query_name": (
                document.get("saas", {})
                .get("database", {})
                .get("query_name")
            ),
            "duration_ms": (
                document["event"]["duration"] / NS_PER_MS
            ),
        })

    return {
        "cards": {
            "total_logs": summary["hits"]["total"]["value"],
            "today_logs": aggregations["today"]["doc_count"],
            "error_logs": aggregations["errors"]["doc_count"],
        },
        "today": {
            "date": day_start.date().isoformat(),
            "start": iso(day_start),
            "end": iso(day_end),
        },
        "saas": {
            "http_latency_by_endpoint": latency,
            "http_5xx_by_service": http_rates,
            "slow_sql": {
                "threshold_ms": sql_threshold_ms,
                "execution_count": sql["doc_count"],
                "slowest": slowest,
            },
            "active_users": active_users,
            "active_users_exact": True,
            "feature_usage": features,
        },
    }


def register_stats(app, client_factory):
    stats = Blueprint("stats", __name__)

    threshold = int(os.environ.get("SQL_SLOW_THRESHOLD_MS", "1000"))

    if not 0 <= threshold <= 9_223_372_036_854:
        raise ValueError("SQL_SLOW_THRESHOLD_MS hors limites.")

    @stats.get("/dashboard")
    def dashboard_page():
        return render_template("dashboard.html")

    @stats.get("/api/v1/stats")
    def get_stats():
        now = datetime.now(timezone.utc)

        try:
            parameters = parse_stats_parameters(request.args, now)
        except InvalidFilter as error:
            response = jsonify(error={
                "code": "INVALID_FILTER",
                "field": error.field,
                "message": str(error),
            })
            response.headers["Cache-Control"] = "no-store"
            return response, 400

        host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
        port = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
        url = os.environ.get(
            "ELASTICSEARCH_URL", f"http://{host}:{port}"
        )

        try:
            with Elasticsearch(
                url, request_timeout=10, max_retries=0
            ) as client:
                data = collect_stats(
                    client, parameters, now, threshold
                )

            with client_factory() as client:
                database = client[
                    os.environ.get("MONGODB_DATABASE", "loganalyzer")
                ]
                imported_files = database.imports.count_documents(
                    {"confirmed_at": {"$type": "date"}},
                    maxTimeMS=5000,
                )

        except (ApiError, TransportError, PyMongoError, RuntimeError):
            current_app.logger.exception(
                "Calcul des indicateurs indisponible"
            )
            response = jsonify(error={
                "code": "STATS_UNAVAILABLE",
                "message": (
                    "Les indicateurs sont temporairement indisponibles. "
                    "Réessayez dans quelques instants."
                ),
            })
            response.headers["Cache-Control"] = "no-store"
            return response, 503

        data["cards"]["imported_files"] = imported_files
        data["generated_at"] = iso(now)
        data["timezone"] = TIMEZONE
        data["filters"] = parameters
        data["period_bounds"] = "[start,end)"
        data["duration_unit"] = "ms"

        response = jsonify(data)
        response.headers["Cache-Control"] = "no-store"
        return response

    app.register_blueprint(stats)
