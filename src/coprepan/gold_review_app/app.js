// CO.PRE.PAN gold review client (CPD-0044, codebook gold-body-codebook/1). The text view is docview/1 -- model-independent; no
// machine output exists in a gold package. Every text is set with textContent. Every answer goes to the local server at once and
// is stored there as an event; the client keeps no judgment of its own.
"use strict";

const LABELS = [
  ["body", "B", "Artikeltext"], ["title", "T", "Titel"], ["standfirst", "V", "Vorspann"], ["caption", "C", "Bildunterschrift"],
  ["embed", "E", "Einbettung"], ["foreign", "F", "fremd"], ["unsure", "U", "unsicher"],
];
const KEY_LABEL = Object.fromEntries(LABELS.map(([v, k]) => [k.toLowerCase(), v]));
const LABEL_NAME = Object.fromEntries(LABELS.map(([v, , n]) => [v, n]));
const SOURCE = { complete: "vollständig sichtbar", truncated: "abgeschnitten (Paywall / Teaser)",
  not_visible: "nicht sichtbar (nur in Skripten oder Daten)", not_an_article_page: "keine Artikelseite", not_assessable: "nicht beurteilbar" };
const OUTSIDE = { beginning: "Anfang", middle: "Mitte", end: "Ende" };
const CORE = { yes: "ja", no: "nein", unsure: "unsicher" };
const REASONS = { too_short: "zu kurz", not_an_article: "kein Artikel", live_or_updates: "Live / Updates", list_or_service: "Liste / Service",
  mostly_structured: "überwiegend Tabellen / Listen", paywall_or_truncated: "Paywall / abgeschnitten", sponsored: "bezahlter Inhalt",
  not_editorial: "nicht redaktionell", not_spanish: "nicht Spanisch", other: "anderes" };
const PAGE_TYPES = {
  news_report: "Nachricht / Bericht", opinion: "Meinung / Kolumne", interview: "Interview", feature: "Reportage / Feature",
  live_ticker: "Live-Ticker", preview_or_service: "Vorschau / Service", recipe_or_howto: "Rezept / Anleitung",
  sports_with_tables: "Sportbericht mit Tabellen", list_or_ranking: "Liste / Ranking", gallery_or_video: "Galerie / Video",
  agency_wire: "Agenturmeldung", sponsored_or_press_release: "Gesponsert / Pressemitteilung", paywall_or_teaser: "Paywall / Teaser",
  section_or_index_page: "Rubrik- / Übersichtsseite", not_an_article: "kein Artikel",
};
const GROUP_MIN = 3;

const S = { pkg: null, state: null, idx: 0, kase: null, focus: 0, anchor: 0, sel: [0, 0], open: new Set(), tab: "original", timers: {} };
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
  $("saveState").textContent = ok ? "gespeichert ✓" : "Fehler: " + message;
  $("saveState").className = ok ? "save" : "save err";
}

function cs() { return S.state[S.kase.case_id]; }
function locked() { return S.pkg.frozen || cs().finalized; }
function segs() { return S.kase.view.segments; }

async function send(kind, payload) {
  try {
    const r = await api("/api/event", { kind, case_id: S.kase.case_id, payload: payload || {} });
    S.state[S.kase.case_id] = r.case;
    saved(true);
    renderStatus();
    return true;
  } catch (e) {
    saved(false, e.message);
    return false;
  }
}

