"""Documentation Swagger de l'API d'ingestion existante."""

from flask import Blueprint, jsonify, render_template_string, url_for


STATES = ["EN_ATTENTE", "EN_COURS", "TERMINE", "PARTIEL", "ECHEC"]


def reference(name):
    return {"$ref": f"#/components/schemas/{name}"}


def object_schema(properties, required=()):
    schema = {"type": "object", "properties": properties}

    if required:
        schema["required"] = list(required)

    return schema


def json_response(description, schema):
    return {
        "description": description,
        "content": {
            "application/json": {"schema": schema}
        },
    }


def build_spec(max_upload_bytes):
    text = {"type": "string"}
    uuid = {"type": "string", "format": "uuid"}
    count = {"type": "integer", "minimum": 0}
    nullable_count = {**count, "nullable": True}
    date = {
        "type": "string",
        "format": "date-time",
        "nullable": True,
    }

    diagnostic_properties = {
        "code": text,
        "field": {"type": "string", "nullable": True},
        "message": text,
    }

    schemas = {
        "Diagnostic": object_schema(
            diagnostic_properties,
            ("code", "field", "message"),
        ),
        "PreviewDiagnostic": object_schema(
            {
                **diagnostic_properties,
                "source_line": nullable_count,
            },
            ("source_line", "code", "field", "message"),
        ),
        "ErrorResponse": object_schema(
            {
                "upload_id": uuid,
                "error": object_schema(
                    {"code": text, "message": text},
                    ("code", "message"),
                ),
            },
            ("error",),
        ),
        "PreviewRow": object_schema(
            {
                "source_line": {"type": "integer", "minimum": 1},
                "event": {
                    "description": (
                        "Valeur décodée avant normalisation ECS. "
                        "Elle peut être invalide ou nulle."
                    ),
                },
                "errors": {
                    "type": "array",
                    "items": reference("Diagnostic"),
                },
            },
            ("source_line", "event", "errors"),
        ),
        "Preview": object_schema(
            {
                "preview_limit": {"type": "integer", "enum": [10]},
                "preview_count": {**count, "maximum": 10},
                "events": {
                    "type": "array",
                    "items": reference("PreviewRow"),
                },
                "errors": {
                    "type": "array",
                    "items": reference("PreviewDiagnostic"),
                },
                "can_confirm": {"type": "boolean"},
                "scope": text,
            },
            (
                "preview_limit", "preview_count", "events",
                "errors", "can_confirm", "scope",
            ),
        ),
        "DraftCreated": object_schema(
            {
                "upload_id": uuid,
                "original_filename": text,
                "size_bytes": count,
                "state": {"type": "string", "enum": ["BROUILLON"]},
                "preview": reference("Preview"),
            },
            (
                "upload_id", "original_filename",
                "size_bytes", "state", "preview",
            ),
        ),
        "PreviewRejected": object_schema(
            {
                "original_filename": text,
                "size_bytes": count,
                "preview": reference("Preview"),
            },
            ("original_filename", "size_bytes", "preview"),
        ),
        "Confirmation": object_schema(
            {
                "upload_id": uuid,
                "status": {"type": "string", "enum": STATES},
                "message": text,
            },
            ("upload_id", "status", "message"),
        ),
        "ConfirmationBlocked": object_schema(
            {
                "upload_id": uuid,
                "preview": reference("Preview"),
                "message": text,
            },
            ("upload_id", "preview", "message"),
        ),
        "Cancellation": object_schema(
            {
                "upload_id": uuid,
                "action": {"type": "string", "enum": ["ANNULE"]},
                "message": text,
            },
            ("upload_id", "action", "message"),
        ),
        "ImportRecord": object_schema(
            {
                "upload_id": uuid,
                "original_filename": text,
                "size_bytes": count,
                "schema_version": text,
                "status": {"type": "string", "enum": STATES},
                "expected_count": nullable_count,
                "indexed_count": count,
                "rejected_count": count,
                "confirmed_at": date,
                "updated_at": date,
                "finished_at": date,
                "reading_complete": {"type": "boolean"},
                "progress_percent": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "nullable": True,
                },
                "error": {
                    "type": "object",
                    "nullable": True,
                    "additionalProperties": True,
                    "properties": {
                        "code": text,
                        "message": text,
                    },
                },
            },
        ),
        "Rejection": object_schema(
            {
                "upload_id": uuid,
                "source_line": {"type": "integer", "minimum": 1},
                "original_filename": text,
                "failure_kind": {
                    "type": "string",
                    "enum": ["data", "technical"],
                },
                "errors": {
                    "type": "array",
                    "items": reference("Diagnostic"),
                },
                "raw": {
                    "type": "string",
                    "description": "Contenu original de la ligne.",
                },
                "recorded_at": date,
            },
        ),
        "RejectionsPage": object_schema(
            {
                "upload_id": uuid,
                "items": {
                    "type": "array",
                    "items": reference("Rejection"),
                },
                "has_more": {"type": "boolean"},
                "next_after_line": nullable_count,
            },
            ("upload_id", "items", "has_more", "next_after_line"),
        ),
    }

    def result(description, name):
        return json_response(description, reference(name))

    not_found = result(
        "Identifiant invalide, import absent ou brouillon indisponible.",
        "ErrorResponse",
    )

    unavailable = result(
        "Erreur de stockage ou de MongoDB. Lire error.code et error.message.",
        "ErrorResponse",
    )

    upload_parameter = {
        "name": "upload_id",
        "in": "path",
        "required": True,
        "description": (
            "UUID canonique en minuscules reçu dans la réponse "
            "de prévisualisation. Utiliser votre identifiant réel."
        ),
        "schema": uuid,
    }

    def operation(operation_id, tag, summary, description, responses):
        return {
            "operationId": operation_id,
            "tags": [tag],
            "summary": summary,
            "description": description,
            "responses": responses,
        }

    preview_operation = operation(
        "createPreview",
        "Imports",
        "1. Envoyer un fichier et obtenir la prévisualisation",
        (
            "Envoyer un seul fichier dans le champ file. "
            "Extensions : .csv, .json, .jsonl et .txt. "
            f"Limite du fichier : {max_upload_bytes} octets. "
            "Encodage UTF-8 sans BOM. "
            "CSV : en-tête contractuel et séparateur point-virgule. "
            "TXT : champs séparés par des tabulations. "
            "JSON et JSONL : un objet par ligne, pas un tableau JSON. "
            "Les dix premiers événements sont prévisualisés. "
            "L'encodage du fichier entier et l'en-tête CSV sont contrôlés. "
            "Un aperçu valide ne garantit pas la validité des lignes suivantes. "
            "Copier upload_id de la réponse 201 pour confirmer ou annuler."
        ),
        {
            "201": result(
                "Brouillon créé ; aucun traitement Logstash déclenché.",
                "DraftCreated",
            ),
            "400": result(
                "Fichier absent, nom absent, format refusé ou plusieurs fichiers.",
                "ErrorResponse",
            ),
            "413": result(
                "Fichier ou requête trop volumineux.",
                "ErrorResponse",
            ),
            "422": result(
                "Aperçu invalide ; brouillon supprimé, aucun upload_id retourné.",
                "PreviewRejected",
            ),
            "503": unavailable,
        },
    )

    preview_operation["requestBody"] = {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": object_schema(
                    {
                        "file": {
                            "type": "string",
                            "format": "binary",
                            "description": "Fichier CSV, JSON Lines ou TXT.",
                        },
                    },
                    ("file",),
                ),
            },
        },
    }

    return {
        "openapi": "3.0.3",
        "info": {
            "title": "LogAnalyzer — API d'ingestion",
            "version": "1.0.0",
            "description": (
                "Parcours : prévisualiser, confirmer, consulter le suivi "
                "et consulter les rejets. "
                "Cliquer sur Try it out puis Execute pour appeler l'API. "
                "Ces requêtes agissent réellement sur l'application. "
                "Après confirmation, le tracker transmet les lignes "
                "à Logstash et vérifie les résultats. "
                "La confirmation seule ne prouve pas l'indexation."
            ),
        },
        "servers": [
            {
                "url": "/",
                "description": "Application Flask qui sert cette page",
            },
        ],
        "tags": [
            {"name": "Santé"},
            {"name": "Imports"},
            {"name": "Suivi"},
        ],
        "paths": {
            "/health": {
                "get": operation(
                    "getHealth",
                    "Santé",
                    "Vérifier que Flask répond",
                    (
                        "Vérifie uniquement la réponse de Flask. "
                        "Ne contrôle pas les connexions aux autres services."
                    ),
                    {
                        "200": json_response(
                            "Application accessible.",
                            object_schema(
                                {
                                    "status": {
                                        "type": "string",
                                        "enum": ["ok"],
                                    },
                                    "service": {
                                        "type": "string",
                                        "enum": ["webapp"],
                                    },
                                },
                                ("status", "service"),
                            ),
                        ),
                    },
                ),
            },
            "/api/imports/preview": {
                "post": preview_operation,
            },
            "/api/imports/{upload_id}/confirm": {
                "parameters": [upload_parameter],
                "post": operation(
                    "confirmImport",
                    "Imports",
                    "2. Confirmer un brouillon",
                    (
                        "Sans corps de requête. "
                        "Conserve le fichier et enregistre l'import en EN_ATTENTE. "
                        "Une nouvelle confirmation du même identifiant "
                        "ne crée pas un second import. "
                        "Après une réponse 503 incertaine, "
                        "réessayer avec le même identifiant."
                    ),
                    {
                        "201": result(
                            "Nouvel import enregistré en EN_ATTENTE.",
                            "Confirmation",
                        ),
                        "200": result(
                            "Import déjà enregistré ; état actuel renvoyé.",
                            "Confirmation",
                        ),
                        "404": not_found,
                        "422": result(
                            "L'aperçu revérifié bloque la confirmation.",
                            "ConfirmationBlocked",
                        ),
                        "503": unavailable,
                    },
                ),
            },
            "/api/imports/{upload_id}/cancel": {
                "parameters": [upload_parameter],
                "post": operation(
                    "cancelImport",
                    "Imports",
                    "Annuler un brouillon avant confirmation",
                    (
                        "Sans corps de requête. Supprime uniquement un brouillon. "
                        "Ne permet pas d'annuler un import déjà confirmé "
                        "ni de supprimer ses documents indexés."
                    ),
                    {
                        "200": result(
                            "Brouillon supprimé sans déclencher d'ingestion.",
                            "Cancellation",
                        ),
                        "404": not_found,
                        "503": unavailable,
                    },
                ),
            },
            "/api/imports/{upload_id}": {
                "parameters": [upload_parameter],
                "get": operation(
                    "getImportStatus",
                    "Suivi",
                    "3. Consulter l'état et les compteurs",
                    (
                        "Disponible après confirmation uniquement. "
                        "Réexécuter pendant le traitement. "
                        "EN_ATTENTE : en attente du tracker. "
                        "EN_COURS : traitement ou résultats incomplets. "
                        "TERMINE : tous les événements indexés. "
                        "PARTIEL : événements indexés et rejets de données. "
                        "ECHEC : erreur technique ou aucun événement exploitable. "
                        "La fin de lecture seule ne produit pas TERMINE. "
                        "La progression compte les événements résolus, "
                        "y compris les rejets : 100 % peut donc correspondre "
                        "à PARTIEL. Un total null est encore inconnu."
                    ),
                    {
                        "200": json_response(
                            "Suivi lu dans MongoDB, sans mise en cache.",
                            object_schema(
                                {"import_record": reference("ImportRecord")},
                                ("import_record",),
                            ),
                        ),
                        "404": not_found,
                        "503": unavailable,
                    },
                ),
            },
            "/api/imports/{upload_id}/rejections": {
                "parameters": [upload_parameter],
                "get": {
                    **operation(
                        "getImportRejections",
                        "Suivi",
                        "4. Consulter les rejets et leurs motifs",
                        (
                            "Diagnostics lus dans MongoDB, triés par ligne. "
                            "Une ligne peut avoir plusieurs diagnostics. "
                            "Pour la page suivante, reporter next_after_line "
                            "dans after_line. "
                            "Une liste vide peut signifier qu'aucun diagnostic "
                            "n'est encore disponible."
                        ),
                        {
                            "200": result(
                                "Page de diagnostics.",
                                "RejectionsPage",
                            ),
                            "400": result(
                                "Paramètre after_line ou limit incorrect.",
                                "ErrorResponse",
                            ),
                            "404": not_found,
                            "503": unavailable,
                        },
                    ),
                    "parameters": [
                        {
                            "name": "after_line",
                            "in": "query",
                            "description": (
                                "Retourner les lignes strictement "
                                "supérieures à cette valeur."
                            ),
                            "schema": {
                                "type": "integer",
                                "minimum": 0,
                                "default": 0,
                            },
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "description": "Nombre maximal de lignes renvoyées.",
                            "schema": {
                                "type": "integer",
                                "minimum": 1,
                                "maximum": 100,
                                "default": 20,
                            },
                        },
                    ],
                },
            },
        },
        "components": {"schemas": schemas},
    }


