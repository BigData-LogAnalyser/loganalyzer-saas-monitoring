"""Description OpenAPI de la recherche de logs."""


def extend_search_spec(spec):
    spec["info"]["title"] = "LogAnalyzer — API"
    spec.setdefault("tags", []).append({
        "name": "Recherche",
        "description": "Recherche dans les logs indexés dans Elasticsearch.",
    })

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

    schemas = spec["components"]["schemas"]

    schemas["SearchError"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": {"type": "string"},
                    "field": {
                        "type": "string",
                        "description": "Paramètre incorrect, si applicable.",
                    },
                    "message": {"type": "string"},
                },
            },
        },
    }

    schemas["SearchResults"] = {
        "type": "object",
        "required": [
            "items", "total", "page", "page_size", "total_pages",
            "accessible_pages", "pagination_limited",
            "has_previous", "has_next", "filters",
        ],
        "properties": {
            "items": {
                "type": "array",
                "maxItems": 50,
                "items": {
                    "type": "object",
                    "required": ["id", "index", "document"],
                    "properties": {
                        "id": {"type": "string"},
                        "index": {"type": "string"},
                        "document": {
                            "type": "object",
                            "additionalProperties": True,
                            "description": "Document Elasticsearch normalisé ECS.",
                        },
                    },
                },
            },
            "total": {
                "type": "integer",
                "minimum": 0,
                "description": "Nombre exact de résultats correspondant aux critères.",
            },
            "page": {"type": "integer", "minimum": 1, "maximum": 200},
            "page_size": {"type": "integer", "enum": [50]},
            "total_pages": {"type": "integer", "minimum": 0},
            "accessible_pages": {
                "type": "integer", "minimum": 0, "maximum": 200,
            },
            "pagination_limited": {
                "type": "boolean",
                "description": "Vrai si la recherche dépasse 10 000 résultats.",
            },
            "has_previous": {"type": "boolean"},
            "has_next": {"type": "boolean"},
            "filters": {
                "type": "object",
                "properties": {
                    "q": {"type": "string"},
                    "general": {"type": "string"},
                    "level": {"type": "string"},
                    "service": {"type": "string"},
                    "start": {
                        "type": "string", "format": "date-time", "nullable": True,
                    },
                    "end": {
                        "type": "string", "format": "date-time", "nullable": True,
                    },
                    "sort": {"type": "string"},
                    "order": {"type": "string"},
                    "page": {"type": "integer"},
                },
            },
        },
    }

    spec["paths"]["/api/v1/logs"] = {
        "get": {
            "tags": ["Recherche"],
            "operationId": "searchLogs",
            "summary": "Rechercher et filtrer les logs",
            "description": (
                "Tous les critères fournis sont combinés. "
                "Le texte est recherché dans message et error.message ; "
                "tous les mots sont requis. Le niveau et le service "
                "sont des correspondances exactes. "
                "La période porte sur @timestamp, avec bornes inclusives. "
                "Les dates doivent contenir un fuseau et sont normalisées en UTC. "
                "Le tri par niveau est alphabétique. "
                "Chaque page contient au maximum 50 logs. "
                "La navigation couvre les 10 000 premiers résultats ; "
                "le total reste exact au-delà. "
                "Sans correspondance : HTTP 200, total à zéro et items vide. "
                "Les paramètres inconnus ou répétés sont refusés. "
                "Les résultats peuvent évoluer si de nouveaux logs sont indexés."
            ),
            "parameters": [
                parameter(
                    "general",
                    "Recherche dans les valeurs de tous les champs du document, "
                    "y compris dates, nombres et identifiants techniques. "
                    "Combine fragments littéraux sans distinction de casse "
                    "et mots proches avec fuzziness AUTO. "
                    "Tous les termes doivent correspondre au même événement. "
                    "Maximum 500 caractères et 10 termes. "
                    "Se combine avec q et les autres filtres.",
                    {"type": "string", "maxLength": 500},
                ),

                parameter("q", "Texte recherché dans les messages.", {
                    "type": "string", "maxLength": 500,
                }),
                parameter("level", "Niveau exact.", {
                    "type": "string",
                    "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                }),
                parameter("service", "Nom exact du service.", {
                    "type": "string",
                    "pattern": "^[a-z][a-z0-9-]{0,63}$",
                }),
                parameter("start", "Début inclusif, avec fuseau. Exemple : 2026-11-04T00:00:00Z.", {
                    "type": "string", "format": "date-time",
                }),
                parameter("end", "Fin inclusive, postérieure ou égale au début.", {
                    "type": "string", "format": "date-time",
                }),
                parameter("sort", "Champ de tri principal.", {
                    "type": "string",
                    "enum": ["date", "level", "service"],
                    "default": "date",
                }),
                parameter("order", "Sens du tri.", {
                    "type": "string",
                    "enum": ["asc", "desc"],
                    "default": "desc",
                }),
                parameter("page", "Numéro de page, avec 50 logs par page.", {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 200,
                    "default": 1,
                }),
            ],
            "responses": {
                "200": response(
                    "Recherche exécutée, y compris en l'absence de résultats.",
                    {"$ref": "#/components/schemas/SearchResults"},
                ),
                "400": response(
                    "Paramètre invalide : consulter error.field et error.message.",
                    {"$ref": "#/components/schemas/SearchError"},
                ),
                "503": response(
                    "Recherche indisponible ou résultat Elasticsearch incomplet.",
                    {"$ref": "#/components/schemas/SearchError"},
                ),
            },
        },
    }

    return spec
