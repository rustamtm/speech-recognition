const WS_URL = "ws://127.0.0.1:8765";

let ws = null;
let audioCtx = null;
let source = null;
let processor = null;
let mediaStream = null;
let autoScroll = true;
let committed = "";   // finalized text
let partial = "";     // last partial

const $ = (sel) => document.querySelector(sel);
const transcriptEl = $("#transcript");
const btnStart = $("#btnStart");
const btnStop = $("#btnStop");
const btnClear = $("#btnClear");
const btnCopy = $("#btnCopy");
const btnSave = $("#btnSave");
const langSel = $("#lang");
const statusDot = $("#statusDot");

function setStatus(text, cls) {
  statusDot.textContent = text;
  statusDot.className = `badge rounded-pill ${cls}`;
}

function render() {
  const caretAtEnd = transcriptEl.selectionStart === transcriptEl.value.length &&
                     transcriptEl.selectionEnd === transcriptEl.value.length;
  transcriptEl.value = committed + (partial ? ` ${partial}` : "");
  if (autoScroll && caretAtEnd) {
    transcriptEl.scrollTop = transcriptEl.scrollHeight;
  }
}

function floatTo16BitPCM(float32Array) {
  const buf = new Int16Array(float32Array.length);
  for (let i = 0; i < float32Array.length; i++) {
    let s = Math.max(-1, Math.min(1, float32Array[i]));
    buf[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
  }
  return buf;
}

function setupAudio() {
  audioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
}

async function startStream() {
  if (ws && ws.readyState === WebSocket.OPEN) return;
  ws = new WebSocket(WS_URL);
  ws.binaryType = "arraybuffer";

  ws.onopen = () => {
    setStatus("Connected", "bg-success");
    const code = langSel.value;
    ws.send(JSON.stringify({ type: "control", setLanguage: code || "" }));
  };

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      if (msg.type === "partial") {
        partial = msg.text || "";
        render();
      } else if (msg.type === "final") {
        const text = (msg.text || "").trim();
        if (text) committed += (committed ? " " : "") + text;
        partial = "";
        render();
      } else if (msg.type === "info") {
        setStatus(msg.message || "Info", "bg-primary");
      } else if (msg.type === "error") {
        setStatus("Error", "bg-danger");
        console.error(msg.message);
      }
    } catch {
      // ignore non‑JSON
    }
  };

  ws.onerror = () => setStatus("Error", "bg-danger");
  ws.onclose = () => setStatus("Disconnected", "bg-secondary");
}

async function startRecording() {
  setupAudio();
  await startStream();

  mediaStream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, sampleRate: 16000, noiseSuppression: true, echoCancellation: true } });
  source = audioCtx.createMediaStreamSource(mediaStream);

  const frameSize = 2048; // ~128 ms at 16 kHz
  processor = audioCtx.createScriptProcessor(frameSize, 1, 1);
  processor.onaudioprocess = (e) => {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    const f32 = e.inputBuffer.getChannelData(0);
    const i16 = floatTo16BitPCM(f32);
    ws.send(i16.buffer);
  };

  source.connect(processor);
  processor.connect(audioCtx.destination);

  btnStart.disabled = true;
  btnStop.disabled = false;
  setStatus("Streaming", "bg-success");
}

function stopRecording() {
  if (processor) processor.disconnect();
  if (source) source.disconnect();
  if (mediaStream) mediaStream.getTracks().forEach(t => t.stop());
  if (audioCtx) audioCtx.close();

  btnStart.disabled = false;
  btnStop.disabled = true;
  setStatus("Connected", "bg-primary");
}

function clearTranscript() {
  committed = "";
  partial = "";
  render();
}

async function copyTranscript() {
  await navigator.clipboard.writeText(transcriptEl.value);
}

function saveTranscript() {
  const blob = new Blob([transcriptEl.value], { type: "text/plain;charset=utf-8" });
  const a = document.createElement("a");
  const ts = new Date().toISOString().replace(/[:.]/g, "-");
  a.href = URL.createObjectURL(blob);
  a.download = `transcript-${ts}.txt`;
  document.body.appendChild(a);
  a.click();
  a.remove();
}

btnStart.addEventListener("click", startRecording);
btnStop.addEventListener("click", stopRecording);
btnClear.addEventListener("click", clearTranscript);
btnCopy.addEventListener("click", copyTranscript);
btnSave.addEventListener("click", saveTranscript);

langSel.addEventListener("change", () => {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: "control", setLanguage: langSel.value || "" }));
  }
});

transcriptEl.addEventListener("scroll", () => {
  const atBottom = transcriptEl.scrollTop + transcriptEl.clientHeight >= transcriptEl.scrollHeight - 4;
  autoScroll = atBottom;
});

document.addEventListener("keydown", (e) => {
  if (e.ctrlKey && e.key.toLowerCase() === " ") {
    if (btnStart.disabled) stopRecording(); else startRecording();
    e.preventDefault();
  } else if (e.ctrlKey && e.key.toLowerCase() === "k") {
    clearTranscript(); e.preventDefault();
  } else if (e.ctrlKey && e.key.toLowerCase() === "c") {
    copyTranscript(); e.preventDefault();
  } else if (e.ctrlKey && e.key.toLowerCase() === "s") {
    saveTranscript(); e.preventDefault();
  }
});

