/* ==========================================================================
   Amazon Student - client-side accessibility controls
   --------------------------------------------------------------------------
   We store the user's accessibility preferences in localStorage so they
   persist across pages and visits WITHOUT needing a server round-trip.
   On every page load we read those preferences and apply them as data-*
   attributes on the <html> element, which the CSS reacts to.

   Why localStorage and not the server? These are presentation preferences,
   not security-sensitive data. Keeping them client-side means they apply
   instantly (no flash of unstyled content) and work even before login.
   ========================================================================== */

(function () {
  "use strict";

  var root = document.documentElement;

  // Map of preference key -> the data attribute it controls and its "on" value.
  var PREFS = {
    theme:    { attr: "data-theme",    on: "dark" },
    contrast: { attr: "data-contrast", on: "high" },
    text:     { attr: "data-text",     on: "large" }
  };

  // Apply a single preference to <html> based on a boolean.
  function apply(pref, enabled) {
    var cfg = PREFS[pref];
    if (!cfg) return;
    if (enabled) {
      root.setAttribute(cfg.attr, cfg.on);
    } else {
      root.removeAttribute(cfg.attr);
    }
  }

  // Read all stored preferences and apply them. Runs on every page load.
  function applyStoredPrefs() {
    Object.keys(PREFS).forEach(function (pref) {
      var stored = localStorage.getItem("a11y:" + pref) === "true";
      apply(pref, stored);
    });
  }

  // Persist and apply when a toggle changes.
  function onToggle(pref, enabled) {
    localStorage.setItem("a11y:" + pref, enabled ? "true" : "false");
    apply(pref, enabled);
  }

  // Wire up any toggle inputs present on the page (the Settings page).
  function wireToggles() {
    Object.keys(PREFS).forEach(function (pref) {
      var input = document.getElementById("toggle-" + pref);
      if (!input) return;
      // Reflect current stored state in the checkbox.
      input.checked = localStorage.getItem("a11y:" + pref) === "true";
      input.addEventListener("change", function () {
        onToggle(pref, input.checked);
      });
    });
  }

  // Apply prefs as early as possible to reduce visual flicker.
  applyStoredPrefs();

  // Wire toggles once the DOM is ready.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", wireToggles);
  } else {
    wireToggles();
  }
})();
