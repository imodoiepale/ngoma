"""The ElevenLabs voice director: the tools the agent is given are exactly the tools the browser
answers, the payloads are well formed, and nothing here touches the network or the key."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "voice"))
import elevenlabs_agent as ea  # noqa: E402

VOICE_JS = REPO / "packages" / "studio-ui" / "client" / "components" / "VoiceDirector.js"


def _js_tools() -> set[str]:
    src = VOICE_JS.read_text(encoding="utf-8")
    block = src[src.index("clientTools: {"):src.index("onError")]
    return set(re.findall(r"^\s{6}(\w+):", block, flags=re.M))


def test_agent_tools_match_the_browser_handlers():
    assert {t["name"] for t in ea.tools()} == _js_tools()


def test_tool_payloads_are_client_tools_with_valid_schemas():
    for t in ea.tools():
        cfg = ea.tool_config(t)["tool_config"]
        assert cfg["type"] == "client" and cfg["expects_response"] is True
        params = cfg["parameters"]
        assert params["type"] == "object" and set(params["required"]) <= set(params["properties"])
        assert cfg["description"] and len(cfg["name"]) <= 64


def test_looks_and_kinds_are_offered_from_the_presets():
    by = {t["name"]: t for t in ea.tools()}
    looks, kinds = ea._presets()
    assert by["set_look"]["properties"]["look"]["enum"] == looks and "neon-noir" in looks
    assert by["set_kind"]["properties"]["kind"]["enum"] == kinds and "lookbook" in kinds


def test_agent_config_carries_the_tools_and_the_rules():
    cfg = ea.agent_config(["t1", "t2"])
    prompt = cfg["conversation_config"]["agent"]["prompt"]
    assert prompt["tool_ids"] == ["t1", "t2"]
    assert "spends GPU time" in prompt["prompt"] and "real, named person" in prompt["prompt"]


def test_saved_agent_state_holds_ids_not_secrets():
    if not ea.STATE.exists():
        return
    text = ea.STATE.read_text(encoding="utf-8")
    assert not re.search(r"sk_[0-9a-f]{20,}", text)
    state = json.loads(text)
    assert state["agent_id"] and set(state["tools"]) == {t["name"] for t in ea.tools()}


def test_saved_agent_state_name_matches_the_module():
    """`sync` writes AGENT_NAME into the state file; a rename in the module without the
    preset following it would show the old product name in the ElevenLabs dashboard."""
    if not ea.STATE.exists():
        return
    state = json.loads(ea.STATE.read_text(encoding="utf-8"))
    assert state["name"] == ea.AGENT_NAME
    assert (state["llm"], state["voice_id"]) == (ea.LLM, ea.VOICE_ID)
