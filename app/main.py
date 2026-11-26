import json
import os
import shutil
from pathlib import Path
from uuid import UUID, uuid4

from flask import Flask, jsonify, render_template, request
from werkzeug.exceptions import RequestEntityTooLarge
from werkzeug.utils import secure_filename

from datetime import datetime, timezone

from pymongo import MongoClient
from pymongo.errors import PyMongoError

import fcntl
from contextlib import contextmanager

if __package__:
    from .import_reader import EXTENSIONS, preview_file
else:
    from import_reader import EXTENSIONS, preview_file


app = Flask(__name__)

MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", "104857600"))

if MAX_UPLOAD_BYTES <= 0:
    raise ValueError("MAX_UPLOAD_BYTES doit être supérieur à zéro.")

# Prévoir une marge pour l’enveloppe HTTP du formulaire.
# La taille réelle du fichier est contrôlée séparément.
app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES + 1024 * 1024

UPLOAD_ROOT = Path(os.environ.get("UPLOAD_DIR", "/app/uploads"))

if __package__:
    from .api_docs import register_api_docs
else:
    from api_docs import register_api_docs

register_api_docs(app, MAX_UPLOAD_BYTES)

if __package__:
    from .search import register_search
else:
    from search import register_search

register_search(app)

if __package__:
    from .log_actions import register_log_actions
else:
    from log_actions import register_log_actions

register_log_actions(app)

if __package__:
    from .log_export import register_log_export
else:
    from log_export import register_log_export

register_log_export(app)





@app.get("/")
def home():
    return render_template(
        "import.html",
        max_upload_bytes=MAX_UPLOAD_BYTES,
    )


@app.get("/health")
def health():
    return jsonify(status="ok", service="webapp")


@app.errorhandler(RequestEntityTooLarge)
def upload_too_large(error):
    return jsonify(
        error={
            "code": "FILE_SIZE",
            "message": "La requête dépasse la taille autorisée.",
        }
    ), 413


