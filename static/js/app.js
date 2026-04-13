/**
 * VoiceBridge AI — app.js
 * Features: Voice, Auto-translate, Batch, Document, RAG, Meeting Notes, History search, CSV export
 */
"use strict";
const $ = id => document.getElementById(id);

// ── DOM ───────────────────────────────────────────────────────────────────
const recordBtn      = $("recordBtn");
const recordLabel    = $("recordLabel");
const origText       = $("origText");
const transText      = $("transText");
const translateBtn   = $("translateBtn");
const confidenceBtn  = $("confidenceBtn");
const fromLang       = $("fromLang");
const toLang         = $("toLang");
const swapBtn        = $("swapBtn");
const clearBtn       = $("clearBtn");
const copyOrigBtn    = $("copyOrigBtn");
const copyTransBtn   = $("copyTransBtn");
const speakTransBtn  = $("speakTransBtn");
const sendToRagBtn   = $("sendToRagBtn");
const exportPdfBtn   = $("exportPdfBtn");
const improveBtn     = $("improveBtn");
const detectLangBtn  = $("detectLangBtn");
const uploadAudioBtn = $("uploadAudioBtn");
const audioFileInput = $("audioFileInput");
const statusBar      = $("statusBar");
const waveViz        = $("waveViz");
const origPanel      = $("origPanel");
const charCount      = $("charCount");
const latencyTag     = $("latencyTag");
const qualityBadge   = $("qualityBadge");
const confidenceResult = $("confidenceResult");
const loadingOverlay = $("loadingOverlay");
const loadingText    = $("loadingText");
const themeBtn       = $("themeBtn");
const userAvatar     = $("userAvatar");
const userDropdown   = $("userDropdown");

// ── State ─────────────────────────────────────────────────────────────────
let recognition    = null;
let isRecording    = false;
let ragSessionId   = null;
let sumStyle       = "detailed";
let autoTransTimer = null;
let allHistory     = [];
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// ── Theme ─────────────────────────────────────────────────────────────────
const root = document.documentElement;
const savedTheme = localStorage.getItem("vb_theme") || "light";
applyTheme(savedTheme);

function applyTheme(theme) {
  root.setAttribute("data-theme", theme);
  if (themeBtn) themeBtn.textContent = theme === "dark" ? "☀️" : "🌙";
  localStorage.setItem("vb_theme", theme);
  fetch("/api/auth/theme", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ theme })
  }).catch(() => {});
}
themeBtn?.addEventListener("click", () =>
  applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark")
);

// ── User menu ─────────────────────────────────────────────────────────────
userAvatar?.addEventListener("click", e => {
  e.stopPropagation();
  userDropdown?.classList.toggle("open");
});
document.addEventListener("click", () => userDropdown?.classList.remove("open"));

// ── Tabs ──────────────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    $("tab-" + tab.dataset.tab)?.classList.add("active");
    if (tab.dataset.tab === "history") loadHistory();
  });
});

// ── Helpers ───────────────────────────────────────────────────────────────
function setStatus(msg, cls = "") {
  if (!statusBar) return;
  statusBar.textContent = msg;
  statusBar.className = "status-bar" + (cls ? " " + cls : "");
}
function showLoading(msg = "Processing…") {
  if (loadingText) loadingText.textContent = msg;
  loadingOverlay?.classList.add("active");
}
function hideLoading() { loadingOverlay?.classList.remove("active"); }
function getOrig() { return origText?.textContent.trim() || ""; }
function checkBtn() {
  const has = !!getOrig();
  if (translateBtn) translateBtn.disabled = !has;
  if (confidenceBtn) confidenceBtn.disabled = !has;
}
function esc(s) {
  return String(s || "").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}
