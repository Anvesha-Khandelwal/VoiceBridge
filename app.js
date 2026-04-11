/**
 * VoiceBridge AI — app.js
 * Fixed: translation, summarization, RAG, PDF, dark mode, history all working
 */
"use strict";
const $ = id => document.getElementById(id);

// ── DOM ───────────────────────────────────────────────────────────────────
const recordBtn      = $("recordBtn");
const recordLabel    = $("recordLabel");
const origText       = $("origText");
const transText      = $("transText");
const translateBtn   = $("translateBtn");
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
const sumInput       = $("sumInput");
const summarizeBtn   = $("summarizeBtn");
const summaryResult  = $("summaryResult");
const ragInput       = $("ragInput");
const ragIndexBtn    = $("ragIndexBtn");
const ragIndexStatus = $("ragIndexStatus");
const ragAskSection  = $("ragAskSection");
const ragQuestion    = $("ragQuestion");
const ragAskBtn      = $("ragAskBtn");
const ragChatHistory = $("ragChatHistory");
const dbHistoryList  = $("dbHistoryList");
const loadingOverlay = $("loadingOverlay");
const loadingText    = $("loadingText");
const themeBtn       = $("themeBtn");
const userAvatar     = $("userAvatar");
const userDropdown   = $("userDropdown");
const refreshHistBtn = $("refreshHistoryBtn");

// ── State ─────────────────────────────────────────────────────────────────
let recognition  = null;
let isRecording  = false;
let ragSessionId = null;
let sumStyle     = "detailed";
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// ── Dark mode ─────────────────────────────────────────────────────────────
const root       = document.documentElement;
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

themeBtn?.addEventListener("click", () => {
  applyTheme(root.getAttribute("data-theme") === "dark" ? "light" : "dark");
});

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
    if (tab.dataset.tab === "history") loadDbHistory();
  });
});

// ── Helpers ───────────────────────────────────────────────────────────────
function setStatus(msg, cls = "") {
  if (!statusBar) return;
  statusBar.textContent = msg;
  statusBar.className   = "status-bar" + (cls ? " " + cls : "");
}
function showLoading(msg = "Processing…") {
  if (loadingText) loadingText.textContent = msg;
  loadingOverlay?.classList.add("active");
}
function hideLoading() { loadingOverlay?.classList.remove("active"); }
function getOrig()     { return origText?.textContent.trim() || ""; }
function checkBtn()    { if (translateBtn) translateBtn.disabled = !getOrig(); }
function esc(s)        { return String(s||"").replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;"); }
function copyText(text, btn) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const o = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => btn.textContent = o, 1500);
  });
}

// ── Voice Recording ───────────────────────────────────────────────────────
if (!SpeechRecognition && recordBtn) {
  recordBtn.disabled = true;
  setStatus("Voice input needs Chrome or Edge browser", "error");
}

recordBtn?.addEventListener("click", () => isRecording ? stopRec() : startRec());

function startRec() {
  recognition                  = new SpeechRecognition();
  recognition.lang             = fromLang.value;
  recognition.continuous       = false;
  recognition.interimResults   = true;

  recognition.onstart = () => {
    isRecording = true;
    recordBtn.classList.add("recording");
    origPanel?.classList.add("recording");
    waveViz?.classList.add("active");
    if (recordLabel) recordLabel.textContent = "Recording… tap to stop";
    setStatus("Listening…", "listening");
    origText.textContent = "";
  };

  recognition.onresult = e => {
    let final = "", interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      e.results[i].isFinal
        ? (final   += e.results[i][0].transcript)
        : (interim += e.results[i][0].transcript);
    }
    origText.textContent = final || interim;
    checkBtn();
  };

  recognition.onerror = e => {
    stopRec();
    const msgs = {
      "not-allowed": "Mic permission denied",
      "no-speech":   "No speech detected — try again"
    };
    setStatus(msgs[e.error] || `Error: ${e.error}`, "error");
  };

  recognition.onend = () => {
    stopRec();
    getOrig()
      ? setStatus("Done — click Translate", "success")
      : setStatus("No speech captured", "");
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

// ── Translate ─────────────────────────────────────────────────────────────
translateBtn?.addEventListener("click", doTranslate);
origText?.addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
    e.preventDefault(); doTranslate();
  }
});
origText?.addEventListener("input", checkBtn);

