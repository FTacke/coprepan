// CO.PRE.PAN BODY review client (CPD-0043). Every text from the package is set with textContent, never as markup. Every answer is
// sent to the local server at once and stored there as an event; the client keeps no judgment of its own.
"use strict";

const PAGE_TYPE_LABELS = {
  news_report: "Nachricht / Bericht", opinion: "Meinung / Kolumne", interview: "Interview", feature: "Reportage / Feature",
  live_ticker: "Live-Ticker", preview_or_service: "Vorschau / Service (Wo sehen, Agenda)", recipe_or_howto: "Rezept / Anleitung",
  sports_with_tables: "Sportbericht mit Tabellen", list_or_ranking: "Liste / Ranking", gallery_or_video: "Galerie / Video-Seite",
  agency_wire: "Agenturmeldung", sponsored_or_press_release: "Gesponsert / Pressemitteilung", paywall_or_teaser: "Paywall / Teaser",
  section_or_index_page: "Rubrik- / Übersichtsseite", not_an_article: "kein Artikel",
};
const LABEL_TEXT = { article: "Artikeltext", foreign: "fremd", unsure: "unsicher" };
const OPEN_TEXT = { title: "Titelfläche beurteilen", completeness: "Vollständigkeit angeben", core: "CORE beantworten",
  core_reason: "CORE-Begründung fehlt" };

const S = { pkg: null, state: null, idx: 0, kase: null, focus: 0, tab: "original", timers: {} };
const $ = (id) => document.getElementById(id);

function el(tag, cls, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text !== undefined && text !== null) e.textContent = text;
  return e;
}

async function api(path, body) {
  const options = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const r = await fetch(path, options);
  const data = await r.json().catch(() => ({ error: "keine Antwort" }));
  if (!r.ok) throw new Error(data.error || r.statusText);
  return data;
}

function saved(ok, message) {
  const s = $("saveState");
  s.textContent = ok ? "gespeichert ✓" : "Fehler: " + message;
  s.className = ok ? "save" : "save err";
}

async function send(kind, payload) {
  const cid = S.kase.case_id;
  try {
    const r = await api("/api/event", { kind, case_id: cid, payload: payload || {} });
    S.state[cid] = r.case;
    saved(true);
    renderStatus();
    return true;
  } catch (e) {
    saved(false, e.message);
    return false;
  }
}

function cs() { return S.state[S.kase.case_id]; }

// --- navigation --------------------------------------------------------------------------------------------------------------

async function openCase(i) {
  S.idx = Math.max(0, Math.min(S.pkg.cases.length - 1, i));
  const cid = S.pkg.cases[S.idx];
  S.kase = await api("/api/case/" + cid);
  S.focus = 0;
  $("caseSelect").value = cid;
  render();
  api("/api/event", { kind: "position", case_id: cid, payload: {} }).catch(() => {});
}

function nextOpen() {
  const n = S.pkg.cases.length;
  for (let k = 1; k <= n; k++) {
    const j = (S.idx + k) % n;
    if (!S.state[S.pkg.cases[j]].finalized) return openCase(j);
  }
}

// --- rendering ---------------------------------------------------------------------------------------------------------------

function render() {
  const c = S.kase;
  $("caseId").textContent = c.case_id;
  $("outlet").textContent = c.outlet_id;
  $("country").textContent = c.country_id;
  $("url").textContent = c.url;
  $("fetched").textContent = (c.fetched_at || "–").slice(0, 16).replace("T", " ");
  $("published").textContent = c.published ? String(c.published).slice(0, 16).replace("T", " ") : "unbekannt";
  $("source").src = "/api/case/" + c.case_id + "/source";
  renderPageText();
  renderTitle();
  renderBlocks();
  renderAnswers();
  renderStatus();
  $("machine").classList.add("hidden");
  if (cs().finalized || S.pkg.diagnostic) loadMachine();
}

