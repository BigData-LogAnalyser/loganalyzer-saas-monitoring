"""Documentation OpenAPI de l’historique commun des recherches."""

if __package__:
    from .search import LEVELS, SORT_FIELDS
    from .search_history import PAGE_SIZE, CRITERIA_FIELDS
else:
    from search import LEVELS, SORT_FIELDS
    from search_history import PAGE_SIZE, CRITERIA_FIELDS


def extend_search_history_spec(spec):
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})
    count = {"type": "integer", "minimum": 0}

    schemas["HistoryCriteria"] = {
        "type": "object",
        "required": list(CRITERIA_FIELDS),
        "properties": {
            "general": {"type": "string", "maxLength": 500},
            "q": {"type": "string", "maxLength": 500},
            "level": {"type": "string", "enum": ["", *sorted(LEVELS)]},
            "service": {"type": "string", "maxLength": 64},
            "start": {
                "type": "string", "format": "date-time", "nullable": True,
            },
            "end": {
                "type": "string", "format": "date-time", "nullable": True,
            },
            "sort": {"type": "string", "enum": list(SORT_FIELDS)},
            "order": {"type": "string", "enum": ["asc", "desc"]},
        },
    }

    schemas["SearchHistoryItem"] = {
        "type": "object",
        "required": ["id", "executed_at", "criteria", "result_count"],
        "properties": {
            "id": {"type": "string", "format": "uuid"},
            "executed_at": {
                "type": "string",
                "format": "date-time",
                "description": "Début d’exécution de la recherche, en UTC.",
            },
            "criteria": {"$ref": "#/components/schemas/HistoryCriteria"},
            "result_count": {
                **count,
                "description": "Nombre de résultats observé lors de la recherche.",
            },
        },
    }

    schemas["SearchHistoryResponse"] = {
        "type": "object",
        "required": [
            "items", "total", "page", "page_size", "total_pages",
            "has_previous", "has_next", "scope",
        ],
        "properties": {
            "items": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/SearchHistoryItem"},
            },
            "total": count,
            "page": {"type": "integer", "minimum": 1},
            "page_size": {"type": "integer", "enum": [PAGE_SIZE]},
            "total_pages": count,
            "has_previous": {"type": "boolean"},
            "has_next": {"type": "boolean"},
            "scope": {
                "type": "string",
                "enum": ["application"],
                "description": "Historique commun, sans association à un compte.",
            },
        },
    }

    schemas["SearchHistoryError"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": {"type": "string"},
                    "message": {"type": "string"},
                    "field": {"type": "string"},
                },
            },
        },
    }

    schemas["HistoryRecordingStatus"] = {
        "type": "object",
        "required": ["recorded"],
        "description": (
            "État de l’enregistrement de cette recherche. "
            "recorded=true : identifiant fourni. "
            "recorded=false : pagination ou enregistrement non confirmé. "
            "Une panne MongoDB ne supprime pas les résultats Elasticsearch."
        ),
        "properties": {
            "recorded": {"type": "boolean"},
            "id": {"type": "string", "format": "uuid"},
            "reason": {
                "type": "string",
                "enum": ["pagination", "unavailable"],
            },
            "message": {"type": "string"},
        },
    }

    # Compléter le schéma de succès de la recherche déjà documentée.
    search_schema = (
        spec["paths"]["/api/v1/logs"]["get"]["responses"]["200"]
        ["content"]["application/json"]["schema"]
    )

    while "$ref" in search_schema:
        search_schema = schemas[search_schema["$ref"].rsplit("/", 1)[-1]]

    search_schema.setdefault("properties", {})["history"] = {
        "$ref": "#/components/schemas/HistoryRecordingStatus",
    }

    required = search_schema.setdefault("required", [])
    if "history" not in required:
        required.append("history")

    tag = "Historique des recherches"
    tags = spec.setdefault("tags", [])

    if not any(item.get("name") == tag for item in tags):
        tags.append({"name": tag})

    def response(description, schema):
        return {
            "description": description,
            "content": {
                "application/json": {
                    "schema": {"$ref": f"#/components/schemas/{schema}"},
                },
            },
        }

    spec["paths"]["/api/v1/search-history"] = {
        "get": {
            "tags": [tag],
            "operationId": "listSearchHistory",
            "summary": "Consulter l’historique commun des recherches",
            "description": (
                "Historique enregistré dans MongoDB, sans compte utilisateur. "
                f"{PAGE_SIZE} entrées par page, les plus récentes en premier. "
                "Chaque recherche de logs réussie sur la page 1 est enregistrée, "
                "y compris une recherche sans résultat ou le chargement initial. "
                "Une nouvelle exécution des mêmes critères crée une nouvelle entrée. "
                "Les pages suivantes, les filtres invalides, les échecs "
                "Elasticsearch et les exports CSV ne créent pas d’entrée. "
                "Consulter cet historique ne crée pas de recherche. "
                "Les critères et le nombre de résultats sont conservés, "
                "sans copie des logs. Les recherches antérieures à cette "
                "fonctionnalité ne sont pas reconstituées. "
                "Une page sans entrée retourne HTTP 200. "
                "Les paramètres inconnus ou répétés sont refusés."
            ),
            "parameters": [{
                "name": "page",
                "in": "query",
                "required": False,
                "description": "Numéro de page.",
                "schema": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 1_000_000,
                    "default": 1,
                },
            }],
            "responses": {
                "200": response(
                    "Historique paginé, éventuellement vide.",
                    "SearchHistoryResponse",
                ),
                "400": response(
                    "Paramètre incorrect.",
                    "SearchHistoryError",
                ),
                "503": response(
                    "Historique temporairement indisponible.",
                    "SearchHistoryError",
                ),
            },
        },
    }

    return spec