async function doTranslate() {
  const text = getOrig();
  if (!text) return;

  const src = fromLang?.options[fromLang.selectedIndex]?.dataset?.code || "auto";
  const tgt = toLang?.value || "en";

  showLoading("Translating with Groq LLaMA3…");
  setStatus("Translating…", "working");

  try {
    const res  = await fetch("/api/translate", {
      method:  "POST",
      headers: { "Content-Type": "application/json" },
      body:    JSON.stringify({ text, source_lang: src, target_lang: tgt })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Translation failed");
    if (transText) transText.textContent = data.translated;
    setStatus("Translation complete ✓", "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

// ── Upload audio ──────────────────────────────────────────────────────────
uploadAudioBtn?.addEventListener("click", () => audioFileInput?.click());
audioFileInput?.addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;
  const fd = new FormData();
  fd.append("audio", file);
  const src = fromLang?.options[fromLang.selectedIndex]?.dataset?.code || "";
  if (src) fd.append("lang", src);

  showLoading("Transcribing with Whisper ASR…");
  setStatus("Running Whisper…", "working");
  try {
    const res  = await fetch("/api/transcribe", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    origText.textContent = data.text;
    checkBtn();
    setStatus("Transcription done — click Translate", "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
    if (audioFileInput) audioFileInput.value = "";
  }
});

// ── Detect language ───────────────────────────────────────────────────────
detectLangBtn?.addEventListener("click", async () => {
  const text = getOrig();
  if (!text) return setStatus("Type some text first", "error");
  showLoading("Detecting language…");
  try {
    const res  = await fetch("/api/detect-language", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    setStatus(`Detected language: ${data.language.toUpperCase()}`, "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

// ── Improve text ──────────────────────────────────────────────────────────
improveBtn?.addEventListener("click", async () => {
  const text = getOrig();
  if (!text) return setStatus("Type some text first", "error");
  showLoading("Improving grammar and clarity…");
  try {
    const res  = await fetch("/api/improve-text", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (data.error) throw new Error(data.error);
    origText.textContent = data.improved;
    checkBtn();
    setStatus("Text improved ✓", "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

// ── Swap ──────────────────────────────────────────────────────────────────
swapBtn?.addEventListener("click", () => {
  const fromCode = fromLang?.options[fromLang.selectedIndex]?.dataset?.code;
  const toCode   = toLang?.value;
  const toFrom   = {
    en:"en-US",hi:"hi-IN",es:"es-ES",fr:"fr-FR",de:"de-DE",
    ta:"ta-IN",te:"te-IN",bn:"bn-IN",ja:"ja-JP",zh:"zh-CN",
    ar:"ar-SA",pt:"pt-BR",ru:"ru-RU",ko:"ko-KR"
  };
  const opt = [...(fromLang?.options||[])].find(o => o.value === toFrom[toCode]);
  if (opt) fromLang.value = opt.value;
  if ([...(toLang?.options||[])].some(o => o.value === fromCode)) toLang.value = fromCode;
  const tmpO = getOrig(), tmpT = transText?.textContent.trim() || "";
  origText.textContent  = tmpT;
  if (transText) transText.textContent = tmpO;
  checkBtn();
});

clearBtn?.addEventListener("click", () => {
  origText.textContent = "";
  if (transText) transText.textContent = "";
  if (translateBtn) translateBtn.disabled = true;
  setStatus("");
});

copyOrigBtn?.addEventListener("click",  () => copyText(getOrig(), copyOrigBtn));
copyTransBtn?.addEventListener("click", () => copyText(transText?.textContent.trim(), copyTransBtn));

speakTransBtn?.addEventListener("click", () => {
  const t = transText?.textContent.trim();
  if (!t || !window.speechSynthesis) return;
  const bcp = {
    en:"en-US",hi:"hi-IN",es:"es-ES",fr:"fr-FR",de:"de-DE",
    ta:"ta-IN",te:"te-IN",bn:"bn-IN",ja:"ja-JP",zh:"zh-CN",
    ar:"ar-SA",pt:"pt-BR",ru:"ru-RU",ko:"ko-KR"
  };
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
  if (ragInput)  ragInput.value  = t;
  if (sumInput)  sumInput.value  = t;
  document.querySelector('[data-tab="rag"]')?.click();
});

// ── PDF Export ────────────────────────────────────────────────────────────
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
    const url  = URL.createObjectURL(blob);
    const a    = document.createElement("a");
    a.href = url; a.download = "voicebridge-export.pdf";
    a.click(); URL.revokeObjectURL(url);
    setStatus("PDF downloaded ✓", "success");
  } catch (err) {
    setStatus(`PDF error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
});

// ── Summarize ─────────────────────────────────────────────────────────────
document.querySelectorAll(".style-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".style-btn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    sumStyle = btn.dataset.style;
  });
});

summarizeBtn?.addEventListener("click", async () => {
  const text = sumInput?.value.trim();
  if (!text) return;
  showLoading("Summarizing with LLaMA3…");
  try {
    const res  = await fetch("/api/summarize", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, style: sumStyle })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Summarization failed");
    renderSummary(data);
  } catch (err) {
    if (summaryResult) {
      summaryResult.innerHTML = `<div style="color:var(--red);padding:1rem">Error: ${esc(err.message)}</div>`;
      summaryResult.classList.remove("hidden");
    }
  } finally {
    hideLoading();
  }
});

function renderSummary(data) {
  if (!summaryResult) return;
  let html = "";
  if (data.overview)
    html += `<div class="sum-overview">${esc(data.overview)}</div>`;
  if (data.topics?.length)
    html += `<div class="sum-section-title">Topics</div>
    <div class="sum-tags">${data.topics.map(t=>`<span class="sum-tag">${esc(t)}</span>`).join("")}</div>`;
  if (data.key_points?.length)
    html += `<div class="sum-section-title">Key Points</div>
    <ul class="sum-points">${data.key_points.map(p=>`<li>${esc(p)}</li>`).join("")}</ul>`;
  if (data.action_items?.length)
    html += `<div class="sum-section-title" style="margin-top:1rem">Action Items</div>
    <ul class="sum-points">${data.action_items.map(a=>`<li>${esc(a)}</li>`).join("")}</ul>`;
  if (data.sentiment)
    html += `<div style="margin-top:1rem">
      <span class="sentiment-badge ${data.sentiment}">${esc(data.sentiment)}</span>
    </div>`;
  if (data.word_count)
    html += `<div style="margin-top:1rem;font-size:12px;color:var(--text3);font-family:'DM Mono',monospace">
      ${data.word_count} words analyzed
    </div>`;
  summaryResult.innerHTML = html;
  summaryResult.classList.remove("hidden");
}

// ── RAG ───────────────────────────────────────────────────────────────────
ragIndexBtn?.addEventListener("click", async () => {
  const text = ragInput?.value.trim();
  if (!text) return;
  showLoading("Embedding chunks into FAISS vector store…");
  if (ragIndexStatus) {
    ragIndexStatus.textContent = "Indexing…";
    ragIndexStatus.className   = "rag-status";
  }
  try {
    const res  = await fetch("/api/rag/index", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, title: text.substring(0, 60) + "…" })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    ragSessionId = data.session_id;
    if (ragIndexStatus) {
      ragIndexStatus.textContent = `✓ ${data.chunks_created} chunks indexed (session: ${ragSessionId})`;
      ragIndexStatus.className   = "rag-status success";
    }
    if (ragAskSection) {
      ragAskSection.style.opacity       = "1";
      ragAskSection.style.pointerEvents = "auto";
    }
    if (ragChatHistory) ragChatHistory.innerHTML = "";
  } catch (err) {
    if (ragIndexStatus) {
      ragIndexStatus.textContent = `Error: ${err.message}`;
      ragIndexStatus.className   = "rag-status error";
    }
  } finally {
    hideLoading();
  }
});

ragAskBtn?.addEventListener("click", doRagAsk);
ragQuestion?.addEventListener("keydown", e => { if (e.key === "Enter") doRagAsk(); });
document.querySelectorAll(".sq-btn").forEach(btn => {
  btn.addEventListener("click", () => {
    if (ragQuestion) ragQuestion.value = btn.textContent;
    doRagAsk();
  });
});

async function doRagAsk() {
  const q = ragQuestion?.value.trim();
  if (!q || !ragSessionId) return;
  showLoading("Searching FAISS + generating answer…");
  try {
    const res  = await fetch("/api/rag/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, session_id: ragSessionId })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    const qEl = document.createElement("div");
    qEl.className   = "chat-q";
    qEl.textContent = q;

    const aEl = document.createElement("div");
    aEl.className   = "chat-a";
    aEl.textContent = data.answer;

    if (data.sources?.length) {
      const src = document.createElement("div");
      src.className   = "chat-sources";
      src.textContent = `Sources: ${data.sources.map(s=>`chunk #${s.rank} (${(s.relevance_score*100).toFixed(0)}%)`).join(", ")}`;
      aEl.appendChild(src);
    }

    ragChatHistory?.appendChild(qEl);
    ragChatHistory?.appendChild(aEl);
    ragChatHistory?.scrollTo(0, ragChatHistory.scrollHeight);
    if (ragQuestion) ragQuestion.value = "";
  } catch (err) {
    const errEl = document.createElement("div");
    errEl.className = "chat-a";
    errEl.style.color = "var(--red)";
    errEl.textContent = `Error: ${err.message}`;
    ragChatHistory?.appendChild(errEl);
  } finally {
    hideLoading();
  }
}

// ── DB History ────────────────────────────────────────────────────────────
async function loadDbHistory() {
  if (!dbHistoryList) return;
  dbHistoryList.innerHTML = '<p class="empty-msg">Loading…</p>';
  try {
    const res  = await fetch("/api/history");
    const data = await res.json();
    if (!data.length) {
      dbHistoryList.innerHTML = '<p class="empty-msg">No translations yet</p>';
      return;
    }
    dbHistoryList.innerHTML = data.map(h => `
      <div class="history-item"
           data-orig="${esc(h.original_text)}"
           data-trans="${esc(h.translated_text)}">
        <div class="history-content">
          <div class="history-meta">
            ${esc(h.created_at)} · ${esc(h.source_lang.toUpperCase())} → ${esc(h.target_lang.toUpperCase())}
          </div>
          <div class="history-orig">${esc(h.original_text)}</div>
          <div class="history-trans">${esc(h.translated_text)}</div>
        </div>
        <button class="history-del" data-id="${h.id}" title="Delete">✕</button>
      </div>
    `).join("");

    dbHistoryList.querySelectorAll(".history-item").forEach(el => {
      el.addEventListener("click", e => {
        if (e.target.classList.contains("history-del")) return;
        origText.textContent = el.dataset.orig;
        if (transText) transText.textContent = el.dataset.trans;
        checkBtn();
        document.querySelector('[data-tab="translate"]')?.click();
      });
    });

    dbHistoryList.querySelectorAll(".history-del").forEach(btn => {
      btn.addEventListener("click", async () => {
        await fetch(`/api/history/${btn.dataset.id}`, { method: "DELETE" });
        loadDbHistory();
      });
    });
  } catch {
    dbHistoryList.innerHTML = '<p class="empty-msg">Failed to load history</p>';
  }
}

refreshHistBtn?.addEventListener("click", loadDbHistory);

// ── Keep-alive ping (prevent Render spin-down) ────────────────────────────
setInterval(() => {
  fetch("/ping").catch(() => {});
}, 14 * 60 * 1000); // ping every 14 minutes

// ── Init ──────────────────────────────────────────────────────────────────
setStatus("Ready — tap the mic or type to start");