@app.post("/api/imports/preview")
def create_preview():
    files = request.files.getlist("file")

    if len(files) != 1 or len(request.files) != 1:
        return jsonify(
            error={
                "code": "FILE_FORMAT",
                "message": "Déposez un seul fichier dans le champ file.",
            }
        ), 400

    uploaded = files[0]
    original_name = (uploaded.filename or "").replace("\\", "/")
    original_name = original_name.rsplit("/", 1)[-1]

    if not original_name:
        return jsonify(
            error={
                "code": "FILE_FORMAT",
                "message": "Le fichier doit posséder un nom.",
            }
        ), 400

    extension = Path(original_name).suffix.lower()

    if extension not in EXTENSIONS:
        return jsonify(
            error={
                "code": "FILE_FORMAT",
                "message": "Formats acceptés : CSV, JSON Lines et TXT.",
            }
        ), 400

    upload_id = str(uuid4())
    draft_dir = UPLOAD_ROOT / "drafts" / upload_id
    source_path = draft_dir / f"source{extension}"
    safe_name = secure_filename(original_name)[:255] or f"fichier{extension}"

    try:
        draft_dir.mkdir(parents=True, exist_ok=False)

        size = 0

        with source_path.open("xb") as destination:
            while True:
                chunk = uploaded.stream.read(65536)

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_UPLOAD_BYTES:
                    break

                destination.write(chunk)

        if size > MAX_UPLOAD_BYTES:
            shutil.rmtree(draft_dir)

            return jsonify(
                error={
                    "code": "FILE_SIZE",
                    "message": (
                        f"Le fichier dépasse {MAX_UPLOAD_BYTES} octets."
                    ),
                }
            ), 413

        preview = preview_file(
            source_path,
            max_bytes=MAX_UPLOAD_BYTES,
        )

        if not preview["can_confirm"]:
            shutil.rmtree(draft_dir)

            return jsonify(
                original_filename=safe_name,
                size_bytes=size,
                preview=preview,
            ), 422

        metadata = {
            "upload_id": upload_id,
            "original_filename": safe_name,
            "source_filename": source_path.name,
            "size_bytes": size,
            "schema_version": "1.0",
            "state": "BROUILLON",
        }

        (draft_dir / "metadata.json").write_text(
            json.dumps(metadata, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        return jsonify(
            upload_id=upload_id,
            original_filename=safe_name,
            size_bytes=size,
            state="BROUILLON",
            preview=preview,
        ), 201

    except OSError:
        shutil.rmtree(draft_dir, ignore_errors=True)
        app.logger.exception("Échec de préparation de l’import")

        return jsonify(
            error={
                "code": "STORAGE_ERROR",
                "message": "Impossible de préparer le fichier sur le serveur.",
            }
        ), 503

def valid_upload_id(upload_id):
    try:
        return str(UUID(upload_id)) == upload_id
    except ValueError:
        return False


@contextmanager
def import_lock(upload_id):
    # Une seule action à la fois pour un même dépôt.
    locks_dir = UPLOAD_ROOT / ".locks"
    locks_dir.mkdir(parents=True, exist_ok=True)

    with (locks_dir / f"{upload_id}.lock").open("a") as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)

        try:
            yield
        finally:
            fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


@app.post("/api/imports/<upload_id>/cancel")
def cancel_import(upload_id):
    if not valid_upload_id(upload_id):
        return jsonify(
            error={
                "code": "IMPORT_NOT_FOUND",
                "message": "Identifiant de dépôt invalide.",
            }
        ), 404

    try:
        with import_lock(upload_id):
            draft_dir = UPLOAD_ROOT / "drafts" / upload_id

            if not draft_dir.is_dir():
                return jsonify(
                    error={
                        "code": "IMPORT_NOT_FOUND",
                        "message": "Brouillon absent ou déjà traité.",
                    }
                ), 404

            shutil.rmtree(draft_dir)

            return jsonify(
                upload_id=upload_id,
                action="ANNULE",
                message="Brouillon supprimé ; aucune ingestion déclenchée.",
            )

    except OSError:
        app.logger.exception("Échec de suppression du brouillon")

        return jsonify(
            error={
                "code": "STORAGE_ERROR",
                "message": "Impossible de supprimer complètement le brouillon.",
            }
        ), 503

@app.post("/api/imports/<upload_id>/confirm")
def confirm_import(upload_id):
    if not valid_upload_id(upload_id):
        return jsonify(
            error={
                "code": "IMPORT_NOT_FOUND",
                "message": "Identifiant de dépôt invalide.",
            }
        ), 404

    try:
        with import_lock(upload_id):
            with MongoClient(
                host=os.environ.get("MONGODB_HOST", "mongodb"),
                port=int(os.environ.get("MONGODB_PORT", "27017")),
                serverSelectionTimeoutMS=3000,
                connectTimeoutMS=3000,
                socketTimeoutMS=5000,
            ) as client:
                database = client[
                    os.environ.get("MONGODB_DATABASE", "loganalyzer")
                ]
                imports = database["imports"]

                # Une nouvelle tentative ne crée pas un second import.
                existing = imports.find_one({"_id": upload_id})

                if existing:
                    return jsonify(
                        upload_id=upload_id,
                        status=existing["status"],
                        message="Cet import est déjà enregistré.",
                    ), 200

                draft_dir = UPLOAD_ROOT / "drafts" / upload_id
                confirmed_dir = UPLOAD_ROOT / "confirmed" / upload_id

                # Le dossier confirmé peut déjà exister si une précédente
                # tentative a été interrompue avant la réponse MongoDB.
                if confirmed_dir.is_dir():
                    working_dir = confirmed_dir
                elif draft_dir.is_dir():
                    working_dir = draft_dir
                else:
                    return jsonify(
                        error={
                            "code": "IMPORT_NOT_FOUND",
                            "message": "Brouillon absent ou annulé.",
                        }
                    ), 404

                metadata = json.loads(
                    (working_dir / "metadata.json").read_text(
                        encoding="utf-8"
                    )
                )

                source_name = metadata["source_filename"]

                if (
                    Path(source_name).name != source_name
                    or source_name not in {
                        "source.csv",
                        "source.json",
                        "source.jsonl",
                        "source.txt",
                    }
                ):
                    raise ValueError("Nom de fichier interne incorrect.")

                source_path = working_dir / source_name

                # Vérifier à nouveau l’aperçu avant confirmation.
                preview = preview_file(
                    source_path,
                    max_bytes=MAX_UPLOAD_BYTES,
                )

                if not preview["can_confirm"]:
                    return jsonify(
                        upload_id=upload_id,
                        preview=preview,
                        message="La confirmation est bloquée.",
                    ), 422

                if working_dir == draft_dir:
                    confirmed_dir.parent.mkdir(
                        parents=True,
                        exist_ok=True,
                    )
                    draft_dir.rename(confirmed_dir)

                relative_path = (
                    Path("confirmed") / upload_id / source_name
                ).as_posix()

                document = {
                    "upload_id": upload_id,
                    "original_filename": metadata["original_filename"],
                    "source_relative_path": relative_path,
                    "size_bytes": metadata["size_bytes"],
                    "schema_version": metadata["schema_version"],
                    "status": "EN_ATTENTE",
                    "confirmed_at": datetime.now(timezone.utc),
                    "preview_count": preview["preview_count"],
                    "expected_count": None,
                    "indexed_count": 0,
                    "rejected_count": 0,
                }

                imports.update_one(
                    {"_id": upload_id},
                    {"$setOnInsert": document},
                    upsert=True,
                )

                return jsonify(
                    upload_id=upload_id,
                    status="EN_ATTENTE",
                    message="Import enregistré ; en attente de traitement.",
                ), 201

    except PyMongoError:
        app.logger.exception("Échec de confirmation MongoDB")

        return jsonify(
            upload_id=upload_id,
            error={
                "code": "DATABASE_ERROR",
                "message": (
                    "Confirmation non vérifiée. "
                    "Réessayez avec le même identifiant."
                ),
            },
        ), 503

    except (OSError, ValueError, KeyError):
        app.logger.exception("Échec de préparation du fichier confirmé")

        return jsonify(
            upload_id=upload_id,
            error={
                "code": "STORAGE_ERROR",
                "message": (
                    "Impossible de finaliser le fichier. "
                    "Réessayez avec le même identifiant."
                ),
            },
        ), 503

def tracking_client():
    return MongoClient(
        host=os.environ.get("MONGODB_HOST", "mongodb"),
        port=int(os.environ.get("MONGODB_PORT", "27017")),
        serverSelectionTimeoutMS=3000,
        connectTimeoutMS=3000,
        socketTimeoutMS=5000,
    )


def tracking_json_row(row):
    result = {}

    for key, value in row.items():
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)

            value = value.astimezone(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z")

        result[key] = value

    return result


def tracking_response(**payload):
    response = jsonify(**payload)
    response.headers["Cache-Control"] = "no-store"
    return response


def tracking_not_found():
    return jsonify(error={
        "code": "IMPORT_NOT_FOUND",
        "message": "Import introuvable.",
    }), 404


@app.get("/api/imports/<upload_id>")
def get_import_status(upload_id):
    if not valid_upload_id(upload_id):
        return tracking_not_found()

    try:
        with tracking_client() as client:
            database = client[
                os.environ.get("MONGODB_DATABASE", "loganalyzer")
            ]

            row = database.imports.find_one({"_id": upload_id})

            if row is None:
                return tracking_not_found()

            fields = (
                "upload_id", "original_filename", "size_bytes",
                "schema_version", "status", "expected_count",
                "indexed_count", "rejected_count", "confirmed_at",
                "updated_at", "finished_at", "error",
            )

            result = {
                field: row.get(field)
                for field in fields
            }

            result["reading_complete"] = row.get(
                "reading_complete", False
            )
            result["progress_percent"] = row.get(
                "progress_percent"
            )

            return tracking_response(
                import_record=tracking_json_row(result)
            )

    except PyMongoError:
        app.logger.exception("Lecture du suivi MongoDB impossible")

        return jsonify(error={
            "code": "DATABASE_ERROR",
            "message": "Le suivi est momentanément indisponible.",
        }), 503


@app.get("/api/imports/<upload_id>/rejections")
def get_import_rejections(upload_id):
    if not valid_upload_id(upload_id):
        return tracking_not_found()

    try:
        after_line = int(request.args.get("after_line", "0"))
        limit = int(request.args.get("limit", "20"))

        if after_line < 0 or not 1 <= limit <= 100:
            raise ValueError()

    except (TypeError, ValueError):
        return jsonify(error={
            "code": "INVALID_PARAMETER",
            "message": (
                "after_line doit être positif ou nul ; "
                "limit entre 1 et 100."
            ),
        }), 400

    try:
        with tracking_client() as client:
            database = client[
                os.environ.get("MONGODB_DATABASE", "loganalyzer")
            ]

            if database.imports.find_one(
                {"_id": upload_id},
                {"_id": 1},
            ) is None:
                return tracking_not_found()

            cursor = database.import_rejections.find(
                {
                    "upload_id": upload_id,
                    "source_line": {"$gt": after_line},
                },
                {
                    "_id": 0,
                    "upload_id": 1,
                    "source_line": 1,
                    "original_filename": 1,
                    "failure_kind": 1,
                    "errors": 1,
                    "raw": 1,
                    "recorded_at": 1,
                },
            ).sort("source_line", 1).limit(limit + 1)

            rows = list(cursor)
            has_more = len(rows) > limit
            items = rows[:limit]

            next_line = (
                items[-1]["source_line"]
                if has_more else None
            )

            return tracking_response(
                upload_id=upload_id,
                items=[
                    tracking_json_row(row)
                    for row in items
                ],
                has_more=has_more,
                next_after_line=next_line,
            )

    except PyMongoError:
        app.logger.exception(
            "Lecture des rejets MongoDB impossible"
        )

        return jsonify(error={
            "code": "DATABASE_ERROR",
            "message": (
                "Les diagnostics sont momentanément indisponibles."
            ),
        }), 503

# Liste des fichiers : réutilisation du suivi MongoDB existant.
if __package__:
    from .files import register_files
else:
    from files import register_files

register_files(app, tracking_client, tracking_json_row)


# Historique commun : réutilisation de la connexion MongoDB du suivi.
if __package__:
    from .search_history import register_search_history
else:
    from search_history import register_search_history

register_search_history(app, tracking_client, tracking_json_row)

# Indicateurs du dashboard.
if __package__:
    from .stats import register_stats
else:
    from stats import register_stats

register_stats(app, tracking_client)
