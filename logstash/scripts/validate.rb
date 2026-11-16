require "date"


def register(params)
  @fields = [
    "timestamp", "level", "service", "message", "event_type",
    "endpoint", "http_method", "status_code", "response_time_ms",
    "user_id", "organization_id", "request_id", "error_code",
    "error_message", "db_query", "sql_duration_ms", "action", "feature"
  ].freeze

  @numeric_fields = [
    "status_code", "response_time_ms", "sql_duration_ms"
  ].freeze

  @levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"].freeze

  http_fields = [
    "endpoint", "http_method", "status_code",
    "response_time_ms", "request_id"
  ]

  @family_required = {
    "http" => [
      "endpoint", "http_method", "status_code", "response_time_ms"
    ],
    "application" => [],
    "sql" => ["db_query", "sql_duration_ms"],
    "business" => ["action", "feature"]
  }

  @family_forbidden = {
    "http" => ["db_query", "sql_duration_ms", "action", "feature"],
    "application" => http_fields + [
      "db_query", "sql_duration_ms", "feature"
    ],
    "sql" => http_fields + ["action", "feature"],
    "business" => http_fields + ["db_query", "sql_duration_ms"]
  }

  @business_pairs = [
    ["project-viewed", "projects"],
    ["task-created", "tasks"],
    ["task-updated", "tasks"],
    ["report-generated", "reports"]
  ].freeze
end


def validation_error(code, field, message)
  {
    "code" => code,
    "field" => field,
    "message" => message
  }
end


def valid_timestamp?(value)
  pattern = /\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,3})?(?:Z|[+-][0-9]{2}:[0-9]{2})\z/

  return false unless pattern.match?(value)

  year = value[0, 4].to_i
  month = value[5, 2].to_i
  day = value[8, 2].to_i

  return false unless year.between?(1, 9999)
  return false unless Date.valid_date?(year, month, day)
  return false unless value[11, 2].to_i.between?(0, 23)
  return false unless value[14, 2].to_i.between?(0, 59)
  return false unless value[17, 2].to_i.between?(0, 59)

  unless value.end_with?("Z")
    hours = value[-5, 2].to_i
    minutes = value[-2, 2].to_i

    return false unless hours.between?(0, 14)
    return false unless minutes.between?(0, 59)
    return false if hours == 14 && minutes != 0
  end

  true
end


