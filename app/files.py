"""Consultation des fichiers confirmés depuis le suivi MongoDB."""

import os
import re

from flask import Blueprint, current_app, jsonify, render_template, request
from pymongo.errors import PyMongoError

if __package__:
    from .search import InvalidFilter, parse_date
else:
    from search import InvalidFilter, parse_date


PAGE_SIZE = 20

STATUSES = {
    "EN_ATTENTE", "EN_COURS", "TERMINE", "PARTIEL", "ECHEC",
}

SORT_FIELDS = {
    "date": "confirmed_at",
    "name": "original_filename",
    "size": "size_bytes",
    "status": "status",
    "logs": "indexed_count",
}

ALLOWED_PARAMETERS = {
    "filename", "status", "start", "end", "sort", "order", "page",
}

PUBLIC_FIELDS = (
    "upload_id", "original_filename", "size_bytes", "status",
    "expected_count", "indexed_count", "rejected_count",
    "confirmed_at", "updated_at", "finished_at",
    "reading_complete", "progress_percent",
)


def json_response(payload, status=200):
    response = jsonify(payload)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response


def parse_parameters(args):
    unknown = set(args) - ALLOWED_PARAMETERS

    if unknown:
        raise InvalidFilter(
            sorted(unknown)[0], "Paramètre de consultation inconnu."
        )

    for field in args:
        if len(args.getlist(field)) != 1:
            raise InvalidFilter(
                field, "Ce paramètre ne doit être fourni qu'une seule fois."
            )

    values = {
        field: args.get(field, "").strip()
        for field in ALLOWED_PARAMETERS
    }

    if len(values["filename"]) > 100:
        raise InvalidFilter(
            "filename", "Le nom recherché est limité à 100 caractères."
        )

    status = values["status"]
    sort = values["sort"] or "date"
    order = values["order"] or "desc"
    page_text = values["page"] or "1"

    if status and status not in STATUSES:
        raise InvalidFilter(
            "status",
            "Statuts acceptés : EN_ATTENTE, EN_COURS, TERMINE, PARTIEL, ECHEC.",
        )

    if sort not in SORT_FIELDS:
        raise InvalidFilter(
            "sort", "Tris acceptés : date, name, size, status, logs."
        )

    if order not in {"asc", "desc"}:
        raise InvalidFilter("order", "Ordres acceptés : asc, desc.")

    if (
        not re.fullmatch(r"[1-9][0-9]{0,6}", page_text)
        or int(page_text) > 1_000_000
    ):
        raise InvalidFilter(
            "page", "La page doit être comprise entre 1 et 1 000 000."
        )

    start = parse_date(values["start"], "start")
    end = parse_date(values["end"], "end")

    if start and end and start > end:
        raise InvalidFilter(
            "end", "La fin doit être postérieure ou égale au début."
        )

    return {
        "filename": values["filename"],
        "status": status,
        "start": start,
        "end": end,
        "sort": sort,
        "order": order,
        "page": int(page_text),
    }


def filename_pattern(value):
    """Fragment littéral ou nom proche à une modification."""
    literal = re.escape(value)

    if len(value) < 4 or not any(char.isalpha() for char in value):
        return literal

    variants = {literal}

    for index in range(len(value)):
        before = re.escape(value[:index])
        after = re.escape(value[index + 1:])

        # Une lettre manquante dans le nom enregistré.
        variants.add(before + after)

        # Une lettre différente.
        variants.add(before + "." + after)

        # Deux lettres voisines inversées.
        if index + 1 < len(value):
            swapped = (
                value[:index]
                + value[index + 1]
                + value[index]
                + value[index + 2:]
            )
            variants.add(re.escape(swapped))

    # Une lettre supplémentaire dans le nom enregistré.
    for index in range(len(value) + 1):
        variants.add(
            re.escape(value[:index]) + "." + re.escape(value[index:])
        )

    fuzzy = "|".join(sorted(variants))

    # La recherche approchée porte sur une partie délimitée du nom.
    # Les caractères spéciaux saisis restent littéraux.
    return (
        literal
        + "|(?<![A-Za-z0-9_])(?:"
        + fuzzy
        + ")(?![A-Za-z0-9_])"
    )


def build_query(parameters):
    query = {}

    if parameters["filename"]:
        query["original_filename"] = {
            "$regex": filename_pattern(parameters["filename"]),
            "$options": "i",
        }

    if parameters["status"]:
        query["status"] = parameters["status"]

    period = {}

    if parameters["start"]:
        period["$gte"] = parameters["start"]

    if parameters["end"]:
        period["$lte"] = parameters["end"]

    if period:
        query["confirmed_at"] = period

    return query


def build_sort(parameters):
    primary = SORT_FIELDS[parameters["sort"]]
    direction = 1 if parameters["order"] == "asc" else -1
    result = [(primary, direction)]

    if primary != "confirmed_at":
        result.append(("confirmed_at", -1))

    result.append(("_id", 1))
    return result


def register_files(app, client_factory, serialize_row):
    files = Blueprint("files", __name__)

    @files.get("/api/v1/files")
    def list_files():
        try:
            parameters = parse_parameters(request.args)
        except InvalidFilter as error:
            return json_response({
                "error": {
                    "code": "INVALID_FILTER",
                    "field": error.field,
                    "message": str(error),
                },
            }, 400)

        query = build_query(parameters)

        projection = {
            "_id": 0,
            **{field: 1 for field in PUBLIC_FIELDS},
        }

        try:
            with client_factory() as client:
                collection = client[
                    os.environ.get("MONGODB_DATABASE", "loganalyzer")
                ].imports

                total = collection.count_documents(
                    query, maxTimeMS=5000
                )

                cursor = (
                    collection.find(query, projection)
                    .sort(build_sort(parameters))
                    .skip((parameters["page"] - 1) * PAGE_SIZE)
                    .limit(PAGE_SIZE)
                    .max_time_ms(5000)
                )

                items = [
                    serialize_row({
                        field: row.get(field)
                        for field in PUBLIC_FIELDS
                    })
                    for row in cursor
                ]

        except PyMongoError:
            current_app.logger.exception(
                "Lecture de la liste des imports MongoDB impossible"
            )
            return json_response({
                "error": {
                    "code": "FILES_UNAVAILABLE",
                    "message": (
                        "La liste des fichiers est temporairement "
                        "indisponible. Réessayez dans quelques instants."
                    ),
                },
            }, 503)

        total_pages = (total + PAGE_SIZE - 1) // PAGE_SIZE

        return json_response({
            "items": items,
            "total": total,
            "page": parameters["page"],
            "page_size": PAGE_SIZE,
            "total_pages": total_pages,
            "has_previous": parameters["page"] > 1,
            "has_next": parameters["page"] < total_pages,
            "filters": serialize_row(parameters),
        })

    @files.get("/files")
    def files_page():
        return render_template("files.html")

    app.register_blueprint(files)
