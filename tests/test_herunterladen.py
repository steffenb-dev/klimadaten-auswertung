"""Tests für das Download-Tool – mit simuliertem Server, ohne echte Netzwerkzugriffe."""

from __future__ import annotations

import hashlib
import json

import httpx
import pytest

from klima.herunterladen import (
    MANIFEST_NAME,
    META_ENDUNG,
    TEIL_ENDUNG,
    Lader,
    Zeitraum,
    dateien_ermitteln,
)
from klima.konfiguration import _datensatz_aus_eintrag, lade_quellen

BASIS = "https://beispiel.test/daten/"


def datensatz(**eintrag):
    return _datensatz_aus_eintrag(eintrag.pop("name", "test"), {"beschreibung": "Test", **eintrag})


def lader_mit(tmp_path, behandler, **optionen):
    client = httpx.Client(transport=httpx.MockTransport(behandler))
    return Lader(tmp_path, client=client, fortschritt=False, wartezeit_basis=0, **optionen)


# --- Zeitraum ------------------------------------------------------------------


def test_zeitraum_jahr_und_monat():
    zeitraum = Zeitraum.aus_text("1950", "2000-06")
    assert zeitraum.von == (1950, 1)
    assert zeitraum.bis == (2000, 6)


def test_zeitraum_bis_jahr_meint_dezember():
    assert Zeitraum.aus_text(bis="1980").bis == (1980, 12)


@pytest.mark.parametrize("von, bis", [("19x0", None), ("2000-13", None), ("2001", "2000")])
def test_zeitraum_ungueltig(von, bis):
    with pytest.raises(ValueError):
        Zeitraum.aus_text(von, bis)


def test_zeitraum_ueberschneidung():
    zeitraum = Zeitraum.aus_text("1951", "1980")
    assert zeitraum.ueberschneidet((1900, 1), (1951, 1))
    assert zeitraum.ueberschneidet((1980, 12), (2020, 1))
    assert not zeitraum.ueberschneidet((1981, 1), (2020, 1))
    assert Zeitraum().ueberschneidet((1700, 1), (1700, 1))


# --- Dateiauswahl --------------------------------------------------------------

VERZEICHNIS_HTML = """
<a href="../">Parent</a>
<a href="unter/">unter/</a>
<a href="ersst.v5.195012.nc">x</a>
<a href="ersst.v5.195101.nc">x</a>
<a href="ersst.v5.198012.nc">x</a>
<a href="ersst.v5.198101.nc">x</a>
<a href="liesmich.txt">x</a>
<a href="tageswerte_KL_00001_19370101_19500630_hist.zip">x</a>
<a href="tageswerte_KL_00003_18910101_20110331_hist.zip">x</a>
<a href="tageswerte_KL_00011_19810101_20251231_hist.zip">x</a>
<a href="?C=M;O=A">sortieren</a>
"""


def verzeichnis_server(request: httpx.Request) -> httpx.Response:
    return httpx.Response(200, text=VERZEICHNIS_HTML)


def test_auswahl_nach_jahr_und_monat():
    ersst = datensatz(
        typ="verzeichnis", url=BASIS, muster=r"ersst\.v5\.(?P<jahr>\d{4})(?P<monat>\d{2})\.nc"
    )
    client = httpx.Client(transport=httpx.MockTransport(verzeichnis_server))
    urls = dateien_ermitteln(client, ersst, Zeitraum.aus_text("1951", "1980"))
    assert urls == [BASIS + "ersst.v5.195101.nc", BASIS + "ersst.v5.198012.nc"]
    assert len(dateien_ermitteln(client, ersst, Zeitraum())) == 4


def test_auswahl_nach_beginn_und_ende():
    dwd = datensatz(
        typ="verzeichnis",
        url=BASIS,
        muster=r"tageswerte_KL_\d{5}_(?P<beginn>\d{8})_(?P<ende>\d{8})_hist\.zip",
    )
    client = httpx.Client(transport=httpx.MockTransport(verzeichnis_server))
    urls = dateien_ermitteln(client, dwd, Zeitraum.aus_text("1951", "1980"))
    assert [u.split("_")[2] for u in urls] == ["00003"]


def test_muster_ohne_zeitgruppen_ignoriert_zeitraum():
    alle_txt = datensatz(typ="verzeichnis", url=BASIS, muster=r".*\.txt")
    assert not alle_txt.zeitfilter_moeglich
    client = httpx.Client(transport=httpx.MockTransport(verzeichnis_server))
    assert dateien_ermitteln(client, alle_txt, Zeitraum.aus_text("1951")) == [
        BASIS + "liesmich.txt"
    ]


