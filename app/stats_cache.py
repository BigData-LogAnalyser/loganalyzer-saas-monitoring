"""Cache Redis reconstructible des réponses du dashboard."""

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from zoneinfo import ZoneInfo

from flask import current_app, make_response, request
from redis import Redis
from redis.exceptions import RedisError


PREFIX = "loganalyzer:stats:v2:"
MAX_VALUE_BYTES = 1_048_576


def utc_date(value):
    return datetime.fromisoformat(
        value.replace("Z", "+00:00")
    ).astimezone(timezone.utc)


def build_cache_key(parameters, args, now, timezone_name, threshold, ttl):
    # Une borne implicite est un mode de période, pas une nouvelle
    # milliseconde dans la clé à chaque consultation.
    identity = {
        "start": (
            parameters["start"]
            if args.get("start", "").strip()
            else "24h-before-end"
        ),
        "end": (
            parameters["end"]
            if args.get("end", "").strip()
            else "now"
        ),
        "service": parameters["service"],
        "organization": parameters["organization"],
        "timezone": timezone_name,
        "today": now.astimezone(
            ZoneInfo(timezone_name)
        ).date().isoformat(),
        "sql_threshold_ms": threshold,
        "ttl_seconds": ttl,
        "sources": {
            "elasticsearch": os.environ.get(
                "ELASTICSEARCH_URL",
                "http://"
                + os.environ.get("ELASTICSEARCH_HOST", "elasticsearch")
                + ":"
                + os.environ.get("ELASTICSEARCH_PORT", "9200"),
            ),
            "index": "loganalyzer-logs-*",
            "mongodb_host": os.environ.get("MONGODB_HOST", "mongodb"),
            "mongodb_port": os.environ.get("MONGODB_PORT", "27017"),
            "mongodb_database": os.environ.get(
                "MONGODB_DATABASE", "loganalyzer"
            ),
        },
    }

    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")

    return PREFIX + hashlib.sha256(encoded).hexdigest()


def redis_client():
    return Redis(
        host=os.environ.get("REDIS_HOST", "redis"),
        port=int(os.environ.get("REDIS_PORT", "6379")),
        db=0,
        socket_connect_timeout=0.3,
        socket_timeout=0.3,
        retry_on_timeout=False,
        decode_responses=False,
    )


def valid_data(data, timezone_name, local_day):
    if not isinstance(data, dict):
        return False

    if (
        data.get("timezone") != timezone_name
        or data.get("duration_unit") != "ms"
        or data.get("period_bounds") != "[start,end)"
    ):
        return False

    cards = data.get("cards")
    today = data.get("today")
    saas = data.get("saas")
    filters = data.get("filters")

    if not all(
        isinstance(value, dict)
        for value in (cards, today, saas, filters)
    ):
        return False

    if today.get("date") != local_day:
        return False

    if not all(
        type(cards.get(field)) is int and cards[field] >= 0
        for field in (
            "total_logs", "today_logs", "error_logs", "imported_files"
        )
    ):
        return False

    if not all(
        isinstance(saas.get(field), list)
        for field in (
            "http_latency_by_endpoint",
            "http_5xx_by_service",
            "feature_usage",
        )
    ):
        return False

    sql = saas.get("slow_sql")

    return (
        isinstance(sql, dict)
        and isinstance(sql.get("slowest"), list)
        and type(sql.get("execution_count")) is int
        and type(saas.get("active_users")) is int
        and saas.get("active_users_exact") is True
        and all(
            field in filters
            for field in ("start", "end", "service", "organization")
        )
        and isinstance(data.get("generated_at"), str)
    )


def decode_entry(raw, key, now, timezone_name, ttl):
    if not raw or len(raw) > MAX_VALUE_BYTES:
        return None

    try:
        entry = json.loads(raw)
        if not isinstance(entry, dict) or entry.get("key") != key:
            return None

        data = entry["data"]
        created = utc_date(data["generated_at"])
        expires = utc_date(entry["expires_at"])
        day = now.astimezone(ZoneInfo(timezone_name)).date().isoformat()

        if not valid_data(data, timezone_name, day):
            return None

        if not (
            created <= now < expires
            and expires <= created + timedelta(seconds=ttl)
        ):
            return None

        return data

    except (
        ValueError, TypeError, KeyError, OverflowError,
        UnicodeError, RecursionError,
    ):
        return None


def cache_stats(parse_parameters, timezone_name, threshold):
    ttl = int(os.environ.get("STATS_CACHE_TTL_SECONDS", "60"))

    if not 0 <= ttl <= 3600:
        raise ValueError(
            "STATS_CACHE_TTL_SECONDS doit être compris entre 0 et 3600."
        )

    def decorate(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            now = datetime.now(timezone.utc)

            try:
                parameters = parse_parameters(request.args, now)
            except ValueError:
                # La route conserve son traitement des filtres invalides.
                return view(*args, **kwargs)

            if ttl == 0:
                response = make_response(view(*args, **kwargs))
                response.headers["X-Cache"] = "BYPASS"
                return response

            key = build_cache_key(
                parameters, request.args, now,
                timezone_name, threshold, ttl,
            )

            client = redis_client()
            available = True

            try:
                try:
                    raw = client.get(key)
                except RedisError:
                    available = False
                    raw = None
                    current_app.logger.warning(
                        "Cache Redis indisponible en lecture."
                    )

                if available:
                    cached = decode_entry(
                        raw, key, datetime.now(timezone.utc),
                        timezone_name, ttl,
                    )

                    if cached is not None:
                        response = make_response(cached)
                        response.headers["Cache-Control"] = "no-store"
                        response.headers["X-Cache"] = "HIT"
                        return response

                response = make_response(view(*args, **kwargs))
                response.headers["X-Cache"] = (
                    "MISS" if available else "BYPASS"
                )

                if response.status_code != 200 or not available:
                    return response

                data = response.get_json(silent=True)
                current = datetime.now(timezone.utc)
                local_day = current.astimezone(
                    ZoneInfo(timezone_name)
                ).date().isoformat()

                if not valid_data(data, timezone_name, local_day):
                    return response

                # Si le calcul a traversé minuit, la clé doit être revue.
                if key != build_cache_key(
                    parameters, request.args, current,
                    timezone_name, threshold, ttl,
                ):
                    return response

                try:
                    created = utc_date(data["generated_at"])
                    expires = min(
                        created + timedelta(seconds=ttl),
                        utc_date(data["today"]["end"]),
                    )

                    if expires <= current or created > current:
                        return response

                    payload = json.dumps(
                        {
                            "key": key,
                            "expires_at": expires.isoformat(),
                            "data": data,
                        },
                        ensure_ascii=False,
                        allow_nan=False,
                        separators=(",", ":"),
                    ).encode("utf-8")

                    if len(payload) <= MAX_VALUE_BYTES:
                        client.set(
                            key,
                            payload,
                            pxat=int(expires.timestamp() * 1000),
                        )

                except RedisError:
                    response.headers["X-Cache"] = "BYPASS"
                    current_app.logger.warning(
                        "Cache Redis indisponible en écriture."
                    )
                except (ValueError, TypeError, KeyError, OverflowError):
                    current_app.logger.warning(
                        "Réponse non enregistrée dans le cache."
                    )

                return response

            finally:
                try:
                    client.close()
                except RedisError:
                    pass

        return wrapped

    return decorate
