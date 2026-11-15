import re
from datetime import datetime


FIELDS = (
    "timestamp", "level", "service", "message", "event_type",
    "endpoint", "http_method", "status_code", "response_time_ms",
    "user_id", "organization_id", "request_id", "error_code",
    "error_message", "db_query", "sql_duration_ms", "action", "feature",
)

REQUIRED = FIELDS[:5]

NUMERIC_FIELDS = {
    "status_code", "response_time_ms", "sql_duration_ms",
}

HTTP_FIELDS = {
    "endpoint", "http_method", "status_code",
    "response_time_ms", "request_id",
}

FAMILY_REQUIRED = {
    "http": {"endpoint", "http_method", "status_code", "response_time_ms"},
    "application": set(),
    "sql": {"db_query", "sql_duration_ms"},
    "business": {"action", "feature"},
}

FAMILY_FORBIDDEN = {
    "http": {"db_query", "sql_duration_ms", "action", "feature"},
    "application": HTTP_FIELDS | {"db_query", "sql_duration_ms", "feature"},
    "sql": HTTP_FIELDS | {"action", "feature"},
    "business": HTTP_FIELDS | {"db_query", "sql_duration_ms"},
}

BUSINESS_PAIRS = {
    ("project-viewed", "projects"),
    ("task-created", "tasks"),
    ("task-updated", "tasks"),
    ("report-generated", "reports"),
}

LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
MAX_DURATION_MS = 9223372036854

TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T"
    r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,3})?"
    r"(?:Z|[+-][0-9]{2}:[0-9]{2})"
)

CONTROL_PATTERN = re.compile(r"[\x00-\x1f]")


def valid_timestamp(value):
    if not TIMESTAMP_PATTERN.fullmatch(value):
        return False

    if not value.endswith("Z"):
        hours = int(value[-5:-3])
        minutes = int(value[-2:])
        if hours > 14 or minutes > 59:
            return False
        if hours == 14 and minutes != 0:
            return False

    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False

    return True


def validate_event(event):
    """Retourne les diagnostics ; une liste vide signifie aucun défaut détecté."""
    errors = []

    def add(code, field, message):
        errors.append({
            "code": code,
            "field": field,
            "message": message,
        })

    if not isinstance(event, dict):
        add("ROW_STRUCTURE", None, "Un événement doit être un objet.")
        return errors

    for field in event:
        if field not in FIELDS:
            add("UNKNOWN_FIELD", field, "Champ absent du contrat SCRUM-10.")

    for field in REQUIRED:
        if field not in event:
            add("REQUIRED_FIELD", field, "Champ requis absent.")

    usable = set()

    for field in FIELDS:
        if field not in event:
            continue

        value = event[field]

        if field in NUMERIC_FIELDS:
            # Un booléen Python ne doit pas être accepté comme entier.
            if type(value) is not int:
                add("INVALID_TYPE", field, "Un entier est attendu.")
            else:
                usable.add(field)
            continue

        if not isinstance(value, str):
            add("INVALID_TYPE", field, "Une chaîne de caractères est attendue.")
            continue

        if not value.strip():
            add("EMPTY_FIELD", field, "Le champ présent ne peut pas être vide.")
            continue

        if CONTROL_PATTERN.search(value):
            add("INVALID_VALUE", field, "Caractère de contrôle interdit.")
            continue

        limit = 256
        if field in {"message", "error_message"}:
            limit = 4096
        elif field == "endpoint":
            limit = 2048
        elif field == "service":
            limit = 64

        if len(value) > limit:
            add("INVALID_VALUE", field, f"Maximum autorisé : {limit} caractères.")
            continue

        usable.add(field)

    if "timestamp" in usable and not valid_timestamp(event["timestamp"]):
        add("INVALID_TIMESTAMP", "timestamp", "Date ou fuseau non conforme.")

    if "level" in usable and event["level"] not in LEVELS:
        add("INVALID_LEVEL", "level", "Niveau de log non autorisé.")

    if "service" in usable:
        if not re.fullmatch(r"[a-z][a-z0-9-]{0,63}", event["service"]):
            add("INVALID_VALUE", "service", "Nom de service non conforme.")

    if "http_method" in usable:
        if not re.fullmatch(r"[A-Za-z]{1,20}", event["http_method"]):
            add("INVALID_VALUE", "http_method", "Méthode HTTP non conforme.")

    if "endpoint" in usable:
        endpoint = event["endpoint"]
        if not endpoint.startswith("/") or any(c in endpoint for c in "?# "):
            add("INVALID_VALUE", "endpoint", "Chemin attendu sans espace, ? ou #.")

    if "status_code" in usable:
        if not 100 <= event["status_code"] <= 599:
            add("INVALID_VALUE", "status_code", "Statut attendu entre 100 et 599.")

    for field in ("response_time_ms", "sql_duration_ms"):
        if field in usable and not 0 <= event[field] <= MAX_DURATION_MS:
            add("INVALID_DURATION", field, "Durée entière hors limites autorisées.")

    if "event_type" in usable:
        family = event["event_type"]

        if family not in FAMILY_REQUIRED:
            add("INVALID_FAMILY", "event_type", "Famille d’événement inconnue.")
        else:
            for field in sorted(FAMILY_REQUIRED[family]):
                if field not in event:
                    add("REQUIRED_FIELD", field, "Champ requis pour cette famille.")

            for field in sorted(FAMILY_FORBIDDEN[family]):
                if field in event:
                    add("FIELD_NOT_ALLOWED", field, "Champ interdit pour cette famille.")

            if family == "business" and {"action", "feature"} <= usable:
                if (event["action"], event["feature"]) not in BUSINESS_PAIRS:
                    add("INVALID_VALUE", "feature", "Couple action/fonctionnalité interdit.")

    return errors