"use strict";
(() => {
  const byId = (id) => document.getElementById(id);
  const frame = byId("kibana-frame");
  const embedded = byId("kibana-embedded");
  const fallback = byId("kibana-fallback");
  const state = byId("kibana-state");
  const message = byId("kibana-status");
  const retry = byId("kibana-retry");
  let busy = false;
  let displayProblem = false;

  function showFallback(text) {
    embedded.hidden = true;
    fallback.hidden = false;
    byId("kibana-fallback-message").textContent = text;
    frame.removeAttribute("src");
  }

  async function check(force = false) {
    if (busy || (document.hidden && !force)) return;
    busy = true;
    retry.disabled = true;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 7000);

    if (force) {
      displayProblem = false;
      frame.removeAttribute("src");
    }

    try {
      const response = await fetch("/api/v1/kibana/status", {
        signal: controller.signal, cache: "no-store",
      });
      if (!response.ok) throw new Error("status");
      const data = await response.json();
      const labels = {
        available: "Kibana : disponible",
        degraded: "Kibana : dégradé",
        unavailable: "Kibana : indisponible",
        unconfigured: "Kibana : non configuré",
        disabled: "Affichage intégré désactivé",
      };
      state.dataset.state = data.state;
      state.textContent = labels[data.state] || "Kibana : état inconnu";
      message.textContent = data.message;

      if (data.can_embed && frame.dataset.src && !displayProblem) {
        fallback.hidden = true;
        embedded.hidden = false;
        if (!frame.hasAttribute("src")) frame.src = frame.dataset.src;
      } else if (!displayProblem) {
        showFallback(data.message);
      }
    } catch (error) {
      state.dataset.state = "unavailable";
      state.textContent = "Kibana : vérification impossible";
      message.textContent = "La disponibilité ne peut pas être vérifiée.";
      showFallback("Réessayez ou ouvrez le dashboard directement dans Kibana.");
    } finally {
      clearTimeout(timeout);
      retry.disabled = false;
      busy = false;
    }
  }

  retry.addEventListener("click", () => check(true));
  byId("kibana-display-error").addEventListener("click", () => {
    displayProblem = true;
    showFallback(
      "Le dashboard ne s’affiche pas correctement ici. " +
      "Ouvrez-le dans Kibana ou utilisez « Vérifier / Recharger »."
    );
    message.textContent = "Problème d’affichage signalé.";
  });
  frame.addEventListener("error", () => {
    displayProblem = true;
    showFallback("Le chargement a échoué. Ouvrez le dashboard dans Kibana.");
  });
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) check();
  });
  check();
  setInterval(() => check(), 30000);
})();
