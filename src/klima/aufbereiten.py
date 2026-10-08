"""Aufbereitung: Rohdaten einmal vollständig parsen und als Parquet bzw. NetCDF ablegen.

Ablage: `daten/aufbereitet/<datensatz>/<teil>.parquet` bzw. `.nc` (siehe SPEC.md, F-IO-6a–c).

Jede Ausgabedatei trägt in ihren Metadaten eine Quellkennung: einen Hash über die
SHA-256-Prüfsummen der verwendeten Rohdateien (aus dem Manifest) und die Version der
Aufbereitung. Stimmt die Kennung nicht mehr mit dem aktuellen Manifest überein, gilt die
Datei als veraltet und wird neu erzeugt.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import xarray as xr

from klima.herunterladen import MANIFEST_NAME, Manifest
from klima.parser import dwd, ersst, ghcnm, vergleichsreihen

# Bei Änderungen an Parsern oder Ausgabeformat erhöhen -> alles wird neu aufbereitet
AUFBEREITUNG_VERSION = "1"
METADATEN_SCHLUESSEL = "klima_quellkennung"
PARQUET_ZEILENGRUPPE = 500_000


@dataclass
class Ausgabe:
    """Ein aufbereiteter Teil eines Datensatzes (Tabelle oder Gitter)."""

    teil: str
    daten: pd.DataFrame | xr.Dataset

    @property
    def dateiname(self) -> str:
        return f"{self.teil}.nc" if isinstance(self.daten, xr.Dataset) else f"{self.teil}.parquet"


class RohdatenFehlen(FileNotFoundError):
    """Für einen Datensatz liegen keine heruntergeladenen Rohdaten vor."""


# --- Aufbereiter je Datensatz --------------------------------------------------


def _eine_datei(dateien: list[Path]) -> Path:
    if len(dateien) != 1:
        raise ValueError(f"Erwartet genau eine Rohdatei, gefunden: {len(dateien)}")
    return dateien[0]


def _ghcnm(dateien: list[Path]) -> list[Ausgabe]:
    archiv = _eine_datei(dateien)
    return [
        Ausgabe("stationen", ghcnm.lies_stationen(archiv)),
        Ausgabe("monatswerte", ghcnm.lies_monatswerte(archiv)),
    ]


def _ghcnm_laender(dateien: list[Path]) -> list[Ausgabe]:
    return [Ausgabe("laender", ghcnm.lies_laender(_eine_datei(dateien)))]


def _ersst(dateien: list[Path]) -> list[Ausgabe]:
    return [Ausgabe("sst", ersst.lies_ersst(dateien))]


def _gistemp(dateien: list[Path]) -> list[Ausgabe]:
    return [Ausgabe("reihen", vergleichsreihen.lies_gistemp_alle(dateien))]


def _hadcrut(dateien: list[Path]) -> list[Ausgabe]:
    return [Ausgabe("reihen", vergleichsreihen.lies_hadcrut_alle(dateien))]


def _dwd_stationen(dateien: list[Path]) -> list[Ausgabe]:
    teile = {"KL_Tageswerte": "stationen_tag", "KL_Monatswerte": "stationen_monat"}
    ausgaben = []
    for pfad in sorted(dateien):
        teil = next((t for praefix, t in teile.items() if pfad.name.startswith(praefix)), None)
        if teil is None:
            raise ValueError(f"Unbekannte DWD-Stationsliste: {pfad.name}")
        ausgaben.append(Ausgabe(teil, dwd.lies_stationsliste(pfad)))
    return ausgaben


def _dwd_gebietsmittel(groesse: str) -> Callable[[list[Path]], list[Ausgabe]]:
    def aufbereiter(dateien: list[Path]) -> list[Ausgabe]:
        return [Ausgabe("monatswerte", dwd.lies_gebietsmittel_alle(sorted(dateien), groesse))]

    return aufbereiter


def _dwd_monatswerte(dateien: list[Path]) -> list[Ausgabe]:
    return [Ausgabe("monatswerte", dwd.lies_monatswerte_alle(dateien))]


def _dwd_tageswerte(dateien: list[Path]) -> list[Ausgabe]:
    return [Ausgabe("tageswerte", dwd.lies_tageswerte_alle(dateien))]


AUFBEREITER: dict[str, Callable[[list[Path]], list[Ausgabe]]] = {
    "ghcnm_qcu": _ghcnm,
    "ghcnm_qcf": _ghcnm,
    "ghcnm_qfe": _ghcnm,
    "ghcnm_laender": _ghcnm_laender,
    "ersst_v5": _ersst,
    "gistemp": _gistemp,
    "hadcrut5": _hadcrut,
    "dwd_stationen": _dwd_stationen,
    "dwd_gebietsmittel_temperatur": _dwd_gebietsmittel("temperatur"),
    "dwd_gebietsmittel_niederschlag": _dwd_gebietsmittel("niederschlag"),
    "dwd_monatswerte": _dwd_monatswerte,
    "dwd_tageswerte": _dwd_tageswerte,
}

# Aufbereitete Datensätze, die aus mehreren Rohdatensätzen entstehen; sonst gilt der eigene Name
QUELLDATENSAETZE: dict[str, tuple[str, ...]] = {
    "dwd_monatswerte": ("dwd_monat_historisch", "dwd_monat_aktuell"),
    "dwd_tageswerte": ("dwd_tag_historisch", "dwd_tag_aktuell"),
}


def quelldatensaetze(datensatz: str) -> tuple[str, ...]:
    return QUELLDATENSAETZE.get(datensatz, (datensatz,))


# --- Quellkennung und Aktualität -----------------------------------------------


def quellkennung(manifest: Manifest, datensatz: str) -> str | None:
    """Hash über Version und Prüfsummen aller Rohdateien des Datensatzes.

    None, wenn für mindestens einen Quelldatensatz keine Rohdaten vorliegen.
    """
    eintraege = []
    for quelle in quelldatensaetze(datensatz):
        teil = manifest.eintraege_fuer(quelle)
        if not teil:
            return None
        eintraege += teil
    eintraege.sort(key=lambda e: e["pfad"])
    pruefsumme = hashlib.sha256(f"version={AUFBEREITUNG_VERSION}\n".encode())
    for eintrag in eintraege:
        pruefsumme.update(f"{eintrag['pfad']}:{eintrag['sha256']}\n".encode())
    return pruefsumme.hexdigest()


def gespeicherte_kennung(pfad: Path) -> str | None:
    """Liest die Quellkennung aus einer aufbereiteten Datei, ohne die Daten zu laden."""
    if not pfad.exists():
        return None
    if pfad.suffix == ".parquet":
        metadaten = pq.read_schema(pfad).metadata or {}
        wert = metadaten.get(METADATEN_SCHLUESSEL.encode())
        return wert.decode() if wert else None
    with xr.open_dataset(pfad) as ds:
        return ds.attrs.get(METADATEN_SCHLUESSEL)


# --- Schreiben -----------------------------------------------------------------


def _schreibe_parquet(tabelle: pd.DataFrame, ziel: Path, kennung: str) -> None:
    arrow = pa.Table.from_pandas(tabelle, preserve_index=False)
    metadaten = {**(arrow.schema.metadata or {}), METADATEN_SCHLUESSEL.encode(): kennung.encode()}
    pq.write_table(
        arrow.replace_schema_metadata(metadaten),
        ziel,
        compression="zstd",
        row_group_size=PARQUET_ZEILENGRUPPE,
    )


def _schreibe_netcdf(ds: xr.Dataset, ziel: Path, kennung: str) -> None:
    ds = ds.copy()
    ds.attrs[METADATEN_SCHLUESSEL] = kennung
    kodierung = {name: {"zlib": True, "complevel": 4, "shuffle": True} for name in ds.data_vars}
    ds.to_netcdf(ziel, engine="netcdf4", encoding=kodierung)


def _schreibe(ausgabe: Ausgabe, ziel: Path, kennung: str) -> None:
    """Schreibt atomar: erst in eine temporäre Datei, dann umbenennen."""
    temp = ziel.with_name(ziel.name + ".tmp")
    if isinstance(ausgabe.daten, xr.Dataset):
        _schreibe_netcdf(ausgabe.daten, temp, kennung)
    else:
        _schreibe_parquet(ausgabe.daten, temp, kennung)
    temp.replace(ziel)


# --- Öffentliche Schnittstelle ---------------------------------------------------


@dataclass
class Ergebnis:
    datensatz: str
    status: str  # "aufbereitet", "aktuell", "keine_rohdaten", "kein_parser"
    dateien: list[Path]


class Aufbereitung:
    """Bereitet Datensätze aus `rohverzeichnis` nach `zielverzeichnis` auf."""

    def __init__(self, rohverzeichnis: Path, zielverzeichnis: Path):
        self.rohverzeichnis = rohverzeichnis
        self.zielverzeichnis = zielverzeichnis

    def _manifest(self) -> Manifest:
        return Manifest(self.rohverzeichnis / MANIFEST_NAME)

    def ausgabedateien(self, datensatz: str) -> list[Path]:
        """Vorhandene aufbereitete Dateien eines Datensatzes."""
        ordner = self.zielverzeichnis / datensatz
        if not ordner.exists():
            return []
        return sorted(p for p in ordner.iterdir() if p.suffix in (".parquet", ".nc"))

    def ist_aktuell(self, datensatz: str, manifest: Manifest | None = None) -> bool:
        kennung = quellkennung(manifest or self._manifest(), datensatz)
        dateien = self.ausgabedateien(datensatz)
        return (
            kennung is not None
            and bool(dateien)
            and all(gespeicherte_kennung(p) == kennung for p in dateien)
        )

    def aufbereiten(self, datensatz: str, erzwingen: bool = False) -> Ergebnis:
        if datensatz not in AUFBEREITER:
            return Ergebnis(datensatz, "kein_parser", [])
        manifest = self._manifest()
        kennung = quellkennung(manifest, datensatz)
        if kennung is None:
            return Ergebnis(datensatz, "keine_rohdaten", [])
        if not erzwingen and self.ist_aktuell(datensatz, manifest):
            return Ergebnis(datensatz, "aktuell", self.ausgabedateien(datensatz))

        rohdateien = [
            self.rohverzeichnis / e["pfad"]
            for quelle in quelldatensaetze(datensatz)
            for e in manifest.eintraege_fuer(quelle)
        ]
        fehlend = [p for p in rohdateien if not p.exists()]
        if fehlend:
            raise RohdatenFehlen(
                f"{datensatz}: {len(fehlend)} Rohdatei(en) fehlen, z. B. {fehlend[0]}. "
                f"Bitte `klima laden {' '.join(quelldatensaetze(datensatz))}` ausführen."
            )

        ordner = self.zielverzeichnis / datensatz
        ordner.mkdir(parents=True, exist_ok=True)
        ausgaben = AUFBEREITER[datensatz](rohdateien)
        neue = []
        for ausgabe in ausgaben:
            ziel = ordner / ausgabe.dateiname
            _schreibe(ausgabe, ziel, kennung)
            neue.append(ziel)
        # Veraltete Teile entfernen, die nicht mehr erzeugt werden
        for alt in self.ausgabedateien(datensatz):
            if alt not in neue:
                alt.unlink()
        return Ergebnis(datensatz, "aufbereitet", neue)

    def sicherstellen(self, datensatz: str) -> Path:
        """Bereitet bei Bedarf auf und gibt den Ordner der aufbereiteten Daten zurück."""
        ergebnis = self.aufbereiten(datensatz)
        if ergebnis.status == "keine_rohdaten":
            raise RohdatenFehlen(
                f"Für {datensatz!r} liegen keine Rohdaten vor. "
                f"Bitte zuerst `klima laden {' '.join(quelldatensaetze(datensatz))}` ausführen."
            )
        if ergebnis.status == "kein_parser":
            raise ValueError(f"Für {datensatz!r} gibt es (noch) keine Aufbereitung.")
        return self.zielverzeichnis / datensatz
