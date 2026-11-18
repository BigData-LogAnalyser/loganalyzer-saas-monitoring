require "csv"
require "json"

class LogAnalyzerDuplicateKey < StandardError
end

def check_unique_json_keys(raw)
  factory = Java::ComFasterxmlJacksonCore::JsonFactory.new
  parser = factory.createParser(raw.to_java(:string))
  objects = []

  begin
    while (token = parser.nextToken)
      case token.to_s
      when "START_OBJECT"
        objects << {}

      when "END_OBJECT"
        objects.pop

      when "FIELD_NAME"
        key = parser.getCurrentName.to_s

        if objects.last.key?(key)
          raise LogAnalyzerDuplicateKey, "Clé JSON dupliquée : #{key}"
        end

        objects.last[key] = true
      end
    end
  ensure
    parser.close
  end
end


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
end


def parsing_error(code, field, message)
  {
    "code" => code,
    "field" => field,
    "message" => message
  }
end


def reject_parsing(event, errors)
  event.remove("source")
  event.set("errors", errors)
  event.set("[@metadata][parse_ok]", false)
  [event]
end


def filter(event)
  raw = event.get("raw")
  format = event.get("format")

  unless raw.is_a?(String)
    return reject_parsing(event, [
      parsing_error(
        "ROW_STRUCTURE", nil, "Une ligne de texte est attendue."
      )
    ])
  end

  # La ligne doit être transmise sans sa fin de ligne.
  if raw.include?("\n") || raw.include?("\r")
    return reject_parsing(event, [
      parsing_error(
        "ROW_STRUCTURE", nil,
        "Un événement doit tenir sur une seule ligne physique."
      )
    ])
  end

  source = {}
  errors = []

  case format
    when "json", "jsonl"
        begin
        check_unique_json_keys(raw)

        parsed = JSON.parse(
            raw,
            allow_nan: false,
            create_additions: false
        )

        unless parsed.is_a?(Hash)
            return reject_parsing(event, [
            parsing_error(
                "ROW_STRUCTURE", nil, "Un objet JSON est attendu."
            )
            ])
        end

        source = parsed.to_h

        rescue LogAnalyzerDuplicateKey => error
        return reject_parsing(event, [
            parsing_error("JSON_DUPLICATE_KEY", nil, error.message)
        ])

        rescue JSON::ParserError,
            Java::ComFasterxmlJacksonCore::JsonProcessingException
        return reject_parsing(event, [
            parsing_error("JSON_SYNTAX", nil, "Ligne JSON mal formée.")
        ])
        end

    when "csv", "txt"
      begin
        cells = if format == "csv"
          CSV.parse_line(
            raw,
            col_sep: ";",
            liberal_parsing: false
          )
        else
          # -1 conserve les champs vides situés à la fin.
          raw.split("\t", -1)
        end

      rescue CSV::MalformedCSVError
        return reject_parsing(event, [
          parsing_error("ROW_STRUCTURE", nil, "Ligne CSV mal formée.")
        ])
      end

      unless cells && cells.length == @fields.length
        return reject_parsing(event, [
          parsing_error(
            "ROW_STRUCTURE", nil, "Exactement 18 colonnes sont attendues."
          )
        ])
      end

    @fields.zip(cells).each do |field, value|
      # Une cellule vide représente un champ absent.
      next if value.nil? || value == ""

      if @numeric_fields.include?(field)
        code = field.end_with?("_ms") ?
          "INVALID_DURATION" : "INVALID_VALUE"

        unless /\A(?:0|[1-9][0-9]*)\z/.match?(value)
          errors << parsing_error(
            code, field, "Entier décimal sans signe attendu."
          )
          next
        end

        if value.length > 13
          errors << parsing_error(
            code, field, "Nombre hors limites autorisées."
          )
          next
        end

        value = value.to_i
      end

      source[field] = value
    end

  else
    return reject_parsing(event, [
      parsing_error("FILE_FORMAT", nil, "Format non autorisé.")
    ])
  end

  unless errors.empty?
    return reject_parsing(event, errors)
  end

  event.set("source", source)
  event.set("errors", [])
  event.set("[@metadata][parse_ok]", true)

  [event]
end


# Vérifier que les trois formats donnent les mêmes champs.
reference = {
  "timestamp" => "2026-11-04T10:00:00.000Z",
  "level" => "INFO",
  "service" => "task-service",
  "message" => 'Message; avec "guillemets"',
  "event_type" => "application"
}

cells = reference.values + Array.new(13, "")

examples = {
  "jsonl" => JSON.generate(reference),
  "csv" => CSV.generate_line(
    cells, col_sep: ";", row_sep: "\n"
  ).chomp("\n"),
  "txt" => cells.join("\t")
}

examples.each do |format, raw|
  test "Lecture correcte du format #{format}" do
    parameters do
      {}
    end

    in_event do
      { "format" => format, "raw" => raw }
    end

    expect("champs identiques à la référence") do |events|
      result = events.first

      result.get("[@metadata][parse_ok]") == true &&
        result.get("source") == reference &&
        result.get("errors").empty?
    end
  end
end


invalid_examples = [
  [
    "clé JSON dupliquée",
    "jsonl",
    '{"level":"INFO","level":"ERROR"}',
    "JSON_DUPLICATE_KEY"
  ],
  [
    "colonnes TXT manquantes",
    "txt",
    "champ1\tchamp2",
    "ROW_STRUCTURE"
  ],
  [
    "guillemet CSV non fermé",
    "csv",
    '"guillemet non fermé',
    "ROW_STRUCTURE"
  ]
]

invalid_examples.each do |title, format, raw, expected_code|
  test "Rejet : #{title}" do
    parameters do
      {}
    end

    in_event do
      { "format" => format, "raw" => raw }
    end

    expect("erreur identifiée avec son motif") do |events|
      result = events.first

      result.get("[@metadata][parse_ok]") == false &&
        result.get("errors").any? do |error|
          error["code"] == expected_code
        end
    end
  end
end