(function () {
  "use strict";

  // Pause the animated background blobs when the tab is not visible,
  // so they don't burn CPU/GPU in a background tab.
  function initAurora() {
    var aurora = document.querySelector(".aurora");
    if (!aurora) return;
    document.addEventListener("visibilitychange", function () {
      aurora.classList.toggle("is-paused", document.hidden);
    });
  }

  // Auto-dismiss flash messages after a delay, plus a manual close button.
  function initFlashes() {
    var flashes = document.querySelectorAll(".flash");
    flashes.forEach(function (flash) {
      var closeBtn = document.createElement("button");
      closeBtn.type = "button";
      closeBtn.className = "flash-close";
      closeBtn.setAttribute("aria-label", "Закрыть");
      closeBtn.textContent = "×";
      closeBtn.addEventListener("click", function () { dismiss(flash); });
      flash.appendChild(closeBtn);

      setTimeout(function () { dismiss(flash); }, 6000);
    });

    function dismiss(flash) {
      if (!flash.isConnected) return;
      flash.style.opacity = "0";
      flash.style.transform = "translateY(-6px)";
      setTimeout(function () { flash.remove(); }, 300);
    }
  }

  // Client-side search filter: an <input data-search-target="SELECTOR">
  // hides any [data-searchable] item whose text doesn't match the query.
  function initSearch() {
    document.querySelectorAll("[data-search-target]").forEach(function (input) {
      var container = document.querySelector(input.getAttribute("data-search-target"));
      if (!container) return;
      var items = container.querySelectorAll("[data-searchable]");

      input.addEventListener("input", function () {
        var query = input.value.trim().toLowerCase();
        var visibleCount = 0;
        items.forEach(function (item) {
          var text = item.getAttribute("data-searchable") || item.textContent;
          var match = text.toLowerCase().indexOf(query) !== -1;
          item.classList.toggle("is-hidden", !match);
          if (match) visibleCount += 1;
        });

        var emptyState = container.querySelector(".search-empty-state");
        if (emptyState) emptyState.classList.toggle("is-hidden", visibleCount !== 0);
      });
    });
  }

  // Mobile off-canvas sidebar: hamburger button slides the nav in from the left.
  function initMobileNav() {
    var sidebar = document.getElementById("sidebar");
    var toggle = document.getElementById("menuToggle");
    var closeBtn = document.getElementById("sidebarClose");
    var overlay = document.getElementById("sidebarOverlay");
    if (!sidebar || !toggle || !overlay) return;

    function open() {
      sidebar.classList.add("is-open");
      overlay.classList.add("is-open");
      toggle.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
    }

    function close() {
      sidebar.classList.remove("is-open");
      overlay.classList.remove("is-open");
      toggle.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
    }

    toggle.addEventListener("click", function () {
      if (sidebar.classList.contains("is-open")) close(); else open();
    });
    if (closeBtn) closeBtn.addEventListener("click", close);
    overlay.addEventListener("click", close);
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") close();
    });
    sidebar.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", close);
    });
    window.addEventListener("resize", function () {
      if (window.innerWidth > 860) close();
    });
  }

  // Simple modal dialogs: [data-modal-open="id"] opens #id (+ its overlay),
  // [data-modal-close] / overlay click / Escape closes whatever is open.
  function initModals() {
    var triggers = document.querySelectorAll("[data-modal-open]");
    if (!triggers.length) return;

    function closeAll() {
      document.querySelectorAll(".modal.is-open").forEach(function (m) {
        m.classList.remove("is-open");
      });
      document.querySelectorAll(".modal-overlay.is-open").forEach(function (o) {
        o.classList.remove("is-open");
      });
      document.body.classList.remove("modal-open");
    }

    triggers.forEach(function (trigger) {
      trigger.addEventListener("click", function () {
        var id = trigger.getAttribute("data-modal-open");
        var modal = document.getElementById(id);
        if (!modal) return;
        var overlay = document.querySelector('[data-modal-overlay="' + id + '"]');
        modal.classList.add("is-open");
        if (overlay) overlay.classList.add("is-open");
        document.body.classList.add("modal-open");
        var firstField = modal.querySelector("input, textarea, select");
        if (firstField) firstField.focus();
      });
    });

    document.querySelectorAll("[data-modal-close]").forEach(function (btn) {
      btn.addEventListener("click", closeAll);
    });
    document.querySelectorAll("[data-modal-overlay]").forEach(function (overlay) {
      overlay.addEventListener("click", closeAll);
    });
    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") closeAll();
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    initAurora();
    initFlashes();
    initSearch();
    initMobileNav();
    initModals();
  });
})();
