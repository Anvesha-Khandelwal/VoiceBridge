/**
 * VoiceBridge AI — app.js
 * Handles: tabs, voice recording, translation, summarization, RAG Q&A
 */
"use strict";

// ── DOM ───────────────────────────────────────────────────────────────────
const $ = id => document.getElementById(id);

// Translate tab
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
const uploadAudioBtn = $("uploadAudioBtn");
const audioFileInput = $("audioFileInput");
const statusBar      = $("statusBar");
const historyList    = $("historyList");
const waveViz        = $("waveViz");
const origPanel      = $("origPanel");

// Summarize tab
const sumInput      = $("sumInput");
const summarizeBtn  = $("summarizeBtn");
const summaryResult = $("summaryResult");
const styleBtns     = document.querySelectorAll(".style-btn");

// RAG tab
const ragInput       = $("ragInput");
const ragIndexBtn    = $("ragIndexBtn");
const ragIndexStatus = $("ragIndexStatus");
const ragAskSection  = $("ragAskSection");
const ragQuestion    = $("ragQuestion");
const ragAskBtn      = $("ragAskBtn");
const ragResult      = $("ragResult");
const ragChatHistory = $("ragChatHistory");
const sqBtns         = document.querySelectorAll(".sq-btn");

// Loading
const loadingOverlay = $("loadingOverlay");
const loadingText    = $("loadingText");

// ── State ─────────────────────────────────────────────────────────────────
let recognition   = null;
let isRecording   = false;
let ragSessionId  = null;
let sumStyle      = "detailed";
let history       = JSON.parse(localStorage.getItem("vb_history") || "[]");

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

// ── Tab switching ─────────────────────────────────────────────────────────
document.querySelectorAll(".tab").forEach(tab => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach(t => t.classList.remove("active"));
    document.querySelectorAll(".tab-panel").forEach(p => p.classList.remove("active"));
    tab.classList.add("active");
    $("tab-" + tab.dataset.tab).classList.add("active");
  });
});

// ── Helpers ───────────────────────────────────────────────────────────────
function setStatus(msg, cls = "") {
  statusBar.textContent = msg;
  statusBar.className = "status-bar" + (cls ? " " + cls : "");
}

function showLoading(msg = "Processing…") {
  loadingText.textContent = msg;
  loadingOverlay.classList.add("active");
}

function hideLoading() {
  loadingOverlay.classList.remove("active");
}

function getOriginal() { return origText.textContent.trim(); }

function checkTranslateBtn() {
  translateBtn.disabled = !getOriginal();
}

function copyText(text, btn) {
  if (!text) return;
  navigator.clipboard.writeText(text).then(() => {
    const orig = btn.textContent;
    btn.textContent = "Copied!";
    setTimeout(() => (btn.textContent = orig), 1500);
  });
}

// ── Voice Recording (Web Speech API) ─────────────────────────────────────
if (!SpeechRecognition) {
  recordBtn.disabled = true;
  setStatus("Voice input needs Chrome or Edge browser", "error");
}

recordBtn.addEventListener("click", () => {
  isRecording ? stopRecording() : startRecording();
});

function startRecording() {
  recognition = new SpeechRecognition();
  recognition.lang = fromLang.value;
  recognition.continuous = false;
  recognition.interimResults = true;

  recognition.onstart = () => {
    isRecording = true;
    recordBtn.classList.add("recording");
    origPanel.classList.add("recording");
    waveViz.classList.add("active");
    recordLabel.textContent = "Recording… tap to stop";
    setStatus("Listening…", "listening");
    origText.textContent = "";
  };

  recognition.onresult = e => {
    let final = "", interim = "";
    for (let i = e.resultIndex; i < e.results.length; i++) {
      e.results[i].isFinal ? (final += e.results[i][0].transcript)
                           : (interim += e.results[i][0].transcript);
    }
    origText.textContent = final || interim;
    checkTranslateBtn();
  };

  recognition.onerror = e => {
    stopRecording();
    const msgs = { "not-allowed": "Mic permission denied", "no-speech": "No speech detected" };
    setStatus(msgs[e.error] || `Error: ${e.error}`, "error");
  };

  recognition.onend = () => {
    stopRecording();
    if (getOriginal()) setStatus("Done — click Translate", "success");
    else setStatus("No speech captured", "");
  };

  recognition.start();
}

