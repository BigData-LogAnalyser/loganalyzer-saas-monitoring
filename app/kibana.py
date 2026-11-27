"""Page et contrôle de disponibilité du dashboard Kibana."""
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen
from uuid import UUID

from flask import Blueprint, jsonify, render_template

bp = Blueprint("kibana", __name__)


def valid_base_url(value):
    try:
        parts = urlsplit(value)
        return (
            parts.scheme in ("http", "https")
            and bool(parts.hostname)
            and parts.port != 0
            and parts.username is None
            and parts.password is None
            and not parts.query
            and not parts.fragment
        )
    except ValueError:
        return False


def settings():
    public = os.environ.get("KIBANA_PUBLIC_URL", "").strip().rstrip("/")
    internal = os.environ.get("KIBANA_INTERNAL_URL", "").strip().rstrip("/")
    identifier = os.environ.get("KIBANA_DASHBOARD_ID", "").strip()
    enabled = os.environ.get(
        "KIBANA_EMBED_ENABLED", "false"
    ).lower() in ("1", "true", "yes")

    try:
        identifier = str(UUID(identifier))
    except ValueError:
        identifier = ""

    configured = valid_base_url(public) and bool(identifier)
    dashboard_url = (
        f"{public}/app/dashboards#/view/{identifier}"
        if configured else ""
    )
    query = urlencode({
        "embed": "true",
        "show-time-filter": "true",
        "show-query-input": "true",
        "_g": "(time:(from:now-30d,to:now))",
    })
    return {
        "configured": configured,
        "enabled": enabled,
        "internal": internal,
        "identifier": identifier,
        "dashboard_url": dashboard_url,
        "embed_url": f"{dashboard_url}?{query}" if configured else "",
    }


@bp.get("/kibana")
def kibana_page():
    config = settings()
    return render_template("kibana.html", kibana=config)


def status_response(state, message, can_embed=False):
    response = jsonify(
        state=state, message=message, can_embed=can_embed
    )
    response.headers["Cache-Control"] = "no-store"
    return response


@bp.get("/api/v1/kibana/status")
def kibana_status():
    config = settings()
    if not config["configured"]:
        return status_response(
            "unconfigured", "Le dashboard Kibana n’est pas configuré."
        )
    if not config["enabled"]:
        return status_response(
            "disabled",
            "L’affichage intégré est désactivé. Ouvrez le dashboard dans Kibana.",
        )
    if not valid_base_url(config["internal"]):
        return status_response(
            "unconfigured", "La connexion à Kibana n’est pas configurée."
        )

    try:
        with urlopen(
            config["internal"] + "/api/status", timeout=2
        ) as response:
            health = json.load(response)

        level = health.get("status", {}).get("overall", {}).get("level")
        if level not in ("available", "degraded"):
            return status_response(
                "unavailable", "Kibana n’est pas prêt. Réessayez dans un instant."
            )

        # Vérifier que le dashboard existe dans l’espace Default.
        with urlopen(
            config["internal"] + "/api/saved_objects/dashboard/"
            + config["identifier"],
            timeout=2,
        ) as response:
            saved = json.load(response)

        if saved.get("error") or saved.get("type") != "dashboard":
            return status_response(
                "unavailable", "Le dashboard est introuvable dans Kibana."
            )

        return status_response(
            level,
            "Service Kibana disponible."
            if level == "available"
            else "Kibana fonctionne avec un état dégradé.",
            can_embed=True,
        )
    except HTTPError as error:
        message = (
            "Le dashboard est introuvable dans Kibana."
            if error.code == 404
            else "Kibana est momentanément indisponible."
        )
        return status_response("unavailable", message)
    except (URLError, TimeoutError, OSError, ValueError, AttributeError):
        return status_response(
            "unavailable", "Impossible de joindre Kibana pour le moment."
        )


def register_kibana(app):
    app.register_blueprint(bp)
