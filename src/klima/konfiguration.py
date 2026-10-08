"""Laden der Projektkonfiguration aus `konfiguration/*.toml`."""

from __future__ import annotations

import os
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

GUELTIGE_TYPEN = ("datei", "verzeichnis", "stationsauswahl")

# Benannte Gruppen im Dateimuster, über die `--von`/`--bis` wirken können
ZEITGRUPPEN = ("jahr", "beginn")


def projektwurzel() -> Path:
    """Wurzelverzeichnis des Projekts; über `KLIMA_PROJEKT` überschreibbar."""
    if pfad := os.environ.get("KLIMA_PROJEKT"):
        return Path(pfad).resolve()
    # src/klima/konfiguration.py -> drei Ebenen nach oben
    return Path(__file__).resolve().parents[2]


def rohverzeichnis() -> Path:
    """Ablageort der heruntergeladenen Rohdaten."""
    return projektwurzel() / "daten" / "roh"


@dataclass(frozen=True)
class Datensatz:
    """Ein herunterladbarer Datensatz gemäß `quellen.toml`."""

    name: str
    beschreibung: str
    typ: str
    urls: tuple[str, ...] = ()
    url: str | None = None
    muster: str | None = None
    standard: bool = False
    _muster_kompiliert: re.Pattern[str] | None = field(default=None, repr=False, compare=False)

    @property
    def dateimuster(self) -> re.Pattern[str] | None:
        return self._muster_kompiliert

    @property
    def zeitfilter_moeglich(self) -> bool:
        """True, wenn `--von`/`--bis` die Dateiauswahl einschränken können."""
        if self.dateimuster is None:
            return False
        return any(g in self.dateimuster.groupindex for g in ZEITGRUPPEN)


def _datensatz_aus_eintrag(name: str, eintrag: dict) -> Datensatz:
    typ = eintrag.get("typ")
    if typ not in GUELTIGE_TYPEN:
        raise ValueError(f"Datensatz {name!r}: unbekannter Typ {typ!r}, erlaubt: {GUELTIGE_TYPEN}")

    muster_kompiliert = None
    if typ == "datei":
        urls = tuple(eintrag.get("urls", ()))
        if not urls:
            raise ValueError(f"Datensatz {name!r}: Typ 'datei' benötigt 'urls'.")
    elif typ == "stationsauswahl":
        if "{station}" not in eintrag.get("url", ""):
            raise ValueError(
                f"Datensatz {name!r}: Typ 'stationsauswahl' benötigt 'url' mit Platzhalter "
                "'{station}'."
            )
        urls = ()
    else:
        if not eintrag.get("url") or not eintrag.get("muster"):
            raise ValueError(f"Datensatz {name!r}: Typ 'verzeichnis' benötigt 'url' und 'muster'.")
        if not eintrag["url"].endswith("/"):
            raise ValueError(f"Datensatz {name!r}: 'url' eines Verzeichnisses muss auf '/' enden.")
        muster_kompiliert = re.compile(eintrag["muster"])
        gruppen = muster_kompiliert.groupindex
        if "beginn" in gruppen and "ende" not in gruppen:
            raise ValueError(f"Datensatz {name!r}: Gruppe 'beginn' erfordert auch 'ende'.")
        urls = ()

    return Datensatz(
        name=name,
        beschreibung=eintrag.get("beschreibung", ""),
        typ=typ,
        urls=urls,
        url=eintrag.get("url"),
        muster=eintrag.get("muster"),
        standard=bool(eintrag.get("standard", False)),
        _muster_kompiliert=muster_kompiliert,
    )


def lade_quellen(pfad: Path | None = None) -> dict[str, Datensatz]:
    """Liest `quellen.toml` und gibt die Datensätze in Dateireihenfolge zurück."""
    pfad = pfad or projektwurzel() / "konfiguration" / "quellen.toml"
    with pfad.open("rb") as f:
        roh = tomllib.load(f)
    return {name: _datensatz_aus_eintrag(name, eintrag) for name, eintrag in roh.items()}


def lade_analyse(pfad: Path | None = None) -> dict:
    """Liest die Standardwerte für Analysen aus `analyse.toml`."""
    pfad = pfad or projektwurzel() / "konfiguration" / "analyse.toml"
    with pfad.open("rb") as f:
        return tomllib.load(f)
