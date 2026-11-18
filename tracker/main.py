"""Coordination et suivi des imports confirmés."""

import fcntl
import hashlib
import json
import logging
import os
from pathlib import Path
import sys
import time
from datetime import datetime, timezone
from urllib.request import urlopen

from pymongo import MongoClient, ReturnDocument
from pymongo.errors import PyMongoError

if __package__:
    from .import_state import determine_status
    from .source_reader import inspect_source, iter_source_lines
    from .logstash_client import build_envelope, send_event
    from .result_reader import read_indexed_lines, read_rejections
else:
    from import_state import determine_status
    from source_reader import inspect_source, iter_source_lines
    from logstash_client import build_envelope, send_event
    from result_reader import read_indexed_lines, read_rejections


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)

UPLOAD_ROOT = Path("/uploads")
REJECTIONS = Path("/logstash-data/rejections/rejections.jsonl")

ES_URL = "http://{}:{}".format(
    os.environ["ELASTICSEARCH_HOST"],
    os.environ["ELASTICSEARCH_PORT"],
)

LOGSTASH_URL = os.environ.get(
    "LOGSTASH_URL", "http://logstash:8080/"
)
RESULT_TIMEOUT = float(
    os.environ.get("IMPORT_RESULT_TIMEOUT", "180")
)
MAX_BYTES = int(
    os.environ.get("MAX_UPLOAD_BYTES", "104857600")
)


def now():
    return datetime.now(timezone.utc)


def mongo_client():
    return MongoClient(
        host=os.environ["MONGODB_HOST"],
        port=int(os.environ["MONGODB_PORT"]),
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=10000,
    )


def check_connections():
    with mongo_client() as client:
        client.admin.command("ping")

    with urlopen(ES_URL + "/", timeout=5) as response:
        json.load(response)

    if not UPLOAD_ROOT.is_dir() or not os.access(
        UPLOAD_ROOT, os.R_OK | os.W_OK | os.X_OK
    ):
        raise RuntimeError("Le volume uploads est inaccessible.")

    if not Path("/logstash-data").is_dir() or not os.access(
        "/logstash-data", os.R_OK | os.X_OK
    ):
        raise RuntimeError(
            "Le volume des résultats Logstash est inaccessible."
        )

    logging.info("MongoDB, Elasticsearch et volumes accessibles.")


def source_path(document):
    upload_id = document["upload_id"]
    relative = Path(document["source_relative_path"])

    allowed = {
        "source.csv", "source.json", "source.jsonl", "source.txt"
    }

    if (
        not isinstance(upload_id, str)
        or not upload_id
        or Path(upload_id).name != upload_id
        or upload_id in {".", ".."}
        or relative.name not in allowed
        or relative.parts != (
            "confirmed", upload_id, relative.name
        )
    ):
        raise ValueError("Chemin de fichier confirmé incorrect.")

    path = UPLOAD_ROOT.resolve() / relative

    if path.resolve() != path or not path.is_file():
        raise ValueError(
            "Fichier confirmé absent ou chemin indirect interdit."
        )

    return path


def fingerprint(path):
    digest = hashlib.sha256()

    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(65536), b""):
            digest.update(chunk)

    return digest.hexdigest()


def collect_results(database, document, lines):
    upload_id = document["upload_id"]

    indexed = read_indexed_lines(ES_URL, upload_id, lines)
    rejected = read_rejections(REJECTIONS, upload_id)

    if any(number not in lines for number in rejected):
        raise ValueError(
            "Un rejet référence une ligne hors du fichier."
        )

    if indexed.intersection(rejected):
        raise ValueError(
            "Une ligne est à la fois indexée et rejetée."
        )

    data_count = 0
    technical = None

    for number, row in rejected.items():
        database.import_rejections.update_one(
            {"_id": f"{upload_id}:{number}"},
            {
                "$setOnInsert": {
                    **row,
                    "recorded_at": now(),
                }
            },
            upsert=True,
        )

        if row["failure_kind"] == "data":
            data_count += 1
        else:
            technical = {
                "code": row["errors"][0]["code"],
                "message": row["errors"][0]["message"],
                "source_line": number,
            }

    return len(indexed), data_count, technical


def save_progress(
    database,
    document,
    indexed,
    rejected,
    reading_complete,
    error=None,
):
    expected = document["expected_count"]

    status = determine_status(
        expected_count=expected,
        indexed_count=indexed,
        rejected_count=rejected,
        reading_complete=reading_complete,
        technical_failure=error is not None,
    )

    if status == "ECHEC" and error is None:
        error = {
            "code": "NO_INDEXED_EVENTS",
            "message": "Aucun événement n'a pu être indexé.",
        }

    percent = (
        (indexed + rejected) * 100 // expected
        if expected else 0
    )

    if status == "EN_COURS":
        percent = min(percent, 99)

    values = {
        "status": status,
        "indexed_count": indexed,
        "rejected_count": rejected,
        "reading_complete": reading_complete,
        "progress_percent": percent,
        "error": error,
        "updated_at": now(),
    }

    if status in {"TERMINE", "PARTIEL", "ECHEC"}:
        values["finished_at"] = now()

    database.imports.update_one(
        {"_id": document["_id"]},
        {"$set": values},
    )

    return status


