"use strict";

(() => {
  const reducedMotion = window.matchMedia(
    "(prefers-reduced-motion: reduce)"
  );

  for (const dialog of document.querySelectorAll("dialog")) {
    const nativeShowModal = dialog.showModal.bind(dialog);
    const nativeClose = dialog.close.bind(dialog);

    let animation = null;
    let closing = false;

    function cancelAnimation() {
      if (!animation) return;
      animation.onfinish = null;
      animation.cancel();
      animation = null;
    }

    dialog.showModal = function () {
      if (dialog.open) return;

      cancelAnimation();
      closing = false;
      nativeShowModal();

      if (reducedMotion.matches) return;

      const active = dialog.animate(
        [
          { opacity: 0, transform: "translateY(10px)" },
          { opacity: 1, transform: "translateY(0)" },
        ],
        {
          duration: 180,
          easing: "cubic-bezier(.2, .7, .3, 1)",
          fill: "both",
        }
      );

      animation = active;
      active.onfinish = () => {
        if (animation !== active) return;
        active.cancel();
        animation = null;
      };
    };

    dialog.close = function (returnValue) {
      if (!dialog.open || closing) return;

      const style = getComputedStyle(dialog);
      const opacity = style.opacity;
      const transform = style.transform;

      cancelAnimation();

      const finish = () => {
        if (returnValue === undefined) nativeClose();
        else nativeClose(returnValue);
        closing = false;
      };

      if (reducedMotion.matches) {
        finish();
        return;
      }

      closing = true;

      const active = dialog.animate(
        [
          { opacity, transform },
          { opacity: 0, transform: "translateY(10px)" },
        ],
        {
          duration: 180,
          easing: "ease-in",
          fill: "both",
        }
      );

      animation = active;
      active.onfinish = () => {
        if (animation !== active) return;
        finish();
        active.cancel();
        animation = null;
      };
    };

    dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      dialog.close();
    });

    dialog.addEventListener("close", () => {
      cancelAnimation();
      closing = false;
    });
  }
})();
