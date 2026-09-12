"""The secrets path works end to end: what set_secret.py stores is what adapters read."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "packages" / "common"))
import vault  # noqa: E402


def test_environment_wins(monkeypatch, tmp_path):
    monkeypatch.setenv("EPALLE_SECRETS_DIR", str(tmp_path))
    monkeypatch.setenv("POSTIZ_API_KEY", "from-env")
    assert vault.get("POSTIZ_API_KEY") == "from-env"
    assert vault.source("POSTIZ_API_KEY") == "environment"


def test_missing_is_none_not_empty_string(monkeypatch, tmp_path):
    monkeypatch.setenv("EPALLE_SECRETS_DIR", str(tmp_path))
    monkeypatch.delenv("OPENWA_API_KEY", raising=False)
    assert vault.get("OPENWA_API_KEY") is None
    assert "set_secret.py openwa" in vault.missing_hint("OPENWA_API_KEY")


def test_refuses_to_write_inside_the_repo_or_store_empty():
    with pytest.raises(ValueError):
        vault.put("OPENROUTER_API_KEY", "x", REPO / "work" / "leak.dpapi")
    with pytest.raises(ValueError):
        vault.put("OPENROUTER_API_KEY", "   ")


@pytest.mark.skipif(sys.platform != "win32", reason="DPAPI is Windows-only")
def test_set_secret_round_trips_to_the_adapter_read(monkeypatch, tmp_path):
    monkeypatch.setenv("EPALLE_SECRETS_DIR", str(tmp_path))
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    env = {k: v for k, v in os.environ.items() if k != "OPENROUTER_API_KEY"}
    r = subprocess.run([sys.executable, "infra/runpod/set_secret.py", "openrouter",
                        "--value", "sk-or-test-roundtrip"], cwd=REPO, capture_output=True,
                       text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "sk-or" not in r.stdout, "set_secret must never echo any part of the value"
    assert vault.get("OPENROUTER_API_KEY") == "sk-or-test-roundtrip"
    assert "encrypted store" in vault.source("OPENROUTER_API_KEY")


def test_every_known_secret_is_storable_from_the_cli():
    r = subprocess.run([sys.executable, "infra/runpod/set_secret.py", "--help"], cwd=REPO,
                       capture_output=True, text=True)
    for name in vault.KNOWN:
        assert name in r.stdout


def test_no_adapter_reads_a_secret_around_the_vault():
    """A direct os.environ read skips the encrypted store, so a stored key is silently ignored."""
    names = "|".join(vault.KNOWN.values())
    pat = re.compile(r"os\.environ(?:\.get\(|\[)['\"](" + names + r")['\"]")
    pod_side = {"download_planned.py", "download-workflow-models.py", "handler.py", "vault.py"}
    offenders = [str(p.relative_to(REPO))
                 for root in ("packages", "infra") for p in (REPO / root).rglob("*.py")
                 if p.name not in pod_side and "node_modules" not in p.parts
                 and pat.search(p.read_text(encoding="utf-8", errors="replace"))]
    assert not offenders, offenders
