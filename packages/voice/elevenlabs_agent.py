"""The studio's voice director on ElevenLabs: ten client tools and one agent that uses them.

The tools run in the browser (components/VoiceDirector.js), so the agent never touches the
repo, a GPU or money directly: every tool turns into a director utterance or a run request
that goes through the same gates as typing. The key is read from the vault; agent and tool
ids are not secret and live in brands/_presets/voice-agent.json.

    python packages/voice/elevenlabs_agent.py payload      # print what would be sent; no network
    python packages/voice/elevenlabs_agent.py sync         # create or update the tools and the agent
    python packages/voice/elevenlabs_agent.py signed-url   # a short-lived URL for one browser session
    python packages/voice/elevenlabs_agent.py show         # the agent as ElevenLabs holds it
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import yaml

REPO = Path(__file__).resolve().parents[2]
API = "https://api.elevenlabs.io"
STATE = REPO / "brands" / "_presets" / "voice-agent.json"
AGENT_NAME = "EPALLE Studio Director"
VOICE_ID = "21m00Tcm4TlvDq8ikWAM"      # the same default voice packages/voice/tts.py uses
LLM = "gemini-2.5-flash"


def _presets() -> tuple[list[str], list[str]]:
    d = yaml.safe_load((REPO / "brands" / "_presets" / "directors.yaml").read_text(encoding="utf-8"))
    p = yaml.safe_load((REPO / "brands" / "_presets" / "profiles.yaml").read_text(encoding="utf-8"))
    return sorted(d["presets"]), sorted(p["profiles"])


def _str(desc: str, enum: list[str] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {"type": "string", "description": desc}
    if enum:
        out["enum"] = enum
    return out


def tools() -> list[dict[str, Any]]:
    looks, kinds = _presets()
    return [
        {"name": "director_say", "description": "Pass any instruction about the piece to the studio director in plain words, when no more specific tool fits. Returns the director's reply.",
         "properties": {"text": _str("The instruction, e.g. 'make scene two a night market'.")}, "required": ["text"]},
        {"name": "add_scene", "description": "Add one scene to the storyboard at a place or moment.",
         "properties": {"place": _str("Where or when the scene happens, e.g. 'a rooftop at golden hour'.")}, "required": ["place"]},
        {"name": "set_angles", "description": "Set how many camera angles to generate for every scene.",
         "properties": {"count": _str("3, 5, 10 or 20.", ["3", "5", "10", "20"])}, "required": ["count"]},
        {"name": "set_look", "description": "Choose the visual aesthetic (framing, lens, palette, grade, motion).",
         "properties": {"look": _str("The look.", looks)}, "required": ["look"]},
        {"name": "set_kind", "description": "Choose the kind of piece, which sets the beats, narration and scene count.",
         "properties": {"kind": _str("The kind of piece.", kinds)}, "required": ["kind"]},
        {"name": "attach_reference", "description": "Attach a folder of reference files the user has in the studio: clothes, a location, jewellery, or a motion clip.",
         "properties": {"purpose": _str("What the references are for.", ["wardrobe", "location", "jewellery", "motion"]),
                        "name": _str("The folder name the user gave, e.g. 'red-dress'."),
                        "rights": _str("Owned by the user, licensed, or unclear. Ask if you do not know.", ["owned", "licensed", "unclear"])},
         "required": ["purpose", "name", "rights"]},
        {"name": "keep_candidates", "description": "Record which candidate images the user keeps at a pick step. Only call after the user names the numbers.",
         "properties": {"pick_node": _str("The pick step id from workflow_status, e.g. 'scene1.pick.keep'."),
                        "numbers": _str("Comma-separated candidate numbers, e.g. '1, 3, 4'.")},
         "required": ["pick_node", "numbers"]},
        {"name": "set_run_mode", "description": "Change how stages run: dry-run spends nothing; stage-approval needs the user to approve each stage; auto runs until a pick or publishing.",
         "properties": {"mode": _str("The run mode.", ["dry-run", "stage-approval", "auto"])}, "required": ["mode"]},
        {"name": "run_stage", "description": "Run one stage under the current run mode. Say the cost gate out loud if the reply mentions approval or budget.",
         "properties": {"stage": _str("A stage id from workflow_status, or 'next'.")}, "required": ["stage"]},
        {"name": "workflow_status", "description": "Read the current workflow: title, run mode, look, kind, scenes, stages, picks waiting and steps not runnable yet.",
         "properties": {}, "required": []},
    ]


PROMPT = """You are the director's assistant inside EPALLE Studio, a production studio that turns an idea into images and video.
The person talking to you is directing a piece. Your job is to turn what they say into studio actions with your tools, then say briefly what changed.

