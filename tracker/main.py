import json
import logging
import os
from pathlib import Path
import sys
import time
import urllib.request

from pymongo import MongoClient


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def check_connections():
    mongo_host = os.environ["MONGODB_HOST"]
    mongo_port = int(os.environ["MONGODB_PORT"])

    with MongoClient(
        host=mongo_host,
        port=mongo_port,
        serverSelectionTimeoutMS=5000,
        connectTimeoutMS=5000,
        socketTimeoutMS=5000,
    ) as client:
        client.admin.command("ping")

    es_host = os.environ["ELASTICSEARCH_HOST"]
    es_port = os.environ["ELASTICSEARCH_PORT"]

    with urllib.request.urlopen(
        f"http://{es_host}:{es_port}/",
        timeout=5,
    ) as response:
        cluster = json.load(response)

    uploads = Path("/uploads")
    if not uploads.is_dir() or not os.access(
        uploads, os.R_OK | os.W_OK | os.X_OK
    ):
        raise RuntimeError("Le dossier /uploads est inaccessible")

    logging.info(
        "MongoDB OK | Elasticsearch %s OK | uploads accessible",
        cluster["cluster_name"],
    )


if __name__ == "__main__":
    if "--check" in sys.argv:
        check_connections()
    else:
        logging.info("Tracker démarré : vérifications infrastructure SCRUM-13")
        while True:
            try:
                check_connections()
            except Exception:
                logging.exception("Échec de vérification du tracker")
            time.sleep(30)