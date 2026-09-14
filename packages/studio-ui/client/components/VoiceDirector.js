"use client";

import { useEffect, useRef, useState } from "react";

// Talk to the director. Prefers the browser's own speech recognition (no key, no upload);
// falls back to recording a clip and transcribing it with the studio's local whisper.
// An ElevenLabs conversational agent can be plugged in through /api/voice/session once a
// key and agent id are stored; until then this button is speech-to-text only.
export default function VoiceDirector({ onUtterance }) {
  const [state, setState] = useState("idle");   // idle | listening | transcribing | unsupported
  const rec = useRef(null);
  const chunks = useRef([]);

  useEffect(() => () => { try { rec.current?.stop?.(); } catch { /* already stopped */ } }, []);

  async function start() {
    const SR = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (SR) {
      const r = new SR();
      r.lang = "en-KE"; r.interimResults = false; r.maxAlternatives = 1;
      r.onresult = (e) => { const t = e.results[0][0].transcript; setState("idle"); if (t) onUtterance(t); };
      r.onerror = () => setState("idle");
      r.onend = () => setState((s) => (s === "listening" ? "idle" : s));
      rec.current = r;
      setState("listening");
      r.start();
      return;
    }
    if (!navigator.mediaDevices?.getUserMedia) { setState("unsupported"); return; }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream);
    chunks.current = [];
    mr.ondataavailable = (e) => chunks.current.push(e.data);
    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      setState("transcribing");
      const form = new FormData();
      form.append("audio", new Blob(chunks.current, { type: mr.mimeType || "audio/webm" }), "clip.webm");
      const res = await fetch("/api/transcribe", { method: "POST", body: form });
      const data = await res.json().catch(() => ({}));
      setState("idle");
      if (res.ok && data.transcript) onUtterance(data.transcript);
    };
    rec.current = mr;
    setState("listening");
    mr.start();
  }

  function stop() {
    try { rec.current?.stop(); } catch { /* nothing recording */ }
    if (rec.current instanceof MediaRecorder) return;   // onstop finishes it
    setState("idle");
  }

  if (state === "unsupported") return <span className="chip" title="This browser has no microphone access">No mic</span>;
  return (
    <button type="button" className={`icon-btn mic${state === "listening" ? " is-on" : ""}`}
      onClick={state === "listening" ? stop : start} disabled={state === "transcribing"}
      aria-pressed={state === "listening"} aria-label={state === "listening" ? "Stop listening" : "Talk to the director"}
      title={state === "transcribing" ? "Transcribing…" : "Talk to the director"}>
      {state === "listening" ? "■" : state === "transcribing" ? "…" : "🎙"}
    </button>
  );
}
