"use strict";

(() => {
  const labels = {
    q: "Messages",
    start: "Début UTC",
    end: "Fin UTC",
    sort: "Tri",
    order: "Ordre",
    upload_id: "Import",
  };

  for (const form of document.querySelectorAll("[data-compact-filters]")) {
    const details = form.querySelector(".advanced-filters");
    const fields = details.querySelector(".advanced-fields");
    const count = details.querySelector(".advanced-count");
    const list = form.querySelector(".filter-active-list");
    const defaults = { sort: "date", order: "desc" };

    function update() {
      list.replaceChildren();
      let total = 0;

      for (const input of fields.querySelectorAll("input, select")) {
        const name = input.name || input.id.replace("dashboard-", "");
        const value = input.value.trim();

        if (!value || value === defaults[name]) continue;

        let display = value;

        if (input.tagName === "SELECT") {
          display = input.selectedOptions[0]?.textContent || value;
        } else if (input.type === "datetime-local") {
          display = value.replace("T", " ");
        }

        const item = document.createElement("li");
        const text = `${labels[name] || name} : ${display}`;
        item.textContent = text.length > 90
          ? `${text.slice(0, 87)}…` : text;
        item.title = text;
        list.append(item);
        total += 1;
      }

      list.hidden = total === 0;
      count.hidden = total === 0;
      count.textContent = String(total);
    }

    form.addEventListener("input", update);
    form.addEventListener("change", update);
    form.addEventListener("submit", update);

    // Ouvre les champs repliés si la validation du navigateur les réclame.
    form.addEventListener("invalid", (event) => {
      if (fields.contains(event.target)) details.open = true;
    }, true);

    form.addEventListener("reset", () => {
      setTimeout(() => {
        details.open = false;
        update();
      }, 0);
    });

    const preset = form.querySelector("#dashboard-preset");

    if (preset) {
      preset.addEventListener("change", () => {
        details.open = preset.value === "custom";
        if (details.open) {
          document.getElementById("dashboard-start").focus();
        }
        update();
      });
    }

    document.addEventListener("search:loaded", update);
    document.addEventListener("files:loaded", update);
    document.addEventListener("dashboard:loaded", update);

    update();
  }
})();

/* Ouverture et fermeture progressives des filtres avancés. */
(() => {
  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  );

  for (const details of document.querySelectorAll(".advanced-filters")) {
    const summary = details.querySelector(":scope > summary");
    const content = document.createElement("div");
    content.className = "advanced-content";

    // Regroupe le contenu sans modifier les champs du formulaire.
    for (const node of [...details.childNodes]) {
      if (node !== summary) content.append(node);
    }
    details.append(content);

    let animation = null;
    let closing = false;

    function stop() {
      if (animation) {
        animation.cancel();
        animation = null;
      }
    }

    function animate(from, to, onFinish) {
      stop();

      if (reducedMotion.matches) {
        if (onFinish) onFinish();
        return;
      }

      animation = content.animate(
        [
          { height: `${from}px`, opacity: from === 0 ? 0 : 1 },
          { height: `${to}px`, opacity: to === 0 ? 0 : 1 },
        ],
        {
          duration: 220,
          easing: "cubic-bezier(.2, .7, .3, 1)",
          fill: "both",
        }
      );

      animation.onfinish = () => {
        stop();
        if (onFinish) onFinish();
      };
    }

    summary.addEventListener("click", (event) => {
      event.preventDefault();

      if (closing) {
        const height = content.getBoundingClientRect().height;
        closing = false;
        animate(height, content.scrollHeight);
        return;
      }

      if (details.open) {
        const height = content.getBoundingClientRect().height;
        closing = true;
        animate(height, 0, () => {
          closing = false;
          details.open = false;
        });
      } else {
        details.open = true;
      }
    });

    // Gère aussi l’ouverture déclenchée par le sélecteur de période.
    new MutationObserver(() => {
      if (details.open) {
        closing = false;
        stop();
        animate(0, content.scrollHeight);
      } else {
        closing = false;
        stop();
      }
    }).observe(details, {
      attributes: true,
      attributeFilter: ["open"],
    });
  }
})();