def process_import(database, document):
    upload_id = document["upload_id"]
    lines = None
    reading_complete = False
    indexed = document.get("indexed_count", 0)
    rejected = document.get("rejected_count", 0)

    try:
        path = source_path(document)
        expected = inspect_source(path, max_bytes=MAX_BYTES)
        checksum = fingerprint(path)

        if document.get("source_sha256") not in (None, checksum):
            raise ValueError(
                "Le fichier a changé depuis sa prise en charge."
            )

        document["expected_count"] = expected

        first = 2 if path.suffix.lower() == ".csv" else 1
        lines = range(first, first + expected)

        database.imports.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "expected_count": expected,
                    "source_sha256": checksum,
                    "reading_complete": False,
                    "updated_at": now(),
                }
            },
        )

        logging.info(
            "Import %s : envoi de %s événements.",
            upload_id,
            expected,
        )

        last_check = time.monotonic()

        for sent, row in enumerate(
            iter_source_lines(path), start=1
        ):
            send_event(
                build_envelope(document, row, path),
                url=LOGSTASH_URL,
            )

            if (
                sent % 50 == 0
                or time.monotonic() - last_check >= 2
            ):
                indexed, rejected, technical = collect_results(
                    database, document, lines
                )

                if technical:
                    save_progress(
                        database, document,
                        indexed, rejected, False, technical,
                    )
                    return

                save_progress(
                    database, document,
                    indexed, rejected, False,
                )
                last_check = time.monotonic()

        if sent != expected or fingerprint(path) != checksum:
            raise ValueError(
                "Le fichier a changé pendant son traitement."
            )

        reading_complete = True

        database.imports.update_one(
            {"_id": document["_id"]},
            {
                "$set": {
                    "reading_complete": True,
                    "updated_at": now(),
                }
            },
        )

        deadline = time.monotonic() + RESULT_TIMEOUT

        while True:
            indexed, rejected, technical = collect_results(
                database, document, lines
            )

            status = save_progress(
                database, document,
                indexed, rejected, True, technical,
            )

            if status != "EN_COURS":
                logging.info(
                    "Import %s : %s, %s indexés, %s rejetés.",
                    upload_id, status, indexed, rejected,
                )
                return

            if time.monotonic() >= deadline:
                raise TimeoutError(
                    "Résultats d'indexation ou de rejet "
                    "encore manquants."
                )

            time.sleep(2)

    except PyMongoError:
        # Conserver EN_COURS : reprise avec les mêmes identifiants.
        raise

    except Exception as error:
        logging.exception("Échec de l'import %s", upload_id)

        if lines is not None:
            try:
                indexed, rejected, _ = collect_results(
                    database, document, lines
                )
            except PyMongoError:
                raise
            except Exception:
                logging.exception(
                    "Dernier bilan indisponible ; "
                    "compteurs conservés."
                )

        failure = {
            "code": getattr(error, "code", "INDEXING_ERROR"),
            "message": str(error),
        }

        document.setdefault("expected_count", None)

        save_progress(
            database, document,
            indexed, rejected, reading_complete, failure,
        )


def run():
    if RESULT_TIMEOUT <= 0 or MAX_BYTES <= 0:
        raise ValueError(
            "Délais et limite de taille doivent être positifs."
        )

    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

    with (UPLOAD_ROOT / ".tracker.lock").open("a") as lock:
        try:
            fcntl.flock(
                lock.fileno(),
                fcntl.LOCK_EX | fcntl.LOCK_NB,
            )
        except BlockingIOError:
            raise RuntimeError(
                "Un tracker utilise déjà ce volume uploads."
            )

        with mongo_client() as client:
            database = client[
                os.environ.get(
                    "MONGODB_DATABASE", "loganalyzer"
                )
            ]

            while True:
                try:
                    document = (
                        database.imports.find_one_and_update(
                            {
                                "status": {
                                    "$in": [
                                        "EN_ATTENTE",
                                        "EN_COURS",
                                    ]
                                }
                            },
                            {
                                "$set": {
                                    "status": "EN_COURS",
                                    "updated_at": now(),
                                }
                            },
                            sort=[("confirmed_at", 1)],
                            return_document=ReturnDocument.AFTER,
                        )
                    )

                    if document:
                        process_import(database, document)
                    else:
                        time.sleep(2)

                except PyMongoError:
                    logging.exception(
                        "MongoDB indisponible ; "
                        "nouvelle tentative dans 5 s."
                    )
                    time.sleep(5)


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_connections()
    else:
        run()