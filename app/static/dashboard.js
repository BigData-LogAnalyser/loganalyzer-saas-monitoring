(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId("dashboard-form");
  const results = byId("dashboard-results");
  const message = byId("dashboard-message");
  let active = null;

  const numbers = new Intl.NumberFormat("fr-FR", {
    maximumFractionDigits: 3,
  });

  const dates = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Africa/Tunis",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hourCycle: "h23",
  });

  function number(value) {
    return value == null ? "N/D" : numbers.format(value);
  }

  function date(value) {
    return value ? dates.format(new Date(value)) : "N/D";
  }

  function table(id, rows, emptyMessage, columns) {
    const body = byId(id);
    body.replaceChildren();

    if (rows.length === 0) {
      const row = document.createElement("tr");
      const cell = document.createElement("td");
      cell.colSpan = columns;
      cell.textContent = emptyMessage;
      row.appendChild(cell);
      body.appendChild(row);
      return;
    }

    for (const values of rows) {
      const row = document.createElement("tr");

      for (const value of values) {
        const cell = document.createElement("td");
        cell.textContent = value ?? "N/D";
        row.appendChild(cell);
      }

      body.appendChild(row);
    }
  }

  function render(data) {
    const cards = data.cards;
    const saas = data.saas;

    byId("card-total").textContent = number(cards.total_logs);
    byId("card-today").textContent = number(cards.today_logs);
    byId("card-errors").textContent = number(cards.error_logs);
    byId("card-files").textContent = number(cards.imported_files);

    byId("dashboard-period").textContent =
      `Période d’analyse : du ${date(data.filters.start)} inclus ` +
      `au ${date(data.filters.end)} exclu — Africa/Tunis. ` +
      `Service : ${data.filters.service || "tous"}. ` +
      `Organisation : ${data.filters.organization || "toutes"}.`;

    byId("dashboard-generated").textContent =
      `Calcul lancé le ${date(data.generated_at)} — Africa/Tunis.`;

    byId("dashboard-today").textContent =
      `Journée du ${data.today.date} dans Africa/Tunis ; ` +
      "filtres service et organisation.";

    table(
      "dashboard-latency",
      saas.http_latency_by_endpoint.map((row) => [
        row.endpoint,
        number(row.request_count),
        number(row.average_ms),
      ]),
      "N/D : aucune requête HTTP admissible sur cette période.",
      3
    );

    table(
      "dashboard-http",
      saas.http_5xx_by_service.map((row) => [
        row.service,
        number(row.response_count),
        number(row.error_count),
        number(row.error_rate_percent),
      ]),
      "N/D : aucune réponse HTTP admissible sur cette période.",
      4
    );

    const sql = saas.slow_sql;
    byId("dashboard-sql-summary").textContent =
      `${number(sql.execution_count)} exécution(s) strictement au-dessus ` +
      `de ${number(sql.threshold_ms)} ms. ` +
      "Les dix exécutions les plus lentes sont affichées au maximum.";

    table(
      "dashboard-sql",
      sql.slowest.map((row) => [
        date(row.timestamp),
        row.service,
        row.query_name,
        number(row.duration_ms),
      ]),
      "Aucune exécution SQL au-dessus du seuil sur cette période.",
      4
    );

    byId("dashboard-users").textContent = number(saas.active_users);

    table(
      "dashboard-features",
      saas.feature_usage.map((row) => [
        row.feature,
        number(row.usage_count),
      ]),
      "Aucune utilisation métier admissible sur cette période.",
      2
    );
  }

  async function load() {
    if (active) active.abort();

    const controller = new AbortController();
    active = controller;
    const parameters = new URLSearchParams();

    for (const field of ["start", "end", "service", "organization"]) {
      const value = byId(`dashboard-${field}`).value.trim();

      if (value) {
        parameters.set(
          field,
          field === "start" || field === "end" ? `${value.length === 16 ? value + ":00" : value}Z` : value
        );
      }
    }

    results.hidden = true;
    message.dataset.error = "false";
    message.textContent = "Calcul des indicateurs…";
    form.setAttribute("aria-busy", "true");

    try {
      const response = await fetch(`/api/v1/stats?${parameters}`, {
        cache: "no-store",
        headers: { Accept: "application/json" },
        signal: controller.signal,
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error?.message || "Lecture des indicateurs impossible."
        );
      }

      if (active !== controller) return;

      render(data);
      results.hidden = false;
      message.textContent = "Indicateurs chargés.";
    } catch (error) {
      if (active !== controller || error.name === "AbortError") return;

      message.dataset.error = "true";
      message.textContent = error instanceof TypeError
        ? "Connexion impossible. Réessayez avec Afficher / Actualiser."
        : error.message;
    } finally {
      if (active === controller) {
        form.setAttribute("aria-busy", "false");
      }
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    load();
  });

  byId("dashboard-reset").addEventListener("click", () => {
    form.reset();
    load();
  });

  load();
})();
