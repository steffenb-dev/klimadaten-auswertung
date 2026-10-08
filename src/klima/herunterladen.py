"""Download-Tool: lädt die Rohdaten aus `quellen.toml` nach `daten/roh/<datensatz>/`.

Funktionen (siehe SPEC.md, Abschnitt 4.1):
- Auswahl der Dateien, bei Verzeichnissen optional eingeschränkt auf einen Zeitraum
- bedingte Downloads über ETag/Last-Modified (unveränderte Dateien werden nicht übertragen)
- Fortsetzen abgebrochener Downloads über HTTP-Range
- Wiederholung bei Netzwerk- und Serverfehlern
- Manifest mit URL, Zeitpunkt, Größe und SHA-256 jeder Datei

Archive werden bewusst nicht entpackt; gelesen wird direkt aus dem Archiv (siehe `klima.archiv`).
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from urllib.parse import urljoin, urlsplit

import httpx
from tqdm import tqdm

from klima.konfiguration import Datensatz

BENUTZER_AGENT = "klimadaten-auswertung/0.1"
MAX_VERSUCHE = 4
WARTEZEIT_BASIS_S = 2.0
BLOCKGROESSE = 1 << 20
TEIL_ENDUNG = ".teil"
META_ENDUNG = ".teil.json"
MANIFEST_NAME = "manifest.json"

Monat = tuple[int, int]  # (Jahr, Monat)


# --- Zeitraum ------------------------------------------------------------------


def _lies_monat(text: str | None, anfang: bool) -> Monat | None:
    if text is None:
        return None
    treffer = re.fullmatch(r"(\d{4})(?:-(\d{1,2}))?", text.strip())
    if not treffer:
        raise ValueError(f"Ungültige Zeitangabe {text!r}, erwartet JJJJ oder JJJJ-MM.")
    jahr = int(treffer[1])
    monat = int(treffer[2]) if treffer[2] else (1 if anfang else 12)
    if not 1 <= monat <= 12:
        raise ValueError(f"Ungültiger Monat in {text!r}.")
    return (jahr, monat)


@dataclass(frozen=True)
class Zeitraum:
    """Geschlossener Zeitraum auf Monatsbasis; `None` bedeutet offen."""

    von: Monat | None = None
    bis: Monat | None = None

    @classmethod
    def aus_text(cls, von: str | None = None, bis: str | None = None) -> Zeitraum:
        """Erzeugt einen Zeitraum aus `JJJJ` oder `JJJJ-MM`; `--bis 2000` meint Dezember 2000."""
        zeitraum = cls(_lies_monat(von, anfang=True), _lies_monat(bis, anfang=False))
        if zeitraum.von and zeitraum.bis and zeitraum.von > zeitraum.bis:
            raise ValueError("Beginn des Zeitraums liegt nach dem Ende.")
        return zeitraum

    @property
    def offen(self) -> bool:
        return self.von is None and self.bis is None

    def ueberschneidet(self, beginn: Monat, ende: Monat) -> bool:
        """True, wenn sich [beginn, ende] mit dem Zeitraum überschneidet."""
        return (self.bis is None or beginn <= self.bis) and (self.von is None or ende >= self.von)


def _im_zeitraum(treffer: re.Match[str], zeitraum: Zeitraum) -> bool:
    """Prüft anhand der benannten Gruppen eines Dateinamens, ob die Datei im Zeitraum liegt."""
    gruppen = treffer.groupdict()
    if gruppen.get("jahr"):
        jahr = int(gruppen["jahr"])
        if gruppen.get("monat"):
            monat = int(gruppen["monat"])
            return zeitraum.ueberschneidet((jahr, monat), (jahr, monat))
        return zeitraum.ueberschneidet((jahr, 1), (jahr, 12))
    if gruppen.get("beginn") and gruppen.get("ende"):
        beginn, ende = gruppen["beginn"], gruppen["ende"]
        return zeitraum.ueberschneidet(
            (int(beginn[:4]), int(beginn[4:6])), (int(ende[:4]), int(ende[4:6]))
        )
    return True


# --- Dateiauswahl --------------------------------------------------------------


def dateiname(url: str) -> str:
    return PurePosixPath(urlsplit(url).path).name


def verzeichnis_auflisten(client: httpx.Client, url: str) -> list[str]:
    """Liest eine HTML-Verzeichnisliste und gibt die absoluten URLs der Einträge zurück."""
    antwort = _mit_wiederholung(lambda: client.get(url))
    antwort.raise_for_status()
    verweise = re.findall(r'href="([^"?#]+)"', antwort.text)
    return sorted({urljoin(url, v) for v in verweise})


def dateien_ermitteln(
    client: httpx.Client,
    datensatz: Datensatz,
    zeitraum: Zeitraum,
    stationen: list[str] | None = None,
) -> list[str]:
    """Liefert die URLs, die für einen Datensatz (und ggf. Zeitraum) zu laden sind.

    Beim Typ `stationsauswahl` werden die URLs aus `stationen` gebildet.
    """
    if datensatz.typ == "datei":
        return list(datensatz.urls)
    if datensatz.typ == "stationsauswahl":
        if not stationen:
            raise ValueError(
                f"Datensatz {datensatz.name!r} braucht Stations-IDs (Option --station)."
            )
        assert datensatz.url is not None
        return [datensatz.url.format(station=s.strip()) for s in stationen]

    assert datensatz.url is not None and datensatz.dateimuster is not None
    ergebnis = []
    for url in verzeichnis_auflisten(client, datensatz.url):
        # Nur direkte Einträge des Verzeichnisses, keine Eltern- oder Unterverzeichnisse
        if not url.startswith(datensatz.url) or "/" in url[len(datensatz.url) :]:
            continue
        treffer = datensatz.dateimuster.fullmatch(dateiname(url))
        if treffer and _im_zeitraum(treffer, zeitraum) and _station_passt(treffer, stationen):
            ergebnis.append(url)
    return ergebnis


def _station_passt(treffer: re.Match[str], stationen: list[str] | None) -> bool:
    """Stationsfilter für Verzeichnisse, deren Dateimuster eine Gruppe `station` hat."""
    if not stationen or "station" not in treffer.re.groupindex:
        return True
    gesucht = {s.strip().zfill(len(treffer["station"])) for s in stationen}
    return treffer["station"] in gesucht


# --- Manifest ------------------------------------------------------------------


class Manifest:
    """Protokoll aller heruntergeladenen Dateien (`daten/roh/manifest.json`), threadsicher."""

    def __init__(self, pfad: Path):
        self.pfad = pfad
        self._sperre = threading.Lock()
        self._eintraege: dict[str, dict] = {}
        if pfad.exists():
            self._eintraege = json.loads(pfad.read_text(encoding="utf-8"))

    def eintrag(self, url: str) -> dict | None:
        with self._sperre:
            return self._eintraege.get(url)

    def setze(self, url: str, eintrag: dict) -> None:
        with self._sperre:
            self._eintraege[url] = eintrag

    def eintraege_fuer(self, datensatz: str) -> list[dict]:
        with self._sperre:
            return [e for e in self._eintraege.values() if e.get("datensatz") == datensatz]

    def urls_fuer(self, datensatz: str) -> list[str]:
        with self._sperre:
            return [u for u, e in self._eintraege.items() if e.get("datensatz") == datensatz]

    def entferne(self, url: str) -> dict | None:
        with self._sperre:
            return self._eintraege.pop(url, None)

    def speichern(self) -> None:
        with self._sperre:
            self.pfad.parent.mkdir(parents=True, exist_ok=True)
            temp = self.pfad.with_suffix(".tmp")
            temp.write_text(
                json.dumps(self._eintraege, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            temp.replace(self.pfad)


# --- Download ------------------------------------------------------------------


class VoruebergehenderFehler(Exception):
    """Fehler, bei dem sich ein erneuter Versuch lohnt (Netzwerk, HTTP 5xx, Abbruch)."""


def _mit_wiederholung(aufruf, versuche: int = MAX_VERSUCHE, basis: float = WARTEZEIT_BASIS_S):
    """Führt `aufruf` aus und wiederholt bei vorübergehenden Fehlern mit wachsender Wartezeit."""
    for versuch in range(1, versuche + 1):
        try:
            ergebnis = aufruf()
            if isinstance(ergebnis, httpx.Response) and ergebnis.status_code >= 500:
                raise VoruebergehenderFehler(f"HTTP {ergebnis.status_code}")
            return ergebnis
        except (httpx.TransportError, VoruebergehenderFehler):
            if versuch == versuche:
                raise
            time.sleep(basis * 2 ** (versuch - 1))


def _sha256(pfad: Path) -> str:
    pruefsumme = hashlib.sha256()
    with pfad.open("rb") as f:
        while block := f.read(BLOCKGROESSE):
            pruefsumme.update(block)
    return pruefsumme.hexdigest()


@dataclass
class Ergebnis:
    """Ergebnis für eine Datei: `neu`, `aktualisiert`, `unveraendert`, `entfernt` oder `fehler`."""

    url: str
    pfad: Path
    status: str
    meldung: str = ""


class Lader:
    """Lädt Datensätze herunter und führt das Manifest."""

    def __init__(
        self,
        rohverzeichnis: Path,
        client: httpx.Client | None = None,
        parallel: int = 8,
        erzwingen: bool = False,
        fortschritt: bool = True,
        wartezeit_basis: float = WARTEZEIT_BASIS_S,
    ):
        self.rohverzeichnis = rohverzeichnis
        self.client = client or httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(60.0, connect=20.0),
            headers={"User-Agent": BENUTZER_AGENT},
        )
        self.parallel = max(1, parallel)
        self.erzwingen = erzwingen
        self.fortschritt = fortschritt
        self.wartezeit_basis = wartezeit_basis
        self.manifest = Manifest(rohverzeichnis / MANIFEST_NAME)

    def lade_datensatz(
        self,
        datensatz: Datensatz,
        zeitraum: Zeitraum | None = None,
        stationen: list[str] | None = None,
    ) -> list[Ergebnis]:
        """Lädt alle (ggf. zeitlich gefilterten) Dateien eines Datensatzes.

        `stationen`: Stations-IDs für Datensätze vom Typ `stationsauswahl`.
        """
        zeitraum = zeitraum or Zeitraum()
        urls = dateien_ermitteln(self.client, datensatz, zeitraum, stationen)
        zielordner = self.rohverzeichnis / datensatz.name
        zielordner.mkdir(parents=True, exist_ok=True)

        try:
            if len(urls) <= 1:
                ergebnisse = [
                    self.lade_datei(url, zielordner / dateiname(url), datensatz, balken=True)
                    for url in urls
                ]
            else:
                ergebnisse = self._lade_parallel(urls, zielordner, datensatz)
            # Nur bei vollständigem Abgleich aufräumen – mit Zeit- oder Stationsfilter liefert
            # die Auswahl bewusst nur einen Teil der Serverdateien
            if datensatz.typ == "verzeichnis" and zeitraum.offen and not stationen:
                ergebnisse += self._entferne_verwaiste(datensatz, set(urls))
        finally:
            self.manifest.speichern()
        return ergebnisse

    def _entferne_verwaiste(self, datensatz: Datensatz, aktuelle_urls: set[str]) -> list[Ergebnis]:
        """Entfernt Dateien, die nicht mehr auf dem Server liegen.

        Beispiel: Der DWD benennt historische Dateien jährlich um, weil das Enddatum im
        Namen steht. Ohne Aufräumen lägen sonst alte und neue Fassung nebeneinander.
        Nur bei ungefiltertem Abgleich, da eine Zeitauswahl nur einen Teil der Liste liefert.
        """
        ergebnisse = []
        for url in self.manifest.urls_fuer(datensatz.name):
            if url in aktuelle_urls:
                continue
            eintrag = self.manifest.entferne(url)
            pfad = self.rohverzeichnis / eintrag["pfad"]
            pfad.unlink(missing_ok=True)
            ergebnisse.append(Ergebnis(url, pfad, "entfernt"))
        return ergebnisse

    def _lade_parallel(
        self, urls: list[str], zielordner: Path, datensatz: Datensatz
    ) -> list[Ergebnis]:
        ergebnisse = []
        with (
            ThreadPoolExecutor(max_workers=self.parallel) as pool,
            tqdm(
                total=len(urls), desc=datensatz.name, unit="Datei", disable=not self.fortschritt
            ) as balken,
        ):
            auftraege = [
                pool.submit(self.lade_datei, url, zielordner / dateiname(url), datensatz, False)
                for url in urls
            ]
            for auftrag in as_completed(auftraege):
                ergebnisse.append(auftrag.result())
                balken.update(1)
        return sorted(ergebnisse, key=lambda e: e.url)

    def lade_datei(
        self, url: str, ziel: Path, datensatz: Datensatz, balken: bool = False
    ) -> Ergebnis:
        """Lädt eine Datei mit Wiederholung; Fehler werden als Ergebnis zurückgegeben."""
        try:
            return _mit_wiederholung(
                lambda: self._lade_datei_einmal(url, ziel, datensatz, balken),
                basis=self.wartezeit_basis,
            )
        except (httpx.HTTPError, VoruebergehenderFehler, OSError) as fehler:
            return Ergebnis(url, ziel, "fehler", str(fehler) or type(fehler).__name__)

    def _lade_datei_einmal(
        self, url: str, ziel: Path, datensatz: Datensatz, balken: bool
    ) -> Ergebnis:
        teil = ziel.with_name(ziel.name + TEIL_ENDUNG)
        meta = ziel.with_name(ziel.name + META_ENDUNG)
        alt = self.manifest.eintrag(url)

        if self.erzwingen:
            teil.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)

        # Komprimierung auf Transportebene abschalten, damit Größen und Range-Angaben stimmen
        kopf = {"Accept-Encoding": "identity"}
        bereits = 0
        if teil.exists() and meta.exists():
            # Abgebrochenen Download fortsetzen – nur, wenn sich die Datei nicht geändert hat
            validator = json.loads(meta.read_text(encoding="utf-8"))
            if pruefwert := validator.get("etag") or validator.get("last_modified"):
                bereits = teil.stat().st_size
                kopf["Range"] = f"bytes={bereits}-"
                kopf["If-Range"] = pruefwert
        elif ziel.exists() and alt and not self.erzwingen:
            if alt.get("etag"):
                kopf["If-None-Match"] = alt["etag"]
            if alt.get("last_modified"):
                kopf["If-Modified-Since"] = alt["last_modified"]

        with self.client.stream("GET", url, headers=kopf) as antwort:
            if antwort.status_code == 304:
                return Ergebnis(url, ziel, "unveraendert")
            if antwort.status_code == 416:
                # Range ungültig (z. B. Teil bereits vollständig) – beim nächsten Versuch neu laden
                teil.unlink(missing_ok=True)
                meta.unlink(missing_ok=True)
                raise VoruebergehenderFehler("HTTP 416, Download wird neu gestartet")
            if antwort.status_code >= 500:
                raise VoruebergehenderFehler(f"HTTP {antwort.status_code}")
            antwort.raise_for_status()

            etag = antwort.headers.get("etag")
            last_modified = antwort.headers.get("last-modified")
            if antwort.status_code == 206:
                modus = "ab"
            else:
                modus, bereits = "wb", 0
                meta.write_text(
                    json.dumps({"etag": etag, "last_modified": last_modified}), encoding="utf-8"
                )
            laenge = antwort.headers.get("content-length")
            erwartet = bereits + int(laenge) if laenge else None

            with (
                teil.open(modus) as datei,
                tqdm(
                    total=erwartet,
                    initial=bereits,
                    desc=ziel.name,
                    unit="B",
                    unit_scale=True,
                    unit_divisor=1024,
                    disable=not (balken and self.fortschritt),
                ) as fortschritt,
            ):
                try:
                    for block in antwort.iter_bytes(BLOCKGROESSE):
                        datei.write(block)
                        fortschritt.update(len(block))
                except httpx.TransportError as fehler:
                    raise VoruebergehenderFehler(f"Verbindung abgebrochen: {fehler}") from fehler

        groesse = teil.stat().st_size
        if erwartet is not None and groesse != erwartet:
            raise VoruebergehenderFehler(f"unvollständig: {groesse} von {erwartet} Bytes")

        status = "aktualisiert" if ziel.exists() else "neu"
        teil.replace(ziel)
        meta.unlink(missing_ok=True)

        eintrag = {
            "datensatz": datensatz.name,
            "pfad": ziel.relative_to(self.rohverzeichnis).as_posix(),
            "groesse": groesse,
            "sha256": _sha256(ziel),
            "etag": etag,
            "last_modified": last_modified,
            "geladen_am": datetime.now(UTC).isoformat(timespec="seconds"),
        }
        self.manifest.setze(url, eintrag)
        return Ergebnis(url, ziel, status)
