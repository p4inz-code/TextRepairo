/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
 *
 * TextRepairo UI components. Every control the user sees is drawn by the app (no native
 * dropdowns, dialogs, tooltips, menus or checkboxes) and keeps real keyboard and
 * screen-reader behavior. No frameworks and no network access.
 */
(() => {
  "use strict";

  const NS = "http://www.w3.org/2000/svg";

  // ------------------------------------------------------------ dom helpers
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, "");
      else if (v !== false && v != null) n.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null && kid !== false) n.append(kid);
    return n;
  };

  const ICONS = {
    close: ["M6 6l12 12M18 6L6 18"],
    gear: ["M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6z",
      "M19.4 15a1.7 1.7 0 0 0 .3 1.9l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.9-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.9.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.9 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.9l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.9.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.9-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.9V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"],
    moon: ["M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8z"],
    clock: ["M12 7v5l3 2", "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"],
    lock: ["M5 11h14v9H5z", "M8 11V8a4 4 0 0 1 8 0v3"],
    chevron: ["M6 9l6 6 6-6"],
    check: ["M5 12.5l4.5 4.5L19 7.5"],
    trash: ["M4 7h16", "M9 7V4h6v3", "M6 7l1 13h10l1-13"],
    doc: ["M7 3h7l4 4v14H7z", "M14 3v4h4", "M10 12h5M10 16h5"],
    heart: ["M12 20s-7-4.4-7-10a4 4 0 0 1 7-2.6A4 4 0 0 1 19 10c0 5.6-7 10-7 10z"],
    info: ["M12 11v5", "M12 8h.01", "M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z"],
    pulse: ["M3 12h4l2-6 4 12 2-6h6"],
    link: ["M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1", "M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"],
    warn: ["M12 4l9 16H3z", "M12 10v4", "M12 17h.01"],
    doc2: ["M5 4h14v16H5z", "M9 9h6M9 13h6M9 17h3"],
    download: ["M12 4v11", "M7 11l5 5 5-5", "M5 20h14"],
  };
  function icon(name, cls = "") {
    const s = document.createElementNS(NS, "svg");
    s.setAttribute("viewBox", "0 0 24 24");
    s.setAttribute("aria-hidden", "true");
    s.setAttribute("class", "ico " + cls);
    for (const d of ICONS[name] || []) {
      const p = document.createElementNS(NS, "path");
      p.setAttribute("d", d);
      s.append(p);
    }
    return s;
  }

  const FOCUSABLE = 'button:not([disabled]), [href], input:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"]):not([disabled])';

  // ------------------------------------------------------------ focus traps (stack: only the top one reacts)
  const trapStack = [];
  document.addEventListener("keydown", (e) => {
    const top = trapStack[trapStack.length - 1];
    if (!top) return;
    if (e.key === "Escape") {
      if (top.onEscape) { e.preventDefault(); e.stopPropagation(); top.onEscape(); }
      return;
    }
    if (e.key !== "Tab") return;
    const items = [...top.root.querySelectorAll(FOCUSABLE)].filter((n) => n.offsetParent !== null);
    if (!items.length) { e.preventDefault(); return; }
    const first = items[0], last = items[items.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === top.root ||
        !top.root.contains(document.activeElement))) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && (document.activeElement === last || !top.root.contains(document.activeElement))) {
      e.preventDefault(); first.focus();
    }
  }, true);

  function trap(root, onEscape) {
    const entry = { root, onEscape };
    trapStack.push(entry);
    return () => { const i = trapStack.indexOf(entry); if (i >= 0) trapStack.splice(i, 1); };
  }
  const hasOpenDialog = () => trapStack.length > 0;

  // ------------------------------------------------------------ dialogs and drawers
  let dialogId = 0;
  function dialog({ title, eyebrow, content, actions = [], side = false, wide = false, dismissible = true,
                    onClose, initialFocus, headerExtra }) {
    const prev = document.activeElement;
    const id = "dlg-" + (++dialogId);
    const overlay = el("div", { class: "overlay" + (side ? " side" : "") });
    const box = el(side ? "aside" : "div", {
      class: (side ? "drawer" : "dialog") + (wide ? " wide" : ""), role: "dialog", "aria-modal": "true",
      "aria-labelledby": id,
    });
    let closed = false;
    const close = (result) => {
      if (closed) return;
      closed = true;
      release();
      overlay.classList.add("leaving");
      overlay.remove();
      if (prev && prev.focus && document.contains(prev)) prev.focus();
      if (onClose) onClose(result);
    };
    const head = el("div", { class: side ? "drawer-head" : "dialog-head" },
      el("div", {}, eyebrow ? el("p", { class: "eyebrow", text: eyebrow }) : null, el("h2", { id, text: title })),
      headerExtra || null,
      dismissible ? el("button", { class: "icon-btn", type: "button", "aria-label": "Close", "data-tip": "Close",
        onclick: () => close() }, icon("close")) : null);
    const body = el("div", { class: side ? "drawer-body" : "dialog-body" }, content);
    box.append(head, body);
    if (actions.length) {
      const foot = el("div", { class: "dialog-actions" });
      for (const a of actions) {
        foot.append(el("button", {
          class: a.kind || "secondary", type: "button", id: a.id || null, disabled: !!a.disabled,
          onclick: (e) => a.onClick ? a.onClick(close, e.currentTarget) : close(a.value),
        }, a.label));
      }
      box.append(foot);
    }
    overlay.append(box);
    overlay.addEventListener("mousedown", (e) => { if (e.target === overlay && dismissible) close(); });
    document.body.append(overlay);
    const release = trap(box, dismissible ? () => close() : null);
    box.tabIndex = -1;
    const target = (initialFocus && box.querySelector(initialFocus)) ||
      box.querySelector(".dialog-actions .primary, .dialog-actions .danger-solid") || box;
    target.focus();
    return { close, el: box, body, overlay };
  }

  function confirmDialog({ title, message, confirmLabel = "OK", cancelLabel = "Cancel", danger = false }) {
    return new Promise((resolve) => {
      dialog({
        title, content: el("p", { class: "dlg-text", text: message }),
        actions: [
          { label: cancelLabel, kind: "secondary", value: false },
          { label: confirmLabel, kind: danger ? "danger-solid" : "primary", value: true },
        ],
        initialFocus: danger ? ".secondary" : ".primary",
        onClose: (r) => resolve(r === true),
      });
    });
  }

  function promptDialog({ title, label, placeholder = "", confirmLabel = "OK" }) {
    return new Promise((resolve) => {
      const input = el("input", { class: "text-input", type: "text", placeholder, "aria-label": label,
        spellcheck: "false" });
      let value = null;
      const d = dialog({
        title, content: el("div", {}, el("p", { class: "dlg-text", text: label }), input),
        actions: [
          { label: "Cancel", kind: "secondary", value: null },
          { label: confirmLabel, kind: "primary", onClick: (close) => { value = input.value.trim(); close(value); } },
        ],
        initialFocus: "input", onClose: (r) => resolve(r || null),
      });
      input.addEventListener("keydown", (e) => { if (e.key === "Enter") { value = input.value.trim(); d.close(value); } });
    });
  }

  // ------------------------------------------------------------ toasts
  function toast(msg, kind = "info", ms = 6000) {
    const host = document.getElementById("toasts");
    if (!host) return;
    const t = el("div", { class: "toast" + (kind === "error" ? " error" : kind === "ok" ? " ok" : ""), role: "status", text: msg });
    host.append(t);
    setTimeout(() => t.remove(), ms);
  }

  // ------------------------------------------------------------ tooltips (replace native title="")
  const tip = el("div", { class: "tooltip", role: "tooltip", id: "tooltip", hidden: true });
  let tipTimer = null, tipFor = null;
  function showTip(target) {
    const text = target.getAttribute("data-tip");
    if (!text) return;
    tip.textContent = text;
    tip.hidden = false;
    const r = target.getBoundingClientRect();
    const tw = tip.offsetWidth, th = tip.offsetHeight;
    let x = r.left + r.width / 2 - tw / 2;
    x = Math.max(8, Math.min(x, window.innerWidth - tw - 8));
    let y = r.bottom + 8;
    if (y + th > window.innerHeight - 8) y = r.top - th - 8;
    tip.style.left = x + "px";
    tip.style.top = y + "px";
    target.setAttribute("aria-describedby", "tooltip");
    tipFor = target;
  }
  function hideTip() {
    clearTimeout(tipTimer);
    tip.hidden = true;
    if (tipFor) tipFor.removeAttribute("aria-describedby");
    tipFor = null;
  }
  document.addEventListener("DOMContentLoaded", () => document.body.append(tip));
  document.addEventListener("mouseover", (e) => {
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (!t || t === tipFor) return;
    clearTimeout(tipTimer);
    tipTimer = setTimeout(() => showTip(t), 450);
  });
  document.addEventListener("mouseout", (e) => {
    const t = e.target.closest && e.target.closest("[data-tip]");
    if (t) hideTip();
  });
  document.addEventListener("focusin", (e) => { const t = e.target.closest && e.target.closest("[data-tip]"); if (t && t.matches(":focus-visible")) showTip(t); });
  document.addEventListener("focusout", hideTip);
  document.addEventListener("mousedown", hideTip, true);
  document.addEventListener("keydown", (e) => { if (e.key === "Escape") hideTip(); }, true);

  // ------------------------------------------------------------ popups: close when clicking elsewhere
  let openPopup = null;
  function closePopup() { if (openPopup) { const p = openPopup; openPopup = null; p.close(); } }
  document.addEventListener("mousedown", (e) => { if (openPopup && !openPopup.el.contains(e.target) && !(openPopup.owner && openPopup.owner.contains(e.target))) closePopup(); }, true);
  window.addEventListener("blur", closePopup);
  window.addEventListener("resize", closePopup);
  document.addEventListener("scroll", (e) => { if (openPopup && !openPopup.el.contains(e.target)) closePopup(); }, true);

  function placePopup(popup, anchorRect, minWidth) {
    popup.style.minWidth = (minWidth || anchorRect.width) + "px";
    popup.style.left = "0px"; popup.style.top = "0px";
    document.body.append(popup);
    const w = popup.offsetWidth, h = popup.offsetHeight;
    let x = Math.min(anchorRect.left, window.innerWidth - w - 8);
    let y = anchorRect.bottom + 6;
    if (y + h > window.innerHeight - 8) y = Math.max(8, anchorRect.top - h - 6);
    popup.style.left = Math.max(8, x) + "px";
    popup.style.top = y + "px";
  }

  // ------------------------------------------------------------ custom select (replaces <select>)
  function select({ id, label, options, value, onChange, disabled = false }) {
    let current = value;
    const labelOf = (v) => (options.find((o) => o.value === v) || options[0] || { label: "" }).label;
    const btn = el("button", {
      class: "select-btn", type: "button", id: id || null, role: "combobox", "aria-haspopup": "listbox",
      "aria-expanded": "false", "aria-label": label || null, disabled,
    }, el("span", { class: "select-value", text: labelOf(current) }), icon("chevron"));
    const wrap = el("div", { class: "select" }, btn);

    function open() {
      if (btn.disabled || openPopup) return;
      closePopup();
      const list = el("ul", { class: "listbox", role: "listbox", tabindex: "-1" });
      let active = Math.max(0, options.findIndex((o) => o.value === current));
      const items = options.map((o, i) => {
        const li = el("li", { class: "option", role: "option", id: `${id || "sel"}-opt-${i}`,
          "aria-selected": String(o.value === current) },
          el("span", { class: "opt-label", text: o.label }),
          o.desc ? el("span", { class: "opt-desc", text: o.desc }) : null,
          o.value === current ? icon("check") : null);
        li.addEventListener("mousedown", (e) => { e.preventDefault(); choose(i); });
        li.addEventListener("mousemove", () => setActive(i));
        list.append(li);
        return li;
      });
      function setActive(i) {
        active = (i + items.length) % items.length;
        items.forEach((n, k) => n.classList.toggle("active", k === active));
        btn.setAttribute("aria-activedescendant", items[active].id);
        items[active].scrollIntoView({ block: "nearest" });
      }
      function choose(i) {
        const v = options[i].value;
        close();
        if (v !== current) { current = v; btn.querySelector(".select-value").textContent = labelOf(v); if (onChange) onChange(v); }
        btn.focus();
      }
      let typed = "", typedTimer = null;
      const onKey = (e) => {
        if (e.key === "ArrowDown") { e.preventDefault(); setActive(active + 1); }
        else if (e.key === "ArrowUp") { e.preventDefault(); setActive(active - 1); }
        else if (e.key === "Home") { e.preventDefault(); setActive(0); }
        else if (e.key === "End") { e.preventDefault(); setActive(items.length - 1); }
        else if (e.key === "Enter" || e.key === " ") { e.preventDefault(); choose(active); }
        else if (e.key === "Escape") { e.preventDefault(); e.stopPropagation(); close(); btn.focus(); }
        else if (e.key === "Tab") { close(); }
        else if (e.key.length === 1 && !e.ctrlKey && !e.metaKey) {
          clearTimeout(typedTimer); typed += e.key.toLowerCase();
          typedTimer = setTimeout(() => (typed = ""), 700);
          const hit = options.findIndex((o) => o.label.toLowerCase().startsWith(typed));
          if (hit >= 0) setActive(hit);
        }
      };
      const close = () => {
        btn.removeEventListener("keydown", onKey, true);
        btn.setAttribute("aria-expanded", "false"); btn.removeAttribute("aria-activedescendant");
        list.remove(); if (openPopup && openPopup.el === list) openPopup = null;
      };
      btn.addEventListener("keydown", onKey, true);
      btn.setAttribute("aria-expanded", "true");
      placePopup(list, btn.getBoundingClientRect(), Math.max(btn.offsetWidth, 180));
      setActive(active);
      openPopup = { el: list, owner: wrap, close };
    }
    btn.addEventListener("click", () => { if (openPopup && openPopup.owner === wrap) closePopup(); else open(); });
    btn.addEventListener("keydown", (e) => {
      if (!openPopup && ["ArrowDown", "ArrowUp", "Enter", " "].includes(e.key)) { e.preventDefault(); open(); }
    });
    wrap.setValue = (v) => { current = v; btn.querySelector(".select-value").textContent = labelOf(v); };
    wrap.button = btn;
    return wrap;
  }

  // ------------------------------------------------------------ segmented control (radio group)
  function segmented({ label, options, value, onChange, disabled = false, id }) {
    let current = value;
    const root = el("div", { class: "segmented", role: "radiogroup", "aria-label": label, id: id || null });
    const btns = options.map((o) => {
      const b = el("button", { class: "seg", type: "button", role: "radio", "data-value": o.value,
        "aria-checked": String(o.value === current), tabindex: o.value === current ? "0" : "-1", disabled,
        "data-tip": o.tip || null }, o.label);
      b.addEventListener("click", () => set(o.value, true));
      root.append(b);
      return b;
    });
    function set(v, fire) {
      current = v;
      btns.forEach((b) => { const on = b.dataset.value === v; b.setAttribute("aria-checked", String(on)); b.tabIndex = on ? 0 : -1; });
      if (fire && onChange) onChange(v);
    }
    root.addEventListener("keydown", (e) => {
      if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
      e.preventDefault();
      const vals = options.map((o) => o.value);
      const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
      const next = vals[(vals.indexOf(current) + dir + vals.length) % vals.length];
      set(next, true);
      root.querySelector(`[data-value="${next}"]`).focus();
    });
    root.setValue = (v) => set(v, false);
    root.setDisabled = (d) => { btns.forEach((b) => (b.disabled = d)); root.classList.toggle("disabled", d); };
    root.setDisabled(disabled);
    return root;
  }

  // ------------------------------------------------------------ switch (replaces checkbox)
  function toggle({ label, desc, checked, onChange, id }) {
    const input = el("input", { type: "checkbox", role: "switch", class: "switch-input", id: id || null });
    input.checked = !!checked;
    input.addEventListener("change", () => onChange && onChange(input.checked));
    const row = el("label", { class: "switch-row" },
      el("span", { class: "switch-text" }, el("span", { class: "switch-label", text: label }),
        desc ? el("span", { class: "muted small", text: desc }) : null),
      input, el("span", { class: "switch-track", "aria-hidden": "true" }, el("span", { class: "switch-thumb" })));
    row.input = input;
    return row;
  }

  // ------------------------------------------------------------ progress bar (real values only)
  function progress({ label = "" } = {}) {
    const text = el("span", { class: "pg-text" });
    const pct = el("span", { class: "pg-pct" });
    const fill = el("div", { class: "pg-fill" });
    const track = el("div", { class: "bar", role: "progressbar", "aria-valuemin": "0", "aria-valuemax": "100",
      "aria-label": label || "Progress" }, fill);
    const detail = el("p", { class: "pg-detail muted small" });
    const wait = el("span", { class: "pg-wait", hidden: true });
    const root = el("div", { class: "progress-block" },
      el("div", { class: "progress-label" }, text, pct), track, detail);
    root.append(wait);
    let lastAnnounced = -1;
    const live = el("span", { class: "sr-only", "aria-live": "polite" });
    root.append(live);
    return {
      root,
      /** pct: real number 0..100, or null while the length is unknown (shows time only). */
      set({ pct: p, text: t, detail: d, elapsed }) {
        text.textContent = t || "";
        detail.textContent = d || "";
        const known = typeof p === "number" && isFinite(p);
        track.hidden = !known;
        wait.hidden = known;
        root.classList.toggle("unknown", !known);
        if (known) {
          const v = Math.max(0, Math.min(100, p));
          fill.style.width = v + "%";
          track.setAttribute("aria-valuenow", String(Math.round(v)));
          pct.textContent = (v >= 100 ? 100 : Math.floor(v)) + "%";
          const step = Math.floor(v / 25) * 25;
          if (step !== lastAnnounced) { lastAnnounced = step; live.textContent = `${t || label}: ${step}%`; }
        } else {
          track.removeAttribute("aria-valuenow");
          pct.textContent = elapsed != null ? `${Math.round(elapsed)} s` : "";
          wait.hidden = false;
        }
      },
    };
  }

  // ------------------------------------------------------------ context menu (replaces the browser one)
  function contextMenu(target, getItems) {
    target.addEventListener("contextmenu", (e) => {
      e.preventDefault();
      closePopup();
      const menu = el("ul", { class: "menu", role: "menu", tabindex: "-1" });
      const items = getItems();
      const nodes = items.map((it) => {
        const li = el("li", { class: "menu-item" + (it.disabled ? " disabled" : ""), role: "menuitem",
          "aria-disabled": it.disabled ? "true" : null, tabindex: "-1" },
          el("span", { text: it.label }), it.shortcut ? el("kbd", { text: it.shortcut }) : null);
        li.addEventListener("mousedown", (ev) => { ev.preventDefault(); if (!it.disabled) { closePopup(); it.onClick(); } });
        menu.append(li);
        return li;
      });
      let active = -1;
      const setActive = (i) => { active = (i + nodes.length) % nodes.length; nodes.forEach((n, k) => n.classList.toggle("active", k === active)); };
      const onKey = (ev) => {
        if (ev.key === "ArrowDown") { ev.preventDefault(); setActive(active + 1); }
        else if (ev.key === "ArrowUp") { ev.preventDefault(); setActive(active - 1); }
        else if (ev.key === "Enter" && active >= 0 && !items[active].disabled) { ev.preventDefault(); closePopup(); items[active].onClick(); }
        else if (ev.key === "Escape") { ev.preventDefault(); closePopup(); }
      };
      const close = () => { document.removeEventListener("keydown", onKey, true); menu.remove(); if (openPopup && openPopup.el === menu) openPopup = null; target.focus && target.focus(); };
      document.addEventListener("keydown", onKey, true);
      placePopup(menu, { left: e.clientX, bottom: e.clientY, top: e.clientY, width: 0 }, 180);
      openPopup = { el: menu, owner: null, close };
    });
  }

  // ------------------------------------------------------------ clipboard
  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (_) { /* fall through */ }
    const ta = el("textarea", { class: "offscreen", "aria-hidden": "true", tabindex: "-1" });
    ta.value = text; document.body.append(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) { /* ignore */ }
    ta.remove();
    return ok;
  }

  window.TR_UI = { el, icon, dialog, confirm: confirmDialog, prompt: promptDialog, toast, select, segmented,
    toggle, progress, contextMenu, copyText, hasOpenDialog, closePopup, trap };
})();
