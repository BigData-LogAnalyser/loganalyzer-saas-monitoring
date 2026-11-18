"""Lecture des fichiers originaux destinés à Logstash."""

import codecs
from pathlib import Path


FIELDS = (
    "timestamp", "level", "service", "message", "event_type",
    "endpoint", "http_method", "status_code", "response_time_ms",
    "user_id", "organization_id", "request_id", "error_code",
    "error_message", "db_query", "sql_duration_ms", "action", "feature",
)

EXTENSIONS = {".csv", ".json", ".jsonl", ".txt"}
DEFAULT_MAX_BYTES = 104857600


class SourceFileError(ValueError):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def decode_line(raw):
    # Conserver les espaces et les tabulations finales.
    if raw.endswith(b"\n"):
        raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]

    return raw.decode("utf-8")


def inspect_source(path, max_bytes=DEFAULT_MAX_BYTES):
    """Vérifier le fichier entier et compter ses événements."""
    path = Path(path)

    if path.suffix.lower() not in EXTENSIONS:
        raise SourceFileError("FILE_FORMAT", "Format non autorisé.")

    size = path.stat().st_size

    if size > max_bytes:
        raise SourceFileError("FILE_SIZE", "Fichier trop volumineux.")

    if size == 0:
        raise SourceFileError("FILE_EMPTY", "Le fichier est vide.")

    count = 0

    with path.open("rb") as source:
        if source.read(3) == codecs.BOM_UTF8:
            raise SourceFileError("FILE_ENCODING", "BOM UTF-8 interdit.")

        source.seek(0)

        for number, raw in enumerate(source, start=1):
            try:
                line = decode_line(raw)
            except UnicodeDecodeError as error:
                raise SourceFileError(
                    "FILE_ENCODING",
                    f"Encodage UTF-8 incorrect à la ligne {number}.",
                ) from error

            if number == 1 and path.suffix.lower() == ".csv":
                if line != ";".join(FIELDS):
                    raise SourceFileError(
                        "CSV_HEADER", "En-tête CSV incorrect."
                    )
                continue

            # Une ligne vide interne compte aussi :
            # Logstash devra la rejeter avec un motif.
            count += 1

    if count == 0:
        raise SourceFileError(
            "FILE_EMPTY", "Le fichier ne contient aucun événement."
        )

    return count


def iter_source_lines(path):
    """Lire les lignes ; appeler inspect_source avant l'envoi."""
    path = Path(path)
    is_csv = path.suffix.lower() == ".csv"

    with path.open("rb") as source:
        for number, raw in enumerate(source, start=1):
            if is_csv and number == 1:
                continue

            yield {
                "source_line": number,
                "raw": decode_line(raw),
            }