function stopRecording() {
  isRecording = false;
  recordBtn.classList.remove("recording");
  origPanel.classList.remove("recording");
  waveViz.classList.remove("active");
  recordLabel.textContent = "Tap to speak";
  try { recognition?.stop(); } catch (_) {}
}

// ── Translate ─────────────────────────────────────────────────────────────
translateBtn.addEventListener("click", doTranslate);
origText.addEventListener("keydown", e => {
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) { e.preventDefault(); doTranslate(); }
});

async function doTranslate() {
  const text = getOriginal();
  if (!text) return;

  const srcCode = fromLang.options[fromLang.selectedIndex].dataset.code || "auto";
  const tgtCode = toLang.value;

  showLoading("Translating with Groq LLaMA3…");
  setStatus("Translating…", "working");

  try {
    const res = await fetch("/api/translate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, source_lang: srcCode, target_lang: tgtCode })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error || "Translation failed");

    transText.textContent = data.translated;
    setStatus("Translation complete ✓", "success");
    addToHistory(text, data.translated, srcCode, tgtCode);
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  } finally {
    hideLoading();
  }
}

// ── Upload audio file → server Whisper ───────────────────────────────────
uploadAudioBtn.addEventListener("click", () => audioFileInput.click());
audioFileInput.addEventListener("change", async e => {
  const file = e.target.files[0];
  if (!file) return;

  const srcCode = fromLang.options[fromLang.selectedIndex].dataset.code || "";
  const fd = new FormData();
  fd.append("audio", file);
  if (srcCode) fd.append("lang", srcCode);

  showLoading("Transcribing with Whisper ASR…");
  setStatus("Running Whisper…", "working");

  try {
    const res = await fetch("/api/transcribe", { method: "POST", body: fd });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    origText.textContent = data.text;
    checkTranslateBtn();
    setStatus("Transcription complete — click Translate", "success");
  } catch (err) {
    setStatus(`Transcription error: ${err.message}`, "error");
  } finally {
    hideLoading();
    audioFileInput.value = "";
  }
});

// ── Swap languages ────────────────────────────────────────────────────────
swapBtn.addEventListener("click", () => {
  const fromCode = fromLang.options[fromLang.selectedIndex].dataset.code;
  const toCode   = toLang.value;
  const toFrom   = { en:"en-US", hi:"hi-IN", es:"es-ES", fr:"fr-FR", de:"de-DE",
                     ta:"ta-IN", te:"te-IN", bn:"bn-IN", ja:"ja-JP", zh:"zh-CN",
                     ar:"ar-SA", pt:"pt-BR", ru:"ru-RU", ko:"ko-KR" };
  const opt = [...fromLang.options].find(o => o.value === toFrom[toCode]);
  if (opt) fromLang.value = opt.value;
  if ([...toLang.options].some(o => o.value === fromCode)) toLang.value = fromCode;

  const tmpO = getOriginal();
  const tmpT = transText.textContent.trim();
  origText.textContent = tmpT;
  transText.textContent = tmpO;
  checkTranslateBtn();
});

// ── Other translate controls ──────────────────────────────────────────────
clearBtn.addEventListener("click", () => {
  origText.textContent = "";
  transText.textContent = "";
  translateBtn.disabled = true;
  setStatus("");
});
copyOrigBtn.addEventListener("click",  () => copyText(getOriginal(), copyOrigBtn));
copyTransBtn.addEventListener("click", () => copyText(transText.textContent.trim(), copyTransBtn));
speakTransBtn.addEventListener("click", () => {
  const t = transText.textContent.trim();
  if (!t || !window.speechSynthesis) return;
  const bcp = { en:"en-US", hi:"hi-IN", es:"es-ES", fr:"fr-FR", de:"de-DE",
                ta:"ta-IN", te:"te-IN", bn:"bn-IN", ja:"ja-JP", zh:"zh-CN",
                ar:"ar-SA", pt:"pt-BR", ru:"ru-RU", ko:"ko-KR" };
  const u = new SpeechSynthesisUtterance(t);
  u.lang = bcp[toLang.value] || toLang.value;
  window.speechSynthesis.cancel();
  window.speechSynthesis.speak(u);
  speakTransBtn.textContent = "Speaking…";
  u.onend = () => (speakTransBtn.textContent = "▶ Speak");
});

// Send original transcript to RAG tab
sendToRagBtn.addEventListener("click", () => {
  const t = getOriginal();
  if (!t) return;
  ragInput.value = t;
  sumInput.value = t;
  // Switch to RAG tab
  document.querySelectorAll(".tab").forEach(tab => {
    if (tab.dataset.tab === "rag") tab.click();
  });
});

origText.addEventListener("input", checkTranslateBtn);

// ── History ───────────────────────────────────────────────────────────────
function addToHistory(orig, trans, src, tgt) {
  const time = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  history.unshift({ orig, trans, src, tgt, time });
  if (history.length > 30) history.pop();
  localStorage.setItem("vb_history", JSON.stringify(history));
  renderHistory();
}

function renderHistory() {
  if (!history.length) {
    historyList.innerHTML = '<p class="empty-msg">No translations yet</p>';
    return;
  }
  historyList.innerHTML = history.map((h, i) => `
    <div class="history-item" data-i="${i}">
      <div class="history-meta">${h.time} · ${h.src.toUpperCase()} → ${h.tgt.toUpperCase()}</div>
      <div class="history-orig">${esc(h.orig)}</div>
      <div class="history-trans">${esc(h.trans)}</div>
    </div>
  `).join("");
  historyList.querySelectorAll(".history-item").forEach(el => {
    el.addEventListener("click", () => {
      const h = history[Number(el.dataset.i)];
      origText.textContent = h.orig;
      transText.textContent = h.trans;
      checkTranslateBtn();
    });
  });
}

// ── SUMMARIZE TAB ─────────────────────────────────────────────────────────
styleBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    styleBtns.forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    sumStyle = btn.dataset.style;
  });
});

