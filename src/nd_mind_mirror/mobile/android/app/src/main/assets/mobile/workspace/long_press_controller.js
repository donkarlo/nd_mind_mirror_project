"use strict";

/**
 * Converts a stationary touch or pointer hold into a deterministic long-press action.
 */
class LongPressController {
  constructor(delayMs = 520, movementTolerancePx = 16) {
    this.delayMs = delayMs;
    this.movementTolerancePx = movementTolerancePx;
  }

  bind(element, handler) {
    let timer = null;
    let startX = 0;
    let startY = 0;
    let suppressNextClick = false;
    let lastTriggeredAt = 0;

    const clearTimer = () => {
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
    };

    element.addEventListener("pointerdown", (event) => {
      if (event.button !== 0) return;
      clearTimer();
      startX = event.clientX;
      startY = event.clientY;
      timer = window.setTimeout(() => {
        timer = null;
        suppressNextClick = true;
        lastTriggeredAt = Date.now();
        navigator.vibrate?.(18);
        handler();
      }, this.delayMs);
    });

    element.addEventListener("pointermove", (event) => {
      if (timer === null) return;
      if (
        Math.abs(event.clientX - startX) > this.movementTolerancePx ||
        Math.abs(event.clientY - startY) > this.movementTolerancePx
      ) {
        clearTimer();
      }
    });

    ["pointerup", "pointercancel", "pointerleave"].forEach((name) => {
      element.addEventListener(name, clearTimer);
    });

    element.addEventListener(
      "click",
      (event) => {
        if (!suppressNextClick) return;
        suppressNextClick = false;
        event.preventDefault();
        event.stopImmediatePropagation();
      },
      true,
    );

    element.addEventListener("contextmenu", (event) => {
      event.preventDefault();
      clearTimer();
      if (Date.now() - lastTriggeredAt < 700) return;
      suppressNextClick = true;
      lastTriggeredAt = Date.now();
      handler();
    });
  }
}