# --- Download ------------------------------------------------------------------

INHALT = b"0123456789" * 1000
ETAG = '"v1"'


def test_neuer_download_und_manifest(tmp_path):
    def server(request):
        assert request.headers["accept-encoding"] == "identity"
        return httpx.Response(200, content=INHALT, headers={"ETag": ETAG})

    quelle = datensatz(name="gistemp", typ="datei", urls=[BASIS + "GLB.csv"])
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(quelle)

    assert [e.status for e in ergebnisse] == ["neu"]
    assert (tmp_path / "gistemp" / "GLB.csv").read_bytes() == INHALT
    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text())
    eintrag = manifest[BASIS + "GLB.csv"]
    assert eintrag["pfad"] == "gistemp/GLB.csv"
    assert eintrag["sha256"] == hashlib.sha256(INHALT).hexdigest()
    assert eintrag["etag"] == ETAG


def test_unveraenderte_datei_wird_nicht_erneut_uebertragen(tmp_path):
    def server(request):
        if request.headers.get("if-none-match") == ETAG:
            return httpx.Response(304)
        return httpx.Response(200, content=INHALT, headers={"ETag": ETAG})

    quelle = datensatz(name="gistemp", typ="datei", urls=[BASIS + "GLB.csv"])
    lader_mit(tmp_path, server).lade_datensatz(quelle)
    zweiter_lauf = lader_mit(tmp_path, server).lade_datensatz(quelle)
    assert [e.status for e in zweiter_lauf] == ["unveraendert"]

    erzwungen = lader_mit(tmp_path, server, erzwingen=True).lade_datensatz(quelle)
    assert [e.status for e in erzwungen] == ["aktualisiert"]


def test_abgebrochener_download_wird_fortgesetzt(tmp_path):
    ziel = tmp_path / "test" / "gross.bin"
    ziel.parent.mkdir()
    ziel.with_name(ziel.name + TEIL_ENDUNG).write_bytes(INHALT[:4000])
    ziel.with_name(ziel.name + META_ENDUNG).write_text(json.dumps({"etag": ETAG}))

    def server(request):
        assert request.headers["range"] == "bytes=4000-"
        assert request.headers["if-range"] == ETAG
        return httpx.Response(206, content=INHALT[4000:], headers={"ETag": ETAG})

    quelle = datensatz(typ="datei", urls=[BASIS + "gross.bin"])
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(quelle)

    assert [e.status for e in ergebnisse] == ["neu"]
    assert ziel.read_bytes() == INHALT
    assert not ziel.with_name(ziel.name + TEIL_ENDUNG).exists()
    assert not ziel.with_name(ziel.name + META_ENDUNG).exists()


def test_wiederholung_bei_serverfehler(tmp_path):
    aufrufe = []

    def server(request):
        aufrufe.append(request)
        if len(aufrufe) < 3:
            return httpx.Response(503)
        return httpx.Response(200, content=INHALT)

    quelle = datensatz(typ="datei", urls=[BASIS + "a.csv"])
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(quelle)
    assert [e.status for e in ergebnisse] == ["neu"]
    assert len(aufrufe) == 3


def test_nicht_gefunden_ist_fehler_ohne_wiederholung(tmp_path):
    aufrufe = []

    def server(request):
        aufrufe.append(request)
        return httpx.Response(404)

    quelle = datensatz(typ="datei", urls=[BASIS + "fehlt.csv"])
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(quelle)
    assert [e.status for e in ergebnisse] == ["fehler"]
    assert len(aufrufe) == 1


def test_unvollstaendige_uebertragung_wird_erkannt(tmp_path):
    def server(request):
        return httpx.Response(
            200, content=INHALT[:10], headers={"Content-Length": str(len(INHALT))}
        )

    quelle = datensatz(typ="datei", urls=[BASIS + "a.csv"])
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(quelle)
    assert [e.status for e in ergebnisse] == ["fehler"]
    assert not (tmp_path / "test" / "a.csv").exists()


def test_paralleler_download_mehrerer_dateien(tmp_path):
    def server(request):
        if request.url.path.endswith("/"):
            return httpx.Response(200, text=VERZEICHNIS_HTML)
        return httpx.Response(200, content=request.url.path.encode())

    ersst = datensatz(
        name="ersst",
        typ="verzeichnis",
        url=BASIS,
        muster=r"ersst\.v5\.(?P<jahr>\d{4})(?P<monat>\d{2})\.nc",
    )
    ergebnisse = lader_mit(tmp_path, server, parallel=4).lade_datensatz(ersst)
    assert [e.status for e in ergebnisse] == ["neu"] * 4
    assert (tmp_path / "ersst" / "ersst.v5.198101.nc").read_bytes() == b"/daten/ersst.v5.198101.nc"


