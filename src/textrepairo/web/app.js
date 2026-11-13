/* TextRepairo front end. No frameworks, no network calls except to the local server. */
(() => {
  "use strict";

  // ------------------------------------------------------------ token + api
  const params = new URLSearchParams(location.search);
  let TOKEN = params.get("t") || "";
  try {
    if (TOKEN) sessionStorage.setItem("tr-token", TOKEN);
    else TOKEN = sessionStorage.getItem("tr-token") || "";
  } catch (_) { /* storage may be blocked */ }
  if (params.has("t")) history.replaceState(null, "", location.pathname);

  const $ = (id) => document.getElementById(id);
  const el = (tag, attrs = {}, ...kids) => {
    const n = document.createElement(tag);
    for (const [k, v] of Object.entries(attrs)) {
      if (k === "class") n.className = v;
      else if (k === "text") n.textContent = v;
      else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
      else if (v === true) n.setAttribute(k, "");
      else if (v !== false && v != null) n.setAttribute(k, v);
    }
    for (const kid of kids) if (kid != null) n.append(kid);
    return n;
  };

  async function api(path, body) {
    const res = await fetch(path, {
      method: body === undefined ? "GET" : "POST",
      headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).error || msg; } catch (_) {}
      throw new Error(msg);
    }
    return res.json();
  }

  // POST + read Server-Sent Events. Calls onEvent(obj) for each message.
  async function stream(path, body, onEvent, signal) {
    const res = await fetch(path, {
      method: "POST",
      headers: { "X-Token": TOKEN, "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
      signal,
    });
    if (!res.ok) {
      let msg = res.statusText;
      try { msg = (await res.json()).error || msg; } catch (_) {}
      throw new Error(msg);
    }
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
        if (line) {
          try { onEvent(JSON.parse(line.slice(5))); } catch (_) {}
        }
      }
    }
  }

  // ------------------------------------------------------------ state
  const state = { status: null, mode: "fix", busy: false, ctrl: null, last: null, exampleIdx: 0 };

  const EXAMPLES = {
    fix: [
      "i dont know wich one is better, we should of asked him yesterday",
      "mujhe kal office jana hai lekin meri tabiyat thik nahi hai, boss ko kaise bataun?",
      "Me gustaria reservar una mesa para dos personas manana a las ocho, por favor.",
    ],
    formal: [
      "hey, cant make it to the meeting tmrw, got some stuff to do. can we do it later?",
      "Hallo, ich wollte fragen ob ihr die Rechnung schon bekommen habt, danke.",
    ],
    friendly: [
      "Your invoice is overdue. Pay immediately.",
      "Please send the report by Friday. No more delays.",
    ],
    prompt: [
      "write me email to my boss i need leave next week fever and doctor said rest, short and polite",
      "make python script rename all photos in folder by date taken, windows, explain how to run",
    ],
  };

  // ------------------------------------------------------------ toasts
  function toast(msg, kind = "info", ms = 6000) {
    const t = el("div", { class: "toast" + (kind === "error" ? " error" : ""), role: "status", text: msg });
    $("toasts").append(t);
    setTimeout(() => t.remove(), ms);
  }

  // ------------------------------------------------------------ theme
  function applyTheme(theme) {
    if (theme === "light" || theme === "dark") document.documentElement.dataset.theme = theme;
    else delete document.documentElement.dataset.theme;
  }
  function effectiveTheme() {
    const t = document.documentElement.dataset.theme;
    if (t) return t;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  // ------------------------------------------------------------ status
  const fmtBytes = (n) => (n >= 1e9 ? (n / 1e9).toFixed(1) + " GB" : Math.round(n / 1e6) + " MB");

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
    return s;
  }

  function currentModel() {
    const s = state.status;
    return s.models.find((m) => m.id === s.settings.model_id);
  }

  function renderStatusPill() {
    const s = state.status;
    const dot = $("statusDot");
    if (!s.ready) {
      $("statusText").textContent = "Setup needed";
      dot.className = "dot bad";
      return;
    }
    const m = currentModel();
    const backend = s.backend === "cpu" ? "CPU" : s.backend[0].toUpperCase() + s.backend.slice(1);
    $("statusText").textContent = `${m ? m.tier : "Model"} · ${backend} · Offline`;
    dot.className = "dot " + (state.busy ? "busy" : "ok");
  }

  // ------------------------------------------------------------ modes
  function renderModes() {
    const wrap = $("modes");
    wrap.replaceChildren();
    for (const m of state.status.modes) {
      const b = el("button", {
        class: "mode", type: "button", role: "radio", "data-id": m.id,
        "aria-checked": String(m.id === state.mode), tabindex: m.id === state.mode ? "0" : "-1",
        onclick: () => setMode(m.id),
      }, el("span", { class: "m-label", text: m.label }), el("span", { class: "m-sum", text: m.summary }));
      wrap.append(b);
    }
  }
  function setMode(id) {
    state.mode = id;
    for (const b of $("modes").children) {
      const on = b.dataset.id === id;
      b.setAttribute("aria-checked", String(on));
      b.tabIndex = on ? 0 : -1;
    }
  }
  $("modes").addEventListener("keydown", (e) => {
    if (!["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(e.key)) return;
    e.preventDefault();
    const ids = state.status.modes.map((m) => m.id);
    const dir = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : -1;
    const next = ids[(ids.indexOf(state.mode) + dir + ids.length) % ids.length];
    setMode(next);
    $("modes").querySelector(`[data-id="${next}"]`).focus();
  });

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

  function setBusy(on) {
    state.busy = on;
    $("goBtn").hidden = on;
    $("stopBtn").hidden = !on;
    $("output").classList.toggle("streaming", on);
    $("input").readOnly = on;
    if (state.status) renderStatusPill();
  }

  function resetResult() {
    $("output").textContent = "";
    $("diff").replaceChildren();
    $("warnings").hidden = true;
    $("stats").textContent = "";
    $("retryBtn").hidden = true;
    $("copyBtn").disabled = true;
  }

  async function repair() {
    if (state.busy) return;
    const text = $("input").value;
    if (!text.trim()) { toast("Type or paste some text first."); $("input").focus(); return; }
    if (!state.status || !state.status.ready) { openSetup(); return; }
    resetResult();
    $("empty").hidden = true;
    showTab("result");
    setBusy(true);
    state.ctrl = new AbortController();
    let failed = false;
    try {
      await stream("/api/repair", { text, mode: state.mode }, (ev) => {
        if (ev.event === "partial") {
          $("output").textContent = ev.text;
        } else if (ev.event === "done") {
          state.last = ev;
          $("output").textContent = ev.text;
          renderDiff(ev.diff);
          if (ev.warnings.length) {
            const w = $("warnings");
            w.replaceChildren(...ev.warnings.map((x) => el("p", { text: x })));
            w.hidden = false;
          }
          const tps = ev.seconds > 0 ? ` · ${(ev.tokens / ev.seconds).toFixed(1)} tokens/s` : "";
          $("stats").textContent = `${ev.seconds.toFixed(1)} s${tps}`;
          $("copyBtn").disabled = !ev.text;
          $("retryBtn").hidden = false;
        } else if (ev.event === "error") {
          failed = true;
          toast(ev.message, "error", 12000);
        }
      }, state.ctrl.signal);
    } catch (e) {
      if (e.name !== "AbortError") { failed = true; toast(e.message || String(e), "error", 12000); }
    } finally {
      setBusy(false);
      state.ctrl = null;
      if (!$("output").textContent && !state.last) $("empty").hidden = false;
      if (failed && !$("output").textContent) $("empty").hidden = false;
    }
  }

  function stop() { if (state.ctrl) state.ctrl.abort(); }

  async function copyText(text) {
    try { await navigator.clipboard.writeText(text); return true; } catch (_) {}
    const ta = el("textarea", { style: "position:fixed;opacity:0" });
    ta.value = text; document.body.append(ta); ta.select();
    let ok = false;
    try { ok = document.execCommand("copy"); } catch (_) {}
    ta.remove();
    return ok;
  }

  $("goBtn").onclick = repair;
  $("retryBtn").onclick = () => { state.last = null; repair(); };
  $("stopBtn").onclick = stop;
  $("copyBtn").onclick = async () => {
    const ok = await copyText($("output").textContent);
    toast(ok ? "Copied to clipboard." : "Could not copy. Select the text and copy it manually.", ok ? "info" : "error", 2500);
  };
  $("clearBtn").onclick = () => { $("input").value = ""; updateCount(); resetResult(); state.last = null; $("empty").hidden = false; $("input").focus(); };
  $("pasteBtn").onclick = async () => {
    try { $("input").value = await navigator.clipboard.readText(); updateCount(); $("input").focus(); }
    catch (_) { toast("Paste is blocked here. Click the box and press Ctrl+V."); $("input").focus(); }
  };
  $("exampleBtn").onclick = () => {
    const list = EXAMPLES[state.mode] || EXAMPLES.fix;
    $("input").value = list[state.exampleIdx++ % list.length];
    updateCount(); $("input").focus();
  };
  function updateCount() {
    const t = $("input").value.trim();
    const words = t ? t.split(/\s+/).length : 0;
    $("inCount").textContent = `${words} word${words === 1 ? "" : "s"} · ${$("input").value.length} characters`;
  }
  $("input").addEventListener("input", updateCount);
  document.addEventListener("keydown", (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === "Enter") { e.preventDefault(); repair(); }
    else if (e.key === "Escape") {
      if (!$("settings").hidden) closeSettings();
      else if (state.busy) stop();
    }
  });

  // ------------------------------------------------------------ downloads
  async function runJob(path, body, onProgress) {
    let err = null;
    await stream(path, body, (ev) => {
      if (ev.event === "progress") onProgress(ev.done, ev.total);
      else if (ev.event === "error") err = ev.message;
    });
    if (err) throw new Error(err);
  }

  // ------------------------------------------------------------ setup
  let setupChoice = null;
  function openSetup() {
    const s = state.status;
    setupChoice = setupChoice || s.recommended_model;
    $("setup").hidden = false;
    $("setupError").hidden = true;
    renderSetup();
    $("setupGo").focus();
  }
  function renderSetup() {
    const s = state.status;
    const steps = $("setupSteps");
    steps.replaceChildren(
      el("li", { class: s.runtime_ready ? "done" : "on", text: "1. Text engine" }),
      el("li", { class: s.model_ready ? "done" : (s.runtime_ready ? "on" : ""), text: "2. Language model" }),
      el("li", { text: "3. Start writing" }),
    );
    const cards = $("setupModels");
    cards.replaceChildren();
    for (const m of s.models.filter((x) => x.tier !== "Custom")) {
      const card = el("button", {
        class: "card", type: "button", role: "radio", "aria-checked": String(m.id === setupChoice),
        onclick: () => { setupChoice = m.id; renderSetup(); },
      },
        el("span", { class: "radio" }),
        el("span", {},
          el("span", { class: "c-title" },
            el("span", { text: `${m.tier} · ${m.name}` }),
            m.id === s.recommended_model ? el("span", { class: "badge", text: "Recommended for this PC" }) : null,
            m.installed ? el("span", { class: "badge soft", text: "Downloaded" }) : null),
          el("span", { class: "c-desc", text: m.description })),
        el("span", { class: "c-size", text: fmtBytes(m.size) }));
      cards.append(card);
    }
    const chosen = s.models.find((m) => m.id === setupChoice);
    $("setupGo").textContent = chosen && chosen.installed ? "Continue" : "Download and continue";
  }
  $("setupGo").onclick = async () => {
    const s = state.status;
    const chosen = s.models.find((m) => m.id === setupChoice);
    if (!chosen) return;
    $("setupError").hidden = true;
    $("setupGo").disabled = true;
    $("setupModels").style.pointerEvents = "none";
    $("setupProgress").hidden = false;
    const prog = (label) => (done, total) => {
      const pct = total ? Math.round((done * 100) / total) : 0;
      $("setupProgressText").textContent = label;
      $("setupProgressPct").textContent = total ? `${pct}%  (${fmtBytes(done)} of ${fmtBytes(total)})` : fmtBytes(done);
      $("setupBar").style.width = pct + "%";
    };
    try {
      if (!s.runtime_ready) {
        const be = s.backend === "metal" ? "metal" : "cpu";
        await runJob("/api/runtime/install", { backend: be }, prog("Downloading the text engine…"));
      }
      if (!chosen.installed) {
        await runJob("/api/models/download", { id: chosen.id }, prog(`Downloading ${chosen.name}…`));
      }
      await api("/api/settings", { model_id: chosen.id });
      await refresh();
      $("setup").hidden = true;
      toast("All set. You can now work offline.");
    } catch (e) {
      $("setupError").textContent = e.message;
      $("setupError").hidden = false;
    } finally {
      $("setupGo").disabled = false;
      $("setupModels").style.pointerEvents = "";
      await refresh();
      if (!$("setup").hidden) renderSetup();
    }
  };
  $("setupSkip").onclick = async () => { $("setup").hidden = true; openSettings(); };

  // ------------------------------------------------------------ settings
  let lastFocus = null;
  function openSettings() {
    lastFocus = document.activeElement;
    renderSettings();
    $("settings").hidden = false;
    $("settingsClose").focus();
  }
  function closeSettings() {
    $("settings").hidden = true;
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  async function pickModelFile() {
    if (window.pywebview && window.pywebview.api && window.pywebview.api.pick_file) {
      const p = await window.pywebview.api.pick_file();
      return p || null;
    }
    return window.prompt("Full path of the .gguf model file:") || null;
  }

  function renderSettings() {
    const s = state.status;
    const list = $("modelList");
    list.replaceChildren();
    for (const m of s.models) {
      const active = m.id === s.settings.model_id && m.installed;
      const actions = el("div", { class: "row-actions" });
      if (m.installed) {
        if (!active) actions.append(el("button", { class: "btn-sm", type: "button", text: "Use this model", onclick: () => useModel(m.id) }));
        actions.append(el("button", { class: "btn-sm danger", type: "button", text: "Delete", onclick: () => deleteModel(m) }));
      } else {
        actions.append(el("button", { class: "btn-sm", type: "button", text: `Download (${fmtBytes(m.size)})`, onclick: (e) => downloadModel(m, e.currentTarget) }));
      }
      list.append(el("div", { class: "model-row" + (active ? " active" : "") },
        el("div", { class: "row1" },
          el("span", { class: "name", text: m.tier === "Custom" ? m.name : `${m.tier} · ${m.name}` }),
          el("span", { class: "muted small", text: active ? "In use" : fmtBytes(m.size) })),
        el("span", { class: "muted small", text: `${m.description} License: ${m.license}.` }),
        actions));
    }
    // backend
    const sel = $("backendSel");
    sel.replaceChildren(el("option", { value: "auto", text: "Automatic (recommended)" }));
    const labels = { cpu: "CPU only", vulkan: "GPU (Vulkan)", cuda: "GPU (NVIDIA CUDA)", metal: "GPU (Apple Metal)" };
    for (const b of s.available_backends) sel.append(el("option", { value: b, text: labels[b] || b }));
    sel.value = s.settings.backend;
    const hw = s.hardware;
    $("backendHelp").textContent =
      `This computer: ${hw.cpu_threads} CPU threads, ${hw.ram_gb} GB RAM` +
      (hw.gpu_name ? `, ${hw.gpu_name}` : ", no dedicated GPU found") +
      `. Using: ${s.backend}. The CPU uses about half of your cores to stay cool.`;
    const gpuBackend = s.available_backends.find((b) => b === "vulkan" || b === "metal");
    const needGpu = gpuBackend && gpuBackend !== "metal" && hw.gpu_vendor !== "none" && !s.installed_backends.includes(gpuBackend);
    $("gpuInstall").hidden = !needGpu;
    $("gpuBtn").onclick = async () => {
      $("gpuBarWrap").hidden = false; $("gpuBtn").disabled = true;
      try {
        await runJob("/api/runtime/install", { backend: gpuBackend }, (d, t) => { $("gpuBar").style.width = (t ? (d * 100) / t : 0) + "%"; });
        await api("/api/settings", { backend: "auto" });
        toast("GPU acceleration installed.");
      } catch (e) { toast(e.message, "error", 10000); }
      $("gpuBtn").disabled = false; $("gpuBarWrap").hidden = true;
      await refresh(); renderSettings();
    };
    $("themeSel").value = s.settings.theme;
    const dm = $("defaultModeSel");
    dm.replaceChildren(...s.modes.map((m) => el("option", { value: m.id, text: m.label })));
    dm.value = s.settings.default_mode;
    $("aboutText").textContent = `TextRepairo ${s.version} · ${s.platform}. Data folder: ${s.data_dir}`;
  }

  async function useModel(id) {
    await api("/api/engine/stop", {});
    await api("/api/settings", { model_id: id });
    await refresh(); renderSettings();
    toast("Model changed. It loads on your next repair.", "info", 3000);
  }
  async function deleteModel(m) {
    if (!window.confirm(`Delete ${m.name}? You can download it again later.`)) return;
    try { await api("/api/models/delete", { id: m.id }); } catch (e) { toast(e.message, "error"); }
    await refresh(); renderSettings();
  }
  async function downloadModel(m, btn) {
    btn.disabled = true;
    try {
      await runJob("/api/models/download", { id: m.id }, (d, t) => {
        btn.textContent = `Downloading ${t ? Math.round((d * 100) / t) : 0}%`;
      });
      toast(`${m.name} is ready.`);
    } catch (e) { toast(e.message, "error", 10000); }
    await refresh(); renderSettings();
  }
  $("importBtn").onclick = async () => {
    const p = await pickModelFile();
    if (!p) return;
    try {
      const r = await api("/api/models/import", { path: p });
      await api("/api/settings", { model_id: r.id });
      toast("Model imported and selected.");
    } catch (e) { toast(e.message, "error", 9000); }
    await refresh(); renderSettings();
  };
  $("backendSel").onchange = async (e) => {
    await api("/api/engine/stop", {});
    await api("/api/settings", { backend: e.target.value });
    await refresh(); renderSettings();
  };
  $("themeSel").onchange = async (e) => { await api("/api/settings", { theme: e.target.value }); await refresh(); };
  $("defaultModeSel").onchange = async (e) => { await api("/api/settings", { default_mode: e.target.value }); await refresh(); };
  $("settingsBtn").onclick = openSettings;
  $("statusPill").onclick = () => (state.status && state.status.ready ? openSettings() : openSetup());
  $("settingsClose").onclick = closeSettings;
  $("settings").addEventListener("click", (e) => { if (e.target === $("settings")) closeSettings(); });
  $("themeBtn").onclick = async () => {
    const next = effectiveTheme() === "dark" ? "light" : "dark";
    applyTheme(next);
    try { await api("/api/settings", { theme: next }); } catch (_) {}
  };

  // ------------------------------------------------------------ boot
  (async function init() {
    const s = await refresh();
    if (!s) return;
    state.mode = s.settings.default_mode || "fix";
    renderModes();
    updateCount();
    if (!s.ready) openSetup();
    $("input").focus();
  })();
})();
