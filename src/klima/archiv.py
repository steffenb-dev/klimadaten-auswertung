"""Lesen von Rohdaten direkt aus Archiven – ohne Entpacken auf die Festplatte.

Die Rohdaten bleiben so, wie sie heruntergeladen wurden (`.tar.gz`, `.zip`, `.gz` oder
unkomprimiert). Für Auswertungen werden einzelne Dateien im Arbeitsspeicher geöffnet –
als Datenstrom, damit auch große Dateien zeilenweise gelesen und dabei nach Zeitraum
und Stationen gefiltert werden können, ohne sie vollständig in den RAM zu laden.

Beispiel:

    with oeffne_text(pfad, "*.qcu.dat") as datei:
        for zeile in datei:
            ...
"""

from __future__ import annotations

import gzip
import io
import tarfile
import zipfile
from collections.abc import Iterator
from contextlib import contextmanager
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath
from typing import BinaryIO, TextIO


def _art(pfad: Path) -> str:
    name = pfad.name.lower()
    if name.endswith((".tar.gz", ".tgz", ".tar.bz2", ".tar.xz", ".tar")):
        return "tar"
    if name.endswith(".zip"):
        return "zip"
    if name.endswith(".gz"):
        return "gz"
    return "datei"


def ist_archiv(pfad: Path) -> bool:
    return _art(pfad) != "datei"


def inhalt(pfad: Path) -> list[str]:
    """Namen aller Dateien im Archiv (bei `.gz` bzw. unkomprimiert: die Datei selbst)."""
    art = _art(pfad)
    if art == "tar":
        with tarfile.open(pfad, "r:*") as archiv:
            return [m.name for m in archiv.getmembers() if m.isfile()]
    if art == "zip":
        with zipfile.ZipFile(pfad) as archiv:
            return [n for n in archiv.namelist() if not n.endswith("/")]
    if art == "gz":
        return [pfad.name[: -len(".gz")]]
    return [pfad.name]


def _passt(name: str, muster: str) -> bool:
    """Vergleicht mit dem vollständigen Pfad im Archiv und mit dem reinen Dateinamen."""
    return fnmatch(name, muster) or fnmatch(PurePosixPath(name).name, muster)


def finde(pfad: Path, muster: str = "*") -> list[str]:
    """Dateien im Archiv, deren Name auf das Muster passt (z. B. `*.qcu.dat`)."""
    return [n for n in inhalt(pfad) if _passt(n, muster)]


def _genau_ein_treffer(pfad: Path, namen: list[str], muster: str | None) -> str:
    treffer = namen if muster is None else [n for n in namen if _passt(n, muster)]
    if len(treffer) != 1:
        beschreibung = "Dateien" if muster is None else f"Treffer für {muster!r}"
        raise FileNotFoundError(
            f"{pfad.name}: {len(treffer)} {beschreibung}, erwartet genau einen "
            f"(vorhanden: {', '.join(namen[:10])}{' …' if len(namen) > 10 else ''})"
        )
    return treffer[0]


@contextmanager
def oeffne(pfad: Path, muster: str | None = None) -> Iterator[BinaryIO]:
    """Öffnet eine Datei aus einem Archiv als Binärstrom im Arbeitsspeicher.

    `muster` wählt die Datei im Archiv aus (Name oder Platzhalter wie `*.inv`); ohne Muster
    muss das Archiv genau eine Datei enthalten. Bei `.gz` und unkomprimierten Dateien wird
    das Muster ignoriert.
    """
    art = _art(pfad)
    if art == "tar":
        with tarfile.open(pfad, "r:*") as archiv:
            mitglieder = {m.name: m for m in archiv.getmembers() if m.isfile()}
            name = _genau_ein_treffer(pfad, list(mitglieder), muster)
            datei = archiv.extractfile(mitglieder[name])
            assert datei is not None
            with datei:
                yield datei
    elif art == "zip":
        with zipfile.ZipFile(pfad) as archiv:
            namen = [n for n in archiv.namelist() if not n.endswith("/")]
            name = _genau_ein_treffer(pfad, namen, muster)
            with archiv.open(name) as datei:
                yield datei
    elif art == "gz":
        with gzip.open(pfad, "rb") as datei:
            yield datei
    else:
        with pfad.open("rb") as datei:
            yield datei


@contextmanager
def oeffne_text(
    pfad: Path, muster: str | None = None, encoding: str = "utf-8", errors: str = "strict"
) -> Iterator[TextIO]:
    """Wie `oeffne`, aber als Textstrom (zeilenweise lesbar)."""
    with oeffne(pfad, muster) as binaer:
        text = io.TextIOWrapper(binaer, encoding=encoding, errors=errors, newline="")
        try:
            yield text
        finally:
            text.detach()


def lies(pfad: Path, muster: str | None = None) -> bytes:
    """Liest eine Datei aus einem Archiv vollständig in den Arbeitsspeicher."""
    with oeffne(pfad, muster) as datei:
        return datei.read()
