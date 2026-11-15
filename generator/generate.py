import argparse
import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import random
import shutil
from faker import Faker


FIELDS = [
    "timestamp", "level", "service", "message", "event_type",
    "endpoint", "http_method", "status_code", "response_time_ms",
    "user_id", "organization_id", "request_id", "error_code",
    "error_message", "db_query", "sql_duration_ms", "action", "feature",
]

BUSINESS_ACTIONS = [
    ("project-viewed", "projects"),
    ("task-created", "tasks"),
    ("task-updated", "tasks"),
    ("report-generated", "reports"),
]


def parse_date(value):
    try:
        date = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if date.utcoffset() is None:
            raise ValueError("Fuseau horaire obligatoire")
        return date.astimezone(timezone.utc)
    except ValueError as error:
        raise argparse.ArgumentTypeError(
            "Date attendue avec fuseau, par exemple 2026-11-04T08:00:00Z"
        ) from error


def timestamp(date):
    return date.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def make_event(index, start, duration_ms, scenario, rng, fake):
    offset = rng.randrange(duration_ms)

    # Pour le pic, 80 % des événements sont placés dans les 10 %
    # centraux de la période.
    if scenario == "pic" and rng.random() < 0.8:
        lower = duration_ms * 45 // 100
        upper = max(lower + 1, duration_ms * 55 // 100)
        offset = rng.randrange(lower, upper)

    family = rng.choice(["http", "application", "sql", "business"])
    error_rate = 0.4 if scenario == "erreurs" else 0.03
    failed = rng.random() < error_rate

    event = {
        "timestamp": timestamp(start + timedelta(milliseconds=offset)),
        "level": "ERROR" if failed else "INFO",
        "service": "task-service",
        "message": "Opération réussie",
        "event_type": family,
        "user_id": f"U{fake.random_int(min=1, max=100)}",
        "organization_id": f"ORG{fake.random_int(min=1, max=10)}",
    }

    if failed:
        event["error_code"] = "SYNTHETIC_ERROR"
        event["error_message"] = "Erreur synthétique de démonstration"

    if family == "http":
        event.update({
            "service": "api-gateway",
            "message": "Erreur HTTP" if failed else "Requête HTTP traitée",
            "endpoint": rng.choice([
                "/api/tasks", "/api/projects", "/api/reports",
            ]),
            "http_method": rng.choice([
                "GET", "POST", "PUT", "PATCH", "DELETE",
            ]),
            "status_code": 500 if failed else 200,
            "response_time_ms": (
                rng.randint(3001, 8000)
                if scenario == "lenteurs"
                else rng.randint(20, 500)
            ),
            "request_id": fake.uuid4(),
        })

    elif family == "application":
        event["message"] = (
            "Échec du traitement applicatif"
            if failed else "Traitement applicatif terminé"
        )

    elif family == "sql":
        event.update({
            "message": "Erreur SQL" if failed else "Requête SQL exécutée",
            "db_query": rng.choice([
                "list_tasks", "list_projects", "report_summary",
            ]),
            "sql_duration_ms": (
                rng.randint(1001, 5000)
                if scenario == "lenteurs"
                else rng.randint(5, 300)
            ),
        })

    else:
        action, feature = rng.choice(BUSINESS_ACTIONS)
        event.update({
            "message": (
                f"Échec de l'action {action}"
                if failed else f"Action {action} effectuée"
            ),
            "action": action,
            "feature": feature,
        })

    return event


def invalid_events(start):
    base = {
        "timestamp": timestamp(start),
        "level": "INFO",
        "service": "api-gateway",
        "message": "Événement volontairement invalide",
        "event_type": "http",
        "endpoint": "/api/tasks",
        "http_method": "GET",
        "status_code": 200,
        "response_time_ms": 125,
    }

    cases = [
        ("service", None, "REQUIRED_FIELD"),
        ("timestamp", "date-invalide", "INVALID_TIMESTAMP"),
        ("level", "FATAL", "INVALID_LEVEL"),
        ("status_code", 700, "INVALID_VALUE"),
        ("response_time_ms", -1, "INVALID_DURATION"),
        ("sql_duration_ms", 10, "FIELD_NOT_ALLOWED"),
    ]

    events = []
    expected = []

    for index, (field, value, code) in enumerate(cases, start=1):
        event = dict(base)
        if value is None:
            event.pop(field)
        else:
            event[field] = value

        events.append(event)
        expected.append({
            "ligne_jsonl_txt": index,
            "ligne_csv": index + 1,
            "field": field,
            "code": code,
        })

    return events, expected


def write_formats(folder, events):
    folder.mkdir(parents=True, exist_ok=True)

    with (
        (folder / "logs.csv").open(
            "w", encoding="utf-8", newline=""
        ) as csv_file,
        (folder / "logs.jsonl").open(
            "w", encoding="utf-8", newline=""
        ) as json_file,
        (folder / "logs.txt").open(
            "w", encoding="utf-8", newline=""
        ) as text_file,
    ):
        writer = csv.writer(
            csv_file, delimiter=";", lineterminator="\n"
        )
        writer.writerow(FIELDS)

        for event in events:
            values = [event.get(field, "") for field in FIELDS]
            writer.writerow(values)
            json_file.write(
                json.dumps(event, ensure_ascii=False) + "\n"
            )
            text_file.write(
                "\t".join(str(value) for value in values) + "\n"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Générateur synthétique LogAnalyzer — contrat v1"
    )
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--start", type=parse_date, required=True)
    parser.add_argument("--end", type=parse_date, required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--scenario",
        choices=["normal", "erreurs", "lenteurs", "pic"],
        default="normal",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if args.count < 1:
        parser.error("--count doit être supérieur ou égal à 1")

    if args.end <= args.start:
        parser.error("--end doit être après --start")

    duration = args.end - args.start
    duration_ms = (
        duration.days * 86_400_000
        + duration.seconds * 1000
        + duration.microseconds // 1000
    )

    if duration_ms < 1:
        parser.error("La période doit durer au moins une milliseconde")

    # Un dossier neuf évite d'écraser un jeu existant.
    if args.output.exists():
        parser.error("Le dossier --output existe déjà, choisir un autre nom")

    rng = random.Random(args.seed)
    fake = Faker("fr_FR")
    fake.seed_instance(args.seed)
    events = (
        make_event(
            index, args.start, duration_ms, args.scenario, rng, fake
        )
        for index in range(args.count)
    )

    write_formats(args.output / "valides", events)

    invalid, expected = invalid_events(args.start)
    write_formats(args.output / "invalides", invalid)

    (args.output / "invalides" / "attendus.json").write_text(
        json.dumps(expected, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    samples = Path(__file__).resolve().parents[1] / "samples"
    reference = args.output / "reference"
    reference.mkdir()

    shutil.copytree(samples / "valides", reference / "valides")
    shutil.copyfile(
        samples / "attendus.json", reference / "attendus.json"
    )
    shutil.copyfile(
        samples / "README.md", reference / "README-source.md"
    )

    print(f"Scénario : {args.scenario}")
    print(f"Graine : {args.seed}")
    print(f"Événements valides par format : {args.count}")
    print("Événements invalides par format : 6")
    print(f"Résultats enregistrés dans : {args.output}")


if __name__ == "__main__":
    main()