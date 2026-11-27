"use strict";

(() => {
  const byId = (id) => document.getElementById(id);
  const panel = byId("services-health");
  const list = byId("services-list");
  const button = byId("services-refresh");
  const message = byId("services-message");
  const checked = byId("services-checked");

  const names = [
    "Webapp Flask", "Elasticsearch", "MongoDB", "Redis", "Logstash", "Kibana",
  ];
  const labels = {
    available: "Disponible",
    degraded: "Dégradé",
    unavailable: "Indisponible",
    unknown: "Non vérifié",
    checking: "Vérification…",
  };
  const dates = new Intl.DateTimeFormat("fr-FR", {
    timeZone: "Africa/Tunis",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
    hourCycle: "h23",
  });

  let controller = null;
  let timer = null;
  let stopped = false;

  function render(services) {
    list.replaceChildren();

    for (const service of services) {
      const item = document.createElement("li");
      const name = document.createElement("span");
      const badge = document.createElement("span");

      const state = Object.hasOwn(labels, service.status)
        ? service.status : "unknown";

      item.className = "service-pill";
      item.dataset.health = state;
      item.title = service.message || labels[state];
      item.tabIndex = 0;

      name.className = "service-name";
      name.textContent = service.name;
      badge.className = "service-health-label";
      badge.textContent = labels[state];

      const description = document.createElement("div");
      description.className = "service-description";
      const descriptionText = document.createElement("span");
      descriptionText.textContent = service.message || labels[state];
      description.append(descriptionText);

      item.append(name, badge, description);
      list.append(item);
    }
  }

  async function refresh() {
    clearTimeout(timer);
    if (controller) controller.abort();

    const active = new AbortController();
    controller = active;
    const timeout = setTimeout(() => active.abort(), 8000);

    button.disabled = true;
    panel.setAttribute("aria-busy", "true");
    message.textContent = "Vérification des services…";

    render(names.map((name) => ({
      name,
      status: "checking",
      message: "Contrôle en cours.",
    })));

    try {
      const response = await fetch("/api/v1/services/status", {
        signal: active.signal,
        headers: { Accept: "application/json" },
        cache: "no-store",
      });

      const data = await response.json();

      if (!response.ok || !Array.isArray(data.services)) {
        throw new Error("Réponse de contrôle invalide.");
      }
      if (controller !== active || stopped) return;

      render(data.services);
      checked.textContent =
        `Dernier contrôle : ${dates.format(new Date(data.checked_at))} ` +
        "— Africa/Tunis";

      const unavailable = data.services.filter(
        (service) => service.status === "unavailable"
      ).length;

      message.textContent = unavailable
        ? `${unavailable} service(s) indisponible(s). Nouvelle vérification automatique.`
        : "Vérification automatique toutes les 30 secondes.";

    } catch (error) {
      if (controller !== active || stopped) return;

      render(names.map((name) => ({
        name,
        status: "unknown",
        message: "Le contrôle de disponibilité n’a pas pu aboutir.",
      })));

      checked.textContent = "Disponibilité actuelle non vérifiée.";
      message.textContent = error.name === "AbortError"
        ? "Le contrôle a dépassé le délai prévu. Utilisez Vérifier pour réessayer."
        : "Contrôle indisponible. Vérifiez la connexion ou réessayez.";
    } finally {
      clearTimeout(timeout);

      if (controller === active && !stopped) {
        button.disabled = false;
        panel.setAttribute("aria-busy", "false");

        if (!document.hidden) {
          timer = setTimeout(refresh, 30000);
        }
      }
    }
  }

  button.addEventListener("click", refresh);

  document.addEventListener("visibilitychange", () => {
    clearTimeout(timer);
    if (!document.hidden && !stopped) refresh();
  });

  window.addEventListener("pagehide", () => {
    stopped = true;
    clearTimeout(timer);
    if (controller) controller.abort();
  });

  window.addEventListener("pageshow", (event) => {
    if (event.persisted) {
      stopped = false;
      refresh();
    }
  });

  refresh();
})();
