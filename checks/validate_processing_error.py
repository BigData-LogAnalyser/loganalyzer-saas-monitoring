#!/usr/bin/env python3
"""SCRUM-18 : erreur HTTP contrôlée du traitement, avec bilan MongoDB réel.

Les 12 scénarios du script validate_ingestion.py couvrent le parcours public.
Ce scénario prépare un import de test dans une base MongoDB temporaire et
appelle le coordinateur avec un destinataire HTTP local répondant 503.
La configuration du tracker de production et Logstash restent inchangés.
"""

import argparse
from datetime import datetime, timezone
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
import logging
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from threading import Thread
import traceback
from uuid import uuid4


def utcnow():
    return datetime.now(timezone.utc)


def json_default(value):
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()
    raise TypeError(f"Valeur non sérialisable : {type(value).__name__}")


def require(condition, message):
    if not condition:
        raise AssertionError(message)


class RefusingHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        size = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(size)
        self.server.received.append(json.loads(body))
        payload = b'{"message":"Erreur HTTP 503 controlee pour SCRUM-18"}'
        self.send_response(503)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--samples", default="/samples")
    parser.add_argument("--output", default="/results")
    parser.add_argument("--baseline", required=True)
    args = parser.parse_args()

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    run_id = utcnow().strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    report_path = output / f"erreur-traitement-{run_id}.json"
    report = {
        "ticket": "SCRUM-18",
        "run_id": run_id,
        "started_at": utcnow(),
        "scenario": "Erreur HTTP 503 contrôlée pendant le traitement",
        "scope": (
            "Coordinateur et client HTTP réels, destinataire HTTP contrôlé, "
            "MongoDB temporaire réel et vérification Elasticsearch réelle."
        ),
        "result": "EN_COURS",
        "cleanup": {},
    }

    def save():
        temporary = report_path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=json_default) + "\n",
            encoding="utf-8",
        )
        temporary.replace(report_path)

    client = None
    database_name = None
    server = None
    worker = None
    logs = io.StringIO()
    root_logger = logging.getLogger()
    original_handlers = list(root_logger.handlers)
    original_level = root_logger.level
    tracker = None
    previous_root = None
    previous_url = None
    save()

    try:
        baseline_path = Path(args.baseline)
        baseline_bytes = baseline_path.read_bytes()
        baseline = json.loads(baseline_bytes)
        require(
            baseline.get("ticket") == "SCRUM-18"
            and baseline.get("result") == "OK"
            and baseline.get("passed") == 12
            and baseline.get("failed") == 0,
            "Le bilan de référence doit confirmer les 12 scénarios réussis.",
        )
        report["baseline"] = {
            "filename": baseline_path.name,
            "sha256": hashlib.sha256(baseline_bytes).hexdigest(),
            "run_id": baseline["run_id"],
            "passed": baseline["passed"],
        }

        # Le script est monté dans /checks, le code du tracker est dans /app.
        sys.path.insert(0, "/app")
        import main as tracker_module
        from pymongo import MongoClient
        tracker = tracker_module
        # basicConfig() du tracker peut avoir installé un handler.
        original_handlers = list(root_logger.handlers)
        original_level = root_logger.level
        root_logger.handlers = [logging.StreamHandler(logs)]
        root_logger.setLevel(logging.INFO)

        client = MongoClient(
            host=os.environ["MONGODB_HOST"],
            port=int(os.environ["MONGODB_PORT"]),
            serverSelectionTimeoutMS=5000,
            connectTimeoutMS=5000,
            socketTimeoutMS=10000,
        )
        client.admin.command("ping")
        database_name = "loganalyzer_scrum18_check_" + uuid4().hex
        database = client[database_name]
        report["temporary_database"] = database_name

        content = (Path(args.samples) / "valides" / "logs.jsonl").read_bytes()
        references = json.loads(
            (Path(args.samples) / "attendus.json").read_text(encoding="utf-8")
        )
        expected = references["valides"]["evenements_par_fichier"]
        upload_id = str(uuid4())
        report["upload_id"] = upload_id
        report["source_sha256"] = hashlib.sha256(content).hexdigest()

        with TemporaryDirectory(prefix="scrum18-processing-") as folder:
            root = Path(folder).resolve()
            relative = Path("confirmed") / upload_id / "source.jsonl"
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_bytes(content)

            document = {
                "_id": upload_id,
                "upload_id": upload_id,
                "original_filename": "scrum18-erreur-traitement.jsonl",
                "source_relative_path": relative.as_posix(),
                "size_bytes": len(content),
                "schema_version": "1.0",
                "status": "EN_COURS",
                "confirmed_at": utcnow(),
                "expected_count": None,
                "indexed_count": 0,
                "rejected_count": 0,
            }
            database.imports.insert_one(document.copy())
            require(tracker.inspect_source(source) == expected, "Nombre de lignes source incorrect.")

            server = ThreadingHTTPServer(("127.0.0.1", 0), RefusingHandler)
            server.daemon_threads = True
            server.received = []
            worker = Thread(
                target=lambda: server.serve_forever(poll_interval=0.05),
                daemon=True,
            )
            worker.start()

            previous_root = tracker.UPLOAD_ROOT
            previous_url = tracker.LOGSTASH_URL
            tracker.UPLOAD_ROOT = root
            tracker.LOGSTASH_URL = f"http://127.0.0.1:{server.server_port}/"
            print("TEST : réponse HTTP 503 contrôlée pendant l'envoi.", flush=True)
            save()
            tracker.process_import(database, document)

            row = database.imports.find_one({"_id": upload_id})
            report["import_record"] = row
            report["http_requests_received"] = server.received
            require(row is not None, "Le bilan MongoDB est absent.")
            require(len(server.received) == 1, "Une seule tentative HTTP était attendue.")
            received = server.received[0]
            require(received["context"]["upload_id"] == upload_id, "Identifiant HTTP incorrect.")
            require(received["context"]["source_line"] == 1, "Première ligne incorrecte.")
            require(received["raw"] == content.split(b"\n", 1)[0].decode("utf-8"), "Ligne HTTP altérée.")
            print("OK : la première ligne a bien été transmise au serveur de test.", flush=True)

            require(row["status"] == "ECHEC", f"État incorrect : {row['status']}.")
            require(row["expected_count"] == expected, "Total attendu incorrect.")
            require(row["indexed_count"] == 0, "Indexations fictives comptées.")
            require(row["rejected_count"] == 0, "Panne HTTP comptée comme rejet de données.")
            require(row["reading_complete"] is False, "Lecture déclarée complète malgré l'arrêt de transmission.")
            require(row["error"]["code"] == "LOGSTASH_HTTP", "Code d'échec incorrect.")
            require("503" in row["error"]["message"], "Le motif ne précise pas le statut HTTP 503.")
            print("OK : état ECHEC et motif LOGSTASH_HTTP / HTTP 503 enregistrés dans MongoDB.", flush=True)
            print(f"OK : {expected} attendus, 0 indexé et 0 rejet de données.", flush=True)

            indexed = tracker.read_indexed_lines(
                tracker.ES_URL, upload_id, range(1, expected + 1)
            )
            require(not indexed, "Documents inattendus dans Elasticsearch.")
            require(database.import_rejections.count_documents({"upload_id": upload_id}) == 0, "Faux rejet conservé dans MongoDB.")
            require(not tracker.read_rejections(tracker.REJECTIONS, upload_id), "Faux rejet conservé dans le fichier Logstash.")
            report["elasticsearch_indexed_lines"] = sorted(indexed)
            print("OK : absence d'indexation et de faux rejet vérifiée.", flush=True)

        report["cleanup"]["temporary_files_removed"] = not root.exists()
        report["result"] = "OK"

    except Exception as error:
        report["result"] = "ECHEC"
        report["error"] = str(error)
        report["traceback"] = traceback.format_exc()
        print(f"ECHEC DU TEST : {error}", flush=True)

    finally:
        if tracker is not None and previous_root is not None:
            tracker.UPLOAD_ROOT = previous_root
            tracker.LOGSTASH_URL = previous_url
        if server is not None:
            if worker is not None and worker.is_alive():
                server.shutdown()
                worker.join(timeout=2)
            server.server_close()
        if client is not None:
            try:
                if database_name is not None:
                    require(database_name.startswith("loganalyzer_scrum18_check_"), "Nom de base temporaire inattendu.")
                    client.drop_database(database_name)
                    report["cleanup"]["temporary_database_removed"] = True
            except Exception as error:
                report["cleanup"]["error"] = str(error)
                report["result"] = "ECHEC"
            finally:
                client.close()
        report["tracker_logs"] = logs.getvalue()
        root_logger.handlers = original_handlers
        root_logger.setLevel(original_level)
        report["finished_at"] = utcnow()
        save()

    if report["result"] == "OK":
        print("OK : fichiers temporaires et base MongoDB de test supprimés.", flush=True)
        print("Bilan : scénario d'erreur de traitement réussi.", flush=True)
    print(f"Résultats enregistrés : {report_path}", flush=True)
    return 0 if report["result"] == "OK" else 1


if __name__ == "__main__":
    sys.exit(main())