async function rangeDigest(a, b) {
  const text = segs().slice(a, b + 1).map((s) => s.sha256).join("\n");
  const buf = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(text));
  return [...new Uint8Array(buf)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

// --- navigation --------------------------------------------------------------------------------------------------------------

async function openCase(i) {
  if (S.kase) await flushTexts();                       // a text typed in the case being left is saved there, never in the next
  S.idx = Math.max(0, Math.min(S.pkg.cases.length - 1, i));
  const cid = S.pkg.cases[S.idx];
  S.kase = await api("/api/case/" + cid);
  S.focus = 0; S.anchor = 0; S.sel = [0, 0]; S.open = new Set();
  $("caseSelect").value = cid;
  render();
  if (!S.pkg.frozen) api("/api/event", { kind: "position", case_id: cid, payload: {} }).catch(() => {});
  const h1 = segs().findIndex((s) => s.tag === "h1");
  if (h1 >= 0) { setFocus(h1, false); scrollToSeg(h1); } else { $("view").parentElement.scrollTop = 0; }
}

function nextOpen() {
  const n = S.pkg.cases.length;
  for (let k = 1; k <= n; k++) {
    const j = (S.idx + k) % n;
    if (!S.state[S.pkg.cases[j]].finalized) return openCase(j);
  }
}

// --- the text view ----------------------------------------------------------------------------------------------------------

function groups() {
  // runs of navigation / footer / selection-list segments, folded by default (presentation only; every text stays reachable)
  const out = [];
  const g = (s) => s.flags.includes("nav") || s.flags.includes("footer") || s.tag === "select";
  let i = 0;
  const list = segs();
  while (i < list.length) {
    if (g(list[i])) {
      let j = i;
      while (j + 1 < list.length && g(list[j + 1])) j++;
      if (j - i + 1 >= GROUP_MIN) out.push([i, j]);
      i = j + 1;
    } else i++;
  }
  return out;
}

function render() {
  const c = S.kase;
  $("caseId").textContent = c.case_id;
  $("outlet").textContent = c.outlet_id;
  $("country").textContent = c.country_id;
  $("url").textContent = c.url;
  $("fetched").textContent = (c.fetched_at || "–").slice(0, 16).replace("T", " ");
  $("source").src = "/api/case/" + c.case_id + "/source";
  $("statedHeadline").textContent = c.stated.headline || "–";
  $("statedDescription").textContent = c.stated.description || "–";
  $("statedBody").textContent = c.stated.article_body || "– (keine Angabe)";
  renderView();
  $("restConfirmed").checked = cs().finalized;
  renderQuestions();
  renderStatus();
}

function renderView() {
  const view = $("view");
  view.replaceChildren();
  const gs = groups();
  const groupAt = new Map(gs.map(([a, b]) => [a, b]));
  const list = segs();
  for (let i = 0; i < list.length; i++) {
    if (groupAt.has(i) && !S.open.has(i)) {
      const a = i, b = groupAt.get(i);                 // the loop variable moves on below; the handlers keep the group's own bounds
      const row = el("div", "group", "▸ " + (list[a].flags.includes("footer") ? "Fußzeile" : list[a].tag === "select" ? "Auswahlliste" : "Navigation")
        + " · " + (b - a + 1) + " Segmente (" + (a + 1) + "–" + (b + 1) + ") – klicken: auswählen · Doppelklick: ausklappen");
      row.dataset.from = a; row.dataset.to = b;
      row.addEventListener("click", () => { S.anchor = a; S.sel = [a, b]; S.focus = a; paint(); });
      row.addEventListener("dblclick", () => { S.open.add(a); renderView(); });
      view.append(row);
      i = b;
      continue;
    }
    view.append(segRow(i));
  }
  paint();
}

function segRow(i) {
  const s = segs()[i];
  const row = el("div", "seg" + (s.flags.includes("hidden") ? " hiddenseg" : ""));
  row.dataset.i = i;
  row.append(el("div", "n", String(i + 1)));
  const box = el("div", "c");
  box.append(el("span", "meta2", s.tag + (s.flags.length ? " · " + s.flags.join(" ") : "") + (s.link_share >= 0.5 ? " · link" : "")));
  const t = el("div", "t");
  t.dataset.i = i;
  fillText(t, i);
  box.append(t);
  row.append(box);
  row.addEventListener("click", (ev) => {
    if (String(window.getSelection()).length) return;              // a text selection inside the segment: a span, not a range
    if (ev.shiftKey) { S.sel = [Math.min(S.anchor, i), Math.max(S.anchor, i)]; S.focus = i; }
    else { S.anchor = i; S.sel = [i, i]; S.focus = i; }
    paint();
  });
  return row;
}

function fillText(t, i) {
  const s = segs()[i];
  const spans = Object.entries(cs().spans).filter(([, sp]) => sp.segment === i);
  t.replaceChildren();
  if (!spans.length) { t.textContent = s.text; return; }
  const lab = new Array(s.text.length).fill(null);
  for (const [, sp] of spans) for (let k = sp.start; k < Math.min(sp.end, s.text.length); k++) lab[k] = sp.label;
  let k = 0;
  while (k < s.text.length) {
    let j = k;
    while (j + 1 < s.text.length && lab[j + 1] === lab[k]) j++;
    const piece = s.text.slice(k, j + 1);
    if (lab[k] === null) t.append(document.createTextNode(piece));
    else { const sp = el("span", "sp l-" + lab[k], piece); sp.title = LABEL_NAME[lab[k]] + " (Teilspanne)"; t.append(sp); }
    k = j + 1;
  }
}

function paint() {
  const labels = cs().labels;
  document.querySelectorAll("#view .seg").forEach((row) => {
    const i = +row.dataset.i;
    const v = labels[String(i)];
    row.classList.remove(...[...row.classList].filter((c) => c.startsWith("l-") || c === "sel" || c === "focus"));
    if (v) row.classList.add("l-" + v);
    if (i >= S.sel[0] && i <= S.sel[1]) row.classList.add("sel");
    if (i === S.focus) row.classList.add("focus");
  });
  document.querySelectorAll("#view .group").forEach((row) => {
    const a = +row.dataset.from, b = +row.dataset.to;
    const ls = new Set(); for (let i = a; i <= b; i++) if (labels[String(i)]) ls.add(labels[String(i)]);
    row.classList.toggle("labelled", ls.size > 0);
    row.style.outline = (S.sel[0] <= a && S.sel[1] >= b) ? "2px solid #1f5fa8" : "";
  });
  const n = S.sel[1] - S.sel[0] + 1;
  $("selInfo").textContent = "Auswahl: Segment " + (S.sel[0] + 1) + (n > 1 ? "–" + (S.sel[1] + 1) + " (" + n + ")" : "");
  let words = 0;
  segs().forEach((s, i) => { if (labels[String(i)] === "body") words += s.text.split(/\s+/).filter(Boolean).length; });
  $("counts").textContent = "· " + segs().length + " Segmente · als Artikeltext markiert: " + words + " Wörter";
}

function setFocus(i, extend) {
  S.focus = Math.max(0, Math.min(segs().length - 1, i));
  if (extend) S.sel = [Math.min(S.anchor, S.focus), Math.max(S.anchor, S.focus)];
  else { S.anchor = S.focus; S.sel = [S.focus, S.focus]; }
  const g = groups().find(([a, b]) => S.focus >= a && S.focus <= b && !S.open.has(a));
  if (g) { S.open.add(g[0]); renderView(); }
  paint();
}

function scrollToSeg(i) {
  const row = document.querySelector('#view .seg[data-i="' + i + '"]');
  if (row) row.scrollIntoView({ block: "center" });
}

// --- labelling ----------------------------------------------------------------------------------------------------------------

function textSelection() {
  const sel = window.getSelection();
  if (!sel || sel.isCollapsed || !sel.rangeCount) return null;
  const range = sel.getRangeAt(0);
  const t1 = (range.startContainer.nodeType === 1 ? range.startContainer : range.startContainer.parentElement).closest(".t");
  const t2 = (range.endContainer.nodeType === 1 ? range.endContainer : range.endContainer.parentElement).closest(".t");
  if (!t1 || t1 !== t2) return { error: "Eine Teilspanne liegt in einem einzigen Segment." };
  const pre = document.createRange();
  pre.selectNodeContents(t1);
  pre.setEnd(range.startContainer, range.startOffset);
  const start = pre.toString().length;
  const end = start + range.toString().length;
  return { segment: +t1.dataset.i, start, end };
}

async function applyLabel(label) {
  if (locked()) return;
  const span = textSelection();
  if (span && span.error) { saved(false, span.error); return; }
  if (span) {
    const s = segs()[span.segment];
    if (label === null) {
      const hit = Object.entries(cs().spans).filter(([, sp]) => sp.segment === span.segment && sp.start < span.end && sp.end > span.start);
      for (const [id] of hit) await send("span_remove", { span_id: id });
    } else if (span.start === 0 && span.end >= s.text.length) {
      await sendRange(span.segment, span.segment, label);                    // the whole segment: a segment label
    } else {
      await send("span_add", { segment: span.segment, sha256: s.sha256, start: span.start, end: span.end, label });
    }
    window.getSelection().removeAllRanges();
    const t = document.querySelector('#view .t[data-i="' + span.segment + '"]');
    if (t) fillText(t, span.segment);
    paint();
    return;
  }
  await sendRange(S.sel[0], S.sel[1], label);
  paint();
}

async function sendRange(a, b, label) {
  const digest = await rangeDigest(a, b);
  return send("label_range", { from: a, to: b, digest, label });
}

function jumpOpen() {
  const labels = cs().labels;
  const list = segs();
  for (let k = 1; k <= list.length; k++) {
    const i = (S.focus + k) % list.length;
    if (!labels[String(i)] && list[i].text.split(/\s+/).length >= 8) { setFocus(i, false); scrollToSeg(i); return; }
  }
  saved(true);
  $("saveState").textContent = "kein unmarkiertes längeres Segment";
}

function findFromOriginal() {
  let text = "";
  try { text = String($("source").contentWindow.getSelection()); } catch (e) { text = ""; }
  const needle = text.replace(/\s+/g, " ").trim().toLowerCase().slice(0, 80);
  if (!needle) { saved(false, "erst im Original Text markieren"); return; }
  const i = segs().findIndex((s) => s.text.toLowerCase().includes(needle));
  if (i < 0) { saved(false, "nicht in der Textansicht gefunden – ggf. unter „Text außerhalb der Textansicht“ angeben"); return; }
  setFocus(i, false);
  scrollToSeg(i);
  const row = document.querySelector('#view .seg[data-i="' + i + '"]');
  if (row) { row.classList.add("find"); setTimeout(() => row.classList.remove("find"), 1800); }
}

// --- case questions -------------------------------------------------------------------------------------------------------------

function radios(box, map, current, onPick) {
  box.replaceChildren();
  for (const [v, name] of Object.entries(map)) {
    const b = el("button", current === v ? "on" : "", name);
    b.dataset.v = v;
    b.disabled = locked();
    b.addEventListener("click", () => onPick(current === v ? null : v));
    box.append(b);
  }
}

function checks(box, map, current, onChange) {
  box.replaceChildren();
  for (const [v, name] of Object.entries(map)) {
    const l = el("label");
    const x = el("input");
    x.type = "checkbox"; x.value = v; x.checked = current.includes(v); x.disabled = locked();
    x.addEventListener("change", () => onChange([...box.querySelectorAll("input:checked")].map((y) => y.value)));
    l.append(x, document.createTextNode(" " + name));
    box.append(l);
  }
}

function renderQuestions() {
  const s = cs();
  radios($("sourceState"), SOURCE, s.source_state, (v) => send("source_state", { value: v }).then(renderQuestions));
  checks($("outsideParts"), OUTSIDE, s.outside_view.parts, (parts) => send("outside_view", { parts, note: $("outsideNote").value }));
  $("outsideNote").value = s.outside_view.note || "";
  radios($("coreChoice"), CORE, s.core && s.core.value, (v) => send("core", { value: v, reasons: s.core ? s.core.reasons : [], note: $("coreNote").value }).then(renderQuestions));
  checks($("coreReasons"), REASONS, s.core ? s.core.reasons : [], (reasons) => {
    if (!cs().core) { saved(false, "erst ja / nein / unsicher wählen"); renderQuestions(); return; }
    send("core", { value: cs().core.value, reasons, note: $("coreNote").value });
  });
  $("coreNote").value = s.core ? s.core.note : "";
  checks($("pageTypes"), PAGE_TYPES, s.page_types.values, (values) => send("page_types", { values, other: $("pageTypeOther").value }));
  $("pageTypeOther").value = s.page_types.other || "";
  $("comment").value = s.comment || "";
  for (const id of ["outsideNote", "coreNote", "pageTypeOther", "comment", "restConfirmed"]) $(id).disabled = locked();
  if (s.finalized) $("restConfirmed").checked = true;
}

function renderStatus() {
  const total = S.pkg.cases.length;
  const closed = S.pkg.cases.filter((c) => S.state[c].finalized).length;
  $("progressText").textContent = closed + " / " + total + " abgeschlossen";
  $("meterFill").style.width = (100 * closed / Math.max(1, total)) + "%";
  [...$("caseSelect").options].forEach((o) => {
    const s = S.state[o.value];
    o.textContent = (s.finalized ? "✓ " : s.events ? "… " : "  ") + o.value;
  });
  if (!S.kase) return;
  const s = cs();
  const items = s.open_items.map((x) => ({ source_state: "Quelle angeben", core: "CORE beantworten", core_reason: "CORE-Grund fehlt" })[x] || x);
  if (!s.finalized && !$("restConfirmed").checked) items.push("Rest bestätigen");
  const open = $("openItems");
  open.textContent = s.finalized ? "Abgeschlossen" + (s.reopened ? " (wieder geöffnet: " + s.reopened + "×)" : "")
    : (items.length ? "Noch offen: " + items.join(" · ") : "Kann abgeschlossen werden.");
  open.className = "open" + (s.finalized || !items.length ? " ok" : "");
  $("finalizeBtn").classList.toggle("hidden", s.finalized || S.pkg.frozen);
  $("finalizeBtn").disabled = items.length > 0;
  $("reopenBtn").classList.toggle("hidden", !s.finalized || S.pkg.frozen);
  document.querySelectorAll("#labelButtons button").forEach((b) => { b.disabled = locked(); });
}

async function finalize() {
  await flushTexts();
  if (!$("restConfirmed").checked) { saved(false, "erst bestätigen, dass der unmarkierte Rest kein Artikeltext ist"); return; }
  if (await send("finalize", { rest_confirmed: true })) { renderQuestions(); renderStatus(); paint(); }
}

async function reopen() {
  if (!confirm("Fall wieder öffnen? Die Korrektur wird im Ereignisprotokoll festgehalten.")) return;
  if (await send("reopen", {})) { renderQuestions(); renderStatus(); }
}

function debounced(name, fn) {
  clearTimeout(S.timers[name]);
  S.pending = S.pending || {};
  S.pending[name] = fn;
  S.timers[name] = setTimeout(() => { delete S.pending[name]; fn(); }, 700);
}

async function flushTexts() {
  // a text typed a moment ago is saved before the case is closed or left
  const pending = Object.entries(S.pending || {});
  S.pending = {};
  for (const [name, fn] of pending) { clearTimeout(S.timers[name]); await fn(); }
}

// --- keys ----------------------------------------------------------------------------------------------------------------------

function onKey(ev) {
  const t = ev.target.tagName;
  if ((ev.ctrlKey || ev.metaKey) && ev.key === "Enter") {             // closing works from a text field as well
    ev.preventDefault();
    flushTexts().then(() => { if (!$("finalizeBtn").disabled) finalize(); });
    return;
  }
  if ((t === "INPUT" && ev.target.type !== "checkbox") || t === "TEXTAREA" || t === "SELECT") {
    if (ev.key === "Escape") ev.target.blur();
    return;
  }
  if (ev.altKey && ev.key === "ArrowRight") { ev.preventDefault(); return openCase(S.idx + 1); }
  if (ev.altKey && ev.key === "ArrowLeft") { ev.preventDefault(); return openCase(S.idx - 1); }
  if (ev.ctrlKey || ev.metaKey || ev.altKey) return;
  const k = ev.key.toLowerCase();
  if (k === "?") { $("help").classList.toggle("hidden"); return; }
  if (k === "escape") { $("help").classList.add("hidden"); window.getSelection().removeAllRanges(); return; }
  if (k === "j" || ev.key === "ArrowDown") { ev.preventDefault(); setFocus(S.focus + 1, ev.shiftKey); scrollToSeg(S.focus); }
  else if (k === "k" || ev.key === "ArrowUp") { ev.preventDefault(); setFocus(S.focus - 1, ev.shiftKey); scrollToSeg(S.focus); }
  else if (k in KEY_LABEL) { ev.preventDefault(); applyLabel(KEY_LABEL[k]); }
  else if (k === "x" || ev.key === "Backspace" || ev.key === "Delete") { ev.preventDefault(); applyLabel(null); }
  else if (k === "g") { const h = segs().findIndex((s) => s.tag === "h1"); if (h >= 0) { setFocus(h, false); scrollToSeg(h); } }
  else if (k === "n") jumpOpen();
  else if (k === "s") findFromOriginal();
  else if (k === "q") $("questions").scrollIntoView({ block: "start" });
}

// --- start ---------------------------------------------------------------------------------------------------------------------

async function start() {
  S.pkg = await api("/api/package");
  S.state = await api("/api/state");
  $("kind").textContent = { HOLDOUT: "Validierung", PRACTICE: "ÜBUNG – kein Gold", DIAGNOSTIC: "Diagnose – nicht unabhängig" }[S.pkg.kind] || S.pkg.kind;
  $("kind").className = "kind " + S.pkg.kind;
  $("codebookId").textContent = S.pkg.codebook;
  const banner = S.pkg.frozen ? "Das Gold dieses Pakets ist eingefroren – nur Ansicht."
    : S.pkg.kind === "PRACTICE" ? "Übungspaket: zum Kennenlernen der Oberfläche. Diese Urteile werden nie als Gold verwendet." : "";
  if (banner) { $("banner").textContent = banner; $("banner").classList.remove("hidden"); }
  const sel = $("caseSelect");
  for (const c of S.pkg.cases) { const o = el("option", "", c); o.value = c; sel.append(o); }
  sel.addEventListener("change", () => openCase(S.pkg.cases.indexOf(sel.value)));
  for (const [v, k, name] of LABELS) {
    const b = el("button", "");
    b.append(el("span", "k", k), document.createTextNode(name));
    b.title = name + " (" + k + ")";
    b.addEventListener("mousedown", (e) => e.preventDefault());               // keep a text selection alive while clicking
    b.addEventListener("click", () => applyLabel(v));
    $("labelButtons").append(b);
  }
  const clear = el("button", "", "X löschen");
  clear.addEventListener("mousedown", (e) => e.preventDefault());
  clear.addEventListener("click", () => applyLabel(null));
  $("labelButtons").append(clear);
  $("prev").addEventListener("click", () => openCase(S.idx - 1));
  $("next").addEventListener("click", () => openCase(S.idx + 1));
  $("nextOpen").addEventListener("click", nextOpen);
  $("jumpH1").addEventListener("click", () => onKey({ key: "g", target: document.body, preventDefault() {} }));
  $("jumpOpen").addEventListener("click", jumpOpen);
  $("toQuestions").addEventListener("click", () => $("questions").scrollIntoView({ block: "start" }));
  $("findBtn").addEventListener("click", findFromOriginal);
  $("finalizeBtn").addEventListener("click", finalize);
  $("reopenBtn").addEventListener("click", reopen);
  $("restConfirmed").addEventListener("change", renderStatus);
  $("helpBtn").addEventListener("click", () => $("help").classList.toggle("hidden"));
  $("helpClose").addEventListener("click", () => $("help").classList.add("hidden"));
  $("tabOriginal").addEventListener("click", () => setTab("original"));
  $("tabStated").addEventListener("click", () => setTab("stated"));
  $("outsideNote").addEventListener("input", () => debounced("outside", () => send("outside_view", { parts: cs().outside_view.parts, note: $("outsideNote").value })));
  $("coreNote").addEventListener("input", () => debounced("core", () => { if (cs().core) send("core", { value: cs().core.value, reasons: cs().core.reasons, note: $("coreNote").value }); }));
  $("pageTypeOther").addEventListener("input", () => debounced("types", () => send("page_types", { values: cs().page_types.values, other: $("pageTypeOther").value })));
  $("comment").addEventListener("input", () => debounced("comment", () => send("comment", { text: $("comment").value })));
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
  $("tabStated").classList.toggle("active", tab === "stated");
  $("source").classList.toggle("hidden", tab !== "original");
  $("stated").classList.toggle("hidden", tab !== "stated");
}

window.GOLD_REVIEW = S;     // for the browser check script only (read access to the client state)
document.addEventListener("DOMContentLoaded", () => start().catch((e) => saved(false, e.message)));
