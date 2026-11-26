"""Historique commun des recherches de logs, conservé dans MongoDB."""

import os
import re
from uuid import uuid4

from flask import Blueprint, current_app, jsonify, render_template, request
from pymongo.errors import PyMongoError


PAGE_SIZE = 20
COLLECTION = "search_history"

CRITERIA_FIELDS = (
    "general", "q", "level", "service", "start", "end", "sort", "order", "upload_id",
)


def history_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def record_search(parameters, total, executed_at):
    if parameters["page"] != 1:
        return {"recorded": False, "reason": "pagination"}

    history_id = str(uuid4())
    document = {
        "_id": history_id,
        "executed_at": executed_at,
        "criteria": {
            field: parameters[field]
            for field in CRITERIA_FIELDS
        },
        "result_count": total,
    }

    factory = current_app.extensions["search_history"]["client_factory"]

    try:
        with factory() as client:
            database = client[
                os.environ.get("MONGODB_DATABASE", "loganalyzer")
            ]
            database[COLLECTION].insert_one(document)

    except PyMongoError:
        current_app.logger.exception(
            "Enregistrement de l’historique MongoDB non confirmé"
        )
        return {
            "recorded": False,
            "reason": "unavailable",
            "message": (
                "Les résultats sont disponibles, mais leur enregistrement "
                "dans l’historique n’a pas pu être confirmé."
            ),
        }

    return {"recorded": True, "id": history_id}


def register_search_history(app, client_factory, serialize_row):
    app.extensions["search_history"] = {
        "client_factory": client_factory,
    }

    history = Blueprint("search_history", __name__)

    @history.get("/api/v1/search-history")
    def list_search_history():
        unknown = set(request.args) - {"page", "order"}

        if unknown:
            return history_response({
                "error": {
                    "code": "INVALID_FILTER",
                    "field": sorted(unknown)[0],
                    "message": "Paramètre d’historique inconnu.",
                },
            }, 400)

        if len(request.args.getlist("page")) > 1:
            return history_response({
                "error": {
                    "code": "INVALID_FILTER",
                    "field": "page",
                    "message": "Le paramètre page ne doit être fourni qu’une fois.",
                },
            }, 400)

        order = request.args.get("order", "desc").strip()

        if (
            len(request.args.getlist("order")) > 1
            or order not in {"asc", "desc"}
        ):
            return history_response({
                "error": {
                    "code": "INVALID_FILTER",
                    "field": "order",
                    "message": "Fournissez une seule valeur : asc ou desc.",
                },
            }, 400)

        direction = 1 if order == "asc" else -1
        page_text = request.args.get("page", "1").strip()

        if (
            not re.fullmatch(r"[1-9][0-9]{0,6}", page_text)
            or int(page_text) > 1_000_000
        ):
            return history_response({
                "error": {
                    "code": "INVALID_FILTER",
                    "field": "page",
                    "message": "La page doit être comprise entre 1 et 1 000 000.",
                },
            }, 400)

        page = int(page_text)

        try:
            with client_factory() as client:
                collection = client[
                    os.environ.get("MONGODB_DATABASE", "loganalyzer")
                ][COLLECTION]

                total = collection.count_documents({}, maxTimeMS=5000)

                cursor = (
                    collection.find(
                        {},
                        {
                            "_id": 1,
                            "executed_at": 1,
                            "criteria": 1,
                            "result_count": 1,
                        },
                    )
                    .sort([("executed_at", direction), ("_id", direction)])
                    .skip((page - 1) * PAGE_SIZE)
                    .limit(PAGE_SIZE)
                    .max_time_ms(5000)
                )

                items = [
                    serialize_row({
                        "id": row["_id"],
                        "executed_at": row["executed_at"],
                        "criteria": row["criteria"],
                        "result_count": row["result_count"],
                    })
                    for row in cursor
                ]

        except PyMongoError:
            current_app.logger.exception(
                "Consultation de l’historique MongoDB impossible"
            )
            return history_response({
                "error": {
                    "code": "HISTORY_UNAVAILABLE",
                    "message": (
                        "L’historique des recherches est temporairement "
                        "indisponible. Réessayez dans quelques instants."
                    ),
                },
            }, 503)

        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        return history_response({
            "items": items,
            "total": total,
            "page": page,
            "page_size": PAGE_SIZE,
            "total_pages": total_pages,
            "has_previous": page > 1,
            "has_next": page < total_pages,
            "scope": "application",
            "order": order,
        })

    @history.get("/search-history")
    def history_page():
        return render_template("search_history.html")

    app.register_blueprint(history)