function renderPageText() {
  const box = $("pageText");
  box.replaceChildren();
  for (const b of S.kase.page_text) {
    const p = el("p");
    p.append(el("span", "k", b.kind), document.createTextNode(b.text));
    box.append(p);
  }
}

function renderTitle() {
  const box = $("titleBlocks");
  box.replaceChildren();
  if (!S.kase.title_blocks.length) box.append(el("div", "hint", "Keine Titelfläche erkannt."));
  for (const b of S.kase.title_blocks) {
    const d = el("div", "titleblock");
    d.append(el("span", "k", b.kind === "title" ? "Titel" : "Vorspann"), document.createTextNode(b.text));
    box.append(d);
  }
  $("titleChoice").classList.toggle("hidden", !S.kase.title_blocks.length);
}

function renderBlocks() {
  const list = $("blocks");
  list.replaceChildren();
  S.kase.blocks.forEach((b, i) => {
    const li = el("li", "block");
    li.dataset.i = i;
    li.append(el("div", "n", String(b.n)));
    const t = el("div", "t");
    t.append(el("span", "k", b.kind));
    t.append(document.createTextNode(b.text));
    li.append(t);
    const btns = el("div", "btns");
    for (const v of ["article", "foreign", "unsure"]) {
      const bt = el("button", "", LABEL_TEXT[v]);
      bt.dataset.v = v;
      bt.addEventListener("click", () => { S.focus = i; label(i, v); });
      btns.append(bt);
    }
    li.append(btns);
    li.append(el("div", "mach"));
    li.addEventListener("click", (ev) => { if (ev.target.tagName !== "BUTTON") { S.focus = i; paintBlocks(); } });
    list.append(li);
  });
  paintBlocks();
}

function paintBlocks() {
  const labels = cs().blocks;
  document.querySelectorAll("#blocks .block").forEach((li) => {
    const b = S.kase.blocks[+li.dataset.i];
    const v = labels[String(b.index)];
    li.className = "block" + (v ? " l-" + v : "") + (+li.dataset.i === S.focus ? " focus" : "");
    li.querySelectorAll(".btns button").forEach((bt) => bt.classList.toggle("on", bt.dataset.v === v));
    li.querySelectorAll(".btns button").forEach((bt) => { bt.disabled = cs().finalized; });
  });
  const done = S.kase.blocks.filter((b) => labels[String(b.index)]).length;
  $("blockCount").textContent = done + " von " + S.kase.blocks.length + " Blöcken beurteilt";
  const f = document.querySelector("#blocks .block.focus");
  if (f) f.scrollIntoView({ block: "nearest" });
}

function renderAnswers() {
  const s = cs();
  document.querySelectorAll("#titleChoice button").forEach((b) => b.classList.toggle("on", b.dataset.v === s.title));
  document.querySelectorAll("#coreChoice button").forEach((b) => b.classList.toggle("on", s.core && b.dataset.v === s.core.value));
  $("coreReason").value = s.core ? s.core.reason : "";
  document.querySelectorAll("#completeness input").forEach((x) => { x.checked = (s.completeness || []).includes(x.value); });
  const types = $("pageTypes");
  if (!types.childElementCount) {
    for (const v of S.pkg.vocabulary.page_types) {
      const l = el("label");
      const x = el("input");
      x.type = "checkbox";
      x.value = v;
      x.addEventListener("change", sendPageTypes);
      l.append(x, document.createTextNode(" " + (PAGE_TYPE_LABELS[v] || v)));
      types.append(l);
    }
  }
  types.querySelectorAll("input").forEach((x) => { x.checked = s.page_types.values.includes(x.value); });
  $("pageTypeOther").value = s.page_types.other || "";
  $("comment").value = s.comment || "";
  renderMarks();
  const locked = s.finalized;
  document.querySelectorAll("#titleChoice button, #coreChoice button, #completeness input, #pageTypes input, #allArticle, #markBtn")
    .forEach((x) => { x.disabled = locked; });
  for (const id of ["coreReason", "pageTypeOther", "comment"]) $(id).disabled = locked;
}

