"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const layout = byId("files-layout");
  const detail = byId("file-detail");
  const body = byId("files-body");
  const form = byId("files-form");
  const detailButton = byId("selected-file-detail");
  const logsButton = byId("selected-file-logs");
  const selectionMessage = byId("files-selection-message");

  let selectedRow = null;

  let restoreDetailFocus = true;

  function closeDetail(restoreFocus = true) {
    restoreDetailFocus = restoreFocus;
    window.dispatchEvent(new Event("tracking-stop"));
    if (detail.open) detail.close();
  }

  detail.addEventListener("close", () => {
    window.dispatchEvent(new Event("tracking-stop"));
    if (restoreDetailFocus && !detailButton.disabled) {
      detailButton.focus({ preventScroll: true });
    }
    restoreDetailFocus = true;
  });

  function clearSelection() {
    closeDetail(false);

    for (const row of body.querySelectorAll(".is-selected")) {
      row.classList.remove("is-selected");
    }

    for (const radio of body.querySelectorAll(
      'input[name="selected-file"]'
    )) {
      radio.checked = false;
    }

    selectedRow = null;
    detailButton.disabled = true;
    logsButton.disabled = true;
    selectionMessage.textContent =
      "Sélectionnez une ligne pour activer les actions.";
  }

  function selectRow(row) {
    if (!row?.dataset.uploadId || selectedRow === row) return;

    closeDetail(false);
    selectedRow?.classList.remove("is-selected");

    selectedRow = row;
    row.classList.add("is-selected");
    row.querySelector('input[name="selected-file"]').checked = true;

    detailButton.disabled = false;
    logsButton.disabled = false;
    selectionMessage.textContent =
      `Fichier sélectionné : ${row.dataset.filename || row.dataset.uploadId}`;
  }

  body.addEventListener("click", (event) => {
    if (event.target.closest("button, a, input, select, textarea")) return;
    if (window.getSelection()?.toString()) return;

    const row = event.target.closest("tr[data-upload-id]");
    if (!row) return;

    selectRow(row);
    row.querySelector('input[name="selected-file"]').focus();
  });

  body.addEventListener("change", (event) => {
    if (!event.target.matches('input[name="selected-file"]')) return;
    selectRow(event.target.closest("tr"));
  });

  detailButton.addEventListener("click", () => {
    if (!selectedRow?.isConnected) return;

    restoreDetailFocus = true;
    if (!detail.open) detail.showModal();

    const size = selectedRow.dataset.sizeBytes;
    byId("file-detail-meta").textContent =
      `Confirmation UTC : ${selectedRow.dataset.confirmedAt || "—"} · ` +
      (size === "" ? "Taille inconnue" :
        `${new Intl.NumberFormat("fr-FR", {
          maximumFractionDigits: 2,
        }).format(Number(size) / 1048576)} Mio`);

    byId("tracking-id").value = selectedRow.dataset.uploadId;
    byId("tracking-form").requestSubmit();
    byId("tracking-title").focus({ preventScroll: true });
  });

  logsButton.addEventListener("click", () => {
    if (!selectedRow?.isConnected) return;

    window.location.assign("/logs?" + new URLSearchParams({
      upload_id: selectedRow.dataset.uploadId,
    }));
  });

  byId("file-detail-close").addEventListener(
    "click", () => closeDetail()
  );

  document.addEventListener("files:loading", clearSelection);

  document.addEventListener("click", (event) => {
    const button = event.target.closest("button[data-sort]");
    if (!button || !form.contains(button)) {
      if (!button || !layout.contains(button)) return;
    }

    const sort = form.elements.namedItem("sort");
    const order = form.elements.namedItem("order");
    const field = button.dataset.sort;

    order.value = sort.value === field
      ? (order.value === "asc" ? "desc" : "asc")
      : (field === "name" || field === "status" ? "asc" : "desc");

    sort.value = field;
    form.requestSubmit();
  });

  document.addEventListener("files:loaded", (event) => {
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
  });

  const state = byId("tracking-status");
  new MutationObserver(() => {
    state.dataset.state = state.textContent;
  }).observe(state, {
    childList: true, characterData: true, subtree: true,
  });
})();