function copyText(text, btn) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const o = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => btn.textContent = o, 1500);
  });
}
function showSkeleton() {
  if (!transText) return;
  transText.innerHTML = `
    <div class="skeleton" style="width:88%"></div>
    <div class="skeleton" style="width:72%"></div>
    <div class="skeleton" style="width:55%"></div>
  `;
}
function setQuality(score) {
  if (!qualityBadge || score == null || score < 0) return;
  qualityBadge.classList.remove("hidden","excellent","good","fair","poor");
  let label, cls;
  if (score >= 0.80)      { label = "Excellent"; cls = "excellent"; }
  else if (score >= 0.65) { label = "Good";      cls = "good"; }
  else if (score >= 0.50) { label = "Fair";      cls = "fair"; }
  else                    { label = "Poor";       cls = "poor"; }
  qualityBadge.textContent = label;
  qualityBadge.classList.add(cls);
}

// ── Voice recording ───────────────────────────────────────────────────────
if (!SpeechRecognition && recordBtn) {
  recordBtn.disabled = true;
  setStatus("Voice input needs Chrome or Edge", "error");
}

recordBtn?.addEventListener("click", () => isRecording ? stopRec() : startRec());

function startRec() {
  recognition = new SpeechRecognition();
  recognition.lang           = fromLang.value;
  recognition.continuous     = false;
  recognition.interimResults = true;

  recognition.onstart = () => {
    isRecording = true;
    recordBtn.classList.add("recording");
    origPanel?.classList.add("recording");
    waveViz?.classList.add("active");
    if (recordLabel) recordLabel.textContent = "Recording… tap to stop";
    setStatus("Listening…", "listening");
    origText.textContent = "";
    charCount.textContent = "0";
  };
  recognition.onresult = e => {
    let final = "", interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      e.results[i].isFinal
        ? (final   += e.results[i][0].transcript)
        : (interim += e.results[i][0].transcript);
    }
    origText.textContent = final || interim;
    charCount.textContent = origText.textContent.length;
    checkBtn();
  };
  recognition.onerror = e => {
    stopRec();
    const msgs = { "not-allowed": "Mic permission denied", "no-speech": "No speech detected" };
    setStatus(msgs[e.error] || `Error: ${e.error}`, "error");
  };
  recognition.onend = () => {
    stopRec();
    if (getOrig()) {
      setStatus("Done — translating…", "success");
      doTranslate();  // auto-translate after speaking
    }
  };
  recognition.start();
}

function stopRec() {
  isRecording = false;
  recordBtn?.classList.remove("recording");
  origPanel?.classList.remove("recording");
  waveViz?.classList.remove("active");
  if (recordLabel) recordLabel.textContent = "Tap to speak";
  try { recognition?.stop(); } catch (_) {}
}

// ── Auto-translate on typing (debounced 900ms) ────────────────────────────
origText?.addEventListener("input", () => {
  const len = origText.textContent.length;
  if (charCount) charCount.textContent = len;
  checkBtn();
  clearTimeout(autoTransTimer);
  if (len > 15) {
    autoTransTimer = setTimeout(doTranslate, 900);
  }
});

origText?.addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault();
    clearTimeout(autoTransTimer);
    doTranslate();
  }
});

// ── Translate ─────────────────────────────────────────────────────────────
translateBtn?.addEventListener("click", () => {
  clearTimeout(autoTransTimer);
  doTranslate();
});

async function doTranslate() {
  const text = getOrig();
  if (!text || text.length < 2) return;

  const src = fromLang?.options[fromLang.selectedIndex]?.dataset?.code || "auto";
  const tgt = toLang?.value || "en";

  setStatus("Translating…", "working");
  showSkeleton();
  if (latencyTag) latencyTag.textContent = "";
  if (qualityBadge) qualityBadge.classList.add("hidden");

  try {
    const res  = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source_lang: src, target_lang: tgt })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Translation failed");

    transText.innerHTML = "";
    transText.textContent = data.translated;

    if (data.latency_ms) {
      latencyTag.textContent = `${data.latency_ms}ms`;
    }
    if (data.quality_score != null) {
      setQuality(data.quality_score);
    }
    setStatus("✓ Translated", "success");
  } catch (err) {
    transText.innerHTML = "";
    setStatus(`Error: ${err.message}`, "error");
  }
}

