/* FundTrail shared UI behaviour (design system v2).
   Loaded by _layout.html on every page except the untouched graph page.
   No frameworks — plain DOM, offline-safe, CSP-compliant (external file). */
(function () {
  'use strict';

  /* ── Dark mode (Feature C16) ─────────────────────────────── */
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    try { localStorage.setItem('ft-theme', theme); } catch (e) { /* private mode */ }
  }
  var themeBtn = document.getElementById('themeToggle');
  if (themeBtn) {
    themeBtn.addEventListener('click', function () {
      var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(cur);
    });
  }

  /* ── Sidebar collapse + mobile hamburger ─────────────────── */
  var collapseBtn = document.getElementById('navCollapse');
  if (collapseBtn) {
    collapseBtn.addEventListener('click', function () {
      var collapsed = document.body.classList.toggle('nav-collapsed');
      collapseBtn.setAttribute('aria-label', collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      collapseBtn.setAttribute('title',      collapsed ? 'Expand sidebar' : 'Collapse sidebar');
      try { localStorage.setItem('ft-nav', collapsed ? '1' : ''); } catch (e) {}
    });
    /* sync label to restored collapsed state on page load */
    if (document.body.classList.contains('nav-collapsed')) {
      collapseBtn.setAttribute('aria-label', 'Expand sidebar');
      collapseBtn.setAttribute('title',      'Expand sidebar');
    }
  }

  /* ── Toasts: auto-dismiss after 4s, manual close ─────────── */
  document.querySelectorAll('.toast').forEach(function (toast) {
    var close = function () {
      toast.style.opacity = '0';
      setTimeout(function () { toast.remove(); }, 250);
    };
    var btn = toast.querySelector('.toast-close');
    if (btn) btn.addEventListener('click', close);
    setTimeout(close, 4000);
  });

  /* ── Sortable tables: click a th.sortable to sort rows ───── */
  document.querySelectorAll('th.sortable').forEach(function (th) {
    th.setAttribute('tabindex', '0');
    th.setAttribute('role', 'button');
    th.setAttribute('aria-label', 'Sort by ' + th.textContent.trim());
    function sortBy() {
      var table = th.closest('table');
      var tbody = table.querySelector('tbody');
      var idx = Array.prototype.indexOf.call(th.parentNode.children, th);
      var asc = !th.classList.contains('sort-asc');
      table.querySelectorAll('th.sortable').forEach(function (h) {
        h.classList.remove('sort-asc', 'sort-desc');
      });
      th.classList.add(asc ? 'sort-asc' : 'sort-desc');
      var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'))
        .filter(function (r) { return !r.querySelector('.empty-state'); });
      rows.sort(function (a, b) {
        var av = (a.children[idx] ? a.children[idx].textContent.trim() : '');
        var bv = (b.children[idx] ? b.children[idx].textContent.trim() : '');
        var an = parseFloat(av.replace(/[₹,%\s,]/g, ''));
        var bn = parseFloat(bv.replace(/[₹,%\s,]/g, ''));
        if (!isNaN(an) && !isNaN(bn)) return asc ? an - bn : bn - an;
        return asc ? av.localeCompare(bv) : bv.localeCompare(av);
      });
      rows.forEach(function (r) { tbody.appendChild(r); });
    }
    th.addEventListener('click', sortBy);
    th.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); sortBy(); }
    });
  });

  /* ── Debounced table filter (Fix E23): input[data-filter-table=id] ── */
  function debounce(fn, ms) {
    var t;
    return function () {
      var args = arguments, self = this;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(self, args); }, ms);
    };
  }
  document.querySelectorAll('input[data-filter-table]').forEach(function (input) {
    var table = document.getElementById(input.getAttribute('data-filter-table'));
    if (!table) return;
    input.addEventListener('input', debounce(function () {
      var q = input.value.trim().toLowerCase();
      table.querySelectorAll('tbody tr').forEach(function (row) {
        if (row.querySelector('.empty-state')) return;
        row.style.display = row.textContent.toLowerCase().indexOf(q) === -1 ? 'none' : '';
      });
    }, 200));
  });

  /* ── Count-up animation for dashboard stats ──────────────── */
  document.querySelectorAll('[data-countup]').forEach(function (el) {
    var target = parseFloat(el.getAttribute('data-countup'));
    if (isNaN(target)) return;
    var decimals = (String(el.getAttribute('data-countup')).split('.')[1] || '').length;
    var prefix = el.getAttribute('data-prefix') || '';
    var start = null, dur = 800;
    function fmt(v) { return prefix + v.toLocaleString('en-IN', { minimumFractionDigits: decimals, maximumFractionDigits: decimals }); }
    function step(ts) {
      if (!start) start = ts;
      var p = Math.min((ts - start) / dur, 1);
      el.textContent = fmt(target * (1 - Math.pow(1 - p, 3)));
      if (p < 1) requestAnimationFrame(step); else el.textContent = fmt(target);
    }
    requestAnimationFrame(step);
  });

  /* ── Time-of-day greeting, refreshed every minute (real time) ── */
  function updateGreeting() {
    var el = document.querySelector('[data-greeting]');
    if (!el) return;
    var h = new Date().getHours();
    var word = h < 5 ? 'Good night' : h < 12 ? 'Good morning' : h < 17 ? 'Good afternoon' : 'Good evening';
    el.textContent = word + ', ' + (el.getAttribute('data-greeting') || 'Officer');
    var dateEl = document.querySelector('[data-today]');
    if (dateEl) {
      dateEl.textContent = new Date().toLocaleDateString('en-IN',
        { weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
    }
  }
  updateGreeting();
  setInterval(updateGreeting, 60 * 1000);

  /* ── Modals: [data-modal-open=id] / .modal-backdrop close ── */
  function openModal(backdrop) {
    backdrop.classList.add('open');
    var f = backdrop.querySelector('input, button, select, textarea, a');
    if (f) f.focus();
  }
  function closeModal(backdrop) { backdrop.classList.remove('open'); }
  document.querySelectorAll('[data-modal-open]').forEach(function (btn) {
    btn.addEventListener('click', function () {
      var m = document.getElementById(btn.getAttribute('data-modal-open'));
      if (m) openModal(m);
    });
  });
  document.querySelectorAll('.modal-backdrop').forEach(function (backdrop) {
    backdrop.addEventListener('click', function (e) { if (e.target === backdrop) closeModal(backdrop); });
    backdrop.querySelectorAll('[data-modal-close]').forEach(function (btn) {
      btn.addEventListener('click', function () { closeModal(backdrop); });
    });
    /* basic focus trap */
    backdrop.addEventListener('keydown', function (e) {
      if (e.key !== 'Tab') return;
      var focusables = backdrop.querySelectorAll('button, a, input, select, textarea, [tabindex]');
      if (!focusables.length) return;
      var first = focusables[0], last = focusables[focusables.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    });
  });
  document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
      document.querySelectorAll('.modal-backdrop.open').forEach(closeModal);
    }
  });

  /* ── Feature B11: idle-session warning + auto-logout.
        Server session lifetime is 30 min; warn at 28, logout at 30. ── */
  var IDLE_WARN_MS = 28 * 60 * 1000;
  var IDLE_LOGOUT_MS = 30 * 60 * 1000;
  var idleModal = document.getElementById('idleModal');
  if (idleModal) {
    var warnTimer, logoutTimer;
    var resetIdle = function () {
      clearTimeout(warnTimer); clearTimeout(logoutTimer);
      closeModal(idleModal);
      warnTimer = setTimeout(function () { openModal(idleModal); }, IDLE_WARN_MS);
      logoutTimer = setTimeout(function () { window.location.href = '/logout'; }, IDLE_LOGOUT_MS);
    };
    ['click', 'keydown', 'mousemove', 'scroll'].forEach(function (evt) {
      document.addEventListener(evt, debounce(resetIdle, 1000), { passive: true });
    });
    var stayBtn = document.getElementById('idleStay');
    if (stayBtn) stayBtn.addEventListener('click', resetIdle);
    resetIdle();
  }

  /* ── Buttons that disable themselves + show a spinner on submit ── */
  document.querySelectorAll('form[data-busy-button]').forEach(function (form) {
    form.addEventListener('submit', function () {
      var btn = form.querySelector('button[type="submit"]');
      if (!btn || btn.disabled) return;
      btn.disabled = true;
      btn.dataset.label = btn.textContent;
      btn.innerHTML = '<span class="spinner" role="status" aria-label="Working"></span> ' +
                      (form.getAttribute('data-busy-button') || 'Working…');
    });
  });
})();
