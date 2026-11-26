"""Documentation OpenAPI des indicateurs du dashboard."""


def extend_stats_spec(spec):
    schemas = spec.setdefault("components", {}).setdefault("schemas", {})

    def obj(properties):
        return {
            "type": "object",
            "required": list(properties),
            "properties": properties,
        }

    def array(item):
        return {"type": "array", "items": item}

    def ref(name):
        return {"$ref": f"#/components/schemas/{name}"}

    count = {"type": "integer", "minimum": 0}
    duration = {"type": "number", "minimum": 0}
    text = {"type": "string"}
    nullable_text = {"type": "string", "nullable": True}
    timestamp = {"type": "string", "format": "date-time"}

    schemas["DashboardFilters"] = obj({
        "start": timestamp,
        "end": timestamp,
        "service": text,
        "organization": text,
    })

    schemas["DashboardCards"] = obj({
        "total_logs": {
            **count,
            "description": (
                "Toutes les dates ; filtres service et organisation."
            ),
        },
        "today_logs": {
            **count,
            "description": (
                "Journée courante dans Africa/Tunis ; "
                "filtres service et organisation."
            ),
        },
        "error_logs": {
            **count,
            "description": (
                "Niveaux ERROR ou CRITICAL dans la période sélectionnée ; "
                "filtres service et organisation."
            ),
        },
        "imported_files": {
            **count,
            "description": (
                "Imports confirmés dans MongoDB, tous statuts et toutes "
                "dates ; indépendant des filtres sur les logs."
            ),
        },
    })

    schemas["DashboardLatency"] = obj({
        "endpoint": text,
        "request_count": count,
        "average_ms": duration,
    })

    schemas["DashboardHttpRate"] = obj({
        "service": text,
        "response_count": count,
        "error_count": count,
        "error_rate_percent": {
            "type": "number",
            "minimum": 0,
            "maximum": 100,
            "description": (
                "100 × réponses HTTP 500–599 / réponses HTTP 100–599."
            ),
        },
    })

    schemas["DashboardSqlExecution"] = obj({
        "id": text,
        "index": text,
        "timestamp": {**timestamp, "nullable": True},
        "service": nullable_text,
        "query_name": nullable_text,
        "duration_ms": duration,
    })

    schemas["DashboardSlowSql"] = obj({
        "threshold_ms": count,
        "execution_count": count,
        "slowest": {
            **array(ref("DashboardSqlExecution")),
            "maxItems": 10,
            "description": (
                "Dix exécutions les plus lentes au maximum, "
                "durée strictement supérieure au seuil."
            ),
        },
    })

    schemas["DashboardFeatureUsage"] = obj({
        "feature": text,
        "usage_count": count,
    })

    schemas["DashboardSaas"] = obj({
        "http_latency_by_endpoint": array(ref("DashboardLatency")),
        "http_5xx_by_service": array(ref("DashboardHttpRate")),
        "slow_sql": ref("DashboardSlowSql"),
        "active_users": {
            **count,
            "description": (
                "Identifiants user.id distincts non vides des événements "
                "HTTP ou métier de la période. "
                "Ne mesure pas les connexions simultanées."
            ),
        },
        "active_users_exact": {
            "type": "boolean",
            "enum": [True],
        },
        "feature_usage": {
            **array(ref("DashboardFeatureUsage")),
            "description": (
                "Actions métier admissibles ; classement par nombre "
                "d’utilisations décroissant puis nom de fonctionnalité."
            ),
        },
    })

    schemas["DashboardStats"] = obj({
        "cards": ref("DashboardCards"),
        "today": obj({
            "date": {"type": "string", "format": "date"},
            "start": timestamp,
            "end": timestamp,
        }),
        "saas": ref("DashboardSaas"),
        "generated_at": {
            **timestamp,
            "description": "Instant de lancement du calcul, en UTC.",
        },
        "timezone": {"type": "string", "enum": ["Africa/Tunis"]},
        "filters": ref("DashboardFilters"),
        "period_bounds": {"type": "string", "enum": ["[start,end)"]},
        "duration_unit": {"type": "string", "enum": ["ms"]},
    })

    schemas["DashboardError"] = {
        "type": "object",
        "required": ["error"],
        "properties": {
            "error": {
                "type": "object",
                "required": ["code", "message"],
                "properties": {
                    "code": text,
                    "message": text,
                    "field": text,
                },
            }
        },
    }

    def response(description, schema):
        return {
            "description": description,
            "content": {
                "application/json": {"schema": schema}
            },
        }

    tag = "Dashboard et KPI"
    tags = spec.setdefault("tags", [])

    if not any(item.get("name") == tag for item in tags):
        tags.append({
            "name": tag,
            "description": "Indicateurs de volume et d’activité SaaS.",
        })

    spec.setdefault("paths", {})["/api/v1/stats"] = {
        "get": {
            "tags": [tag],
            "operationId": "getDashboardStats",
            "summary": "Calculer les indicateurs du dashboard",
            "description": (
                "Les KPI SaaS portent sur [start inclus, end exclu[. "
                "Sans dates : les 24 dernières heures. Avec end seul : "
                "les 24 heures précédant end. Avec start seul : de start "
                "à maintenant. Les dates exigent un fuseau et sont "
                "normalisées en UTC. Le jour courant utilise Africa/Tunis. "
                "Les quatre cartes ont les périmètres décrits dans leur "
                "schéma. Les durées sont retournées en millisecondes. "
                "Une liste HTTP vide signifie une absence de population "
                "admissible : l’interface affiche N/D, pas un taux nul. "
                "Le décompte des utilisateurs distincts est exact. "
                "Le seuil SQL est configurable avec SQL_SLOW_THRESHOLD_MS, "
                "1000 ms par défaut. Les paramètres inconnus ou répétés "
                "sont refusés. Aucune recherche n’est ajoutée à l’historique. "
                "En cas de panne d’une source ou d’agrégation incomplète, "
                "l’API renvoie HTTP 503 sans chiffres partiels."
            ),
            "parameters": [
                {
                    "name": "start",
                    "in": "query",
                    "description": "Début inclus de la période.",
                    "schema": timestamp,
                    "example": "2026-11-04T00:00:00Z",
                },
                {
                    "name": "end",
                    "in": "query",
                    "description": (
                        "Fin exclue, strictement postérieure au début."
                    ),
                    "schema": timestamp,
                    "example": "2026-11-05T00:00:00Z",
                },
                {
                    "name": "service",
                    "in": "query",
                    "description": "Service exact ; vide pour tous.",
                    "schema": {
                        "type": "string",
                        "maxLength": 64,
                        "pattern": "^$|^[a-z][a-z0-9-]{0,63}$",
                    },
                },
                {
                    "name": "organization",
                    "in": "query",
                    "description": (
                        "Identifiant exact d’organisation ; vide pour toutes. "
                        "Caractères de contrôle interdits."
                    ),
                    "schema": {"type": "string", "maxLength": 128},
                },
            ],
            "responses": {
                "200": response(
                    "Indicateurs calculés ; listes vides si aucune "
                    "population admissible.",
                    ref("DashboardStats"),
                ),
                "400": response(
                    "Paramètre invalide : INVALID_FILTER.",
                    ref("DashboardError"),
                ),
                "503": response(
                    "Calcul indisponible : STATS_UNAVAILABLE.",
                    ref("DashboardError"),
                ),
            },
        }
    }


    # Contrat du cache Redis des KPI.
    operation = spec["paths"]["/api/v1/stats"]["get"]

    operation["description"] = operation["description"].replace(
        "En cas de panne d’une source ou d’agrégation incomplète, "
        "l’API renvoie HTTP 503 sans chiffres partiels.",
        "Lorsqu’un recalcul est nécessaire, une panne d’une source "
        "ou une agrégation incomplète produit HTTP 503 sans chiffres partiels.",
    )

    operation["description"] += (
        " La réponse complète peut être mise en cache dans Redis. "
        "TTL configurable avec STATS_CACHE_TTL_SECONDS : 60 secondes "
        "par défaut, 0 pour désactiver, maximum 3600. "
        "L’expiration est calculée depuis generated_at et limitée "
        "au prochain minuit dans Africa/Tunis. "
        "Pour une période relative, les bornes et la date du calcul "
        "initial sont conservées sur un HIT. "
        "Un import ne déclenche pas d’invalidation immédiate. "
        "Un cache valide peut être servi pendant une panne des sources. "
        "Si Redis est indisponible, le calcul utilise les sources."
    )

    operation["responses"]["200"]["headers"] = {
        "X-Cache": {
            "description": (
                "HIT : réponse réutilisée ; MISS : calcul depuis les sources ; "
                "BYPASS : cache désactivé ou indisponible."
            ),
            "schema": {
                "type": "string",
                "enum": ["HIT", "MISS", "BYPASS"],
            },
        },
        "Cache-Control": {
            "description": "Cache HTTP désactivé ; Redis est géré côté serveur.",
            "schema": {"type": "string", "enum": ["no-store"]},
        },
    }


    # Ajouts SCRUM-25 : graphiques et contrôles des services.
    cards = schemas["DashboardCards"]
    cards["properties"]["critical_logs"] = {
        **count,
        "description": (
            "Logs CRITICAL de la période sélectionnée, "
            "avec filtres service et organisation."
        ),
    }
    cards["required"].append("critical_logs")

    schemas["DashboardTimelinePoint"] = obj({
        "timestamp": {
            **timestamp,
            "description": (
                "Début de l’intervalle ; le premier intervalle peut "
                "commencer avant start. Seuls les événements de la "
                "période sélectionnée sont comptés."
            ),
        },
        "count": count,
    })

    schemas["DashboardLevelCount"] = obj({
        "level": {
            "type": "string",
            "enum": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        },
        "count": count,
    })

    schemas["DashboardServiceErrors"] = obj({
        "service": text,
        "error_count": count,
    })

    schemas["DashboardRecentEvent"] = obj({
        "id": text,
        "index": text,
        "timestamp": {**timestamp, "nullable": True},
        "level": nullable_text,
        "service": nullable_text,
        "message": nullable_text,
    })

    schemas["DashboardOverview"] = obj({
        "period_total": {
            **count,
            "description": (
                "Nombre exact de logs de la période sélectionnée, "
                "avec filtres service et organisation."
            ),
        },
        "interval_seconds": {
            "type": "integer",
            "minimum": 1,
            "description": (
                "Intervalle fixe du graphique temporel, en secondes ; "
                "calculé selon la durée de la période pour obtenir "
                "environ 60 intervalles."
            ),
        },
        "logs_over_time": array(ref("DashboardTimelinePoint")),
        "levels": {
            **array(ref("DashboardLevelCount")),
            "minItems": 5,
            "maxItems": 5,
            "description": "Les cinq niveaux sont présents, même à zéro.",
        },
        "errors_by_service": {
            **array(ref("DashboardServiceErrors")),
            "maxItems": 10,
            "description": (
                "Logs ERROR et CRITICAL par service ; dix premiers "
                "services par nombre décroissant, puis nom croissant."
            ),
        },
        "errors_service_limit": {"type": "integer", "enum": [10]},
        "recent_events": {
            **array(ref("DashboardRecentEvent")),
            "maxItems": 5,
            "description": (
                "Cinq événements les plus récents au maximum ; "
                "date décroissante puis event.id croissant."
            ),
        },
    })

    schemas["DashboardStats"]["properties"]["overview"] = ref(
        "DashboardOverview"
    )
    schemas["DashboardStats"]["required"].append("overview")

    operation["description"] += (
        " Le bloc overview fournit les graphiques et les cinq "
        "événements récents de la période filtrée. "
        "critical_logs détaille la population CRITICAL déjà incluse "
        "dans error_logs. Le préfixe Redis est désormais "
        "loganalyzer:stats:v2: pour distinguer ce format de réponse."
    )

    schemas["ServiceStatus"] = obj({
        "name": {
            "type": "string",
            "enum": [
                "Webapp Flask", "Elasticsearch", "MongoDB",
                "Redis", "Logstash",
            ],
        },
        "status": {
            "type": "string",
            "enum": ["available", "degraded", "unavailable", "unknown"],
        },
        "message": text,
        "duration_ms": {
            "type": "integer",
            "minimum": 0,
            "nullable": True,
            "description": (
                "Durée du contrôle en millisecondes ; null pour Flask."
            ),
        },
    })

    schemas["ServicesStatusResponse"] = obj({
        "checked_at": timestamp,
        "services": {
            **array(ref("ServiceStatus")),
            "minItems": 5,
            "maxItems": 5,
        },
    })

    service_tag = "État des services"
    if not any(item.get("name") == service_tag for item in tags):
        tags.append({
            "name": service_tag,
            "description": "Contrôles de disponibilité du dashboard.",
        })

    spec["paths"]["/api/v1/services/status"] = {
        "get": {
            "tags": [service_tag],
            "operationId": "getServicesStatus",
            "summary": "Vérifier la disponibilité des cinq services",
            "description": (
                "Flask est disponible lorsque cette requête aboutit. "
                "Les contrôles Elasticsearch, MongoDB, Redis et Logstash "
                "sont exécutés indépendamment en parallèle. "
                "MongoDB et Redis sont contrôlés par ping ; Logstash "
                "par son API et la présence du pipeline main. "
                "Elasticsearch green correspond à available, yellow à "
                "degraded et red à unavailable. Une réponse non reconnue "
                "correspond à unknown ; une exception à unavailable. "
                "HTTP 200 contient le bilan même si un service échoue. "
                "Ce contrôle ne garantit pas une ingestion complète. "
                "Kibana et le tracker ne sont pas contrôlés. "
                "La réponse n’est pas mise en cache."
            ),
            "responses": {
                "200": {
                    **response(
                        "Bilan de disponibilité des cinq services.",
                        ref("ServicesStatusResponse"),
                    ),
                    "headers": {
                        "Cache-Control": {
                            "schema": {
                                "type": "string",
                                "enum": ["no-store"],
                            },
                        },
                    },
                },
            },
        },
    }

    return spec
