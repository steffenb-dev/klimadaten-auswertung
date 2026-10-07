"""Fertige Auswertungen: rechnen, Grafiken erzeugen und speichern.

Werden von der Kommandozeile (`klima analysieren …`) und aus Notebooks aufgerufen.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from klima import deutschland as de
from klima.anomalien import anomalien, standard_referenzperiode
from klima.grafik import interaktiv, statisch
from klima.trend import Trend, linearer_trend

QUELLE_DWD = "Daten: Deutscher Wetterdienst (DWD), Climate Data Center"
QUELLE_DWD_GHCNM = QUELLE_DWD + "; NOAA NCEI GHCN-Monthly v4"

# Feste Farben je Quelle – eine Quelle hat in jeder Grafik dieselbe Farbe
FARBEN_QUELLEN = {
    de.DWD_OFFIZIELL: "#2a78d6",
    de.DWD_STATIONEN: "#eb6834",
    de.GHCNM_QCF: "#1baf7a",
    de.GHCNM_QCU: "#eda100",
}


def dateiname_sicher(text: str) -> str:
    """Kleinbuchstaben, Umlaute transkribiert, alles andere außer a–z/0–9 als `_`."""
    text = text.lower()
    for umlaut, ersatz in (("ä", "ae"), ("ö", "oe"), ("ü", "ue"), ("ß", "ss")):
        text = text.replace(umlaut, ersatz)
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


@dataclass
class Ergebnis:
    """Ergebnis einer Auswertung: Kennzahlen und erzeugte Dateien."""

    trends: dict[str, Trend] = field(default_factory=dict)
    tabellen: dict[str, pd.DataFrame] = field(default_factory=dict)
    dateien: list[Path] = field(default_factory=list)


def deutschland(
    trend_von: int = 1951,
    referenz: tuple[int, int] | None = None,
    ab_jahr: int = 1881,
    unterordner: str = "deutschland",
) -> Ergebnis:
    """Temperatur und Niederschlag in Deutschland: eigene Gebietsmittel vs. DWD.

    `ab_jahr`: Beginn der Darstellung. Die offiziellen DWD-Gebietsmittel beginnen 1881;
    davor gibt es nur wenige Einzelstationen, deren Mittel nicht für Deutschland steht.
    """
    referenz = referenz or standard_referenzperiode()
    ref_text = f"{referenz[0]}–{referenz[1]}"
    ergebnis = Ergebnis()

    # Temperatur
    temperatur = de.temperatur_jahresanomalien(referenz).loc[ab_jahr:]
    ergebnis.tabellen["temperatur"] = temperatur
    for name in temperatur.columns:
        ergebnis.trends[f"Temperatur: {name}"] = linearer_trend(temperatur[name], von=trend_von)

    offiziell = temperatur[de.DWD_OFFIZIELL]
    trend = ergebnis.trends[f"Temperatur: {de.DWD_OFFIZIELL}"]
    untertitel = (
        f"Jahresmittel, Abweichung von {ref_text}; dünn: Einzeljahre, kräftig: 11-jähriges Mittel. "
        f"Trend DWD: {trend.text()}"
    )
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(
            temperatur, "Temperatur in Deutschland – vier Wege zum Gebietsmittel",
            untertitel=untertitel, referenz=referenz, farben=FARBEN_QUELLEN,
            quelle=QUELLE_DWD_GHCNM,
        ),
        "temperatur_quellenvergleich", unterordner,
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.zeitreihen(
                temperatur, "Temperatur in Deutschland – vier Wege zum Gebietsmittel",
                untertitel=f"Jahresmittel, Abweichung von {ref_text}", referenz=referenz,
                farben=FARBEN_QUELLEN,
            ),
            "temperatur_quellenvergleich", unterordner,
        )
    )  # fmt: skip
    ergebnis.dateien += statisch.speichern(
        statisch.warming_stripes(
            offiziell, f"Deutschland {int(offiziell.dropna().index.min())}–"
            f"{int(offiziell.dropna().index.max())}", quelle=QUELLE_DWD,
        ),
        "warming_stripes", unterordner,
    )  # fmt: skip

    # Abweichung der eigenen Berechnungen vom DWD
    abweichung = temperatur.drop(columns=de.DWD_OFFIZIELL).sub(offiziell, axis=0)
    ergebnis.tabellen["abweichung_vom_dwd"] = abweichung
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(
            abweichung, "Eigene Berechnung minus offizielles DWD-Gebietsmittel",
            untertitel="Jahresmittel der Temperatur; 0 = exakte Übereinstimmung",
            glaettung=None, farben=FARBEN_QUELLEN, quelle=QUELLE_DWD_GHCNM,
        ),
        "temperatur_abweichung_vom_dwd", unterordner,
    )  # fmt: skip

    # Niederschlag
    niederschlag = de.niederschlag_jahresanomalien(referenz).loc[ab_jahr:]
    ergebnis.tabellen["niederschlag"] = niederschlag
    for name in niederschlag.columns:
        ergebnis.trends[f"Niederschlag: {name}"] = linearer_trend(niederschlag[name], von=trend_von)
    ergebnis.dateien += statisch.speichern(
        statisch.balken_relativ(
            niederschlag[de.DWD_OFFIZIELL], "Niederschlag in Deutschland",
            untertitel=f"Jahressumme, Abweichung von {ref_text} in Prozent",
            quelle=QUELLE_DWD,
        ),
        "niederschlag", unterordner,
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.zeitreihen(
                niederschlag, "Niederschlag in Deutschland – eigene Berechnung vs. DWD",
                einheit="%", untertitel=f"Jahressumme, Abweichung von {ref_text}",
                referenz=referenz, farben=FARBEN_QUELLEN,
            ),
            "niederschlag_quellenvergleich", unterordner,
        )
    )  # fmt: skip

    # Stationskarten der Trends
    for wert, groesse, titel, einheit in (
        ("tmittel", "temperatur", f"Temperaturtrend je DWD-Station seit {trend_von}", "°C/Dekade"),
        ("niederschlag", "niederschlag", f"Niederschlagstrend je DWD-Station seit {trend_von}",
         "% des Mittels/Dekade"),
    ):  # fmt: skip
        trends = de.stationstrends(von=trend_von, wert=wert)
        ergebnis.tabellen[f"stationstrends_{wert}"] = trends
        untertitel = f"{len(trends)} Stationen mit mind. 80 % vollständigen Jahren"
        ergebnis.dateien += statisch.speichern(
            statisch.stationskarte(
                trends, "trend", titel, einheit, untertitel, quelle=QUELLE_DWD, groesse=groesse
            ),
            # nur PNG: als SVG wären die detaillierten Küstenlinien ~20 MB groß
            f"karte_trend_{wert}", unterordner, formate=("png",),
        )  # fmt: skip
        ergebnis.dateien.append(
            interaktiv.speichern(
                interaktiv.stationskarte(
                    trends, "trend", titel, einheit, untertitel, groesse=groesse
                ),
                f"karte_trend_{wert}", unterordner,
            )
        )  # fmt: skip
    return ergebnis


def station(
    stations_id: str,
    trend_von: int = 1951,
    referenz: tuple[int, int] | None = None,
    unterordner: str = "stationen",
) -> Ergebnis:
    """Temperatur und Niederschlag einer DWD-Station."""
    referenz = referenz or standard_referenzperiode()
    stations_id = str(stations_id).zfill(5)
    treffer = de.einlesen.dwd_stationen("monat").query("stations_id == @stations_id")
    if treffer.empty:
        raise ValueError(f"Unbekannte DWD-Station {stations_id}.")
    name = treffer.iloc[0]["name"]
    ergebnis = Ergebnis()

    temperatur = de.station_jahreswerte(stations_id, "tmittel").rename("tmittel")
    anomalie = anomalien(
        temperatur.reset_index(), "tmittel", gruppe=None, referenz=referenz
    ).set_index("jahr")["anomalie"]
    ergebnis.tabellen["temperatur"] = anomalie.to_frame()
    ergebnis.trends["Temperatur"] = trend = linearer_trend(anomalie, von=trend_von)

    datei = f"{stations_id}_{dateiname_sicher(name)}"
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(
            anomalie.rename(name).to_frame(), f"Temperatur in {name}",
            untertitel=f"DWD-Station {stations_id}; Jahresmittel, Abweichung von "
            f"{referenz[0]}–{referenz[1]}. Trend: {trend.text()}",
            referenz=referenz, quelle=QUELLE_DWD,
        ),
        f"{datei}_temperatur", unterordner,
    )  # fmt: skip
    ergebnis.dateien += statisch.speichern(
        statisch.warming_stripes(
            anomalie, f"{name} {int(anomalie.index.min())}–{int(anomalie.index.max())}",
            quelle=QUELLE_DWD,
        ),
        f"{datei}_warming_stripes", unterordner,
    )  # fmt: skip

    niederschlag = de.station_jahreswerte(stations_id, "niederschlag").rename("niederschlag")
    if len(niederschlag) >= 10:
        relativ = anomalien(
            niederschlag.reset_index(), "niederschlag", gruppe=None, referenz=referenz,
            relativ=True,
        ).set_index("jahr")["anomalie"]  # fmt: skip
        ergebnis.tabellen["niederschlag"] = relativ.to_frame()
        ergebnis.trends["Niederschlag"] = linearer_trend(relativ, von=trend_von)
        ergebnis.dateien += statisch.speichern(
            statisch.balken_relativ(
                relativ, f"Niederschlag in {name}",
                untertitel=f"DWD-Station {stations_id}; Jahressumme, Abweichung von "
                f"{referenz[0]}–{referenz[1]} in Prozent",
                quelle=QUELLE_DWD,
            ),
            f"{datei}_niederschlag", unterordner,
        )  # fmt: skip
    return ergebnis


def jahresverlauf_deutschland(
    hervorheben: int = 5,
    ab_jahr: int = 1881,
    mindestzellen: int = 15,
    referenz: tuple[int, int] | None = None,
    unterordner: str = "deutschland",
) -> Ergebnis:
    """Tagesmitteltemperatur Deutschland: jedes Jahr eine Linie über Tag 1–365.

    Alle Jahre ab `ab_jahr` dünn, die letzten `hervorheben` Jahre farbig. Ein Jahr wird
    gezeigt, wenn an jedem Tag mindestens `mindestzellen` 1°-Gitterzellen besetzt sind;
    das laufende (unvollständige) Jahr wird bis zum letzten Messtag gezeigt.
    """
    from klima import jahresverlauf as jv

    referenz = referenz or standard_referenzperiode()
    ergebnis = Ergebnis()
    tagesmittel = jv.deutschland_tagesmittel(referenz=referenz)
    ergebnis.tabellen["tagesmittel"] = tagesmittel

    letztes_jahr = int(tagesmittel["jahr"].max())
    jahre = [j for j in jv.vollstaendige_jahre(tagesmittel, mindestzellen) if j >= ab_jahr]
    laufend = letztes_jahr not in jahre
    if laufend:
        jahre.append(letztes_jahr)
    matrix = jv.jahresmatrix(tagesmittel).loc[jahre]
    ergebnis.tabellen["jahresmatrix"] = matrix

    markiert = jahre[-hervorheben:]
    letzter_tag = tagesmittel["datum"].max()
    bezeichnungen = {letztes_jahr: f"{letztes_jahr} (bis {letzter_tag:%d.%m.})"} if laufend else {}
    referenzlinie = (
        tagesmittel[tagesmittel["tag"] != jv.SCHALTTAG].groupby("tag")["referenz"].first()
    )
    referenz_name = f"Mittel {referenz[0]}–{referenz[1]}"

    vollstaendig = len(jahre) - int(laufend)
    untertitel = (
        f"DWD-Stationen, eigenes Gebietsmittel; {vollstaendig} vollständige Jahre "
        f"{jahre[0]}–{jahre[-1 - int(laufend)]}"
        + (f" + {letztes_jahr} bis {letzter_tag:%d.%m.}" if laufend else "")
        + "; 365-Tage-Kalender (29. Februar ausgelassen)"
    )
    titel = "Tagesmitteltemperatur in Deutschland – jedes Jahr eine Linie"
    argumente = dict(
        titel=titel, hervorheben=markiert, untertitel=untertitel, referenz=referenzlinie,
        referenz_name=referenz_name, bezeichnungen=bezeichnungen,
    )  # fmt: skip
    ergebnis.dateien += statisch.speichern(
        statisch.jahresverlauf(matrix, quelle=QUELLE_DWD, **argumente),
        "jahresverlauf_temperatur", unterordner,
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.jahresverlauf(matrix, **argumente), "jahresverlauf_temperatur", unterordner
        )
    )
    return ergebnis
