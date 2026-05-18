"""Mapping from ruang display name to EMR's id_ruangx numeric value.

Source: docs/EMR-FLOW.md - discovered from Task 7 EMR site inspection.
"""
from __future__ import annotations

# EMR id_ruangx -> display label mapping
RUANG_ID_TO_NAME: dict[int, str] = {
    144: "RAWAT INAP",
    145: "UGD",
    146: "IMUNISASI",
    147: "POLI MTBS",
    148: "POLI KIA",
    149: "POLI GIGI",
    150: "POLI UMUM",
    151: "GUDANG PENYIMPANAN BARANG",
    153: "PONED",
    559: "POLI LANSIA",
    653: "POLI GIZI",
    654: "POLI REMAJA",
    655: "POLI SANITASI",
    656: "POLI KB",
    657: "POLI AKUPRESSUR",
    721: "GUDANG OBAT ED/RUSAK",
    729: "PSC 119",
    776: "PROLANIS",
    870: "POLI CJH",
    871: "POLI TB",
    872: "POLI DISABILITAS",
    873: "CKG",
    874: "POLI PTM",
}

# Reverse map: display name -> id_ruangx value
RUANG_NAME_TO_ID: dict[str, int] = {v: k for k, v in RUANG_ID_TO_NAME.items()}

# Special "all ruang" sentinel
RUANG_ALL_VALUE = "0"


def resolve_ruang_id(ruang_name: str | None) -> str:
    """Resolve a ruang display name to its EMR id_ruangx value.

    Args:
        ruang_name: Display name (e.g., "POLI UMUM") or None for all ruang.

    Returns:
        String value to pass to <select name='id_ruangx'>.

    Raises:
        ValueError: If name not in known mapping.
    """
    if ruang_name is None or ruang_name == "":
        return RUANG_ALL_VALUE
    upper = ruang_name.upper().strip()
    if upper in RUANG_NAME_TO_ID:
        return str(RUANG_NAME_TO_ID[upper])
    raise ValueError(
        f"Unknown ruang name: {ruang_name!r}. "
        f"Valid names: {sorted(RUANG_NAME_TO_ID)}"
    )