SWAGGER_HTML = """<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LogAnalyzer — Swagger UI</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.36.0/swagger-ui.css">
</head>
<body>
  <p style="padding:12px;font-family:sans-serif">
    <a href="{{ home_url }}">Retour à l'import</a> ·
    <a href="{{ spec_url }}">Spécification OpenAPI JSON</a>
  </p>
  <div id="swagger-ui"></div>
  <noscript>Activez JavaScript pour afficher Swagger UI.</noscript>
  <script
    src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.36.0/swagger-ui-bundle.js">
  </script>
  <script>
    if (typeof SwaggerUIBundle === "undefined") {
      document.getElementById("swagger-ui").textContent =
        "Swagger UI n'a pas pu être chargé. Vérifiez l'accès Internet à jsDelivr.";
    } else {
      SwaggerUIBundle({
        url: {{ spec_url | tojson }},
        dom_id: "#swagger-ui",
        deepLinking: true,
        displayRequestDuration: true,
        docExpansion: "list",
        defaultModelsExpandDepth: -1,
        supportedSubmitMethods: ["get", "post"],
        validatorUrl: null,
        presets: [SwaggerUIBundle.presets.apis],
        layout: "BaseLayout"
      });
    }
  </script>
</body>
</html>"""


def register_api_docs(app, max_upload_bytes):
    docs = Blueprint("api_docs", __name__)

    @docs.get("/api/openapi.json")
    def openapi_spec():
        if __package__:
            from .search_docs import extend_search_spec
        else:
            from search_docs import extend_search_spec

        response = jsonify(extend_search_spec(build_spec(max_upload_bytes)))
        response.headers["Cache-Control"] = "no-store"
        return response

    @docs.get("/api/docs")
    def swagger_ui():
        return render_template_string(
            SWAGGER_HTML,
            spec_url=url_for("api_docs.openapi_spec"),
            home_url=url_for("home"),
        )

    app.register_blueprint(docs)
