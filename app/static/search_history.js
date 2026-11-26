"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const body = byId("history-body");
  const message = byId("history-message");
  const count = byId("history-count");
  const pageLabel = byId("history-page");
  const previous = byId("history-previous");
  const next = byId("history-next");
  const refresh = byId("history-refresh");
  const results = byId("history-results");
  const sortButton = byId("history-sort");

  const numbers = new Intl.NumberFormat("fr-FR");
  const dates = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "UTC",
    year: "numeric", month: "2-digit", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hourCycle: "h23",
  });

  const filterLabels = {
    level: "Niveau",
    service: "Service",
    upload_id: "Import",
    start: "Début — UTC",
    end: "Fin — UTC",
    sort: "Tri",
    order: "Ordre",
  };

  const sorts = {
    date: "Date de l’événement",
    level: "Niveau",
    service: "Service",
  };

  const replayFields = [
    "general", "q", "level", "service", "upload_id",
    "start", "end", "sort", "order",
  ];

  let currentPage = 1;
  let order = "desc";
  let controller = null;

  function element(tag, text, className) {
    const node = document.createElement(tag);
    if (text != null) node.textContent = text;
    if (className) node.className = className;
    return node;
  }

  function date(value) {
    const parsed = new Date(value);
    return value && !Number.isNaN(parsed.getTime())
      ? dates.format(parsed) : "—";
  }

  function renderItem(item) {
    const criteria = item.criteria || {};
    const row = element("tr");

    const dateCell = element("td", null, "history-date");
    const time = element("time", date(item.executed_at));
    time.dateTime = item.executed_at;
    time.title = item.executed_at;
    dateCell.append(time);
    row.append(dateCell);

    const textCell = element("td", null, "history-text");

    for (const [field, label] of [
      ["general", "Recherche générale"],
      ["q", "Texte dans les messages"],
    ]) {
      if (!criteria[field]) continue;
      const block = element("div", null, "query-block");
      block.append(
        element("span", label, "query-label"),
        element("code", criteria[field])
      );
      textCell.append(block);
    }

    if (!textCell.children.length) {
      textCell.append(element("span", "Aucun texte", "hint"));
    }
    row.append(textCell);

    const filterCell = element("td");
    const list = element("ul", null, "history-criteria");

    for (const [field, label] of Object.entries(filterLabels)) {
      let value = criteria[field];
      if (value === undefined || value === null || value === "") continue;

      if (field === "sort") value = sorts[value] || value;
      if (field === "order") {
        value = { asc: "Croissant", desc: "Décroissant" }[value] || value;
      }
      if (field === "start" || field === "end") value = date(value);

      list.append(element("li", `${label} : ${value}`));
    }

    if (!list.children.length) {
      filterCell.append(element("span", "Aucun filtre", "hint"));
    } else {
      filterCell.append(list);
    }
    row.append(filterCell);

    row.append(element(
      "td",
      item.result_count == null ? "—" : numbers.format(item.result_count),
      "history-result-count"
    ));

    const action = element("td");
    const link = element("a", "Relancer", "button button-primary replay-link");
    const parameters = new URLSearchParams();

    for (const field of replayFields) {
      const value = criteria[field];
      if (value !== null && value !== undefined && value !== "") {
        parameters.set(field, String(value));
      }
    }

    link.href = "/logs" + (parameters.size ? `?${parameters}` : "");
    link.setAttribute(
      "aria-label", `Relancer la recherche du ${date(item.executed_at)} UTC`
    );
    action.append(link);
    row.append(action);
    body.append(row);
  }

  async function loadPage(page) {
    if (controller) controller.abort();
    const activeController = new AbortController();
    controller = activeController;

    body.replaceChildren();
    count.textContent = "";
    pageLabel.textContent = "";
    previous.disabled = true;
    next.disabled = true;
    refresh.disabled = true;
    sortButton.disabled = true;
    byId("history-empty").hidden = true;
    byId("history-table").hidden = false;
    byId("history-pagination").hidden = false;

    message.dataset.error = "false";
    message.textContent = "Chargement de l’historique…";
    results.setAttribute("aria-busy", "true");

    const parameters = new URLSearchParams({ page: String(page), order });

    try {
      const response = await fetch(`/api/v1/search-history?${parameters}`, {
        signal: activeController.signal,
        headers: { Accept: "application/json" },
        cache: "no-store",
      });

      const data = await response.json();
      if (controller !== activeController) return;

      if (!response.ok) {
        throw new Error(
          data.error?.message || "Impossible de consulter l’historique."
        );
      }

      currentPage = data.page;
      order = data.order;
      for (const item of data.items) renderItem(item);

      count.textContent =
        `${numbers.format(data.total)} recherche(s) enregistrée(s) — ` +
        `${data.items.length} affichée(s).`;

      byId("history-date-header").setAttribute(
        "aria-sort", order === "asc" ? "ascending" : "descending"
      );
      byId("history-sort-arrow").textContent =
        order === "asc" ? " ↑" : " ↓";

      if (data.total === 0) {
        message.textContent = "Historique chargé.";
        byId("history-empty").hidden = false;
        byId("history-table").hidden = true;
        byId("history-pagination").hidden = true;
      } else {
        message.textContent = data.items.length
          ? (order === "desc"
            ? "Les recherches les plus récentes sont affichées en premier."
            : "Les recherches les plus anciennes sont affichées en premier.")
          : "Cette page est vide. Revenez à la page précédente.";

        pageLabel.textContent = `Page ${data.page} / ${data.total_pages}`;
      }

      previous.disabled = !data.has_previous;
      next.disabled = !data.has_next;
    } catch (error) {
      if (error.name === "AbortError" || controller !== activeController) return;
      message.dataset.error = "true";
      message.textContent = error instanceof TypeError
        ? "Connexion impossible. Utilisez Actualiser pour réessayer."
        : error.message;
    } finally {
      if (controller === activeController) {
        results.setAttribute("aria-busy", "false");
        refresh.disabled = false;
        sortButton.disabled = false;
      }
    }
  }

  previous.addEventListener("click", () => loadPage(currentPage - 1));
  next.addEventListener("click", () => loadPage(currentPage + 1));
  refresh.addEventListener("click", () => loadPage(1));

  sortButton.addEventListener("click", () => {
    order = order === "desc" ? "asc" : "desc";
    loadPage(1);
  });

  loadPage(1);
})();
