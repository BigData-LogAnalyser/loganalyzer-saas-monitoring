"use strict";

(() => {
  const root = document.getElementById("dashboard-overview");
  const tooltip = document.createElement("div");

  tooltip.id = "dashboard-chart-tooltip";
  tooltip.className = "chart-tooltip";
  tooltip.setAttribute("role", "tooltip");
  tooltip.hidden = true;
  document.body.append(tooltip);

  let active = null;

  function position(x, y) {
    const gap = 14;
    const padding = 10;
    const bounds = tooltip.getBoundingClientRect();

    let left = x + gap;
    let top = y + gap;

    if (left + bounds.width > window.innerWidth - padding) {
      left = x - bounds.width - gap;
    }
    if (top + bounds.height > window.innerHeight - padding) {
      top = y - bounds.height - gap;
    }

    tooltip.style.left = `${Math.max(
      padding,
      Math.min(left, window.innerWidth - bounds.width - padding)
    )}px`;

    tooltip.style.top = `${Math.max(
      padding,
      Math.min(top, window.innerHeight - bounds.height - padding)
    )}px`;
  }

  function hide() {
    if (active) {
      active.removeAttribute("aria-describedby");
      active.removeAttribute("data-tip-active");
    }
    active = null;
    tooltip.hidden = true;
  }

  function show(target, x, y) {
    if (active !== target) hide();

    active = target;
    tooltip.textContent = target.getAttribute("data-chart-tip");
    target.setAttribute("aria-describedby", tooltip.id);
    target.setAttribute("data-tip-active", "true");
    tooltip.hidden = false;
    position(x, y);
  }

  function targetFrom(event) {
    const target = event.target.closest("[data-chart-tip]");
    return target && root.contains(target) ? target : null;
  }

  root.addEventListener("pointerover", (event) => {
    if (event.pointerType === "touch") return;
    const target = targetFrom(event);
    if (target) show(target, event.clientX, event.clientY);
  });

  root.addEventListener("pointermove", (event) => {
    if (active && !tooltip.hidden && event.pointerType !== "touch") {
      position(event.clientX, event.clientY);
    }
  });

  root.addEventListener("pointerout", (event) => {
    if (
      active &&
      active.contains(event.target) &&
      !active.contains(event.relatedTarget)
    ) {
      hide();
    }
  });

  root.addEventListener("focusin", (event) => {
    const target = targetFrom(event);
    if (!target) return;
    const bounds = target.getBoundingClientRect();
    show(target, bounds.left + bounds.width / 2, bounds.bottom);
  });

  root.addEventListener("focusout", hide);

  // Sur écran tactile, toucher un élément affiche sa valeur.
  root.addEventListener("pointerup", (event) => {
    if (event.pointerType !== "touch") return;
    const target = targetFrom(event);
    if (target) show(target, event.clientX, event.clientY);
  });

  document.addEventListener("pointerdown", (event) => {
    if (!root.contains(event.target)) hide();
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") hide();
  });

  document.addEventListener("dashboard:loaded", hide);
  window.addEventListener("scroll", hide, true);
  window.addEventListener("resize", hide);
})();
