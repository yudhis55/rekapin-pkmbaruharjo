"""Tests for config module: settings, ruang list, selectors."""
from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from pydantic import SecretStr, ValidationError

from config.ruang import RUANG_LIST
from config.selectors import Selectors, load_selectors
from config.settings import Settings


def test_settings_loads_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMR_USERNAME", "user1")
    monkeypatch.setenv("EMR_PASSWORD", "pw1")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test/daf")
    monkeypatch.setenv("EMR_PUSKESMAS", "PUSKESMAS X")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    assert isinstance(s.emr_password, SecretStr)
    assert s.emr_password.get_secret_value() == "pw1"
    assert s.emr_puskesmas == "PUSKESMAS X"
    # Defaults
    assert s.browser_mode == "headless"
    assert s.scrape_timeout == 60


def test_settings_password_redacted_in_repr(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("EMR_USERNAME", "u")
    monkeypatch.setenv("EMR_PASSWORD", "supersecret123")
    monkeypatch.setenv("EMR_BASE_URL", "https://example.test")
    monkeypatch.setenv("EMR_PUSKESMAS", "P")
    s = Settings(_env_file=None)  # type: ignore[call-arg]
    text = repr(s)
    assert "supersecret123" not in text
    assert "**********" in text or "SecretStr" in text


def test_settings_missing_required_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    # Clear all relevant env vars
    for key in ["EMR_USERNAME", "EMR_PASSWORD", "EMR_BASE_URL", "EMR_PUSKESMAS"]:
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None)  # type: ignore[call-arg]


def test_ruang_list_non_empty() -> None:
    assert len(RUANG_LIST) >= 1
    assert all(isinstance(r, str) and r.strip() for r in RUANG_LIST)
    assert "Poli Umum" in RUANG_LIST


def test_selectors_yaml_loads() -> None:
    sel = load_selectors()
    assert isinstance(sel, Selectors)
    assert sel.login.username_input  # non-empty
    assert sel.daftar.patient_table


def test_selectors_yaml_invalid_raises(tmp_path: Path) -> None:
    bad_yaml = tmp_path / "bad.yaml"
    bad_yaml.write_text("login:\n  username_input: only_one_field\n", encoding="utf-8")
    # Clear cache to force reload
    load_selectors.cache_clear()
    with pytest.raises(ValidationError):
        load_selectors(str(bad_yaml))