summarizeBtn.addEventListener("click", async () => {
  const text = sumInput.value.trim();
  if (!text) return;

  showLoading("Summarizing with LLaMA3…");

  try {
    const res = await fetch("/api/summarize", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, style: sumStyle })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);
    renderSummary(data);
  } catch (err) {
    summaryResult.innerHTML = `<div style="color:var(--red)">Error: ${esc(err.message)}</div>`;
    summaryResult.classList.remove("hidden");
  } finally {
    hideLoading();
  }
});

function renderSummary(data) {
  let html = "";

  if (data.overview) {
    html += `<div class="sum-overview">${esc(data.overview)}</div>`;
  }

  if (data.topics?.length) {
    html += `<div class="sum-section-title">Topics</div>
    <div class="sum-tags">${data.topics.map(t => `<span class="sum-tag">${esc(t)}</span>`).join("")}</div>`;
  }

  if (data.key_points?.length) {
    html += `<div class="sum-section-title">Key Points</div>
    <ul class="sum-points">${data.key_points.map(p => `<li>${esc(p)}</li>`).join("")}</ul>`;
  }

  if (data.action_items?.length) {
    html += `<div class="sum-section-title" style="margin-top:1rem">Action Items</div>
    <ul class="sum-points">${data.action_items.map(a => `<li>${esc(a)}</li>`).join("")}</ul>`;
  }

  if (data.sentiment) {
    html += `<div style="margin-top:1rem">
      <span class="sum-section-title" style="display:inline">Sentiment </span>
      <span class="sentiment-badge ${data.sentiment}">${data.sentiment}</span>
    </div>`;
  }

  if (data.word_count) {
    html += `<div style="margin-top:1rem;font-size:12px;color:var(--text3);font-family:'DM Mono',monospace">${data.word_count} words analyzed</div>`;
  }

  summaryResult.innerHTML = html;
  summaryResult.classList.remove("hidden");
}