# --- Konfiguration -------------------------------------------------------------


def test_projektkonfiguration_ist_gueltig():
    quellen = lade_quellen()
    assert {"ghcnm_qcu", "ghcnm_qcf", "ersst_v5", "gistemp"} <= set(quellen)
    assert quellen["ersst_v5"].zeitfilter_moeglich
    assert not quellen["ghcnm_qcu"].zeitfilter_moeglich


def test_ungueltige_konfiguration():
    with pytest.raises(ValueError, match="unbekannter Typ"):
        datensatz(typ="ftp")
    with pytest.raises(ValueError, match="benötigt 'urls'"):
        datensatz(typ="datei")
    with pytest.raises(ValueError, match="auf '/' enden"):
        datensatz(typ="verzeichnis", url="https://x.test/a", muster=".*")


def test_nicht_mehr_angebotene_dateien_werden_entfernt(tmp_path):
    listen = iter(
        [
            '<a href="tageswerte_KL_00001_19370101_20241231_hist.zip">x</a>',
            '<a href="tageswerte_KL_00001_19370101_20251231_hist.zip">x</a>',
        ]
    )

    def server(request):
        if request.url.path.endswith("/"):
            return httpx.Response(200, text=next(listen))
        return httpx.Response(200, content=b"zip")

    dwd = datensatz(
        name="dwd",
        typ="verzeichnis",
        url=BASIS,
        muster=r"tageswerte_KL_\d{5}_(?P<beginn>\d{8})_(?P<ende>\d{8})_hist\.zip",
    )
    lader_mit(tmp_path, server).lade_datensatz(dwd)
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(dwd)

    assert sorted(e.status for e in ergebnisse) == ["entfernt", "neu"]
    assert [p.name for p in (tmp_path / "dwd").iterdir()] == [
        "tageswerte_KL_00001_19370101_20251231_hist.zip"
    ]
    manifest = json.loads((tmp_path / MANIFEST_NAME).read_text())
    assert list(manifest) == [BASIS + "tageswerte_KL_00001_19370101_20251231_hist.zip"]


def test_zeitfilter_entfernt_keine_dateien(tmp_path):
    def server(request):
        if request.url.path.endswith("/"):
            return httpx.Response(200, text=VERZEICHNIS_HTML)
        return httpx.Response(200, content=b"nc")

    ersst = datensatz(
        name="ersst",
        typ="verzeichnis",
        url=BASIS,
        muster=r"ersst\.v5\.(?P<jahr>\d{4})(?P<monat>\d{2})\.nc",
    )
    lader_mit(tmp_path, server).lade_datensatz(ersst)
    ergebnisse = lader_mit(tmp_path, server).lade_datensatz(ersst, Zeitraum.aus_text("1951"))
    assert "entfernt" not in {e.status for e in ergebnisse}
    assert len(list((tmp_path / "ersst").iterdir())) == 4


def test_stationsfilter_im_verzeichnis(tmp_path):
    liste = (
        '<a href="stundenwerte_TU_03987_18930101_20251231_hist.zip">x</a>'
        '<a href="stundenwerte_TU_00399_19691201_20110801_hist.zip">x</a>'
        '<a href="stundenwerte_TU_05792_19500101_20251231_hist.zip">x</a>'
    )

    def server(request):
        if request.url.path.endswith("/"):
            return httpx.Response(200, text=liste)
        return httpx.Response(200, content=b"zip")

    stunde = datensatz(
        name="stunde",
        typ="verzeichnis",
        url=BASIS,
        muster=r"stundenwerte_TU_(?P<station>\d{5})_(?P<beginn>\d{8})_(?P<ende>\d{8})_hist\.zip",
    )
    assert stunde.stationsfilter_moeglich
    lader = lader_mit(tmp_path, server)
    ergebnisse = lader.lade_datensatz(stunde, stationen=["3987", "399"])
    assert sorted(e.pfad.name[16:21] for e in ergebnisse) == ["00399", "03987"]
    # Ein weiterer gefilterter Lauf entfernt die zuvor geladenen Stationen nicht
    weitere = lader_mit(tmp_path, server).lade_datensatz(stunde, stationen=["5792"])
    assert "entfernt" not in {e.status for e in weitere}
    assert len(list((tmp_path / "stunde").iterdir())) == 3