// ── Translate with confidence ─────────────────────────────────────────────
confidenceBtn?.addEventListener("click", async () => {
  const text = getOrig();
  if (!text) return;
  const src = fromLang?.options[fromLang.selectedIndex]?.dataset?.code || "auto";
  const tgt = toLang?.value || "en";

  showLoading("Analysing translation confidence…");
  try {
    const res  = await fetch("/api/translate-with-confidence", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source_lang: src, target_lang: tgt })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    transText.textContent = data.translation || "";
    renderConfidence(data);
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

function renderConfidence(data) {
  if (!confidenceResult) return;
  confidenceResult.classList.remove("hidden");
  $("confScore").textContent = `${data.confidence}/10`;

  const scoreColor = data.confidence >= 8 ? "#10b981" : data.confidence >= 6 ? "#0ea5e9" : "#f59e0b";
  $("confScore").style.color = scoreColor;

  if ($("confReason")) $("confReason").textContent = data.confidence_reason || "";

  const amb = $("confAmbiguous");
  if (amb && data.ambiguous_phrases?.length) {
    amb.classList.remove("hidden");
    amb.innerHTML = `⚠ Ambiguous: ${data.ambiguous_phrases.map(p => `<strong>${esc(p)}</strong>`).join(", ")}`;
  } else {
    amb?.classList.add("hidden");
  }

  const notes = $("confNotes");
  if (notes && data.notes) {
    notes.classList.remove("hidden");
    notes.textContent = `ℹ ${data.notes}`;
  } else {
    notes?.classList.add("hidden");
  }

  const sim = $("confSimilarity");
  if (sim && data.semantic_similarity != null && data.semantic_similarity >= 0) {
    sim.classList.remove("hidden");
    sim.textContent = `Semantic similarity: ${(data.semantic_similarity * 100).toFixed(1)}%`;
  } else {
    sim?.classList.add("hidden");
  }
}

// ── Upload audio → Whisper ────────────────────────────────────────────────
uploadAudioBtn?.addEventListener("click", () => audioFileInput?.click());
audioFileInput?.addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("audio", file);
  const src = fromLang?.options[fromLang.selectedIndex]?.dataset?.code || "";
  if (src) fd.append("lang", src);
  showLoading("Transcribing with Whisper ASR…");
  try {
    const res  = await fetch("/api/transcribe", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    origText.textContent = data.text;
    charCount.textContent = data.text.length;
    checkBtn();
    setStatus("Transcription done — translating…", "success");
    doTranslate();
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
    audioFileInput.value = "";
  }
});

// ── Other translate panel buttons ─────────────────────────────────────────
swapBtn?.addEventListener("click", () => {
  const fromCode = fromLang?.options[fromLang.selectedIndex]?.dataset?.code;
  const toCode   = toLang?.value;
  const m = { en:"en-US",hi:"hi-IN",es:"es-ES",fr:"fr-FR",de:"de-DE",ta:"ta-IN",te:"te-IN",bn:"bn-IN",ja:"ja-JP",zh:"zh-CN",ar:"ar-SA",pt:"pt-BR",ru:"ru-RU",ko:"ko-KR" };
  const opt = [...(fromLang?.options||[])].find(o => o.value === m[toCode]);
  if (opt) fromLang.value = opt.value;
  if ([...(toLang?.options||[])].some(o => o.value === fromCode)) toLang.value = fromCode;
  const tmpO = getOrig(), tmpT = transText?.textContent.trim() || "";
  origText.textContent = tmpT;
  if (transText) transText.textContent = tmpO;
  charCount.textContent = tmpT.length;
  checkBtn();
});

clearBtn?.addEventListener("click", () => {
  origText.textContent = "";
  if (transText) transText.textContent = "";
  translateBtn.disabled = confidenceBtn.disabled = true;
  charCount.textContent = "0";
  latencyTag.textContent = "";
  qualityBadge?.classList.add("hidden");
  confidenceResult?.classList.add("hidden");
  setStatus("");
  clearTimeout(autoTransTimer);
});

copyOrigBtn?.addEventListener("click",  () => copyText(getOrig(), copyOrigBtn));
copyTransBtn?.addEventListener("click", () => copyText(transText?.textContent.trim(), copyTransBtn));

speakTransBtn?.addEventListener("click", () => {
  const t = transText?.textContent.trim();
  if (!t || !window.speechSynthesis) return;
  const bcp = { en:"en-US",hi:"hi-IN",es:"es-ES",fr:"fr-FR",de:"de-DE",ta:"ta-IN",te:"te-IN",bn:"bn-IN",ja:"ja-JP",zh:"zh-CN",ar:"ar-SA",pt:"pt-BR",ru:"ru-RU",ko:"ko-KR" };
  const u = new SpeechSynthesisUtterance(t);
  u.lang = bcp[toLang?.value] || (toLang?.value || "en");
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  speakTransBtn.textContent = "Speaking…";
  u.onend = () => { speakTransBtn.textContent = "▶ Speak"; };
});

sendToRagBtn?.addEventListener("click", () => {
  const t = getOrig();
  if (!t) return;
  const ri = $("ragInput"), si = $("sumInput"), mi = $("meetingInput");
  if (ri) ri.value = t;
  if (si) si.value = t;
  if (mi) mi.value = t;
  document.querySelector('[data-tab="rag"]')?.click();
});

exportPdfBtn?.addEventListener("click", async () => {
  const orig  = getOrig();
  const trans = transText?.textContent.trim() || "";
  if (!orig && !trans) return setStatus("Nothing to export", "error");
  showLoading("Generating PDF…");
  try {
    const res = await fetch("/api/export/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ original: orig, translated: trans })
    });
    if (!res.ok) throw new Error("PDF generation failed");
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "voicebridge-export.pdf";
    a.click(); URL.revokeObjectURL(url);
    setStatus("PDF downloaded ✓", "success");
  } catch (err) {
    setStatus(`PDF error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

detectLangBtn?.addEventListener("click", async () => {
  const text = getOrig();
  if (!text) return setStatus("Type some text first", "error");
  showLoading("Detecting language…");
  try {
    const res = await fetch("/api/detect-language", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setStatus(`Detected: ${data.language.toUpperCase()}`, "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

improveBtn?.addEventListener("click", async () => {
  const text = getOrig();
  if (!text) return setStatus("Type some text first", "error");
  showLoading("Improving grammar and clarity…");
  try {
    const res = await fetch("/api/improve-text", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    origText.textContent = data.improved;
    charCount.textContent = data.improved.length;
    checkBtn();
    setStatus("Text improved ✓", "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

// ── Document Translator ───────────────────────────────────────────────────
const docDropZone  = $("docDropZone");
const docFileInput = $("docFileInput");
const docPreview   = $("docPreview");
let docContent = "";

docDropZone?.addEventListener("click", () => docFileInput?.click());
docDropZone?.addEventListener("dragover", e => { e.preventDefault(); docDropZone.classList.add("dragover"); });
docDropZone?.addEventListener("dragleave", () => docDropZone.classList.remove("dragover"));
docDropZone?.addEventListener("drop", e => {
  e.preventDefault();
  docDropZone.classList.remove("dragover");
  const file = e.dataTransfer.files[0];
  if (file) loadDocFile(file);
});
docFileInput?.addEventListener("change", e => {
  if (e.target.files[0]) loadDocFile(e.target.files[0]);
});

function loadDocFile(file) {
  if (!file.name.endsWith(".txt")) {
    alert("Only .txt files are supported");
    return;
  }
  const reader = new FileReader();
  reader.onload = e => {
    docContent = e.target.result;
    const words = docContent.split(/\s+/).length;
    $("docMeta").textContent = `📄 ${file.name}  |  ${words} words  |  ${(file.size/1024).toFixed(1)} KB`;
    $("docOrigText").textContent = docContent;
    docPreview?.classList.remove("hidden");
    docDropZone?.classList.add("hidden");
  };
  reader.readAsText(file);
}

$("docTranslateBtn")?.addEventListener("click", async () => {
  if (!docContent) return;
  const src = $("batchFromLang")?.value || "auto";
  const tgt = $("batchToLang")?.value || "en";
  showLoading("Translating document…");
  try {
    const res = await fetch("/api/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: docContent, source_lang: src, target_lang: tgt })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    $("docTransText").textContent = data.translated;
    $("docExportBtn").disabled = false;
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    hideLoading();
  }
});

$("docExportBtn")?.addEventListener("click", async () => {
  const orig  = $("docOrigText")?.textContent || "";
  const trans = $("docTransText")?.textContent || "";
  showLoading("Generating PDF…");
  try {
    const res = await fetch("/api/export/pdf", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ original: orig, translated: trans })
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "voicebridge-document.pdf";
    a.click(); URL.revokeObjectURL(url);
  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    hideLoading();
  }
});

// ── Batch Translate ───────────────────────────────────────────────────────
$("batchTranslateBtn")?.addEventListener("click", async () => {
  const input = $("batchInput")?.value.trim();
  if (!input) return;
  const lines = input.split("\n").filter(l => l.trim());
  if (!lines.length) return;

  const src = $("batchFromLang")?.value || "auto";
  const tgt = $("batchToLang")?.value || "en";
  showLoading(`Translating ${lines.length} sentences…`);

  const results = [];
  try {
    // Translate all lines together as a numbered list (one API call = fast)
    const numbered = lines.map((l, i) => `${i+1}. ${l}`).join("\n");
    const res = await fetch("/api/translate", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        text: `Translate each numbered line separately. Keep numbering:\n${numbered}`,
        source_lang: src, target_lang: tgt
      })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    // Parse numbered response
    const translatedLines = data.translated.split("\n").filter(l => l.trim());
    lines.forEach((orig, i) => {
      const transLine = translatedLines[i] || "";
      const cleaned   = transLine.replace(/^\d+\.\s*/, "");
      results.push({ original: orig, translated: cleaned });
    });

    // Render table
    $("batchCount").textContent = `${results.length} translations`;
    const tbody = $("batchTableBody");
    if (tbody) {
      tbody.innerHTML = results.map((r, i) => `
        <tr>
          <td style="color:var(--text3);font-family:'DM Mono',monospace">${i+1}</td>
          <td>${esc(r.original)}</td>
          <td>${esc(r.translated)}</td>
        </tr>
      `).join("");
    }
    $("batchResults")?.classList.remove("hidden");
    window._batchResults = results;

  } catch (err) {
    alert(`Error: ${err.message}`);
  } finally {
    hideLoading();
  }
});

$("batchExportBtn")?.addEventListener("click", () => {
  const results = window._batchResults;
  if (!results?.length) return;
  const csv = ["Original,Translation",
    ...results.map(r => `"${r.original.replace(/"/g,'""')}","${r.translated.replace(/"/g,'""')}"`)
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "voicebridge-batch.csv";
  a.click(); URL.revokeObjectURL(url);
});

// ── Summarize ─────────────────────────────────────────────────────────────
document.querySelectorAll(".style-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".style-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    sumStyle = btn.dataset.style;
  });
});

$("summarizeBtn")?.addEventListener("click", async () => {
  const text = $("sumInput")?.value.trim();
  if (!text) return;
  showLoading("Summarizing…");
  try {
    const res  = await fetch("/api/summarize", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, style: sumStyle })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    renderSummary(data);
  } catch (err) {
    const sr = $("summaryResult");
    if (sr) { sr.innerHTML = `<div style="color:var(--red)">Error: ${esc(err.message)}</div>`; sr.classList.remove("hidden"); }
  } finally {
    hideLoading();
  }
});

function renderSummary(data) {
  const sr = $("summaryResult");
  if (!sr) return;
  let html = "";
  if (data.overview)       html += `<div class="sum-overview">${esc(data.overview)}</div>`;
  if (data.topics?.length) html += `<div class="sum-section-title">Topics</div><div class="sum-tags">${data.topics.map(t=>`<span class="sum-tag">${esc(t)}</span>`).join("")}</div>`;
  if (data.key_points?.length) html += `<div class="sum-section-title">Key Points</div><ul class="sum-points">${data.key_points.map(p=>`<li>${esc(p)}</li>`).join("")}</ul>`;
  if (data.action_items?.length) html += `<div class="sum-section-title" style="margin-top:1rem">Action Items</div><ul class="sum-points">${data.action_items.map(a=>`<li>${esc(a)}</li>`).join("")}</ul>`;
  if (data.sentiment)      html += `<div style="margin-top:1rem"><span class="sentiment-badge ${data.sentiment}">${data.sentiment}</span></div>`;
  if (data.word_count)     html += `<div style="margin-top:.75rem;font-size:12px;color:var(--text3);font-family:'DM Mono',monospace">${data.word_count} words · ${data.latency_ms||"?"}ms</div>`;
  sr.innerHTML = html;
  sr.classList.remove("hidden");
}

// ── RAG ───────────────────────────────────────────────────────────────────
$("ragIndexBtn")?.addEventListener("click", async () => {
  const text = $("ragInput")?.value.trim();
  if (!text) return;
  const status = $("ragIndexStatus");
  showLoading("Embedding chunks into FAISS…");
  if (status) { status.textContent = "Indexing…"; status.className = "rag-status"; }
  try {
    const res  = await fetch("/api/rag/index", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, title: text.substring(0,60)+"…" })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    ragSessionId = data.session_id;
    if (status) { status.textContent = `✓ ${data.chunks_created} chunks indexed`; status.className = "rag-status success"; }
    const ask = $("ragAskSection");
    if (ask) { ask.style.opacity = "1"; ask.style.pointerEvents = "auto"; }
    const ch = $("ragChatHistory");
    if (ch) ch.innerHTML = "";
  } catch (err) {
    if (status) { status.textContent = `Error: ${err.message}`; status.className = "rag-status error"; }
  } finally {
    hideLoading();
  }
});

$("ragAskBtn")?.addEventListener("click", doRagAsk);
$("ragQuestion")?.addEventListener("keydown", e => { if (e.key === "Enter") doRagAsk(); });
document.querySelectorAll(".sq-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    const rq = $("ragQuestion");
    if (rq) rq.value = btn.textContent;
    doRagAsk();
  });
});

async function doRagAsk() {
  const q = $("ragQuestion")?.value.trim();
  if (!q || !ragSessionId) return;
  showLoading("Searching FAISS + generating answer…");
  try {
    const res  = await fetch("/api/rag/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, session_id: ragSessionId })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    const ch = $("ragChatHistory");
    if (ch) {
      const qEl = document.createElement("div");
      qEl.className = "chat-q"; qEl.textContent = q;
      const aEl = document.createElement("div");
      aEl.className = "chat-a";
      aEl.textContent = data.answer;

      if (data.sources?.length) {
        const src = document.createElement("div");
        src.className = "chat-sources";
        src.textContent = `Sources: ${data.sources.map(s=>`chunk #${s.rank} (${(s.relevance_score*100).toFixed(0)}%)`).join(", ")}`;
        aEl.appendChild(src);
      }
      if (data.retrieval_metrics) {
        const m = data.retrieval_metrics;
        const met = document.createElement("div");
        met.className = `chat-metrics ${m.quality}`;
        met.textContent = `Retrieval quality: ${m.quality} | mean relevance: ${(m.mean_relevance*100).toFixed(0)}% | ${data.latency_ms}ms`;
        aEl.appendChild(met);
      }
      ch.appendChild(qEl);
      ch.appendChild(aEl);
      ch.scrollTo(0, ch.scrollHeight);
    }
    const rq = $("ragQuestion");
    if (rq) rq.value = "";
  } catch (err) {
    const ch = $("ragChatHistory");
    if (ch) {
      const e = document.createElement("div");
      e.className = "chat-a"; e.style.color = "var(--red)";
      e.textContent = `Error: ${err.message}`;
      ch.appendChild(e);
    }
  } finally {
    hideLoading();
  }
}

// ── Meeting Notes ─────────────────────────────────────────────────────────
$("meetingNotesBtn")?.addEventListener("click", async () => {
  const text = $("meetingInput")?.value.trim();
  if (!text) return;
  showLoading("Generating meeting notes…");
  try {
    const res  = await fetch("/api/meeting-notes", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    renderMeetingNotes(data);
  } catch (err) {
    const mr = $("meetingResult");
    if (mr) { mr.innerHTML = `<div style="color:var(--red)">Error: ${esc(err.message)}</div>`; mr.classList.remove("hidden"); }
  } finally {
    hideLoading();
  }
});

function renderMeetingNotes(data) {
  const mr = $("meetingResult");
  if (!mr) return;

  const decisions = (data.key_decisions||[]).map(d=>`<li>${esc(d)}</li>`).join("") || "<li>None noted</li>";
  const actions   = (data.action_items||[]).map(a=>`
    <div class="action-item">
      <div class="action-item-icon">✅</div>
      <div>
        <div class="action-task">${esc(a.task||a)}</div>
        <div class="action-meta">Owner: ${esc(a.owner||"TBD")} · Due: ${esc(a.deadline||"TBD")}</div>
      </div>
    </div>`).join("") || "<p style='color:var(--text3);font-size:13px'>No action items</p>";
  const steps  = (data.next_steps||[]).map(s=>`<li>${esc(s)}</li>`).join("") || "<li>None noted</li>";
  const topics = (data.topics_discussed||[]).map(t=>`<span class="sum-tag">${esc(t)}</span>`).join("") || "";

  mr.innerHTML = `
    <div class="meeting-card">
      <div class="meeting-title">📋 ${esc(data.title||"Meeting Notes")}</div>
      <div class="meeting-summary">${esc(data.summary||"")}</div>
      ${topics ? `<div class="meeting-section"><div class="meeting-section-title">Topics</div><div class="sum-tags">${topics}</div></div>` : ""}
      <div class="meeting-section">
        <div class="meeting-section-title">Key Decisions</div>
        <ul class="sum-points">${decisions}</ul>
      </div>
      <div class="meeting-section">
        <div class="meeting-section-title">Action Items</div>
        ${actions}
      </div>
      <div class="meeting-section">
        <div class="meeting-section-title">Next Steps</div>
        <ul class="sum-points">${steps}</ul>
      </div>
      <div style="margin-top:1rem;display:flex;justify-content:flex-end">
        <button class="btn-ghost sm" onclick="exportMeetingPDF()">⬇ Export as PDF</button>
      </div>
    </div>`;
  mr.classList.remove("hidden");
  window._meetingData = data;
}

window.exportMeetingPDF = async function() {
  const d = window._meetingData;
  if (!d) return;
  const text = [
    d.title, "", d.summary, "",
    "KEY DECISIONS:", ...(d.key_decisions||[]).map(x=>`• ${x}`), "",
    "ACTION ITEMS:", ...(d.action_items||[]).map(a=>`• ${a.task||a} (Owner: ${a.owner||"TBD"}, Due: ${a.deadline||"TBD"})`), "",
    "NEXT STEPS:", ...(d.next_steps||[]).map(x=>`• ${x}`)
  ].join("\n");
  showLoading("Generating PDF…");
  try {
    const res = await fetch("/api/export/pdf", {
      method:"POST", headers:{"Content-Type":"application/json"},
      body: JSON.stringify({ summary: text })
    });
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "meeting-notes.pdf";
    a.click(); URL.revokeObjectURL(url);
  } finally {
    hideLoading();
  }
};

// ── History ───────────────────────────────────────────────────────────────
async function loadHistory() {
  const list = $("dbHistoryList");
  if (!list) return;
  list.innerHTML = '<p class="empty-msg">Loading…</p>';
  try {
    const res  = await fetch("/api/history?limit=100");
    allHistory = await res.json();
    renderHistory(allHistory);
  } catch {
    list.innerHTML = '<p class="empty-msg">Failed to load</p>';
  }
}

function renderHistory(items) {
  const list = $("dbHistoryList");
  if (!list) return;
  if (!items.length) { list.innerHTML = '<p class="empty-msg">No translations yet</p>'; return; }

  const qualityColor = s => {
    if (!s) return "";
    if (s >= 0.80) return "background:#dcfce7;color:#16a34a";
    if (s >= 0.65) return "background:#e0f2fe;color:#0369a1";
    if (s >= 0.50) return "background:#fef3c7;color:#92400e";
    return "background:#fee2e2;color:#dc2626";
  };

  list.innerHTML = items.map(h => `
    <div class="history-item" data-orig="${esc(h.original_text)}" data-trans="${esc(h.translated_text)}">
      <div class="history-content">
        <div class="history-meta">${esc(h.created_at)} · ${esc((h.source_lang||"?").toUpperCase())} → ${esc((h.target_lang||"?").toUpperCase())}</div>
        <div class="history-orig">${esc(h.original_text)}</div>
        <div class="history-trans">${esc(h.translated_text)}</div>
      </div>
      ${h.quality_score ? `<span class="history-quality" style="${qualityColor(h.quality_score)}">${(h.quality_score*100).toFixed(0)}%</span>` : ""}
      <button class="history-del" data-id="${h.id}" title="Delete">✕</button>
    </div>
  `).join("");

  list.querySelectorAll(".history-item").forEach(el => {
    el.addEventListener("click", e => {
      if (e.target.classList.contains("history-del")) return;
      origText.textContent = el.dataset.orig;
      if (transText) transText.textContent = el.dataset.trans;
      charCount.textContent = el.dataset.orig.length;
      checkBtn();
      document.querySelector('[data-tab="translate"]')?.click();
    });
  });
  list.querySelectorAll(".history-del").forEach(btn => {
    btn.addEventListener("click", async () => {
      await fetch(`/api/history/${btn.dataset.id}`, { method: "DELETE" });
      loadHistory();
    });
  });
}

// Search history
$("historySearch")?.addEventListener("input", e => {
  const q = e.target.value.toLowerCase();
  const filtered = allHistory.filter(h =>
    h.original_text.toLowerCase().includes(q) ||
    h.translated_text.toLowerCase().includes(q)
  );
  renderHistory(filtered);
});

$("refreshHistoryBtn")?.addEventListener("click", loadHistory);

// Export history as CSV
$("exportHistoryBtn")?.addEventListener("click", () => {
  if (!allHistory.length) return;
  const csv = ["Date,Original,Translation,Source,Target,Quality",
    ...allHistory.map(h =>
      `"${h.created_at}","${(h.original_text||"").replace(/"/g,'""')}","${(h.translated_text||"").replace(/"/g,'""')}","${h.source_lang}","${h.target_lang}","${h.quality_score||""}"`
    )
  ].join("\n");
  const blob = new Blob([csv], { type: "text/csv" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href = url; a.download = "voicebridge-history.csv";
  a.click(); URL.revokeObjectURL(url);
});

// ── Keep-alive ping ───────────────────────────────────────────────────────
setInterval(() => fetch("/ping").catch(() => {}), 14 * 60 * 1000);

// ── Init ──────────────────────────────────────────────────────────────────
setStatus("Ready — type, speak, or upload audio");