def filter(event)
  source = event.get("source")
  errors = []
  usable = {}

  unless source.is_a?(Hash)
    event.set("errors", [
      validation_error("ROW_STRUCTURE", nil, "Objet source attendu.")
    ])
    event.set("[@metadata][validation_ok]", false)
    return [event]
  end

  (source.keys - @fields).each do |field|
    errors << validation_error(
      "UNKNOWN_FIELD", field, "Champ absent du contrat SCRUM-10."
    )
  end

  @fields.first(5).each do |field|
    unless source.key?(field)
      errors << validation_error(
        "REQUIRED_FIELD", field, "Champ requis absent."
      )
    end
  end

  @fields.each do |field|
    next unless source.key?(field)

    value = source[field]

    if @numeric_fields.include?(field)
      if value.is_a?(Integer)
        usable[field] = true
      else
        errors << validation_error(
          "INVALID_TYPE", field, "Un entier est attendu."
        )
      end
      next
    end

    unless value.is_a?(String)
      errors << validation_error(
        "INVALID_TYPE", field, "Une chaîne de caractères est attendue."
      )
      next
    end

    if /\A[[:space:]]*\z/.match?(value)
      errors << validation_error(
        "EMPTY_FIELD", field, "Le champ présent ne peut pas être vide."
      )
      next
    end

    if /[\x00-\x1f]/.match?(value)
      errors << validation_error(
        "INVALID_VALUE", field, "Caractère de contrôle interdit."
      )
      next
    end

    limit = case field
    when "message", "error_message"
      4096
    when "endpoint"
      2048
    when "service"
      64
    else
      256
    end

    if value.length > limit
      errors << validation_error(
        "INVALID_VALUE", field, "Maximum autorisé : #{limit} caractères."
      )
      next
    end

    usable[field] = true
  end

  if usable["timestamp"] && !valid_timestamp?(source["timestamp"])
    errors << validation_error(
      "INVALID_TIMESTAMP", "timestamp", "Date ou fuseau non conforme."
    )
  end

  if usable["level"] && !@levels.include?(source["level"])
    errors << validation_error(
      "INVALID_LEVEL", "level", "Niveau de log non autorisé."
    )
  end

  if usable["service"] &&
      !/\A[a-z][a-z0-9-]{0,63}\z/.match?(source["service"])
    errors << validation_error(
      "INVALID_VALUE", "service", "Nom de service non conforme."
    )
  end

  if usable["http_method"] &&
      !/\A[A-Za-z]{1,20}\z/.match?(source["http_method"])
    errors << validation_error(
      "INVALID_VALUE", "http_method", "Méthode HTTP non conforme."
    )
  end

  if usable["endpoint"]
    endpoint = source["endpoint"]

    unless endpoint.start_with?("/") && !/[?# ]/.match?(endpoint)
      errors << validation_error(
        "INVALID_VALUE", "endpoint", "Chemin attendu sans espace, ? ou #."
      )
    end
  end

  if usable["status_code"] && !source["status_code"].between?(100, 599)
    errors << validation_error(
      "INVALID_VALUE", "status_code", "Statut attendu entre 100 et 599."
    )
  end

  ["response_time_ms", "sql_duration_ms"].each do |field|
    if usable[field] && !source[field].between?(0, 9_223_372_036_854)
      errors << validation_error(
        "INVALID_DURATION", field, "Durée hors limites autorisées."
      )
    end
  end

  if usable["event_type"]
    family = source["event_type"]

    if !@family_required.key?(family)
      errors << validation_error(
        "INVALID_FAMILY", "event_type", "Famille inconnue."
      )
    else
      @family_required[family].each do |field|
        unless source.key?(field)
          errors << validation_error(
            "REQUIRED_FIELD", field, "Champ requis pour cette famille."
          )
        end
      end

      @family_forbidden[family].each do |field|
        if source.key?(field)
          errors << validation_error(
            "FIELD_NOT_ALLOWED", field, "Champ interdit pour cette famille."
          )
        end
      end

      if family == "business" && usable["action"] && usable["feature"]
        pair = [source["action"], source["feature"]]

        unless @business_pairs.include?(pair)
          errors << validation_error(
            "INVALID_VALUE", "feature",
            "Couple action/fonctionnalité interdit."
          )
        end
      end
    end
  end

  event.set("errors", errors)
  event.set("[@metadata][validation_ok]", errors.empty?)

  [event]
end


# Cas de référence pour les quatre familles.
http = {
  "timestamp" => "2026-11-04T10:00:00.000Z",
  "level" => "INFO",
  "service" => "task-service",
  "message" => "Test de validation",
  "event_type" => "http",
  "endpoint" => "/api/tasks",
  "http_method" => "GET",
  "status_code" => 200,
  "response_time_ms" => 125
}

base = http.reject do |key, _|
  ["endpoint", "http_method", "status_code", "response_time_ms"].include?(key)
end

cases = [
  ["HTTP valide", http, nil],
  [
    "application valide",
    base.merge("event_type" => "application"),
    nil
  ],
  [
    "SQL valide",
    base.merge(
      "event_type" => "sql",
      "db_query" => "list_tasks",
      "sql_duration_ms" => 1200
    ),
    nil
  ],
  [
    "métier valide",
    base.merge(
      "event_type" => "business",
      "action" => "task-created",
      "feature" => "tasks"
    ),
    nil
  ],
  [
    "service absent",
    http.reject { |key, _| key == "service" },
    "REQUIRED_FIELD"
  ],
  [
    "date incorrecte",
    http.merge("timestamp" => "date-invalide"),
    "INVALID_TIMESTAMP"
  ],
  ["niveau interdit", http.merge("level" => "FATAL"), "INVALID_LEVEL"],
  ["statut incorrect", http.merge("status_code" => 700), "INVALID_VALUE"],
  [
    "durée négative",
    http.merge("response_time_ms" => -1),
    "INVALID_DURATION"
  ],
  [
    "champ incompatible",
    http.merge("sql_duration_ms" => 10),
    "FIELD_NOT_ALLOWED"
  ],
  [
    "booléen au lieu d’un entier",
    http.merge("status_code" => true),
    "INVALID_TYPE"
  ],
  [
    "date impossible",
    http.merge("timestamp" => "2026-02-30T10:00:00Z"),
    "INVALID_TIMESTAMP"
  ]
]

cases.each do |title, source, expected_code|
  test title do
    parameters do
      {}
    end

    in_event do
      { "source" => source }
    end

    expect("décision conforme au contrat") do |events|
      result = events.first
      errors = result.get("errors")

      if expected_code.nil?
        result.get("[@metadata][validation_ok]") == true && errors.empty?
      else
        result.get("[@metadata][validation_ok]") == false &&
          errors.any? { |error| error["code"] == expected_code }
      end
    end
  end
end