How to work:
- Call workflow_status at the start and whenever you need stage ids or pick step ids. Never invent ids.
- Use the specific tools (add_scene, set_angles, set_look, set_kind, attach_reference, keep_candidates, set_run_mode, run_stage). Use director_say only when nothing else fits.
- Keep replies to one or two short sentences. Read back numbers and names you set.
- Before run_stage in stage-approval or auto mode, say that it spends GPU time and ask for a clear yes.
- If a tool reply mentions approval, budget, consent, rights or a gap, tell the user plainly; do not retry around it.
- Looks and kinds of piece are style grammar. Never make an image of a real, named person, and never claim a real person's face or voice.
- References with unclear rights can only inspire; say so if the user wants to use them directly.
"""

FIRST_MESSAGE = "Director here. What are we making, and what should it look like?"


def tool_config(t: dict[str, Any]) -> dict[str, Any]:
    return {"tool_config": {"type": "client", "name": t["name"], "description": t["description"],
                            "expects_response": True, "response_timeout_secs": 120,
                            "parameters": {"type": "object", "properties": t["properties"], "required": t["required"]}}}


def agent_config(tool_ids: list[str]) -> dict[str, Any]:
    return {"name": AGENT_NAME, "tags": ["epalle-studio", "director"],
            "conversation_config": {
                "agent": {"first_message": FIRST_MESSAGE, "language": "en",
                          "prompt": {"prompt": PROMPT, "llm": LLM, "temperature": 0.3, "tool_ids": tool_ids}},
                "tts": {"voice_id": VOICE_ID}}}


class AgentError(RuntimeError):
    pass


def _key() -> str:
    sys.path.insert(0, str(REPO / "packages" / "common"))
    import vault
    k = vault.get("ELEVENLABS_API_KEY")
    if not k:
        raise AgentError("ELEVENLABS_API_KEY is not set; run infra/runpod/set_secret.py elevenlabs")
    return k


def _call(method: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"xi-api-key": _key(), "Content-Type": "application/json", "User-Agent": "epalle-studio/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            raw = r.read()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raise AgentError(f"{method} {path} -> {e.code}: {e.read().decode('utf-8', 'replace')[:500]}") from e


def load_state() -> dict[str, Any]:
    return json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}


def sync() -> dict[str, Any]:
    """Create or update every tool, then the agent. Safe to run again; it updates in place."""
    state = load_state()
    ids: dict[str, str] = dict(state.get("tools", {}))
    for t in tools():
        cfg = tool_config(t)
        if t["name"] in ids:
            try:
                _call("PATCH", f"/v1/convai/tools/{ids[t['name']]}", cfg)
                continue
            except AgentError as e:
                if "404" not in str(e):
                    raise
        ids[t["name"]] = _call("POST", "/v1/convai/tools", cfg)["id"]
    cfg = agent_config([ids[t["name"]] for t in tools()])
    agent_id = state.get("agent_id")
    if agent_id:
        try:
            _call("PATCH", f"/v1/convai/agents/{agent_id}", cfg)
        except AgentError as e:
            if "404" not in str(e):
                raise
            agent_id = None
    if not agent_id:
        agent_id = _call("POST", "/v1/convai/agents/create", cfg)["agent_id"]
    state = {"agent_id": agent_id, "name": AGENT_NAME, "llm": LLM, "voice_id": VOICE_ID, "tools": ids}
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8", newline="\n")
    return state


def signed_url() -> str:
    agent_id = load_state().get("agent_id")
    if not agent_id:
        raise AgentError("no voice agent yet; run `python packages/voice/elevenlabs_agent.py sync`")
    q = urllib.parse.urlencode({"agent_id": agent_id})
    return _call("GET", f"/v1/convai/conversation/get-signed-url?{q}")["signed_url"]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["payload", "sync", "signed-url", "show"])
    a = ap.parse_args()
    try:
        if a.command == "payload":
            print(json.dumps({"tools": [tool_config(t) for t in tools()], "agent": agent_config(["<tool ids>"])}, indent=2))
        elif a.command == "sync":
            s = sync()
            print(f"agent {s['agent_id']} with {len(s['tools'])} tools -> {STATE.relative_to(REPO)}")
        elif a.command == "signed-url":
            print(json.dumps({"signed_url": signed_url()}))
        else:
            agent_id = load_state().get("agent_id")
            if not agent_id:
                raise AgentError("no voice agent yet")
            d = _call("GET", f"/v1/convai/agents/{agent_id}")
            prompt = d.get("conversation_config", {}).get("agent", {}).get("prompt", {})
            print(json.dumps({"agent_id": agent_id, "name": d.get("name"), "llm": prompt.get("llm"),
                              "tool_ids": prompt.get("tool_ids")}, indent=2))
    except AgentError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