function renderMarks() {
  const ul = $("marks");
  ul.replaceChildren();
  const marks = Object.entries(cs().missing);
  if (!marks.length) ul.append(el("li", "hint", "Keine Markierung."));
  for (const [id, m] of marks) {
    const li = el("li");
    const q = m.quote.length > 220 ? m.quote.slice(0, 220) + " …" : m.quote;
    li.append(el("span", "q", "„" + q + "“"), document.createTextNode(" " + (m.part ? "(" + m.part.replace("_missing", "") + ")" : "")));
    if (!cs().finalized) {
      const rm = el("button", "", "entfernen");
      rm.addEventListener("click", () => send("missing_remove", { mark_id: id }).then(renderMarks));
      li.append(document.createTextNode(" "), rm);
    }
    ul.append(li);
  }
}

function renderStatus() {
  const total = S.pkg.cases.length;
  const closed = S.pkg.cases.filter((c) => S.state[c].finalized).length;
  $("progressText").textContent = closed + " / " + total + " abgeschlossen";
  $("meterFill").style.width = (100 * closed / Math.max(1, total)) + "%";
  const sel = $("caseSelect");
  [...sel.options].forEach((o) => {
    const s = S.state[o.value];
    o.textContent = (s.finalized ? "✓ " : s.events ? "… " : "  ") + o.value;
  });
  if (!S.kase) return;
  const s = cs();
  const items = s.open_items.map((x) => x.startsWith("blocks_unlabelled:") ? x.split(":")[1] + " Blöcke offen" : (OPEN_TEXT[x] || x));
  const open = $("openItems");
  open.textContent = s.finalized ? "Abgeschlossen" + (s.revised_after_reveal ? " (nach Einblick geändert: nicht blind)" : "")
    : (items.length ? "Noch offen: " + items.join(" · ") : "Alles beantwortet – kann abgeschlossen werden.");
  open.className = "open" + (s.finalized || !items.length ? " ok" : "");
  $("finalizeBtn").classList.toggle("hidden", s.finalized);
  $("finalizeBtn").disabled = items.length > 0;
  $("reopenBtn").classList.toggle("hidden", !s.finalized);
  paintBlocks();
}

// --- answers -----------------------------------------------------------------------------------------------------------------

async function label(i, v) {
  if (cs().finalized) return;
  const b = S.kase.blocks[i];
  const current = cs().blocks[String(b.index)];
  const ok = await send("label_block", { index: b.index, text_sha256: b.text_sha256, label: current === v ? null : v });
  if (ok && current !== v && i === S.focus && S.focus < S.kase.blocks.length - 1) S.focus += 1;
  paintBlocks();
}

async function allArticle() {
  if (cs().finalized) return;
  for (const b of S.kase.blocks) {
    if (!cs().blocks[String(b.index)]) {
      if (!(await send("label_block", { index: b.index, text_sha256: b.text_sha256, label: "article" }))) break;
    }
  }
  paintBlocks();
}

function choose(group, v) {
  if (cs().finalized) return;
  if (group === "title") send("title", { label: cs().title === v ? null : v }).then(renderAnswers);
  if (group === "core") {
    const same = cs().core && cs().core.value === v;
    send("core", { value: same ? null : v, reason: $("coreReason").value }).then(renderAnswers);
  }
}

function sendCompleteness(ev) {
  const v = ev.target.value;
  let values = [...document.querySelectorAll("#completeness input:checked")].map((x) => x.value);
  if (ev.target.checked && (v === "complete" || v === "not_assessable")) values = [v];
  else if (ev.target.checked) values = values.filter((x) => x !== "complete" && x !== "not_assessable");
  send("completeness", { values }).then(renderAnswers);
}

function sendPageTypes() {
  const values = [...document.querySelectorAll("#pageTypes input:checked")].map((x) => x.value);
  send("page_types", { values, other: $("pageTypeOther").value });
}

