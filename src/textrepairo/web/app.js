/* SPDX-License-Identifier: GPL-3.0-or-later
 * Copyright (C) 2026 Atharva Patil, P4inz Interactive Labs
 *
 * TextRepairo front end. No frameworks. The only requests go to the local server.
 */
(() => {
  "use strict";
  const U = window.TR_UI;
  const { el, icon, toast } = U;
  const $ = (id) => document.getElementById(id);
  const NF = new Intl.NumberFormat("en-US");

  // ------------------------------------------------------------ api (session cookie, no token in scripts)
  async function request(path, opts) {
    const res = await fetch(path, opts);
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).error || msg; } catch (_) { /* not json */ }
      throw new Error(msg);
    }
    return res;
  }
  const api = async (path, body) =>
    (await request(path, body === undefined ? undefined : {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
    })).json();
  const apiText = async (path) => (await request(path)).text();

  // POST + read Server-Sent Events. Calls onEvent(obj) for each message.
  async function stream(path, body, onEvent, signal) {
    const res = await request(path, {
      method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body || {}), signal,
    });
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { value, done } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      let idx;
      while ((idx = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, idx);
        buf = buf.slice(idx + 2);
        const line = block.split("\n").find((l) => l.startsWith("data:"));
        if (line) { try { onEvent(JSON.parse(line.slice(5))); } catch (_) { /* ignore bad frame */ } }
      }
    }
  }

  // ------------------------------------------------------------ state
  const state = {
    status: null, style: "fix", formality: "normal", target: "message", busy: false, ctrl: null,
    last: null, exampleIdx: 0, moreOpen: false, sessionBannerDismissed: false,
  };

  const EXAMPLES = {
    fix: ["i dont know wich one is better, we should of asked him yesterday",
      "mujhe kal office jana hai lekin meri tabiyat thik nahi hai, boss ko kaise bataun?",
      "Me gustaria reservar una mesa para dos personas manana a las ocho, por favor."],
    professional: ["hey, cant make it to the meeting tmrw, got some stuff to do. can we do it later?",
      "Hallo, ich wollte fragen ob ihr die Rechnung schon bekommen habt, danke."],
    friendly: ["Your invoice is overdue. Pay immediately.", "Please send the report by Friday. No more delays."],
    prompt: ["write me email to my boss i need leave next week fever and doctor said rest, short and polite",
      "make python script rename all photos in folder by date taken, windows, explain how to run"],
    compose: ["meeting move friday 3pm?? client delay, sorry, tell team",
      "need caption instagram new coffee shop opening saturday fun short"],
    message: ["bro cant come today got fever tell sir", "ngl i forgot abt the party, can u send address again"],
    email: ["email to landlord water leak bathroom since monday need fix urgent",
      "need to ask hr about leave policy for next month, 3 days, family function"],
    casual: ["I will not be able to attend the gathering this evening due to a prior engagement."],
    concise: ["So basically what I wanted to say is that I think that we should probably meet up sometime next week if that works for everyone"],
    persuasive: ["buy our app its good and cheap", "join our workshop saturday, learn photo editing, limited seats"],
    empathetic: ["your request is denied, policy", "we cannot refund you, it is past 30 days"],
  };

  // ------------------------------------------------------------ theme + status
  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }
  const effectiveTheme = () =>
    document.documentElement.dataset.theme || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
  const fmtBytes = (n) => (n >= 1e9 ? (n / 1e9).toFixed(1) + " GB" : Math.round(n / 1e6) + " MB");
  const fmtEta = (s) => (s == null ? "" : s < 60 ? `about ${Math.max(1, s)} s left` : `about ${Math.round(s / 60)} min left`);

  async function refresh() {
    try {
      state.status = await api("/api/status");
    } catch (e) {
      $("statusText").textContent = "Cannot reach the app";
      $("statusDot").className = "dot bad";
      return null;
    }
    const s = state.status;
    applyTheme(s.settings.theme);
    renderStatusPill();
    $("privateTag").hidden = !s.settings.private_mode;
    return s;
  }
  const currentModel = () => state.status.models.find((m) => m.id === state.status.settings.model_id);
  function renderStatusPill() {
    const s = state.status;
    const dot = $("statusDot");
    if (!s.ready) { $("statusText").textContent = "Setup needed"; dot.className = "dot bad"; return; }
    const m = currentModel();
    const backend = s.backend === "cpu" ? "CPU" : s.backend[0].toUpperCase() + s.backend.slice(1);
    $("statusText").textContent = `${m ? m.tier : "Model"} · ${backend} · Offline`;
    dot.className = "dot " + (state.busy ? "busy" : "ok");
  }

  // ------------------------------------------------------------ external links (open in the real browser)
  document.addEventListener("click", (e) => {
    const a = e.target.closest && e.target.closest("a[data-ext]");
    if (!a) return;
    e.preventDefault();
    const url = a.getAttribute("href");
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_url) window.pywebview.api.open_url(url);
    else window.open(url, "_blank", "noopener,noreferrer");
  });
  const extLink = (url, label, ico) => el("a", { href: url, "data-ext": "1", class: "ext", rel: "noopener noreferrer" }, icon(ico || "link"), label);

  // ------------------------------------------------------------ styles + formality
  const styleById = (id) => state.status.styles.find((s) => s.id === id);
  let formalitySeg = null, targetSeg = null;

  function renderStyles() {
    const mk = (s) => el("button", {
      class: "mode", type: "button", role: "radio", "data-id": s.id, "aria-checked": String(s.id === state.style),
      tabindex: s.id === state.style ? "0" : "-1", onclick: () => setStyle(s.id),
    }, el("span", { class: "m-label", text: s.label }), el("span", { class: "m-sum", text: s.summary }));
    $("modes").replaceChildren(...state.status.styles.filter((s) => s.group === "main").map(mk));
    $("moreModes").replaceChildren(...state.status.styles.filter((s) => s.group !== "main").map(mk));
    const sel = styleById(state.style);
    if (sel && sel.group !== "main") state.moreOpen = true;
    setMore(state.moreOpen);
    formalitySeg = U.segmented({
      label: "Formality", value: state.formality,
      options: state.status.formalities.map((f) => ({ value: f.id, label: f.label, tip: f.summary })),
      onChange: (v) => { state.formality = v; },
    });
    $("formalityHost").replaceChildren(formalitySeg);
    applyStyleControls();
  }
  function setMore(open) {
    state.moreOpen = open;
    $("moreModes").hidden = !open;
    $("moreBtn").setAttribute("aria-expanded", String(open));
    $("moreBtn").textContent = open ? "Fewer styles" : "More styles";
  }
  $("moreBtn").onclick = () => setMore(!state.moreOpen);

  function applyStyleControls() {
    const s = styleById(state.style);
    formalitySeg.setDisabled(!s.formality);
    $("formalityLabel").textContent = s.formality ? "Formality" : "Formality (not used by this style)";
    const hasTarget = s.targets && s.targets.length > 0;
    $("targetBox").hidden = !hasTarget;
    if (hasTarget) {
      if (!s.targets.some((t) => t.id === state.target)) state.target = s.targets[0].id;
      targetSeg = U.segmented({
        label: "Write it as", value: state.target,
        options: s.targets.map((t) => ({ value: t.id, label: t.label })),
        onChange: (v) => { state.target = v; },
      });
      $("targetHost").replaceChildren(targetSeg);
    }
  }
  function setStyle(id) {
    state.style = id;
    for (const b of document.querySelectorAll(".mode")) {
      const on = b.dataset.id === id;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
    }
    applyStyleControls();
  }
  function modeKeys(e) {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    const ids = [...document.querySelectorAll(".mode")].map((b) => b.dataset.id);
    const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
    const next = ids[(ids.indexOf(state.style) + dir + ids.length) % ids.length];
    if (styleById(next).group !== "main" && !state.moreOpen) setMore(true);
    setStyle(next);
    document.querySelector(`.mode[data-id="${next}"]`).focus();
  }
  $("modes").addEventListener("keydown", modeKeys);
  $("moreModes").addEventListener("keydown", modeKeys);

  // ------------------------------------------------------------ result view
  function showTab(which) {
    const isDiff = which === "diff";
    $("tabResult").setAttribute("aria-selected", String(!isDiff));
    $("tabDiff").setAttribute("aria-selected", String(isDiff));
    $("output").hidden = isDiff;
    $("diff").hidden = !isDiff;
  }
  $("tabResult").onclick = () => showTab("result");
  $("tabDiff").onclick = () => showTab("diff");

  function renderDiff(ops) {
    const box = $("diff");
    box.replaceChildren();
    for (const o of ops) {
      if (o.op === "eq") box.append(document.createTextNode(o.text));
      else box.append(el(o.op === "ins" ? "ins" : "del", { text: o.text }));
    }
  }

  // ---- progress (real values from the server; nothing is simulated here)
  let pg = null;
  function showProgress(ev) {
    const host = $("progressHost");
    if (!pg) { pg = U.progress({ label: "Repair progress" }); host.replaceChildren(pg.root); }
    host.hidden = false;
    if (ev.phase === "loading") {
      pg.set({ pct: null, text: "Loading the model…", detail: "This only happens the first time after the app starts.", elapsed: ev.elapsed_s });
      return;
    }
    const part = ev.chunks > 1 ? ` · part ${ev.chunk} of ${ev.chunks}` : "";
    const verb = ev.phase === "reading" ? "Reading your text" : ev.phase === "done" ? "Done" : "Writing";
    const bits = [];
    if (ev.phase === "reading") bits.push(`${Math.round((performance.now() - state.runStart) / 1000)} s so far`);
    if (ev.tokens_per_s) bits.push(`${ev.tokens_per_s} tokens/s`);
    if (ev.eta_s != null && ev.phase !== "done") bits.push(fmtEta(ev.eta_s));
    pg.set({ pct: ev.pct, text: verb + part, detail: bits.join(" · ") });
  }
  function hideProgress() { $("progressHost").hidden = true; }

  function setBusy(on) {
    state.busy = on;
    $("goBtn").hidden = on;
    $("stopBtn").hidden = !on;
    $("output").classList.toggle("streaming", on);
    $("input").readOnly = on;
    if (state.status) renderStatusPill();
    if (on) $("stopBtn").focus();
  }

  function resetResult() {
    $("output").textContent = "";
    $("diff").replaceChildren();
    $("warnings").hidden = true;
    $("stats").textContent = "";
    $("retryBtn").hidden = true;
    $("copyBtn").disabled = true;
    hideProgress();
  }

  const charCount = (t) => [...t].length;

  async function repair() {
    if (state.busy) return;
    const text = $("input").value;
    const max = state.status ? state.status.max_chars : 10000;
    if (!text.trim()) { toast("Type or paste some text first."); $("input").focus(); return; }
    if (charCount(text) > max) { toast(`This text is longer than ${NF.format(max)} characters. Split it into parts.`, "error"); return; }
    if (!state.status || !state.status.ready) { openSetup(); return; }
    resetResult();
    $("empty").hidden = true;
    showTab("result");
    setBusy(true);
    state.runStart = performance.now();
    showProgress({ phase: "reading", pct: 0, chunk: 1, chunks: 1 });
    state.ctrl = new AbortController();
    let failed = false;
    const style = styleById(state.style);
    const body = { text, mode: state.style, formality: style.formality ? state.formality : undefined,
      target: style.targets.length ? state.target : undefined };
    try {
      await stream("/api/repair", body, (ev) => {
        if (ev.event === "progress") showProgress(ev);
        else if (ev.event === "partial") $("output").textContent = ev.text;
        else if (ev.event === "done") {
          state.last = ev;
          $("output").textContent = ev.text;
          renderDiff(ev.diff);
          if (ev.warnings.length) {
            $("warnings").replaceChildren(...ev.warnings.map((x) => el("p", { text: x })));
            $("warnings").hidden = false;
          }
          const tps = ev.seconds > 0 && ev.tokens ? ` · ${(ev.tokens / ev.seconds).toFixed(1)} tokens/s` : "";
          const saved = ev.saved ? " · Saved to history" : state.status.settings.private_mode ? " · Private: not saved" : "";
          $("stats").textContent = `${ev.seconds.toFixed(1)} s${tps}${saved}`;
          $("copyBtn").disabled = !ev.text;
          $("retryBtn").hidden = false;
        } else if (ev.event === "error") {
          failed = true;
          toast(ev.message, "error", 12000);
        }
      }, state.ctrl.signal);
    } catch (e) {
      if (e.name !== "AbortError") { failed = true; toast(e.message || String(e), "error", 12000); }
      else $("stats").textContent = "Stopped.";
    } finally {
      setBusy(false);
      hideProgress();
      state.ctrl = null;
      if (!$("output").textContent) $("empty").hidden = false;
      if (state.last && state.last.saved) refreshHistoryCount();
      if (failed) $("input").readOnly = false;
      $("goBtn").focus();
    }
  }
  const stop = () => { if (state.ctrl) state.ctrl.abort(); };
  async function refreshHistoryCount() { try { await refresh(); } catch (_) { /* ignore */ } }

  $("goBtn").onclick = repair;
  $("retryBtn").onclick = () => { state.last = null; repair(); };
  $("stopBtn").onclick = stop;
  $("copyBtn").onclick = async () => {
    const ok = await U.copyText($("output").textContent);
    toast(ok ? "Copied to clipboard." : "Could not copy. Select the text and copy it manually.", ok ? "ok" : "error", 2500);
  };
  $("clearBtn").onclick = () => {
    $("input").value = ""; updateCount(); resetResult(); state.last = null; $("empty").hidden = false; $("input").focus();
  };
  $("pasteBtn").onclick = async () => {
    try { $("input").value = await navigator.clipboard.readText(); updateCount(); $("input").focus(); }
    catch (_) { toast("Paste is blocked here. Click the box and press Ctrl+V."); $("input").focus(); }
  };
  $("exampleBtn").onclick = () => {
    const list = EXAMPLES[state.style] || EXAMPLES.fix;
    $("input").value = list[state.exampleIdx++ % list.length];
    updateCount(); $("input").focus();
  };

  function updateCount() {
    const v = $("input").value;
    const t = v.trim();
    const words = t ? t.split(/\s+/).length : 0;
    const n = charCount(v);
    const max = state.status ? state.status.max_chars : 10000;
    $("inCount").textContent = `${NF.format(words)} word${words === 1 ? "" : "s"}`;
    const lim = $("inLimit");
    lim.textContent = `${NF.format(n)} / ${NF.format(max)}`;
    lim.className = "limit" + (n > max ? " over" : n >= max * 0.9 ? " near" : "");
    $("goBtn").disabled = n > max;
    $("goBtn").setAttribute("aria-describedby", "inLimit");
    if (n > max) lim.textContent += `  ·  ${NF.format(n - max)} too long. Split it into parts.`;
  }
  $("input").addEventListener("input", updateCount);

  // ------------------------------------------------------------ context menus (custom, replace the browser's)
  U.contextMenu($("input"), () => {
    const t = $("input");
    const sel = t.selectionEnd > t.selectionStart;
    const replaceSel = (txt) => {
      const a = t.selectionStart, b = t.selectionEnd;
      t.value = t.value.slice(0, a) + txt + t.value.slice(b);
      t.selectionStart = t.selectionEnd = a + txt.length;
      updateCount();
    };
    return [
      { label: "Cut", shortcut: "Ctrl+X", disabled: !sel || t.readOnly, onClick: async () => { await U.copyText(t.value.slice(t.selectionStart, t.selectionEnd)); replaceSel(""); } },
      { label: "Copy", shortcut: "Ctrl+C", disabled: !sel, onClick: () => U.copyText(t.value.slice(t.selectionStart, t.selectionEnd)) },
      { label: "Paste", shortcut: "Ctrl+V", disabled: t.readOnly, onClick: async () => { try { replaceSel(await navigator.clipboard.readText()); } catch (_) { toast("Paste is blocked here. Press Ctrl+V."); } } },
      { label: "Select all", shortcut: "Ctrl+A", onClick: () => t.select() },
    ];
  });
  U.contextMenu($("output"), () => {
    const s = String(window.getSelection());
    return [
      { label: "Copy selection", shortcut: "Ctrl+C", disabled: !s, onClick: () => U.copyText(s) },
      { label: "Copy all", disabled: !$("output").textContent, onClick: () => U.copyText($("output").textContent) },
      { label: "Select all", shortcut: "Ctrl+A", onClick: () => { const r = document.createRange(); r.selectNodeContents($("output")); const g = window.getSelection(); g.removeAllRanges(); g.addRange(r); } },
    ];
  });

  // ------------------------------------------------------------ banners
  function showBanner({ text, kind, actions = [], progress }) {
    const b = el("div", { class: "banner" + (kind === "warn" ? " warn" : ""), role: "status" },
      el("span", { class: "grow", text }));
    if (progress) b.append(progress.root);
    for (const a of actions) b.append(el("button", { class: a.kind || "secondary small", type: "button", onclick: () => a.onClick(b) }, a.label));
    $("banner").append(b);
    return b;
  }

  // ------------------------------------------------------------ downloads
  async function runJob(path, body, onProgress) {
    let err = null, result = null;
    await stream(path, body, (ev) => {
      if (ev.event === "progress") onProgress(ev.done, ev.total);
      else if (ev.event === "error") err = ev.message;
      else if (ev.event === "done") result = ev.result || {};
    });
    if (err) throw new Error(err);
    return result;
  }
  const bytesProgress = (p, label) => (done, total) => {
    const pct = total ? (done * 100) / total : null;
    p.set({ pct, text: label, detail: total ? `${fmtBytes(done)} of ${fmtBytes(total)}` : fmtBytes(done) });
  };

  // ------------------------------------------------------------ setup (first run)
  let setupChoice = null, setupDlg = null;
  function openSetup() {
    if (setupDlg) return;
    const s = state.status;
    setupChoice = setupChoice || s.recommended_model;
    const steps = el("ol", { class: "steps" });
    const cards = el("div", { class: "model-cards" });
    const prog = U.progress({ label: "Download progress" });
    prog.root.hidden = true;
    const err = el("p", { class: "error", hidden: true });
    const note = el("p", { class: "muted small", text: "You can close the app and continue later. The download resumes where it stopped.", hidden: true });
    const content = el("div", {}, el("p", { class: "lead", text: "TextRepairo uses a small AI model that lives on your computer. You download it once, then it works with no internet." }),
      steps, cards, prog.root, note, err);
    function fill() {
      const st = state.status;
      steps.replaceChildren(
        el("li", { class: st.runtime_ready ? "done" : "on", text: "1. Text engine" }),
        el("li", { class: st.model_ready ? "done" : (st.runtime_ready ? "on" : ""), text: "2. Language model" }),
        el("li", { text: "3. Start writing" }));
      cards.replaceChildren();
      for (const m of st.models.filter((x) => x.tier !== "Custom")) {
        cards.append(el("button", {
          class: "card", type: "button", role: "radio", "aria-checked": String(m.id === setupChoice),
          onclick: () => { setupChoice = m.id; fill(); },
        }, el("span", { class: "radio" }),
          el("span", {}, el("span", { class: "c-title" }, el("span", { text: `${m.tier} · ${m.name}` }),
            m.id === st.recommended_model ? el("span", { class: "badge", text: "Recommended for this PC" }) : null,
            m.installed ? el("span", { class: "badge soft", text: "Downloaded" }) : null),
            el("span", { class: "c-desc", text: m.description })),
          el("span", { class: "c-size", text: fmtBytes(m.size) })));
      }
      const chosen = st.models.find((m) => m.id === setupChoice);
      go.textContent = chosen && chosen.installed ? "Continue" : "Download and continue";
    }
    const go = el("button", { class: "primary", type: "button", id: "setupGo" });
    go.onclick = async () => {
      const st = state.status;
      const chosen = st.models.find((m) => m.id === setupChoice);
      if (!chosen) return;
      err.hidden = true; go.disabled = true; cards.classList.add("busy"); prog.root.hidden = false; note.hidden = false;
      try {
        if (!st.runtime_ready) {
          await runJob("/api/runtime/install", { backend: st.backend === "metal" ? "metal" : "cpu" }, bytesProgress(prog, "Downloading the text engine"));
        }
        if (!chosen.installed) {
          await runJob("/api/models/download", { id: chosen.id }, bytesProgress(prog, `Downloading ${chosen.name}`));
        }
        await api("/api/settings", { model_id: chosen.id });
        await refresh();
        setupDlg.close();
        toast("All set. You can now work offline.", "ok");
      } catch (e) {
        err.textContent = e.message; err.hidden = false;
      } finally {
        go.disabled = false; cards.classList.remove("busy");
        await refresh();
        if (setupDlg) fill();
      }
    };
    const skip = el("button", { class: "secondary", type: "button", text: "I already have a model file" });
    skip.onclick = () => { setupDlg.close(); openSettings(); };
    setupDlg = U.dialog({
      title: "Let’s set up your offline writing assistant", eyebrow: "Welcome", content, dismissible: false, wide: true,
      onClose: () => { setupDlg = null; },
    });
    setupDlg.el.append(el("div", { class: "dialog-actions" }, skip, go));
    fill();
    go.focus();
  }

  // ------------------------------------------------------------ history
  const fmtWhen = (ts) => new Date(ts * 1000).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  const styleLabel = (id) => (styleById(id) || { label: id }).label;

  async function openHistory() {
    const content = el("div", {});
    const d = U.dialog({ title: "History", side: true, content });
    async function fill() {
      let h;
      try { h = await api("/api/history"); } catch (e) { content.replaceChildren(el("p", { class: "error", text: e.message })); return; }
      const parts = [];
      parts.push(el("p", { class: "muted small", text: `${h.count} of ${h.limit} saved on this computer. After ${h.limit}, the oldest are deleted permanently. Nothing is ever uploaded.` }));
      if (!h.enabled) parts.push(el("p", { class: "banner warn", text: "History is switched off, so new results are not saved. You can turn it on in Settings." }));
      else if (h.private) parts.push(el("p", { class: "banner warn", text: "Private mode is on, so new results are not saved." }));
      if (!h.entries.length) parts.push(el("p", { class: "empty-note", text: "Nothing here yet. Your repaired texts will show up here." }));
      const list = el("div", { class: "hist-list" });
      for (const e of h.entries) {
        const open = el("button", { class: "hist-item", type: "button", onclick: async () => { await restore(e.id); d.close(); } },
          el("span", { class: "h-in", text: e.input_snippet || "(empty)" }),
          el("span", { class: "h-out", text: e.output_snippet }),
          el("span", { class: "h-meta", text: `${styleLabel(e.style)}${e.style !== "fix" && e.formality !== "normal" ? " · " + e.formality : ""} · ${fmtWhen(e.ts)}` }));
        const del = el("button", { class: "icon-btn", type: "button", "aria-label": "Delete this entry", "data-tip": "Delete this entry",
          onclick: async () => { await api("/api/history/delete", { id: e.id }); await fill(); await refresh(); } }, icon("trash"));
        list.append(el("div", { class: "hist-row" }, open, del));
      }
      parts.push(list);
      if (h.entries.length) {
        parts.push(el("div", { class: "row-actions" }, el("button", { class: "danger small", type: "button", text: "Clear all history",
          onclick: async () => {
            if (!(await U.confirm({ title: "Clear all history?", message: `This permanently deletes ${h.count} saved result${h.count === 1 ? "" : "s"} from this computer. It cannot be undone.`, confirmLabel: "Delete everything", danger: true }))) return;
            await api("/api/history/clear", {}); await fill(); await refresh(); toast("History cleared.", "ok", 2500);
          } })));
      }
      content.replaceChildren(...parts);
    }
    await fill();
  }
  async function restore(id) {
    try {
      const e = await api("/api/history/get", { id });
      $("input").value = e.input;
      if (styleById(e.style)) setStyle(e.style);
      if (state.status.formalities.some((f) => f.id === e.formality)) { state.formality = e.formality; formalitySeg.setValue(e.formality); }
      resetResult();
      $("empty").hidden = true;
      $("output").textContent = e.output;
      $("diff").replaceChildren(el("span", { class: "muted", text: "Changes are not stored in history. Run it again to see them." }));
      $("copyBtn").disabled = false;
      $("stats").textContent = `From history · ${fmtWhen(e.ts)}`;
      showTab("result");
      updateCount();
    } catch (err) { toast(err.message, "error"); }
  }
  $("historyBtn").onclick = openHistory;

  // ------------------------------------------------------------ settings
  async function pickFile(kind) {
    const fn = kind === "pack" ? "pick_pack" : "pick_file";
    if (window.pywebview && window.pywebview.api && window.pywebview.api[fn]) return (await window.pywebview.api[fn]()) || null;
    return U.prompt({ title: kind === "pack" ? "Import a slang pack" : "Use your own model", label: kind === "pack" ? "Full path of the .json pack file:" : "Full path of the .gguf model file:", placeholder: "C:\\path\\to\\file", confirmLabel: "Import" });
  }
  const setSetting = async (patch) => { await api("/api/settings", patch); await refresh(); };

  function openSettings() {
    const content = el("div", {});
    const d = U.dialog({ title: "Settings", side: true, content });
    const draw = async () => {
      const scroll = d.body.scrollTop;
      await refresh();
      const s = state.status;
      const set = s.settings;
      const sections = [];

      // Model
      const list = el("div", { class: "model-list" });
      for (const m of s.models) {
        const active = m.id === set.model_id && m.installed;
        const actions = el("div", { class: "row-actions" });
        if (m.installed) {
          if (!active) actions.append(el("button", { class: "btn-sm", type: "button", text: "Use this model", onclick: async () => { await api("/api/engine/stop", {}); await setSetting({ model_id: m.id }); toast("Model changed. It loads on your next repair.", "info", 3000); draw(); } }));
          actions.append(el("button", { class: "btn-sm danger", type: "button", text: "Delete", onclick: async () => {
            if (!(await U.confirm({ title: `Delete ${m.name}?`, message: "You can download it again later.", confirmLabel: "Delete", danger: true }))) return;
            try { await api("/api/models/delete", { id: m.id }); } catch (e) { toast(e.message, "error"); }
            draw();
          } }));
        } else {
          const btn = el("button", { class: "btn-sm", type: "button", text: `Download (${fmtBytes(m.size)})` });
          btn.onclick = async () => {
            btn.disabled = true;
            try { await runJob("/api/models/download", { id: m.id }, (dn, t) => { btn.textContent = `Downloading ${t ? Math.floor((dn * 100) / t) : 0}%`; }); toast(`${m.name} is ready.`, "ok"); }
            catch (e) { toast(e.message, "error", 10000); }
            draw();
          };
          actions.append(btn);
        }
        list.append(el("div", { class: "model-row" + (active ? " active" : "") },
          el("div", { class: "row1" }, el("span", { class: "name", text: m.tier === "Custom" ? m.name : `${m.tier} · ${m.name}` }),
            el("span", { class: "muted small", text: active ? "In use" : fmtBytes(m.size) })),
          el("span", { class: "muted small", text: `${m.description} License: ${m.license}.` }), actions));
      }
      sections.push(el("section", {}, el("h3", { text: "Model" }),
        el("p", { class: "muted small", text: "Bigger models write better but need more memory and time." }), list,
        el("button", { class: "secondary small", type: "button", text: "Use my own .gguf file…", onclick: async () => {
          const p = await pickFile("model"); if (!p) return;
          try { const r = await api("/api/models/import", { path: p }); await setSetting({ model_id: r.id }); toast("Model imported and selected.", "ok"); }
          catch (e) { toast(e.message, "error", 9000); }
          draw();
        } })));

      // Speed
      const labels = { cpu: "CPU only", vulkan: "GPU (Vulkan)", cuda: "GPU (NVIDIA CUDA)", metal: "GPU (Apple Metal)" };
      const hw = s.hardware;
      const gpuBackend = s.available_backends.find((b) => b === "vulkan" || b === "metal");
      const needGpu = gpuBackend && gpuBackend !== "metal" && hw.gpu_vendor !== "none" && !s.installed_backends.includes(gpuBackend);
      const gpuBox = el("div", {});
      if (needGpu) {
        const gp = U.progress({ label: "GPU engine download" }); gp.root.hidden = true;
        const gb = el("button", { class: "secondary small", type: "button", text: "Download GPU acceleration" });
        gb.onclick = async () => {
          gb.disabled = true; gp.root.hidden = false;
          try { await runJob("/api/runtime/install", { backend: gpuBackend }, bytesProgress(gp, "Downloading the GPU engine")); await setSetting({ backend: "auto" }); toast("GPU acceleration installed.", "ok"); }
          catch (e) { toast(e.message, "error", 10000); }
          draw();
        };
        gpuBox.append(gb, gp.root);
      }
      sections.push(el("section", {}, el("h3", { text: "Speed" }),
        el("div", { class: "field-row" }, el("span", { text: "Processing" }),
          U.select({ label: "Processing", value: set.backend, options: [{ value: "auto", label: "Automatic (recommended)" }, ...s.available_backends.map((b) => ({ value: b, label: labels[b] || b }))],
            onChange: async (v) => { await api("/api/engine/stop", {}); await setSetting({ backend: v }); draw(); } })),
        el("p", { class: "muted small", text: `This computer: ${hw.cpu_threads} CPU threads, ${hw.ram_gb} GB RAM${hw.gpu_name ? ", " + hw.gpu_name : ", no dedicated GPU found"}. Using: ${s.backend}. The CPU uses about half of your cores to stay cool.` }), gpuBox));

      // Writing defaults
      sections.push(el("section", {}, el("h3", { text: "Writing" }),
        el("div", { class: "field-row" }, el("span", { text: "Default style" }),
          U.select({ label: "Default style", value: set.default_mode, options: s.styles.map((x) => ({ value: x.id, label: x.label })), onChange: (v) => setSetting({ default_mode: v }) })),
        el("div", { class: "field-row" }, el("span", { text: "Default formality" }),
          U.segmented({ label: "Default formality", value: set.default_formality, options: s.formalities.map((f) => ({ value: f.id, label: f.label })), onChange: (v) => setSetting({ default_formality: v }) })),
        el("p", { class: "muted small", text: "Everything is written to sound natural, like a person wrote it. Output is English for now." })));

      // Appearance
      sections.push(el("section", {}, el("h3", { text: "Appearance" }),
        el("div", { class: "field-row" }, el("span", { text: "Theme" }),
          U.segmented({ label: "Theme", value: set.theme, options: [{ value: "system", label: "System" }, { value: "light", label: "Light" }, { value: "dark", label: "Dark" }], onChange: (v) => { applyTheme(v); setSetting({ theme: v }); } }))));

      // Privacy
      sections.push(el("section", {}, el("h3", { text: "Privacy" }),
        U.toggle({ label: "Keep a history", desc: `Saves your last ${s.history_limit} results on this computer only.`, checked: set.history_enabled, onChange: (v) => setSetting({ history_enabled: v }) }),
        U.toggle({ label: "Private mode", desc: "While on, nothing is saved to history.", checked: set.private_mode, onChange: async (v) => { await setSetting({ private_mode: v }); } }),
        U.toggle({ label: "Forget on exit", desc: "Clears the history every time you close the app.", checked: set.forget_on_exit, onChange: (v) => setSetting({ forget_on_exit: v }) }),
        el("div", { class: "row-actions" },
          el("button", { class: "danger small", type: "button", text: `Clear history (${s.history_count})`, onclick: async () => {
            if (!(await U.confirm({ title: "Clear all history?", message: "This permanently deletes every saved result from this computer.", confirmLabel: "Delete everything", danger: true }))) return;
            await api("/api/history/clear", {}); toast("History cleared.", "ok", 2500); draw();
          } }),
          el("button", { class: "secondary small", type: "button", text: "Open data folder", onclick: () => api("/api/open-data-folder", {}) })),
        el("p", { class: "muted small", text: "No telemetry. No accounts. Your text never leaves this device." })));

      // Slang packs
      const packs = el("div", { class: "model-list" });
      for (const p of s.packs) {
        packs.append(el("div", { class: "model-row" },
          el("div", { class: "row1" }, el("span", { class: "name", text: p.name }), el("span", { class: "muted small", text: `${NF.format(p.entries)} entries` })),
          el("div", { class: "row-actions" }, el("span", { class: "badge soft", text: p.source === "bundled" ? "Built in" : "Yours" }),
            p.source === "user" ? el("button", { class: "btn-sm danger", type: "button", text: "Remove", onclick: async () => { await api("/api/packs/remove", { id: p.id }); draw(); } }) : null)));
      }
      sections.push(el("section", {}, el("h3", { text: "Slang packs" }),
        el("p", { class: "muted small", text: "Packs teach the app what slang, chat shorthand and romanized words mean. Only matching entries are used, offline." }), packs,
        el("button", { class: "secondary small", type: "button", text: "Import a pack…", onclick: async () => {
          const p = await pickFile("pack"); if (!p) return;
          try { const r = await api("/api/packs/import", { path: p }); toast(`Pack '${r.id}' imported (${r.entries} entries).`, "ok"); } catch (e) { toast(e.message, "error", 9000); }
          draw();
        } })));

      // Updates
      const upNote = el("p", { class: "muted small", text: "The only network request the app makes on its own is a plain check of this project's GitHub releases, at most once a day. No text or personal data is sent." });
      const upResult = el("p", { class: "small" });
      sections.push(el("section", {}, el("h3", { text: "Updates" }),
        el("div", { class: "field-row" }, el("span", { text: "Check for updates" }),
          U.segmented({ label: "Update mode", value: set.update_mode, options: [{ value: "automatic", label: "Automatic" }, { value: "notify", label: "Notify me" }, { value: "off", label: "Off" }], onChange: (v) => setSetting({ update_mode: v }) })),
        upNote,
        el("div", { class: "row-actions" }, el("button", { class: "secondary small", type: "button", text: "Check now", onclick: async (e) => {
          e.currentTarget.disabled = true; upResult.textContent = "Checking…";
          try { const r = await checkForUpdates(true); upResult.textContent = r ? `Version ${r.latest} is available.` : "You are up to date."; }
          catch (err) { upResult.textContent = err.message; }
          e.currentTarget.disabled = false;
        } })), upResult));

      // Tools
      sections.push(el("section", {}, el("h3", { text: "Help" }),
        el("div", { class: "row-actions" },
          el("button", { class: "secondary small", type: "button", text: "Doctor", onclick: () => { d.close(); openDoctor(); } }),
          el("button", { class: "secondary small", type: "button", text: "About", onclick: () => { d.close(); openAbout(); } })),
        el("p", { class: "muted small", text: `TextRepairo ${s.version} · ${s.platform} · data folder is in ${s.data_mode} mode.` })));

      content.replaceChildren(...sections);
      d.body.scrollTop = scroll;
    };
    draw();
  }
  $("settingsBtn").onclick = openSettings;
  $("privateTag").onclick = openSettings;
  $("statusPill").onclick = () => (state.status && state.status.ready ? openSettings() : openSetup());
  $("themeBtn").onclick = async () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    try { await api("/api/settings", { theme: next }); } catch (_) { /* ignore */ }
  };

  // ------------------------------------------------------------ doctor
  function openDoctor() {
    const list = el("div", { class: "checks" });
    const out = el("div", {});
    const prog = U.progress({ label: "Model check" }); prog.root.hidden = true;
    const content = el("div", {}, el("p", { class: "lead", text: "Checks that everything TextRepairo needs is in place. The report never contains your text." }), list, prog.root, out);
    let report = "";
    const d = U.dialog({ title: "Doctor", content, wide: true, actions: [
      { label: "Copy report", kind: "secondary", onClick: async () => { toast(await U.copyText(report) ? "Report copied." : "Could not copy.", "ok", 2000); } },
      { label: "Test the engine", kind: "secondary", id: "docEngine", onClick: async (_c, btn) => {
        btn.disabled = true; out.replaceChildren(el("p", { class: "muted small", text: "Running a short test… the first run also loads the model." }));
        try { const r = await api("/api/doctor/engine-test", {}); out.replaceChildren(el("p", { class: r.ok ? "banner" : "error", text: r.ok ? `The engine works: ${r.seconds} s${r.tokens_per_s ? ", " + r.tokens_per_s + " tokens/s" : ""}.` : "The engine returned an empty answer." })); }
        catch (e) { out.replaceChildren(el("p", { class: "error", text: e.message })); }
        btn.disabled = false;
      } },
      { label: "Verify model", kind: "secondary", id: "docVerify", onClick: async (_c, btn) => {
        btn.disabled = true; prog.root.hidden = false; out.replaceChildren();
        try {
          const r = await runJob("/api/doctor/verify-model", {}, bytesProgress(prog, "Checking the model file"));
          out.replaceChildren(el("p", { class: r.ok ? "banner" : "error", text: r.message }));
        } catch (e) { out.replaceChildren(el("p", { class: "error", text: e.message })); }
        prog.root.hidden = true; btn.disabled = false;
      } },
      { label: "Run again", kind: "primary", onClick: () => run() },
    ] });
    const fixLabel = { runtime: "Set up", model: "Open settings", reset_settings: "Reset settings", clear_cache: "Clear", clear_history: "Clear history" };
    async function run() {
      list.replaceChildren(el("p", { class: "muted", text: "Checking…" }));
      try {
        const r = await api("/api/doctor/run", {});
        report = r.report;
        list.replaceChildren(...r.checks.map((c) => {
          const act = el("div", { class: "row-actions" });
          if (c.fix) act.append(el("button", { class: "btn-sm", type: "button", text: fixLabel[c.fix] || "Fix", onclick: async () => {
            if (c.fix === "runtime") { d.close(); openSetup(); return; }
            if (c.fix === "model") { d.close(); openSettings(); return; }
            if (c.fix === "reset_settings" && !(await U.confirm({ title: "Reset settings?", message: "Your settings go back to their defaults. Models and history are kept.", confirmLabel: "Reset", danger: true }))) return;
            await api("/api/doctor/fix", { action: c.fix }); toast("Done.", "ok", 2000); await refresh(); run();
          } }));
          return el("div", { class: "check" }, el("span", { class: "st " + c.status, text: { ok: "✓", warn: "!", fail: "×", info: "i" }[c.status] }),
            el("div", {}, el("div", { class: "c-label", text: c.label }), el("div", { class: "c-detail", text: c.detail })), act);
        }));
      } catch (e) { list.replaceChildren(el("p", { class: "error", text: e.message })); }
    }
    run();
  }

  // ------------------------------------------------------------ about
  async function showDoc(name, title) {
    let text = "";
    try { text = await apiText(`/api/about/doc/${name}`); } catch (e) { text = e.message; }
    U.dialog({ title, wide: true, content: el("pre", { class: "docview", text }), actions: [{ label: "Close", kind: "secondary" }] });
  }
  async function openAbout() {
    let a;
    try { a = await api("/api/about"); } catch (e) { toast(e.message, "error"); return; }
    const L = a.links;
    const content = el("div", {},
      el("div", { class: "about-head" },
        el("img", { class: "logo", src: "icon.svg", alt: "" }),
        el("div", {}, el("strong", { text: `${a.name} ${a.version}` }), el("div", { class: "muted small", text: "Fix messy text into clear, natural English, fully offline." }))),
      el("p", { class: "credit", text: `Created by ${a.author}, ${a.brand}.` }),
      el("p", { class: "credit", text: a.copyright }),
      el("p", { class: "credit", text: `License: ${a.license}.` }),
      el("div", { class: "link-list" },
        extLink(L.repo, "GitHub"), extLink(L.portfolio, "Portfolio"), extLink(L.discord, "Discord"),
        extLink(L.donate, "Support (UPI)", "heart"), extLink(L.coffee, "Buy me a coffee", "heart")),
      el("div", { class: "row-actions" },
        el("button", { class: "secondary small", type: "button", text: "License", onclick: () => showDoc("license", "GNU GPL v3") }),
        el("button", { class: "secondary small", type: "button", text: "Additional terms", onclick: () => showDoc("terms", "Additional terms") }),
        el("button", { class: "secondary small", type: "button", text: "Privacy", onclick: () => showDoc("privacy", "Privacy") }),
        el("button", { class: "secondary small", type: "button", text: "Third-party notices", onclick: () => showDoc("notices", "Third-party notices") })),
      el("p", { class: "credit", text: `Models: ${a.models.map((m) => `${m.name} (${m.license})`).join(", ")}.` }),
      el("p", { class: "credit", text: `Data folder (${a.data_mode} mode): ${a.data_dir}` }),
      a.portable_note ? el("p", { class: "credit", text: a.portable_note }) : null,
      el("p", { class: "credit", text: "No telemetry, no accounts. The only network use is the optional update check and downloads you start yourself." }));
    U.dialog({ title: "About TextRepairo", content, wide: true, actions: [{ label: "Close", kind: "primary" }] });
  }

  // ------------------------------------------------------------ updates (like kinoz: automatic / notify / off)
  async function checkForUpdates(manual) {
    const info = await api("/api/update/check", {});
    if (!info.available) return null;
    if (manual) { offerUpdate(info, true); }
    else offerUpdate(info, false);
    return info;
  }
  function offerUpdate(info, force) {
    const mode = state.status.settings.update_mode;
    const releaseBtn = { label: "Release page", kind: "secondary small", onClick: () => window.open(info.page_url, "_blank", "noopener,noreferrer") };
    const later = { label: "Not now", kind: "ghost", onClick: (b) => b.remove() };
    if (info.kind !== "installer") {
      showBanner({ text: `Version ${info.latest} is available. Download it from the release page.`, actions: [{ label: "Open download page", kind: "primary small", onClick: () => openExternal(info.page_url) }, later] });
      return;
    }
    const startDownload = async (banner) => {
      banner.remove();
      const p = U.progress({ label: "Update download" });
      const b2 = showBanner({ text: `Downloading version ${info.latest}…`, progress: p });
      try {
        await runJob("/api/update/download", {}, bytesProgress(p, "Downloading the update"));
        b2.remove();
        showBanner({ text: `Version ${info.latest} is ready and checked. Restart to finish updating.`, actions: [
          { label: "Restart now", kind: "primary small", onClick: async (b) => { try { await api("/api/update/install", {}); toast("Installing the update. TextRepairo will reopen by itself.", "ok", 8000); b.remove(); } catch (e) { toast(e.message, "error", 9000); } } },
          { label: "Later", kind: "ghost", onClick: (b) => { b.remove(); toast("OK. It installs the next time you open TextRepairo.", "info", 5000); } }] });
      } catch (e) { b2.remove(); toast(e.message, "error", 12000); }
    };
    if (mode === "automatic" && !force) {
      const b = showBanner({ text: `Version ${info.latest} is available.`, actions: [] });
      startDownload(b);
    } else {
      showBanner({ text: `Version ${info.latest} is available.`, actions: [{ label: "Download and install", kind: "primary small", onClick: startDownload }, releaseBtn, later] });
    }
  }
  function openExternal(url) {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.open_url) window.pywebview.api.open_url(url);
    else window.open(url, "_blank", "noopener,noreferrer");
  }
  async function startUpdateWatcher() {
    setTimeout(async () => {
      try {
        const st = await api("/api/update/state");
        if (!st.due || st.mode === "off") return;
        await checkForUpdates(false);
      } catch (_) { /* offline or blocked: stay quiet */ }
    }, 8000);
  }

  // ------------------------------------------------------------ keyboard
  document.addEventListener("keydown", (e) => {
    const mod = e.ctrlKey || e.metaKey;
    if (mod && e.key === "Enter") { e.preventDefault(); if (!U.hasOpenDialog()) repair(); }
    else if (mod && e.key.toLowerCase() === "h") { e.preventDefault(); if (!U.hasOpenDialog()) openHistory(); }
    else if (mod && e.key === ",") { e.preventDefault(); if (!U.hasOpenDialog()) openSettings(); }
    else if (e.key === "Escape" && state.busy && !U.hasOpenDialog()) stop();
  });

  // ------------------------------------------------------------ boot
  (async function init() {
    const s = await refresh();
    if (!s) return;
    state.style = s.settings.default_mode || "fix";
    state.formality = s.settings.default_formality || "normal";
    renderStyles();
    updateCount();
    if (!s.ready) openSetup();
    else $("input").focus();
    if (s.safe_mode) {
      showBanner({ kind: "warn", text: "TextRepairo started in safe mode because the last two sessions did not close properly. Automatic updates are paused for now.",
        actions: [{ label: "Open Doctor", kind: "primary small", onClick: () => openDoctor() }] });
      openDoctor();
    } else if (s.settings.update_mode !== "off") {
      startUpdateWatcher();
    }
  })();
})();
