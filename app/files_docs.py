"""Documentation OpenAPI de la liste des fichiers importés."""

if __package__:
    from .files import PAGE_SIZE, STATUSES, SORT_FIELDS, PUBLIC_FIELDS
else:
    from files import PAGE_SIZE, STATUSES, SORT_FIELDS, PUBLIC_FIELDS


def extend_files_spec(spec):
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})

    text = {"type": "string", "nullable": True}
    count = {"type": "integer", "minimum": 0}
    nullable_count = {**count, "nullable": True}
    date = {"type": "string", "format": "date-time", "nullable": True}

    schemas["ImportedFile"] = {
        "type": "object",
        "required": list(PUBLIC_FIELDS),
        "properties": {
            "upload_id": {
                "type": "string", "format": "uuid", "nullable": True,
            },
            "original_filename": text,
            "size_bytes": {
                **nullable_count,
                "description": "Taille du fichier original en octets.",
            },
            "status": {
                "type": "string",
                "enum": sorted(STATUSES),
                "nullable": True,
            },
            "expected_count": nullable_count,
            "indexed_count": nullable_count,
            "rejected_count": nullable_count,
            "confirmed_at": {
                **date,
                "description": "Confirmation de l’import après l’aperçu, en UTC.",
            },
            "updated_at": date,
            "finished_at": date,
            "reading_complete": {"type": "boolean", "nullable": True},
            "progress_percent": {
                "type": "number",
                "minimum": 0,
                "maximum": 100,
                "nullable": True,
            },
        },
    }

    schemas["FilesFilters"] = {
        "type": "object",
        "required": ["filename", "status", "start", "end", "sort", "order", "page"],
        "properties": {
            "filename": {"type": "string", "maxLength": 100},
            "status": {
                "type": "string",
                "enum": ["", *sorted(STATUSES)],
            },
            "start": date,
            "end": date,
            "sort": {"type": "string", "enum": list(SORT_FIELDS)},
            "order": {"type": "string", "enum": ["asc", "desc"]},
            "page": {
                "type": "integer", "minimum": 1, "maximum": 1_000_000,
            },
        },
    }

    schemas["FilesResponse"] = {
        "type": "object",
        "required": [
            "items", "total", "page", "page_size", "total_pages",
            "has_previous", "has_next", "filters",
        ],
        "properties": {
            "items": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ImportedFile"},
            },
            "total": count,
            "page": {"type": "integer", "minimum": 1},
            "page_size": {"type": "integer", "enum": [PAGE_SIZE]},
            "total_pages": count,
            "has_previous": {"type": "boolean"},
            "has_next": {"type": "boolean"},
            "filters": {"$ref": "#/components/schemas/FilesFilters"},
        },
    }

    schemas["FilesErrorResponse"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": {"type": "string"},
                    "field": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
    }

    def parameter(name, description, schema):
        return {
            "name": name,
            "in": "query",
            "required": False,
            "description": description,
            "schema": schema,
        }

    def response(description, schema):
        return {
            "description": description,
            "content": {"application/json": {"schema": schema}},
        }

    tag = "Fichiers importés"
    tags = spec.setdefault("tags", [])

    if not any(item.get("name") == tag for item in tags):
        tags.append({
            "name": tag,
            "description": "Consultation du suivi des imports enregistré dans MongoDB.",
        })

    spec.setdefault("paths", {})["/api/v1/files"] = {
        "get": {
            "tags": [tag],
            "operationId": "listImportedFiles",
            "summary": "Lister les fichiers importés",
            "description": (
                "Liste les imports confirmés de la collection MongoDB imports. "
                "Les aperçus non confirmés ou annulés ne sont pas inclus. "
                f"Pagination fixe de {PAGE_SIZE} fichiers par page. "
                "Les filtres de statut et de période sont combinés. "
                "La période porte sur confirmed_at, avec bornes inclusives. "
                "Les dates doivent comporter un fuseau et sont retournées en UTC. "
                "Le tri logs porte sur indexed_count ; name et status "
                "suivent l’ordre des chaînes stockées dans MongoDB. "
                "Les égalités sont départagées par la date puis l’identifiant. "
                "Une information absente est retournée à null. "
                "Une liste vide ou une page au-delà des résultats renvoie HTTP 200. "
                "Les paramètres inconnus et répétés sont refusés."
            ),
            "parameters": [
                parameter(
                    "filename",
                    "Partie du nom, sans distinction de casse. "
                    "À partir de 4 caractères contenant une lettre, "
                    "tolère une suppression, un ajout, un remplacement "
                    "ou une inversion de deux caractères voisins "
                    "sur une partie délimitée du nom. "
                    "Exemple : mite retrouve mixte.jsonl. "
                    "Les caractères spéciaux sont traités littéralement. "
                    "Combinable avec le statut et la période.",
                    {"type": "string", "maxLength": 100},
                ),
                parameter("status", "Statut exact du traitement.", {
                    "type": "string", "enum": sorted(STATUSES),
                }),
                parameter(
                    "start",
                    "Début inclusif de confirmation, par exemple 2026-11-24T00:00:00Z.",
                    {"type": "string", "format": "date-time"},
                ),
                parameter(
                    "end",
                    "Fin inclusive de confirmation ; doit être supérieure ou égale au début.",
                    {"type": "string", "format": "date-time"},
                ),
                parameter("sort", "Champ de tri.", {
                    "type": "string",
                    "enum": list(SORT_FIELDS),
                    "default": "date",
                }),
                parameter("order", "Sens du tri.", {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                }),
                parameter("page", "Numéro de page.", {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1_000_000,
                    "default": 1,
                }),
            ],
            "responses": {
                "200": response(
                    "Liste paginée ; items vide si aucun fichier ne correspond.",
                    {"$ref": "#/components/schemas/FilesResponse"},
                ),
                "400": response(
                    "Filtre invalide : consulter error.field et error.message.",
                    {"$ref": "#/components/schemas/FilesErrorResponse"},
                ),
                "503": response(
                    "Suivi MongoDB temporairement indisponible.",
                    {"$ref": "#/components/schemas/FilesErrorResponse"},
                ),
            },
        },
    }

    return spec