function debounced(name, fn) {
  clearTimeout(S.timers[name]);
  S.timers[name] = setTimeout(fn, 700);
}

function selectedText() {
  if (S.tab === "original") {
    const w = $("source").contentWindow;
    return w && w.getSelection ? String(w.getSelection()) : "";
  }
  return String(window.getSelection());
}

async function markMissing() {
  if (cs().finalized) return;
  const quote = selectedText().trim();
  if (!quote) { saved(false, "erst links Text markieren"); return; }
  const part = $("markPart").value || null;
  if (await send("missing_add", { quote, view: S.tab === "original" ? "original" : "page_text", part })) renderMarks();
}

async function finalize() {
  if (await send("finalize", {})) { renderAnswers(); loadMachine(); }
}

async function reopen() {
  if (!confirm("Fall wieder öffnen? Jede Änderung danach gilt als nicht blind, weil das Maschinenurteil schon gezeigt wurde.")) return;
  if (await send("reopen", {})) { renderAnswers(); renderStatus(); }
}

// --- the machine labels, after the case is closed ------------------------------------------------------------------------------

async function loadMachine() {
  let m;
  try { m = await api("/api/case/" + S.kase.case_id + "/machine"); } catch (e) { return; }
  S.state[S.kase.case_id].revealed = true;
  const labels = cs().blocks;
  document.querySelectorAll("#blocks .block").forEach((li) => {
    const b = S.kase.blocks[+li.dataset.i];
    const x = m.machine.blocks[String(b.index)];
    const box = li.querySelector(".mach");
    box.replaceChildren();
    box.append(el("span", "role " + x.role, x.role === "body" ? "BODY" : x.role === "title" ? "TITLE" : "NON_BODY"));
    if (x.reason) box.append(document.createTextNode(" " + (x.decision === "included" ? "aufgenommen: " : "ausgeschlossen: ") + x.reason));
    const human = labels[String(b.index)];
    if ((human === "article" && x.role !== "body") || (human === "foreign" && x.role === "body")) {
      box.append(el("span", "diff", human === "article" ? "← Artikeltext entfernt" : "← Fremdes behalten"));
    }
  });
  const sum = $("machineSummary");
  sum.replaceChildren();
  const core = m.machine.core || {};
  sum.append(el("div", "", "CORE (" + (core.ruleset || "?") + "): " + (core.decision === "ACCEPT" ? "ja" : "nein") +
    (core.reasons && core.reasons.length ? " – " + core.reasons.join(", ") : "")));
  sum.append(el("div", "", "BODY-Status: " + (m.machine.body_quality || "–") + " · Wörter: " + (m.machine.words ?? "–")));
  sum.append(el("div", "hint", "Ausgewählt als: " + m.component + " (" + m.stratum + ")"));
  $("machine").classList.remove("hidden");
}

// --- keys ----------------------------------------------------------------------------------------------------------------------

function onKey(ev) {
  const t = ev.target.tagName;
  if (t === "INPUT" && ev.target.type !== "checkbox" || t === "TEXTAREA" || t === "SELECT") { if (ev.key === "Escape") ev.target.blur(); return; }
  if (ev.altKey && ev.key === "ArrowRight") { ev.preventDefault(); return openCase(S.idx + 1); }
  if (ev.altKey && ev.key === "ArrowLeft") { ev.preventDefault(); return openCase(S.idx - 1); }
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
  const k = ev.key.toLowerCase();
  if (k === "?") { $("help").classList.toggle("hidden"); return; }
  if (k === "escape") { $("help").classList.add("hidden"); return; }
  if (k === "j" || ev.key === "ArrowDown") { ev.preventDefault(); S.focus = Math.min(S.kase.blocks.length - 1, S.focus + 1); paintBlocks(); }
  else if (k === "k" || ev.key === "ArrowUp") { ev.preventDefault(); S.focus = Math.max(0, S.focus - 1); paintBlocks(); }
  else if (k === "1") label(S.focus, "article");
  else if (k === "2") label(S.focus, "foreign");
  else if (k === "3") label(S.focus, "unsure");
  else if (k === "a") allArticle();
  else if (k === "m") markMissing();
  else if (k === "y") choose("core", "yes");
  else if (k === "n") choose("core", "no");
  else if (k === "u") choose("core", "unsure");
  else if (k === "f" && !cs().finalized && !$("finalizeBtn").disabled) finalize();
}

