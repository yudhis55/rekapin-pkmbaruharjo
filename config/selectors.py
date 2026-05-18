"""Selectors loaded from config/selectors.yaml with Pydantic validation.

Schema reflects the ACTUAL EMR structure discovered in Task 7:
- Detail pages are form POST navigation (NOT modals)
- No pagination on pendaftaran induk page
- Visit data is inline in nested tables per patient row
- CSRF token required for every form POST
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict


class LoginSelectors(BaseModel):
    """Login form selectors."""

    model_config = ConfigDict(extra="ignore")

    puskesmas_select: str
    puskesmas_value: str  # value attribute of the chosen option (e.g., "16")
    username_input: str
    password_input: str
    submit_button: str
    csrf_token: str
    login_hidden: str
    puskesmas_type: str = "select2_over_native"


class DashboardSelectors(BaseModel):
    """Post-login dashboard navigation."""

    model_config = ConfigDict(extra="ignore")

    pendaftaran_induk_link: str
    pendaftaran_induk_text: str = "PENDAFTARAN INDUK"
    logout_button: str


class DaftarSelectors(BaseModel):
    """Patient list page filters and table."""

    model_config = ConfigDict(extra="ignore")

    # Filter inputs
    search_rm: str
    search_no_rm_lama: str
    search_nik: str
    search_nama: str
    search_alamat: str
    ruang_filter: str
    dokumen_filter: str
    date_filter: str
    apply_filter_button: str
    # Patient table
    patient_table: str
    patient_row: str


class DetailSelectors(BaseModel):
    """Per-patient detail/action selectors (form POST navigation)."""

    model_config = ConfigDict(extra="ignore")

    resume_button: str
    cppt_button: str
    rm_button: str
    edit_button: str
    daftar_button: str
    bayar_button: str
    kunjungan_table: str
    tindakan_table: str
    biaya_field: str


class PaginationSelectors(BaseModel):
    """Pagination controls (None values mean not present)."""

    model_config = ConfigDict(extra="ignore")

    next_button: str | None = None
    page_indicator: str | None = None


class SessionSelectors(BaseModel):
    """Session and CSRF info."""

    model_config = ConfigDict(extra="ignore")

    login_redirect_url_pattern: str
    csrf_token_name: str = "csrf_token_name"


class Selectors(BaseModel):
    """Root selectors model."""

    model_config = ConfigDict(extra="ignore")

    login: LoginSelectors
    dashboard: DashboardSelectors
    daftar: DaftarSelectors
    detail: DetailSelectors
    pagination: PaginationSelectors
    session: SessionSelectors


_DEFAULT_PATH = Path(__file__).parent / "selectors.yaml"


@lru_cache(maxsize=4)
def load_selectors(path: str | None = None) -> Selectors:
    """Load and validate selectors from YAML."""
    yaml_path = Path(path) if path else _DEFAULT_PATH
    with yaml_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return Selectors.model_validate(data)
