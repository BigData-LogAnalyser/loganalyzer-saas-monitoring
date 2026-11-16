require "time"

def filter(event)
  source = event.get("source")
  context = event.get("context")

  unless source.is_a?(Hash) && context.is_a?(Hash)
    raise ArgumentError, "Événement source et contexte requis"
  end

  datasets = {
    "http" => "saas.http",
    "application" => "saas.application",
    "sql" => "saas.database",
    "business" => "saas.business"
  }

  document = {
    "@timestamp" => LogStash::Timestamp.new(
      Time.iso8601(source.fetch("timestamp")).utc
    ),
    "ecs" => {
      "version" => "8.17.0"
    },
    "log" => {
      "level" => source.fetch("level"),
      "file" => {
        "path" => context.fetch("source_path")
      }
    },
    "service" => {
      "name" => source.fetch("service")
    },
    "message" => source.fetch("message"),
    "event" => {
      "dataset" => datasets.fetch(source.fetch("event_type")),
      "kind" => "event",
      "id" => "#{context.fetch('upload_id')}:#{context.fetch('source_line')}"
    },
    "loganalyzer" => {
      "upload_id" => context.fetch("upload_id"),
      "source_line" => context.fetch("source_line"),
      "original_filename" => context.fetch("original_filename"),
      "schema_version" => "1.0"
    }
  }

  if source.key?("user_id")
    document["user"] = { "id" => source["user_id"] }
  end

  if source.key?("organization_id")
    document["organization"] = { "id" => source["organization_id"] }
  end

  error_fields = {}

  if source.key?("error_code")
    error_fields["code"] = source["error_code"]
  end

  if source.key?("error_message")
    error_fields["message"] = source["error_message"]
  end

  document["error"] = error_fields unless error_fields.empty?

  case source.fetch("event_type")
  when "http"
    request_fields = {
      "method" => source.fetch("http_method")
    }

    if source.key?("request_id")
      request_fields["id"] = source["request_id"]
    end

    document["url"] = {
      "path" => source.fetch("endpoint")
    }

    document["http"] = {
      "request" => request_fields,
      "response" => {
        "status_code" => source.fetch("status_code")
      }
    }

    document["event"]["duration"] =
      source.fetch("response_time_ms") * 1_000_000

  when "sql"
    document["saas"] = {
      "database" => {
        "query_name" => source.fetch("db_query")
      }
    }

    document["event"]["duration"] =
      source.fetch("sql_duration_ms") * 1_000_000

  when "business"
    document["event"]["action"] = source.fetch("action")
    document["saas"] = {
      "feature" => source.fetch("feature")
    }

  when "application"
    if source.key?("action")
      document["event"]["action"] = source["action"]
    end
  end

  normalized = LogStash::Event.new(document)

  # Ce champ technique n’appartient pas au document cible.
  normalized.remove("@version")

  [normalized]
end


test "HTTP : champs ECS et conversion des millisecondes" do
  in_event do
    {
      "source" => {
        "timestamp" => "2026-11-04T10:00:00.000Z",
        "level" => "INFO",
        "service" => "task-service",
        "message" => "Liste des tâches consultée",
        "event_type" => "http",
        "endpoint" => "/api/tasks",
        "http_method" => "GET",
        "status_code" => 200,
        "response_time_ms" => 125
      },
      "context" => {
        "upload_id" => "scrum16-test",
        "source_line" => 2,
        "source_path" => "/uploads/confirmed/scrum16-test/source.csv",
        "original_filename" => "logs.csv"
      }
    }
  end

  expect("document HTTP conforme") do |events|
    result = events.first

    events.length == 1 &&
      result.get("[event][dataset]") == "saas.http" &&
      result.get("[event][duration]") == 125_000_000 &&
      result.get("[http][response][status_code]") == 200 &&
      result.get("[service][name]") == "task-service" &&
      result.get("[event][id]") == "scrum16-test:2" &&
      result.get("@version").nil?
  end
end


test "Métier : date convertie en UTC" do
  in_event do
    {
      "source" => {
        "timestamp" => "2026-11-04T11:00:03.000+01:00",
        "level" => "INFO",
        "service" => "task-service",
        "message" => "Tâche créée",
        "event_type" => "business",
        "action" => "task-created",
        "feature" => "tasks"
      },
      "context" => {
        "upload_id" => "scrum16-test",
        "source_line" => 4,
        "source_path" => "/uploads/confirmed/scrum16-test/source.jsonl",
        "original_filename" => "logs.jsonl"
      }
    }
  end

  expect("date UTC et champs métier conformes") do |events|
    result = events.first

    result.get("@timestamp").to_s == "2026-11-04T10:00:03.000Z" &&
      result.get("[event][dataset]") == "saas.business" &&
      result.get("[event][action]") == "task-created" &&
      result.get("[saas][feature]") == "tasks" &&
      result.get("[event][duration]").nil?
  end
end