// --- start ---------------------------------------------------------------------------------------------------------------------

async function start() {
  S.pkg = await api("/api/package");
  S.state = await api("/api/state");
  const mode = $("mode");
  mode.textContent = S.pkg.diagnostic ? "DIAGNOSEMODUS – nicht blind" : "blind";
  mode.className = "mode" + (S.pkg.diagnostic ? " diag" : "");
  const sel = $("caseSelect");
  for (const c of S.pkg.cases) { const o = el("option", "", c); o.value = c; sel.append(o); }
  sel.addEventListener("change", () => openCase(S.pkg.cases.indexOf(sel.value)));
  $("prev").addEventListener("click", () => openCase(S.idx - 1));
  $("next").addEventListener("click", () => openCase(S.idx + 1));
  $("nextOpen").addEventListener("click", nextOpen);
  $("allArticle").addEventListener("click", allArticle);
  $("markBtn").addEventListener("click", markMissing);
  $("finalizeBtn").addEventListener("click", finalize);
  $("reopenBtn").addEventListener("click", reopen);
  $("helpBtn").addEventListener("click", () => $("help").classList.toggle("hidden"));
  $("helpClose").addEventListener("click", () => $("help").classList.add("hidden"));
  document.querySelectorAll("#titleChoice button").forEach((b) => b.addEventListener("click", () => choose("title", b.dataset.v)));
  document.querySelectorAll("#coreChoice button").forEach((b) => b.addEventListener("click", () => choose("core", b.dataset.v)));
  document.querySelectorAll("#completeness input").forEach((x) => x.addEventListener("change", sendCompleteness));
  $("coreReason").addEventListener("input", () => debounced("core", () => { if (cs().core) send("core", { value: cs().core.value, reason: $("coreReason").value }); }));
  $("pageTypeOther").addEventListener("input", () => debounced("types", sendPageTypes));
  $("comment").addEventListener("input", () => debounced("comment", () => send("comment", { text: $("comment").value })));
  $("tabOriginal").addEventListener("click", () => setTab("original"));
  $("tabText").addEventListener("click", () => setTab("text"));
  $("exportBtn").addEventListener("click", async () => {
    try { const r = await api("/api/export", {}); saved(true); alert("Exportiert: " + r.file + " (" + r.cases_closed + " von " + r.cases_total + " Fällen abgeschlossen)"); }
    catch (e) { saved(false, e.message); }
  });
  document.addEventListener("keydown", onKey);
  $("source").addEventListener("load", () => { try { $("source").contentDocument.addEventListener("keydown", onKey); } catch (e) { /* sandboxed */ } });
  const last = S.state._position && S.state._position.case_id;
  const firstOpen = S.pkg.cases.findIndex((c) => !S.state[c].finalized);
  await openCase(last ? S.pkg.cases.indexOf(last) : Math.max(0, firstOpen));
  if (S.pkg.torn_lines_left_out) saved(false, "eine unvollständige letzte Zeile im Log wurde übergangen");
}

function setTab(tab) {
  S.tab = tab;
  $("tabOriginal").classList.toggle("active", tab === "original");
  $("tabText").classList.toggle("active", tab === "text");
  $("source").classList.toggle("hidden", tab !== "original");
  $("pageText").classList.toggle("hidden", tab === "original");
}

document.addEventListener("DOMContentLoaded", () => start().catch((e) => saved(false, e.message)));
