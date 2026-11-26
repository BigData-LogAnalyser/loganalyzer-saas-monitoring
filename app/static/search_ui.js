"use strict";

(() => {
  const form = document.getElementById("search-form");

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-search-sort]");
    if (!button) return;

    const sort = form.elements.namedItem("sort");
    const order = form.elements.namedItem("order");
    const field = button.dataset.searchSort;

    order.value = sort.value === field
      ? (order.value === "asc" ? "desc" : "asc")
      : (field === "date" ? "desc" : "asc");

    sort.value = field;
    form.requestSubmit();
  });

  document.addEventListener("search:loaded", (event) => {
    const filters = event.detail.filters;

    for (const header of document.querySelectorAll("[data-sort-column]")) {
      const selected = header.dataset.sortColumn === filters.sort;

      header.setAttribute(
        "aria-sort",
        selected
          ? (filters.order === "asc" ? "ascending" : "descending")
          : "none"
      );
      header.querySelector("span").textContent =
        selected ? (filters.order === "asc" ? " ↑" : " ↓") : " ↕";
    }

    const parameters = new URLSearchParams();
    for (const [name, value] of Object.entries(filters)) {
      if (name !== "page" && value !== null && value !== "") {
        parameters.set(name, String(value));
      }
    }

    window.history.replaceState(
      null, "",
      window.location.pathname + (parameters.size ? `?${parameters}` : "")
    );
  });
})();

/* Ouverture des détails par la ligne sur tablette et mobile. */
(() => {
  const body = document.getElementById("search-body");
  const compact = window.matchMedia("(max-width: 1100px)");

  const hint = document.createElement("p");
  hint.className = "responsive-row-hint hint";
  hint.textContent =
    "Touchez une ligne pour consulter son détail. " +
    "Au clavier, utilisez Entrée ou Espace.";

  body.closest(".table-container").before(hint);

  function updateRows() {
    hint.hidden = !compact.matches;

    for (const row of body.querySelectorAll("tr")) {
      const button = row.querySelector("button[data-log-id]");
      if (!button) continue;

      row.classList.toggle("row-opens-detail", compact.matches);

      if (compact.matches) {
        row.tabIndex = 0;
        row.setAttribute("aria-haspopup", "dialog");
      } else {
        row.removeAttribute("tabindex");
        row.removeAttribute("aria-haspopup");
      }
    }
  }

  body.addEventListener("click", (event) => {
    if (!compact.matches) return;

    // Préserve les éventuels liens, boutons et la sélection de texte.
    if (event.target.closest("button, a, input, select, textarea")) return;
    if (window.getSelection()?.toString().trim()) return;

    const row = event.target.closest("tr.row-opens-detail");
    row?.querySelector("button[data-log-id]")?.click();
  });

  body.addEventListener("keydown", (event) => {
    if (!compact.matches) return;
    const row = event.target.closest("tr.row-opens-detail");

    if (!row || event.target !== row) return;

    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      row.querySelector("button[data-log-id]")?.click();
    }
  });

  new MutationObserver(updateRows).observe(body, { childList: true });
  compact.addEventListener("change", updateRows);
  updateRows();
})();
