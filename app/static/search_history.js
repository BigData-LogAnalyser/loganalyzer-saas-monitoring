"use strict";

(() => {
  const body = document.getElementById("history-body");
  const message = document.getElementById("history-message");
  const count = document.getElementById("history-count");
  const pageLabel = document.getElementById("history-page");
  const previous = document.getElementById("history-previous");
  const next = document.getElementById("history-next");
  const refresh = document.getElementById("history-refresh");
  const results = document.getElementById("history-results");

  let currentPage = 1;
  let controller = null;

  const labels = {
    general: "Recherche générale",
    q: "Texte dans les messages",
    level: "Niveau",
    service: "Service",
    start: "Début de période — UTC",
    end: "Fin de période — UTC",
    sort: "Tri",
    order: "Ordre",
  };

  const sorts = {
    date: "Date de l’événement",
    level: "Niveau",
    service: "Service",
  };

  function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value ?? "—";
    row.appendChild(cell);
    return cell;
  }

  function renderItem(item) {
    const row = document.createElement("tr");
    appendCell(row, item.executed_at).className = "date";

    const cell = document.createElement("td");
    const list = document.createElement("ul");
    list.className = "criteria";

    for (const [field, label] of Object.entries(labels)) {
      let value = item.criteria[field];
      if (value === null || value === undefined || value === "") continue;

      if (field === "sort") value = sorts[value] || value;
      if (field === "order") {
        value = { asc: "Croissant", desc: "Décroissant" }[value] || value;
      }

      const line = document.createElement("li");
      line.textContent = `${label} : ${value}`;
      list.appendChild(line);
    }

    cell.appendChild(list);
    row.appendChild(cell);
    appendCell(row, item.result_count);
    body.appendChild(row);
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
    message.dataset.error = "false";
    message.textContent = "Chargement de l’historique…";
    results.setAttribute("aria-busy", "true");

    try {
      const response = await fetch(
        `/api/v1/search-history?page=${page}`,
        {
          signal: activeController.signal,
          headers: { Accept: "application/json" },
          cache: "no-store",
        }
      );

      const data = await response.json();
      if (controller !== activeController) return;

      if (!response.ok) {
        throw new Error(
          data.error?.message || "Impossible de consulter l’historique."
        );
      }

      currentPage = data.page;
      for (const item of data.items) renderItem(item);

      count.textContent =
        `${data.total} recherche(s) enregistrée(s) — ` +
        `${data.items.length} affichée(s) sur cette page.`;

      if (data.total === 0) {
        message.textContent = "Aucune recherche enregistrée pour le moment.";
        pageLabel.textContent = "Aucune page";
      } else {
        message.textContent = data.items.length
          ? "Historique chargé."
          : "Cette page ne contient aucune recherche. Revenez à la précédente.";
        pageLabel.textContent = `Page ${data.page} / ${data.total_pages}`;
      }

      previous.disabled = !data.has_previous;
      next.disabled = !data.has_next;
    } catch (error) {
      if (
        error.name === "AbortError" ||
        controller !== activeController
      ) return;

      message.dataset.error = "true";
      message.textContent = error instanceof TypeError
        ? "Connexion impossible. Réessayez dans quelques instants."
        : error.message;
    } finally {
      if (controller === activeController) {
        results.setAttribute("aria-busy", "false");
      }
    }
  }

  previous.addEventListener("click", () => loadPage(currentPage - 1));
  next.addEventListener("click", () => loadPage(currentPage + 1));
  refresh.addEventListener("click", () => loadPage(1));

  loadPage(1);
})();
