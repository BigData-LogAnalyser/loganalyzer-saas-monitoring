"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const message = byId("recent-imports-message");
  const list = byId("recent-imports-list");
  const retry = byId("recent-imports-retry");
  let active = null;

  window.addEventListener("import-file-selected", (event) => {
    const file = event.detail;
    byId("selected-file").hidden = false;
    byId("selected-file-name").textContent = file.name;
    byId("selected-file-size").textContent =
      `${new Intl.NumberFormat("fr-FR", {
        maximumFractionDigits: 2,
      }).format(file.size / 1048576)} Mio`;
  });

  async function loadRecent() {
    if (active) active.abort();
    const controller = new AbortController();
    active = controller;

    retry.hidden = true;
    message.textContent = "Chargement des imports…";

    try {
      const response = await fetch("/api/v1/files?page=1", {
        headers: { Accept: "application/json" },
        cache: "no-store",
        signal: controller.signal,
      });
      const data = await response.json();

      if (!response.ok) {
        throw new Error(
          data.error?.message || "Lecture des imports impossible."
        );
      }

      if (active !== controller) return;
      list.replaceChildren();

      for (const row of data.items.slice(0, 5)) {
        const item = document.createElement("li");
        const link = document.createElement("a");
        const details = document.createElement("span");
        const id = row.upload_id || row.id;

        link.textContent = row.original_filename;
        link.href = typeof id === "string" &&
          /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i.test(id)
          ? `/?upload_id=${encodeURIComponent(id)}#tracking-title`
          : "/files";

        details.className = "hint";
        details.textContent =
          `${row.status} · ${row.indexed_count ?? "—"} logs indexés`;

        item.append(link, details);
        list.append(item);
      }

      message.textContent = data.items.length
        ? "Derniers imports confirmés."
        : "Aucun import confirmé pour le moment.";
    } catch (error) {
      if (error.name === "AbortError" || active !== controller) return;
      list.replaceChildren();
      message.textContent = "Les imports récents sont indisponibles.";
      retry.hidden = false;
    }
  }

  retry.addEventListener("click", loadRecent);
  window.addEventListener("import-confirmed", loadRecent);

  const state = byId("tracking-status");
  const stateColors = {
    TERMINE: ["#e8f5ed", "#19704c"],
    PARTIEL: ["#fff5db", "#855c00"],
    ECHEC: ["#fff0f2", "#ac233a"],
    EN_COURS: ["#eaf1ff", "#0955c9"],
    EN_ATTENTE: ["#f0edff", "#5b4795"],
  };

  new MutationObserver(() => {
    const colors = stateColors[state.textContent] || ["#edf2fa", "#314d73"];
    state.style.backgroundColor = colors[0];
    state.style.color = colors[1];
  }).observe(state, { childList: true, characterData: true, subtree: true });

  loadRecent();
})();
