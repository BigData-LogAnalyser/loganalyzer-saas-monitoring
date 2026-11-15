import codecs
import csv
import json
import re
from pathlib import Path

if __package__:
    from .validation import FIELDS, NUMERIC_FIELDS, validate_event
else:
    from validation import FIELDS, NUMERIC_FIELDS, validate_event


DEFAULT_MAX_UPLOAD_BYTES = 104857600
EXTENSIONS = {".csv", ".json", ".jsonl", ".txt"}
INTEGER_PATTERN = re.compile(r"(?:0|[1-9][0-9]*)")


class FileValidationError(ValueError):
    """Erreur qui empêche l’utilisation du fichier entier."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


class DuplicateKeyError(ValueError):
    pass


class InvalidConstantError(ValueError):
    pass


def diagnostic(code, field, message):
    return {"code": code, "field": field, "message": message}


def check_file(path, max_bytes):
    path = Path(path)

    if path.suffix.lower() not in EXTENSIONS:
        raise FileValidationError(
            "FILE_FORMAT",
            "Extensions acceptées : .csv, .json, .jsonl et .txt.",
        )

    size = path.stat().st_size

    if size > max_bytes:
        raise FileValidationError(
            "FILE_SIZE",
            f"Le fichier dépasse la limite de {max_bytes} octets.",
        )

    if size == 0:
        raise FileValidationError("FILE_EMPTY", "Le fichier est vide.")

    # Vérifier tout l’encodage, sans charger tout le fichier en mémoire.
    decoder = codecs.getincrementaldecoder("utf-8")("strict")

    with path.open("rb") as source:
        if source.read(3) == codecs.BOM_UTF8:
            raise FileValidationError(
                "FILE_ENCODING", "Le BOM UTF-8 est interdit."
            )

        source.seek(0)

        try:
            while True:
                chunk = source.read(65536)
                if not chunk:
                    break
                decoder.decode(chunk)

            decoder.decode(b"", final=True)
        except UnicodeDecodeError as error:
            raise FileValidationError(
                "FILE_ENCODING", "Le fichier doit être encodé en UTF-8."
            ) from error

    return path


def decode_line(raw):
    # Retirer uniquement la fin de ligne, sans supprimer les cellules vides.
    if raw.endswith(b"\n"):
        raw = raw[:-1]
        if raw.endswith(b"\r"):
            raw = raw[:-1]

    return raw.decode("utf-8")


def strict_csv_row(line):
    # Vérifier la position des guillemets avant le décodage CSV.
    state = "start"

    for char in line:
        if state == "start":
            if char == '"':
                state = "quoted"
            elif char != ";":
                state = "plain"

        elif state == "plain":
            if char == '"':
                raise ValueError("Guillemet dans une cellule non citée.")
            if char == ";":
                state = "start"

        elif state == "quoted":
            if char == '"':
                state = "closed"

        elif state == "closed":
            if char == '"':
                state = "quoted"
            elif char == ";":
                state = "start"
            else:
                raise ValueError("Caractère après une cellule citée.")

    if state == "quoted":
        raise ValueError("Guillemet non fermé.")

    return next(csv.reader([line], delimiter=";", strict=True))


def unique_object(pairs):
    result = {}

    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"Clé dupliquée : {key}.")
        result[key] = value

    return result


def reject_constant(value):
    raise InvalidConstantError(f"Constante JSON interdite : {value}.")


def parse_event(line, extension):
    if extension in {".json", ".jsonl"}:
        try:
            event = json.loads(
                line,
                object_pairs_hook=unique_object,
                parse_constant=reject_constant,
            )
        except DuplicateKeyError as error:
            return None, [
                diagnostic("JSON_DUPLICATE_KEY", None, str(error))
            ]
        except InvalidConstantError as error:
            return None, [diagnostic("INVALID_TYPE", None, str(error))]
        except (ValueError, RecursionError):
            return None, [
                diagnostic("JSON_SYNTAX", None, "Ligne JSON mal formée.")
            ]

        return event, validate_event(event)

    try:
        if extension == ".csv":
            cells = strict_csv_row(line)
        else:
            cells = line.split("\t")
    except (csv.Error, ValueError):
        return None, [
            diagnostic("ROW_STRUCTURE", None, "Ligne CSV mal formée.")
        ]

    if len(cells) != len(FIELDS):
        return None, [
            diagnostic(
                "ROW_STRUCTURE",
                None,
                f"18 colonnes attendues ; {len(cells)} reçues.",
            )
        ]

    event = {}
    errors = []

    for field, value in zip(FIELDS, cells):
        if value == "":
            continue

        if field in NUMERIC_FIELDS:
            if not INTEGER_PATTERN.fullmatch(value):
                code = (
                    "INVALID_DURATION"
                    if field.endswith("_ms")
                    else "INVALID_VALUE"
                )
                errors.append(
                    diagnostic(
                        code, field, "Entier décimal sans signe attendu."
                    )
                )
                continue

            # Les domaines autorisés ne dépassent jamais 13 chiffres.
            if len(value) > 13:
                code = (
                    "INVALID_DURATION"
                    if field.endswith("_ms")
                    else "INVALID_VALUE"
                )
                errors.append(
                    diagnostic(code, field, "Nombre hors limites autorisées.")
                )
                continue

            value = int(value)

        event[field] = value

    # Éviter un second diagnostic « absent » pour un nombre mal écrit.
    invalid_numeric = {error["field"] for error in errors}
    errors.extend(
        error for error in validate_event(event)
        if not (
            error["code"] == "REQUIRED_FIELD"
            and error["field"] in invalid_numeric
        )
    )

    return event, errors


def iter_events(path, max_bytes=DEFAULT_MAX_UPLOAD_BYTES):
    """Lire les événements avec leurs lignes physiques et diagnostics."""
    path = check_file(path, max_bytes)
    extension = path.suffix.lower()

    with path.open("rb") as source:
        line_number = 0

        if extension == ".csv":
            header = decode_line(source.readline())
            line_number = 1

            if header != ";".join(FIELDS):
                raise FileValidationError(
                    "CSV_HEADER", "L’en-tête CSV ne respecte pas le contrat."
                )

            if source.peek(1) == b"":
                raise FileValidationError(
                    "FILE_EMPTY", "Le CSV contient uniquement son en-tête."
                )

        for raw in source:
            line_number += 1
            line = decode_line(raw)
            event, errors = parse_event(line, extension)

            yield {
                "source_line": line_number,
                "event": event,
                "errors": errors,
            }


def preview_file(path, max_bytes=DEFAULT_MAX_UPLOAD_BYTES):
    """Vérifier le fichier et prévisualiser au maximum dix événements."""
    from itertools import islice

    result = {
        "preview_limit": 10,
        "preview_count": 0,
        "events": [],
        "errors": [],
        "can_confirm": False,
        "scope": "Aperçu uniquement ; aucun bilan global d’ingestion.",
    }

    reader = iter_events(path, max_bytes=max_bytes)

    try:
        for row in islice(reader, result["preview_limit"]):
            result["events"].append(row)
            result["preview_count"] += 1

            for error in row["errors"]:
                result["errors"].append({
                    "source_line": row["source_line"],
                    **error,
                })

    except FileValidationError as error:
        result["errors"].append({
            "source_line": None,
            "code": error.code,
            "field": None,
            "message": str(error),
        })

    finally:
        reader.close()

    result["can_confirm"] = (
        result["preview_count"] > 0
        and not result["errors"]
    )

    return result