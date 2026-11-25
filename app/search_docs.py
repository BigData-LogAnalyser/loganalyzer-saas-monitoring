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

    return extend_log_actions_spec(spec)


def extend_log_actions_spec(spec):
    from copy import deepcopy

    if __package__:
        from .log_export import CSV_COLUMNS, EXPORT_MAX_ROWS, EXPORT_MAX_BYTES
    else:
        from log_export import CSV_COLUMNS, EXPORT_MAX_ROWS, EXPORT_MAX_BYTES

    spec.setdefault("tags", []).append({
        "name": "Détail et export",
        "description": "Consulter un document et exporter une recherche.",
    })

    error_schema = {"$ref": "#/components/schemas/SearchError"}

    def json_response(description, schema):
        return {
            "description": description,
            "content": {"application/json": {"schema": schema}},
        }

    spec["components"]["schemas"]["LogDetail"] = {
        "type": "object",
        "required": ["id", "index", "document"],
        "properties": {
            "id": {"type": "string"},
            "index": {"type": "string"},
            "document": {
                "type": "object",
                "additionalProperties": True,
                "description": (
                    "Document Elasticsearch complet, "
                    "y compris les champs techniques de recherche."
                ),
            },
        },
    }

    spec["paths"]["/api/v1/logs/{log_id}"] = {
        "get": {
            "tags": ["Détail et export"],
            "operationId": "getLogDetail",
            "summary": "Consulter tous les champs d’un log",
            "description": (
                "Utiliser id et index provenant d’un résultat de recherche. "
                "Sans index, la recherche porte sur les index loganalyzer-logs-*. "
                "Si le même identifiant existe dans plusieurs index, "
                "le paramètre index est nécessaire."
            ),
            "parameters": [
                {
                    "name": "log_id",
                    "in": "path",
                    "required": True,
                    "description": "Identifiant exact du document.",
                    "schema": {"type": "string"},
                },
                {
                    "name": "index",
                    "in": "query",
                    "required": False,
                    "description": "Index exact du résultat sélectionné.",
                    "schema": {
                        "type": "string",
                        "pattern": r"^loganalyzer-logs-[0-9]{4}[.][0-9]{2}[.][0-9]{2}$",
                    },
                },
            ],
            "responses": {
                "200": json_response(
                    "Document trouvé.",
                    {"$ref": "#/components/schemas/LogDetail"},
                ),
                "400": json_response(
                    "Paramètre index incorrect, répété ou paramètre inconnu.",
                    error_schema,
                ),
                "404": json_response(
                    "Log introuvable : consulter error.message.",
                    error_schema,
                ),
                "409": json_response(
                    "Identifiant présent dans plusieurs index : préciser index.",
                    error_schema,
                ),
                "503": json_response(
                    "Consultation temporairement indisponible.",
                    error_schema,
                ),
            },
        },
    }

    parameters = deepcopy(spec["paths"]["/api/v1/logs"]["get"]["parameters"])
    parameters = [
        parameter for parameter in parameters
        if parameter["name"] != "page"
    ]

    spec["paths"]["/api/v1/logs/export"] = {
        "get": {
            "tags": ["Détail et export"],
            "operationId": "exportLogsCsv",
            "summary": "Exporter tous les résultats filtrés en CSV",
            "description": (
                "Réutilise les critères et le tri de la recherche. "
                "Toutes les pages sont exportées ; le paramètre page est refusé. "
                f"Maximum : {EXPORT_MAX_ROWS} documents et "
                f"{EXPORT_MAX_BYTES // (1024 * 1024)} Mio. "
                "Un dépassement est refusé avec HTTP 422, sans CSV tronqué. "
                "Le fichier utilise UTF-8 avec BOM, le séparateur point-virgule "
                "et des fins de ligne CRLF. "
                "Les champs absents donnent des cellules vides. "
                "Les champs calculés search_text et search_values sont exclus. "
                "Une apostrophe protège les cellules textuelles susceptibles "
                "d’être interprétées comme des formules par un tableur. "
                "Une recherche vide produit un fichier contenant les en-têtes. "
                "La recherche est exécutée à nouveau au moment de l’export. "
                "La confirmation affichée dans /logs appartient à l’interface : "
                "Execute dans Swagger appelle directement l’API. "
                "Colonnes : " + ", ".join(CSV_COLUMNS) + "."
            ),
            "parameters": parameters,
            "responses": {
                "200": {
                    "description": "Fichier CSV à télécharger.",
                    "headers": {
                        "Content-Disposition": {
                            "description": "Nom du fichier à télécharger.",
                            "schema": {"type": "string"},
                        },
                        "X-Export-Count": {
                            "description": "Nombre de documents exportés.",
                            "schema": {"type": "integer", "minimum": 0},
                        },
                        "X-Export-Limit": {
                            "description": "Limite du nombre de documents.",
                            "schema": {"type": "integer"},
                        },
                    },
                    "content": {
                        "text/csv": {
                            "schema": {"type": "string", "format": "binary"}
                        },
                    },
                },
                "400": json_response(
                    "Critères invalides ou paramètre page fourni.",
                    error_schema,
                ),
                "422": json_response(
                    "Limite de nombre de documents ou de taille dépassée.",
                    error_schema,
                ),
                "503": json_response(
                    "Export indisponible ou résultats incomplets.",
                    error_schema,
                ),
            },
        },
    }

    return spec
