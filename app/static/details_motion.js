"use strict";

(() => {
  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  );

  for (const details of document.querySelectorAll(".history-scope > details")) {
    const summary = details.querySelector(":scope > summary");
    const content = document.createElement("div");
    content.className = "smooth-details-content";

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
