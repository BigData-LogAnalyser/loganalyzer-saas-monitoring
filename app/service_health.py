"""Contrôles de disponibilité des services du dashboard."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.error import HTTPError
from urllib.request import urlopen

from flask import Blueprint, jsonify
from pymongo import MongoClient
from redis import Redis


def read_json(url):
    with urlopen(url, timeout=2) as response:
        raw = response.read(262145)

    if len(raw) > 262144:
        raise ValueError("Réponse de contrôle trop volumineuse.")

    return json.loads(raw)


def check_elasticsearch():
    host = os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
    port = os.environ.get("ELASTICSEARCH_PORT", "9200")
    base = os.environ.get(
        "ELASTICSEARCH_URL", f"http://{host}:{port}"
    ).rstrip("/")

    data = read_json(base + "/_cluster/health")
    state = data.get("status")

    if state == "green":
        return {
            "status": "available",
            "message": "Cluster opérationnel ; toutes les copies sont allouées.",
        }
    if state == "yellow":
        return {
            "status": "degraded",
            "message": (
                "Données primaires disponibles ; certaines répliques "
                "ne sont pas allouées. Possible sur un cluster à un seul nœud."
            ),
        }
    if state == "red":
        return {
            "status": "unavailable",
            "message": "Certaines données primaires ne sont pas disponibles.",
        }
    return {
        "status": "unknown",
        "message": "L’état du cluster n’a pas pu être interprété.",
    }


def check_mongodb():
    with MongoClient(
        host=os.environ.get("MONGODB_HOST", "mongodb"),
        port=int(os.environ.get("MONGODB_PORT", "27017")),
        serverSelectionTimeoutMS=2000,
        connectTimeoutMS=2000,
        socketTimeoutMS=2000,
    ) as client:
        client.admin.command("ping")

    return {
        "status": "available",
        "message": "MongoDB répond à la commande ping.",
    }


def check_redis():
    client = Redis(
        host=os.environ.get("REDIS_HOST", "redis"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        socket_connect_timeout=2,
        socket_timeout=2,
        retry_on_timeout=False,
    )
    try:
        if not client.ping():
            raise RuntimeError("Réponse PING incorrecte.")
    finally:
        client.close()

    return {
        "status": "available",
        "message": "Redis répond à la commande PING.",
    }


def check_logstash():
    data = read_json("http://logstash:9600/_node/pipelines")
    pipelines = data.get("pipelines")

    if isinstance(pipelines, dict) and "main" in pipelines:
        return {
            "status": "available",
            "message": (
                "L’API Logstash répond et le pipeline main est chargé. "
                "Ce contrôle ne prouve pas l’indexation d’un fichier."
            ),
        }

    return {
        "status": "degraded",
        "message": "L’API répond, mais le pipeline main n’est pas confirmé.",
    }



def check_kibana():
    base = os.environ.get(
        "KIBANA_INTERNAL_URL", "http://kibana:5601"
    ).strip().rstrip("/")

    try:
        data = read_json(base + "/api/status")
    except HTTPError as error:
        # Kibana peut renvoyer 503 avec un bilan JSON exploitable.
        if error.code != 503:
            raise
        with error:
            raw = error.read(262145)
        if len(raw) > 262144:
            raise ValueError("Réponse de contrôle trop volumineuse.")
        data = json.loads(raw)

    level = data.get("status", {}).get("overall", {}).get("level")
    states = {
        "available": (
            "available",
            "L’API de disponibilité Kibana indique un service opérationnel.",
        ),
        "degraded": (
            "degraded",
            "Kibana répond, mais certaines fonctionnalités sont dégradées.",
        ),
        "unavailable": (
            "unavailable",
            "Kibana indique que le service est indisponible.",
        ),
        "critical": (
            "unavailable",
            "Kibana indique un état critique.",
        ),
    }
    status, message = states.get(level, (
        "unknown", "L’état de Kibana n’a pas pu être interprété."
    ))
    return {
        "status": status,
        "message": message + (
            " Ce contrôle ne garantit pas l’affichage intégré du dashboard."
        ),
    }


def run_check(name, function):
    started = time.monotonic()

    try:
        result = function()
    except Exception:
        result = {
            "status": "unavailable",
            "message": (
                "Le service n’a pas répondu correctement au contrôle. "
                "Il peut être arrêté, en démarrage ou inaccessible."
            ),
        }

    return {
        "name": name,
        **result,
        "duration_ms": round((time.monotonic() - started) * 1000),
    }


def register_service_health(app):
    health = Blueprint("service_health", __name__)

    @health.get("/api/v1/services/status")
    def services_status():
        checks = [
            ("Elasticsearch", check_elasticsearch),
            ("MongoDB", check_mongodb),
            ("Redis", check_redis),
            ("Logstash", check_logstash),
            ("Kibana", check_kibana),
        ]

        # Contrôles indépendants exécutés en parallèle.
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(run_check, name, function)
                for name, function in checks
            ]
            services = [future.result() for future in futures]

        services.insert(0, {
            "name": "Webapp Flask",
            "status": "available",
            "message": (
                "L’application Flask a répondu à cette requête de contrôle."
            ),
            "duration_ms": None,
        })

        response = jsonify(
            services=services,
            checked_at=datetime.now(timezone.utc).isoformat(
                timespec="milliseconds"
            ).replace("+00:00", "Z"),
        )
        response.headers["Cache-Control"] = "no-store"
        return response

    app.register_blueprint(health)
