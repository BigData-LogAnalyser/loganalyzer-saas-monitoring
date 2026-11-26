"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const dialog = byId("log-detail-dialog");
  const message = byId("log-detail-message");
  const content = byId("log-detail-content");
  const close = byId("log-detail-close");
  const body = byId("search-body");
  const summary = byId("log-detail-summary");
  const copy = byId("log-detail-copy");
  const copyMessage = byId("log-copy-message");

  let controller = null;
  let opener = null;

  function renderSummary(documentData) {
    if (!summary) return;
    summary.replaceChildren();

    const fields = [
      ["Date — UTC", documentData["@timestamp"]],
      ["Niveau", documentData.log?.level],
      ["Service", documentData.service?.name],
      ["Message", documentData.message],
      ["Fichier", documentData.loganalyzer?.original_filename],
      ["Identifiant de l’import", documentData.loganalyzer?.upload_id],
      ["Ligne source", documentData.loganalyzer?.source_line],
    ];

    for (const [label, value] of fields) {
      if (value === undefined || value === null || value === "") continue;
      const term = document.createElement("dt");
      const description = document.createElement("dd");
      term.textContent = label;
      description.textContent = String(value);
      summary.append(term, description);
    }
  }

  close.addEventListener("click", () => dialog.close());

  dialog.addEventListener("close", () => {
    if (controller) controller.abort();
    if (opener?.isConnected) {
      const target = opener.closest("tr.row-opens-detail") || opener;
      target.focus();
    }
  });

  if (copy) {
    copy.addEventListener("click", async () => {
      if (!content.textContent) return;
      const original = content.textContent;
      copy.disabled = true;

      try {
        await navigator.clipboard.writeText(original);
        if (dialog.open && content.textContent === original) {
          copyMessage.textContent = "JSON copié.";
        }
      } catch {
        if (dialog.open && content.textContent === original) {
          copyMessage.textContent =
            "Copie automatique indisponible. Sélectionnez le JSON pour le copier.";
        }
      } finally {
        copy.disabled = !content.textContent;
      }
    });
  }

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-log-id]");
    if (!button) return;

    if (controller) controller.abort();
    const activeController = new AbortController();
    controller = activeController;
    opener = button;

    message.textContent = "Chargement du document…";
    content.textContent = "";
    if (summary) summary.replaceChildren();
    if (copy) copy.disabled = true;
    if (copyMessage) copyMessage.textContent = "";
    if (!dialog.open) dialog.showModal();

    const parameters = new URLSearchParams({
      index: button.dataset.logIndex,
    });

    try {
      const response = await fetch(
        `/api/v1/logs/${encodeURIComponent(button.dataset.logId)}?${parameters}`,
        {
          signal: activeController.signal,
          headers: { Accept: "application/json" },
          cache: "no-store",
        }
      );

      const data = await response.json();
      if (controller !== activeController || !dialog.open) return;

      if (!response.ok) {
        throw new Error(data.error?.message || `Erreur HTTP ${response.status}.`);
      }

      message.textContent = `Identifiant : ${data.id} — Index : ${data.index}`;
      content.textContent = JSON.stringify(data.document, null, 2);
      renderSummary(data.document);
      if (copy) copy.disabled = false;
    } catch (error) {
      if (error.name === "AbortError") return;
      if (controller !== activeController || !dialog.open) return;
      message.textContent = error instanceof TypeError
        ? "Impossible de joindre le serveur."
        : error.message;
    }
  });
})();
