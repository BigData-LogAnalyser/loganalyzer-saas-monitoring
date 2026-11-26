"use strict";

(() => {
  const form = document.getElementById("search-form");
  const body = document.getElementById("search-body");
  const message = document.getElementById("search-message");
  const count = document.getElementById("search-count");
  const results = document.getElementById("search-results");
  const pageInformation = document.getElementById("page-information");
  const previous = document.getElementById("previous-page");
  const next = document.getElementById("next-page");
  const exportButton = document.getElementById("export-csv");
  const exportMessage = document.getElementById("export-message");
  let exportFilters = null;
  let exporting = false;

  let activeFilters = new URLSearchParams();
  let currentPage = 1;
  let controller = null;

  function readFilters() {
    const parameters = new URLSearchParams();

    for (const [name, raw] of new FormData(form)) {
      let value = String(raw).trim();
      if (!value) continue;

      if (name === "start" || name === "end") {
        // Le formulaire demande explicitement une heure UTC.
        if (value.length === 16) value += ":00";
        value += "Z";
      }

      parameters.set(name, value);
    }

    return parameters;
  }

  function setMessage(text, isError = false) {
    message.textContent = text;
    message.dataset.error = String(isError);
  }

  function appendCell(row, value) {
    const cell = document.createElement("td");
    cell.textContent = value ?? "—";
    row.append(cell);
  }

  async function loadPage(page) {
    if (controller) controller.abort();

    const activeController = new AbortController();
    controller = activeController;

    const parameters = new URLSearchParams(activeFilters);
    parameters.set("page", String(page));

    previous.disabled = true;
    next.disabled = true;
    body.replaceChildren();
    count.textContent = "";
    pageInformation.textContent = "";
    results.setAttribute("aria-busy", "true");
    setMessage("Recherche en cours…");
    exportFilters = null;
    exportButton.disabled = true;

    try {
      const response = await fetch(`/api/v1/logs?${parameters}`, {
        signal: activeController.signal,
        headers: {Accept: "application/json"},
        cache: "no-store",
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error?.message || `Erreur HTTP ${response.status}.`
        );
      }

      if (controller !== activeController) return;

      currentPage = data.page;
      exportFilters = new URLSearchParams();
      for (const [key, value] of Object.entries(data.filters)) {
        if (key !== "page" && value !== null && value !== "") {
          exportFilters.set(key, String(value));
        }
      }
      exportButton.disabled = exporting;
      count.textContent =
        `${data.total} résultat(s) — ${data.items.length} affiché(s) sur cette page.`;

      const fragment = document.createDocumentFragment();

      for (const item of data.items) {
        const documentData = item.document;
        const row = document.createElement("tr");

        appendCell(row, documentData["@timestamp"]);
        appendCell(row, documentData.log?.level);
        appendCell(row, documentData.service?.name);
        appendCell(row, documentData.message);

        const actionsCell = document.createElement("td");
        const detailsButton = document.createElement("button");
        detailsButton.type = "button";
        detailsButton.textContent = "Détails";
        detailsButton.dataset.logId = item.id;
        detailsButton.dataset.logIndex = item.index;
        actionsCell.append(detailsButton);
        row.append(actionsCell);


        fragment.append(row);
      }

      body.append(fragment);

      if (data.total === 0) {
        setMessage("Aucun log ne correspond à ces critères.");
        pageInformation.textContent = "Aucune page";
      } else {
        setMessage(
          data.pagination_limited
            ? "Les 10 000 premiers résultats sont consultables. " +
              "Précisez les filtres pour réduire la recherche."
            : data.items.length === 0
              ? "Cette page ne contient plus de résultats. Revenez à la précédente."
              : "Recherche terminée."
        );

        pageInformation.textContent =
          `Page ${data.page} / ${data.accessible_pages}`;
      }

      if (
        data.history?.recorded === false &&
        data.history.reason === "unavailable"
      ) {
        setMessage(
          `${message.textContent} ${data.history.message}`,
          true
        );
      }

      previous.disabled = !data.has_previous;
      next.disabled = !data.has_next;

    } catch (error) {
      if (error.name === "AbortError") return;
      if (controller !== activeController) return;

      setMessage(
        error instanceof TypeError
          ? "Impossible de joindre le serveur. Vérifiez la connexion."
          : error.message,
        true
      );
    } finally {
      if (controller === activeController) {
        results.setAttribute("aria-busy", "false");
      }
    }
  }


  exportButton.addEventListener("click", async () => {
    if (!exportFilters || exporting) return;

    const confirmed = window.confirm(
      "Confirmer l’export CSV\n\n" +
      "Tous les logs correspondant à la recherche affichée seront exportés, " +
      "toutes pages confondues, dans le même ordre.\n\n" +
      "Le fichier contient 28 colonnes séparées par un point-virgule. " +
      "L’encodage UTF-8 avec une marque de reconnaissance facilite " +
      "l’affichage des accents dans Excel.\n\n" +
      "Limites : 10 000 logs et 20 Mio. " +
      "Un dépassement sera refusé sans fichier tronqué.\n\n" +
      "Les résultats sont recherchés à nouveau au moment de l’export.\n\n" +
      "Cliquez sur OK pour télécharger, ou sur Annuler."
    );

    if (!confirmed) return;

    const parameters = new URLSearchParams(exportFilters);
    exporting = true;
    exportButton.disabled = true;
    exportMessage.textContent = "Préparation du CSV…";

    try {
      const response = await fetch(`/api/v1/logs/export?${parameters}`, {
        headers: {Accept: "text/csv, application/json"},
        cache: "no-store",
      });

      if (!response.ok) {
        const data = await response.json();
        throw new Error(
          data.error?.message || `Erreur HTTP ${response.status}.`
        );
      }

      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      const filename = response.headers
        .get("Content-Disposition")?.match(/filename="([^"]+)"/)?.[1];

      link.href = url;
      link.download = filename || "loganalyzer-export.csv";
      document.body.append(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);

      exportMessage.textContent =
        `${response.headers.get("X-Export-Count")} log(s) exporté(s).`;
    } catch (error) {
      exportMessage.textContent = error instanceof TypeError
        ? "Impossible de joindre le serveur pour l’export."
        : error.message;
    } finally {
      exporting = false;
      exportButton.disabled = exportFilters === null;
    }
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    activeFilters = readFilters();
    loadPage(1);
  });

  form.addEventListener("reset", () => {
    // Attend que le navigateur ait réinitialisé les champs.
    setTimeout(() => {
      activeFilters = readFilters();
      loadPage(1);
    }, 0);
  });

  previous.addEventListener("click", () => loadPage(currentPage - 1));
  next.addEventListener("click", () => loadPage(currentPage + 1));

  activeFilters = readFilters();
  loadPage(1);
})();
