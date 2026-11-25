"use strict";

(() => {
  const form = document.getElementById("files-form");
  const body = document.getElementById("files-body");
  const message = document.getElementById("files-message");
  const count = document.getElementById("files-count");
  const pageLabel = document.getElementById("files-page");
  const previous = document.getElementById("files-previous");
  const next = document.getElementById("files-next");

  const statuses = {
    EN_ATTENTE: "En attente",
    EN_COURS: "En cours",
    TERMINE: "Terminé",
    PARTIEL: "Partiel",
    ECHEC: "Échec",
  };

  let filters = new URLSearchParams();
  let currentPage = 1;
  let controller = null;

  function readFilters() {
    const parameters = new URLSearchParams();

    for (const [name, raw] of new FormData(form)) {
      let value = String(raw).trim();
      if (!value) continue;

      if (name === "start" || name === "end") {
        if (value.length === 16) value += ":00";
        value += "Z";
      }

      parameters.set(name, value);
    }

    return parameters;
  }

  function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value === null || value === undefined
      ? "—"
      : String(value);
    row.appendChild(cell);
    return cell;
  }

  function renderItem(item) {
    const row = document.createElement("tr");

    appendCell(row, item.original_filename).className = "filename";
    appendCell(row, item.confirmed_at);
    appendCell(
      row,
      item.size_bytes === null || item.size_bytes === undefined
        ? null
        : `${Number(item.size_bytes).toLocaleString("fr-FR")} octets`
    );

    const statusCell = appendCell(
      row, statuses[item.status] || item.status
    );
    statusCell.title = item.status || "";

    appendCell(row, item.expected_count);
    appendCell(row, item.indexed_count);
    appendCell(row, item.rejected_count);

    const action = document.createElement("td");

    if (item.upload_id) {
      const link = document.createElement("a");
      const parameters = new URLSearchParams({
        upload_id: item.upload_id,
      });
      link.href = `/?${parameters.toString()}#tracking-title`;
      link.textContent = "Consulter le suivi";
      action.appendChild(link);
    } else {
      action.textContent = "—";
    }

    row.appendChild(action);
    body.appendChild(row);
  }

  async function loadPage(page) {
    if (controller) controller.abort();

    const activeController = new AbortController();
    controller = activeController;

    const parameters = new URLSearchParams(filters);
    parameters.set("page", String(page));

    body.replaceChildren();
    count.textContent = "";
    pageLabel.textContent = "";
    previous.disabled = true;
    next.disabled = true;
    message.dataset.error = "false";
    message.textContent = "Chargement des fichiers…";

    try {
      const response = await fetch(
        `/api/v1/files?${parameters.toString()}`,
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
          data.error?.message || "Impossible de consulter les fichiers."
        );
      }

      currentPage = data.page;

      for (const item of data.items) renderItem(item);

      count.textContent =
        `${data.total} fichier(s) correspondant(s) — ` +
        `${data.items.length} affiché(s) sur cette page.`;

      if (data.total === 0) {
        message.textContent = "Aucun fichier ne correspond aux critères.";
        pageLabel.textContent = "Aucune page";
      } else {
        message.textContent = data.items.length
          ? "Liste chargée."
          : "Cette page ne contient aucun fichier. Revenez à la page précédente.";

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
    }
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    filters = readFilters();
    loadPage(1);
  });

  form.addEventListener("reset", () => {
    setTimeout(() => {
      filters = readFilters();
      loadPage(1);
    }, 0);
  });

  previous.addEventListener("click", () => loadPage(currentPage - 1));
  next.addEventListener("click", () => loadPage(currentPage + 1));

  filters = readFilters();
  loadPage(1);
})();
