(() => {
  const byId = (id) => document.getElementById(id);
  const form = byId("tracking-form");
  const input = byId("tracking-id");
  const panel = byId("tracking-panel");
  const message = byId("tracking-message");
  const progress = byId("tracking-progress");
  const list = byId("tracking-rejections");
  const more = byId("tracking-more");

  const finalStates = new Set(["TERMINE", "PARTIEL", "ECHEC"]);
  const storageKey = "loganalyzer-last-import";
  let active = null;

  async function getJson(path, session) {
    const response = await fetch(path, {
      cache: "no-store",
      signal: session.controller.signal,
    });

    const result = await response.json();

    if (!response.ok) {
      const error = new Error(
        result.error?.message || "Lecture du suivi impossible."
      );
      error.status = response.status;
      throw error;
    }

    return result;
  }

  function render(record) {
    byId("tracking-filename").textContent = record.original_filename;
    byId("tracking-status").textContent = record.status;
    byId("tracking-expected").textContent =
      record.expected_count ?? "Inconnu";
    byId("tracking-indexed").textContent = record.indexed_count ?? 0;
    byId("tracking-rejected").textContent = record.rejected_count ?? 0;

    if (record.progress_percent == null) {
      progress.removeAttribute("value");
      byId("tracking-percent").textContent =
        "Progression en attente de calcul.";
    } else {
      progress.value = record.progress_percent;
      byId("tracking-percent").textContent =
        `${record.progress_percent} % des événements résolus.`;
    }

    const descriptions = {
      EN_ATTENTE: "En attente de prise en charge par le tracker.",

      EN_COURS: record.reading_complete
        ? "Lecture terminée ; vérification des résultats en cours."
        : "Lecture et traitement du fichier en cours.",

      TERMINE: "Tous les événements sont indexés et disponibles.",

      PARTIEL:
        "Traitement terminé avec des événements rejetés. " +
        "Les événements indexés sont disponibles.",

      ECHEC:
        "L’import a échoué. Consultez le motif et les compteurs ci-dessus.",
    };

    byId("tracking-explanation").textContent =
      descriptions[record.status] || record.status;

    const error = byId("tracking-error");
    error.hidden = !record.error;
    error.textContent = record.error
      ? `${record.error.code} : ${record.error.message}`
      : "";
  }

  function appendRejection(row) {
    const item = document.createElement("li");
    const title = document.createElement("strong");

    const kind = row.failure_kind === "technical"
      ? "erreur technique"
      : "rejet de données";

    title.textContent = `Ligne ${row.source_line} — ${kind}`;

    const errors = document.createElement("ul");

    for (const error of row.errors) {
      const diagnostic = document.createElement("li");
      const field = error.field ? `${error.field} — ` : "";

      diagnostic.textContent =
        `${field}${error.code} : ${error.message}`;

      errors.appendChild(diagnostic);
    }

    const details = document.createElement("details");
    const summary = document.createElement("summary");
    const raw = document.createElement("pre");

    summary.textContent = "Afficher la ligne originale";
    raw.textContent = row.raw;

    details.append(summary, raw);
    item.append(title, errors, details);
    list.appendChild(item);
  }

  async function loadRejections(session, reset) {
    session.rejectionBusy = true;
    more.disabled = true;

    try {
      const after = reset ? 0 : session.after;

      const result = await getJson(
        `/api/imports/${session.id}/rejections` +
        `?limit=20&after_line=${after}`,
        session
      );

      if (active !== session) return;

      if (reset) list.replaceChildren();

      for (const row of result.items) {
        appendRejection(row);
      }

      session.after = result.next_after_line;
      more.hidden = !result.has_more;

      byId("tracking-no-rejections").hidden =
        list.children.length > 0;

    } finally {
      session.rejectionBusy = false;

      if (active === session) {
        more.disabled = false;
      }
    }
  }

  function schedule(session) {
    if (active === session) {
      session.timer = setTimeout(() => poll(session), 2000);
    }
  }

  async function poll(session) {
    try {
      const result = await getJson(
        `/api/imports/${session.id}`,
        session
      );

      if (active !== session) return;

      const record = result.import_record;
      render(record);
      message.textContent = "";

      const terminal = finalStates.has(record.status);

      if (!session.rejectionBusy && (
        record.rejected_count !== session.lastCount ||
        (terminal && !session.finalLoaded)
      )) {
        await loadRejections(session, true);

        if (active !== session) return;

        session.lastCount = record.rejected_count;
        session.finalLoaded = terminal;
      }

      if (!terminal || !session.finalLoaded) {
        schedule(session);
      }

    } catch (error) {
      if (active !== session || error.name === "AbortError") {
        return;
      }

      message.textContent = error.status === 404
        ? error.message
        : `Suivi indisponible : ${error.message} ` +
          "Nouvelle tentative automatique.";

      if (error.status !== 404) {
        schedule(session);
      }
    }
  }

  function startTracking(value) {
    const id = String(value || "").trim().toLowerCase();

    if (!/^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/.test(id)) {
      message.textContent =
        "Saisissez un identifiant d’import valide.";
      return;
    }

    if (active) {
      clearTimeout(active.timer);
      active.controller.abort();
    }

    const session = {
      id,
      controller: new AbortController(),
      timer: null,
      after: 0,
      rejectionBusy: false,
      lastCount: -1,
      finalLoaded: false,
    };

    active = session;
    input.value = id;
    panel.hidden = false;
    list.replaceChildren();
    more.hidden = true;
    more.disabled = false;

    byId("tracking-no-rejections").hidden = false;
    byId("tracking-filename").textContent = "Chargement…";
    byId("tracking-status").textContent = "Lecture du suivi…";

    for (const name of ["expected", "indexed", "rejected"]) {
      byId(`tracking-${name}`).textContent = "—";
    }

    byId("tracking-percent").textContent = "";
    byId("tracking-explanation").textContent = "";
    byId("tracking-error").hidden = true;
    progress.removeAttribute("value");
    message.textContent = "Chargement du suivi…";

    try {
      localStorage.setItem(storageKey, id);
    } catch {}

    poll(session);
  }

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    startTracking(input.value);
  });

  more.addEventListener("click", async () => {
    const session = active;

    if (
      !session ||
      session.rejectionBusy ||
      session.after == null
    ) return;

    try {
      await loadRejections(session, false);

    } catch (error) {
      if (
        active === session &&
        error.name !== "AbortError"
      ) {
        message.textContent =
          `Lecture des diagnostics impossible : ${error.message}`;
      }
    }
  });

  window.addEventListener("import-confirmed", (event) => {
    startTracking(event.detail.uploadId);
  });

  // Un import sélectionné dans la liste a priorité sur le dernier import.
  const parameters = new URLSearchParams(window.location.search);

  if (parameters.has("upload_id")) {
    startTracking(parameters.get("upload_id"));
  } else {
    try {
      const saved = localStorage.getItem(storageKey);

      if (saved) {
        startTracking(saved);
      }
    } catch {}
  }
})();