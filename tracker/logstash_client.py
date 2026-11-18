"""Envoi des événements bruts au pipeline HTTP Logstash."""

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


MAX_REQUEST_BYTES = 1048576


class ImportTransportError(RuntimeError):
    """Erreur technique de transmission, distincte d'un rejet de données."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def build_envelope(import_document, row, source_path):
    extension = source_path.suffix.lower().lstrip(".")

    return {
        "format": extension,
        "raw": row["raw"],
        "context": {
            "upload_id": import_document["upload_id"],
            "source_line": row["source_line"],
            "original_filename": import_document["original_filename"],
            "source_path": str(source_path),
        },
    }


def send_event(envelope, url="http://logstash:8080/", timeout=10):
    payload = json.dumps(
        envelope,
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")

    if len(payload) > MAX_REQUEST_BYTES:
        raise ImportTransportError(
            "LOGSTASH_REQUEST_SIZE",
            "Une ligne et son contexte dépassent la limite HTTP de Logstash.",
        )

    request = Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urlopen(request, timeout=timeout) as response:
            # Logstash peut répondre avec du texte : ne pas décoder en JSON.
            response.read()

    except HTTPError as error:
        raise ImportTransportError(
            "LOGSTASH_HTTP",
            f"Logstash a refusé la transmission : HTTP {error.code}.",
        ) from error

    except (URLError, TimeoutError, OSError) as error:
        raise ImportTransportError(
            "LOGSTASH_UNAVAILABLE",
            "Transmission à Logstash non confirmée.",
        ) from error