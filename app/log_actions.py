"""Consultation des documents Elasticsearch."""

import os
import re

from elasticsearch import Elasticsearch
from elasticsearch.exceptions import ApiError
from elastic_transport import TransportError
from flask import Blueprint, current_app, jsonify, request


INDEX_PATTERN = re.compile(r"loganalyzer-logs-\d{4}\.\d{2}\.\d{2}")


def elasticsearch_client():
    host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
    port = int(os.environ.get("ELASTICSEARCH_PORT", "9200"))
    url = os.environ.get("ELASTICSEARCH_URL", f"http://{host}:{port}")

    return Elasticsearch(url, request_timeout=10, max_retries=0)


def json_error(code, message, status):
    response = jsonify(error={"code": code, "message": message})
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def register_log_actions(app):
    actions = Blueprint("log_actions", __name__)

    @actions.get("/api/v1/logs/<string:log_id>")
    def get_log_detail(log_id):
        if set(request.args) - {"index"}:
            return json_error(
                "INVALID_PARAMETER",
                "Seul le paramètre index est accepté.",
                400,
            )

        if len(request.args.getlist("index")) > 1:
            return json_error(
                "INVALID_PARAMETER",
                "Le paramètre index ne doit être fourni qu'une seule fois.",
                400,
            )

        index = request.args.get("index")

        if index is not None and not INDEX_PATTERN.fullmatch(index):
            return json_error(
                "INVALID_PARAMETER",
                "L'index doit avoir le format loganalyzer-logs-AAAA.MM.JJ.",
                400,
            )

        if len(log_id) > 200:
            return json_error(
                "LOG_NOT_FOUND",
                "Ce log est introuvable. Il a peut-être été supprimé.",
                404,
            )

        try:
            with elasticsearch_client() as client:
                result = client.search(
                    index=index or "loganalyzer-logs-*",
                    query={"ids": {"values": [log_id]}},
                    size=2,
                    track_total_hits=True,
                    allow_no_indices=True,
                    ignore_unavailable=True,
                    allow_partial_search_results=False,
                    timeout="5s",
                )

            if (
                result.get("timed_out")
                or result.get("_shards", {}).get("failed", 0)
            ):
                raise RuntimeError("Résultat Elasticsearch incomplet.")

        except (ApiError, TransportError, RuntimeError):
            current_app.logger.exception("Échec de consultation d'un log")
            return json_error(
                "DETAIL_UNAVAILABLE",
                "Le détail du log est temporairement indisponible.",
                503,
            )

        total = result["hits"]["total"]["value"]

        if total == 0:
            return json_error(
                "LOG_NOT_FOUND",
                "Ce log est introuvable. Il a peut-être été supprimé.",
                404,
            )

        if total > 1:
            return json_error(
                "AMBIGUOUS_LOG",
                "Cet identifiant existe dans plusieurs index. "
                "Précisez le paramètre index.",
                409,
            )

        hit = result["hits"]["hits"][0]

        response = jsonify(
            id=hit["_id"],
            index=hit["_index"],
            document=hit["_source"],
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    app.register_blueprint(actions)