// ── RAG TAB ───────────────────────────────────────────────────────────────
ragIndexBtn.addEventListener("click", async () => {
  const text = ragInput.value.trim();
  if (!text) return;

  showLoading("Embedding chunks into FAISS vector store…");
  ragIndexStatus.textContent = "Indexing…";
  ragIndexStatus.className = "rag-status";

  try {
    const res = await fetch("/api/rag/index", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    ragSessionId = data.session_id;
    ragIndexStatus.textContent = `✓ ${data.chunks_created} chunks indexed (session: ${ragSessionId})`;
    ragIndexStatus.className = "rag-status success";

    // Unlock the ask section
    ragAskSection.style.opacity = "1";
    ragAskSection.style.pointerEvents = "auto";
    ragChatHistory.innerHTML = "";

  } catch (err) {
    ragIndexStatus.textContent = `Error: ${err.message}`;
    ragIndexStatus.className = "rag-status error";
  } finally {
    hideLoading();
  }
});

ragAskBtn.addEventListener("click", doRagAsk);
ragQuestion.addEventListener("keydown", e => {
  if (e.key === "Enter") doRagAsk();
});

// Suggested questions
sqBtns.forEach(btn => {
  btn.addEventListener("click", () => {
    ragQuestion.value = btn.textContent;
    doRagAsk();
  });
});

async function doRagAsk() {
  const question = ragQuestion.value.trim();
  if (!question || !ragSessionId) return;

  showLoading("Searching vector store + generating answer…");

  try {
    const res = await fetch("/api/rag/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, session_id: ragSessionId, top_k: 3 })
    });
    const data = await res.json();
    if (!res.ok || data.error) throw new Error(data.error);

    // Add to chat history
    const qEl = document.createElement("div");
    qEl.className = "chat-q";
    qEl.textContent = question;

    const aEl = document.createElement("div");
    aEl.className = "chat-a";
    aEl.textContent = data.answer;

    ragChatHistory.appendChild(qEl);
    ragChatHistory.appendChild(aEl);
    ragChatHistory.scrollTop = ragChatHistory.scrollHeight;

    // Show sources
    renderRagResult(data);
    ragQuestion.value = "";

  } catch (err) {
    ragResult.innerHTML = `<div style="color:var(--red)">Error: ${esc(err.message)}</div>`;
    ragResult.classList.remove("hidden");
  } finally {
    hideLoading();
  }
}

function renderRagResult(data) {
  let html = `<div class="rag-answer">${esc(data.answer)}</div>`;

  if (data.sources?.length) {
    html += `<div class="rag-sources-title">Sources used (${data.sources.length} chunks retrieved)</div>`;
    data.sources.forEach(s => {
      html += `<div class="rag-source-item">
        <div class="rag-source-score">Rank #${s.rank} · Relevance: ${(s.relevance_score * 100).toFixed(0)}%</div>
        ${esc(s.chunk)}
      </div>`;
    });
  }

  if (data.chunks_searched) {
    html += `<div style="font-size:12px;color:var(--text3);margin-top:8px;font-family:'DM Mono',monospace">Searched ${data.chunks_searched} total chunks</div>`;
  }

  ragResult.innerHTML = html;
  ragResult.classList.remove("hidden");
}

// ── Utils ─────────────────────────────────────────────────────────────────
function esc(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;").replace(/>/g,"&gt;");
}

// ── Init ──────────────────────────────────────────────────────────────────
renderHistory();
setStatus("Ready — tap the mic or type to start");
