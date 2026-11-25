"use strict";

(() => {
  const dialog = document.getElementById("log-detail-dialog");
  const message = document.getElementById("log-detail-message");
  const content = document.getElementById("log-detail-content");
  const close = document.getElementById("log-detail-close");
  const body = document.getElementById("search-body");

  let controller = null;

  close.addEventListener("click", () => dialog.close());

  dialog.addEventListener("close", () => {
    if (controller) controller.abort();
  });

  body.addEventListener("click", async (event) => {
    const button = event.target.closest("button[data-log-id]");
    if (!button) return;

    if (controller) controller.abort();

    const activeController = new AbortController();
    controller = activeController;

    message.textContent = "Chargement du document…";
    content.textContent = "";
    dialog.showModal();

    const parameters = new URLSearchParams({
      index: button.dataset.logIndex,
    });

    try {
      const response = await fetch(
        `/api/v1/logs/${encodeURIComponent(button.dataset.logId)}?${parameters}`,
        {
          signal: activeController.signal,
          headers: {Accept: "application/json"},
          cache: "no-store",
        }
      );

      const data = await response.json();

      if (controller !== activeController || !dialog.open) return;

      if (!response.ok) {
        throw new Error(
          data.error?.message || `Erreur HTTP ${response.status}.`
        );
      }

      message.textContent = `Identifiant : ${data.id} — Index : ${data.index}`;
      content.textContent = JSON.stringify(data.document, null, 2);

    } catch (error) {
      if (error.name === "AbortError") return;
      if (controller !== activeController || !dialog.open) return;

      message.textContent = error instanceof TypeError
        ? "Impossible de joindre le serveur."
        : error.message;
    }
  });
})();
