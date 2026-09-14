"use client";

import { useRef, useState } from "react";
import { ConversationProvider, useConversation } from "@elevenlabs/react";

// Talk to the director out loud. The ElevenLabs agent ("EPALLE Studio Director") listens and
// speaks; its tools run here in the browser and go through the same /api/director and /api/run
// gates as typing. Tool names must match packages/voice/elevenlabs_agent.py (a test checks).
// If the agent is not reachable, the button falls back to the browser's own speech recognition.
export default function VoiceDirector(props) {
  return (
    <ConversationProvider>
      <Voice {...props} />
    </ConversationProvider>
  );
}

function Voice({ onUtterance, onRun, getStatus }) {
  const [fallback, setFallback] = useState("idle");   // idle | listening
  const [note, setNote] = useState("");
  const rec = useRef(null);

  const say = async (text) => (await onUtterance(text)) || "Done.";
  const conversation = useConversation({
    clientTools: {
      director_say: ({ text }) => say(text),
      add_scene: ({ place }) => say(`add a scene at ${place}`),
      set_angles: ({ count }) => say(`${count} angles per scene`),
      set_look: ({ look }) => say(`use the ${look} look`),
      set_kind: ({ kind }) => say(`direct it as a ${kind}`),
      attach_reference: ({ purpose, name, rights }) => {
        const owner = rights === "owned" ? "my " : rights === "licensed" ? "licensed " : "";
        return say(`${purpose === "motion" ? "motion clip" : purpose} from ${owner}${name}`);
      },
      keep_candidates: ({ pick_node, numbers }) => say(`keep at ${pick_node}: ${String(numbers)}`),
      set_run_mode: ({ mode }) => say(`switch to ${mode} mode`),
      run_stage: async ({ stage }) => (await onRun?.(stage || "next")) || "Run requested.",
      workflow_status: () => JSON.stringify(getStatus ? getStatus() : {}),
    },
    onError: (e) => setNote(String(e?.message || e || "Voice error")),
    onDisconnect: () => setNote(""),
  });
  const live = conversation.status === "connected" || conversation.status === "connecting";

  async function start() {
    setNote("");
    try {
      const res = await fetch("/api/voice/session", { cache: "no-store" });
      const data = await res.json().catch(() => ({}));
      if (!res.ok || !data.signedUrl) throw new Error(data.error || "The voice agent is not set up.");
      await navigator.mediaDevices.getUserMedia({ audio: true });
      await conversation.startSession({ signedUrl: data.signedUrl, connectionType: "websocket" });
    } catch (e) {
      setNote(`${e.message} Using this browser's speech recognition instead.`);
      listenLocally();
    }
  }

  function listenLocally() {
    const SR = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
    if (!SR) { setNote("No voice agent and no speech recognition in this browser."); return; }
    const r = new SR();
    r.lang = "en-KE"; r.interimResults = false; r.maxAlternatives = 1;
    r.onresult = (e) => { const t = e.results[0][0].transcript; if (t) onUtterance(t); };
    r.onend = () => setFallback("idle");
    r.onerror = () => setFallback("idle");
    rec.current = r;
    setFallback("listening");
    r.start();
  }

  async function stop() {
    if (live) await conversation.endSession();
    try { rec.current?.stop(); } catch { /* not listening */ }
    setFallback("idle");
  }

  const on = live || fallback === "listening";
  return (
    <span className="voice">
      <button type="button" className={`icon-btn mic${on ? " is-on" : ""}`} onClick={on ? stop : start}
        aria-pressed={on} aria-label={on ? "Stop talking to the director" : "Talk to the director"}
        title={live ? (conversation.isSpeaking ? "Director is speaking" : "Director is listening") : "Talk to the director"}>
        {on ? "■" : "🎙"}
      </button>
      {note && <span className="voice-note" role="status">{note}</span>}
    </span>
  );
}
