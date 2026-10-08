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


QUELLE_GHCNM = "Daten: NOAA NCEI GHCN-Monthly v4; Vergleich: NASA GISTEMP v4"
EIGENE_QCF = "GHCNm homogenisiert (eigene Berechnung)"
EIGENE_QCU = "GHCNm unbereinigt (eigene Berechnung)"
EIGENE_HALBKUGEL = "GHCNm homogenisiert, Halbkugelmittel (eigene Berechnung)"
GISTEMP_LAND = "NASA GISTEMP nur Land"
FARBEN_GLOBAL = {
    GISTEMP_LAND: "#2a78d6",
    EIGENE_QCF: "#1baf7a",
    EIGENE_QCU: "#eda100",
    EIGENE_HALBKUGEL: "#e87ba4",
}


def _gistemp_jahre(gebiet: str, art: str) -> pd.Series:
    monate = de.einlesen.gistemp(gebiet=gebiet, art=art)
    vollstaendig = monate.groupby("jahr").filter(lambda g: len(g) == 12)
    return vollstaendig.groupby("jahr")["anomalie"].mean().astype("float64")


def weltweit_land(
    trend_von: int = 1951,
    referenz: tuple[int, int] | None = None,
    ab_jahr: int = 1880,
    unterordner: str = "global",
) -> Ergebnis:
    """Globale Landtemperatur aus GHCNm: QCU vs. QCF, Vergleich mit GISTEMP, Abdeckung, Karten."""
    from klima import weltweit as ww

    referenz = referenz or standard_referenzperiode()
    ref_text = f"{referenz[0]}–{referenz[1]}"
    groesse = ww.standard_zellgroesse()
    ergebnis = Ergebnis()

    gitter: dict[str, pd.DataFrame] = {}
    jahre: dict[str, pd.DataFrame] = {}
    for variante in ("qcf", "qcu"):
        anomalien_ = ww.stationsanomalien(variante, referenz)
        gitter[variante] = ww.gitter_mittel(anomalien_, groesse=groesse)
        jahre[variante] = ww.jahresanomalien(gitter[variante]).loc[ab_jahr:]
        if variante == "qcf":
            abdeckung = ww.abdeckung(gitter["qcf"], anomalien_, groesse).loc[ab_jahr:]
            ergebnis.tabellen["abdeckung"] = abdeckung
            ergebnis.tabellen["stationen_mit_referenz"] = pd.DataFrame(
                {"anzahl": [anomalien_["stations_id"].nunique()]}
            )
        del anomalien_
    ergebnis.tabellen["jahresanomalien_qcf"] = jahre["qcf"]
    ergebnis.tabellen["jahresanomalien_qcu"] = jahre["qcu"]

    # 1) Globale Landkurve: eigene Berechnung (QCF, QCU) vs. GISTEMP Land
    vergleich = pd.DataFrame(
        {
            GISTEMP_LAND: _gistemp_jahre("global", "land").loc[ab_jahr:],
            EIGENE_QCF: jahre["qcf"]["global"],
            EIGENE_QCU: jahre["qcu"]["global"],
            EIGENE_HALBKUGEL: jahre["qcf"]["halbkugelmittel"],
        }
    )
    ergebnis.tabellen["global_land"] = vergleich
    for name in vergleich.columns:
        ergebnis.trends[f"Global Land: {name}"] = linearer_trend(vergleich[name], von=trend_von)
        ergebnis.trends[f"Global Land seit {ab_jahr}: {name}"] = linearer_trend(vergleich[name])
    trend = ergebnis.trends[f"Global Land: {EIGENE_QCF}"]
    titel = "Globale Landtemperatur – eigene Berechnung aus Stationsdaten"
    untertitel = (
        f"Jahresmittel, Abweichung von {ref_text}; {groesse:g}°-Gitter, flächengewichtet. "
        f"Trend homogenisiert: {trend.text()}"
    )
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(vergleich, titel, untertitel=untertitel, referenz=referenz,
                            farben=FARBEN_GLOBAL, quelle=QUELLE_GHCNM),
        "global_land", unterordner,
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.zeitreihen(vergleich, titel, untertitel=f"Jahresmittel, Abweichung von "
                                  f"{ref_text}", referenz=referenz, farben=FARBEN_GLOBAL),
            "global_land", unterordner,
        )
    )  # fmt: skip

    # 2) Halbkugeln (homogenisiert) vs. GISTEMP-Halbkugeln existieren nur als Land+Ozean,
    #    daher hier ohne Vergleichsreihe
    halbkugeln = jahre["qcf"][["nordhalbkugel", "suedhalbkugel"]].rename(
        columns={"nordhalbkugel": "Nordhalbkugel", "suedhalbkugel": "Südhalbkugel"}
    )
    for name in halbkugeln.columns:
        ergebnis.trends[f"Land {name}"] = linearer_trend(halbkugeln[name], von=trend_von)
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(halbkugeln, "Landtemperatur nach Halbkugel",
                            untertitel=f"GHCNm homogenisiert, Abweichung von {ref_text}",
                            referenz=referenz, quelle=QUELLE_GHCNM),
        "halbkugeln_land", unterordner,
    )  # fmt: skip

    # 3) Effekt der Homogenisierung
    differenz = pd.DataFrame(
        {
            "homogenisiert minus unbereinigt": vergleich[EIGENE_QCF] - vergleich[EIGENE_QCU],
            "GISTEMP minus eigene (global)": vergleich[GISTEMP_LAND] - vergleich[EIGENE_QCF],
            "GISTEMP minus eigene (Halbkugelmittel)": vergleich[GISTEMP_LAND]
            - vergleich[EIGENE_HALBKUGEL],
        }
    )
    ergebnis.tabellen["differenzen"] = differenz
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(differenz, "Differenzen der globalen Landkurven",
                            untertitel="Jahresmittel in °C; 0 = gleiche Anomalie",
                            glaettung=11, quelle=QUELLE_GHCNM),
        "global_land_differenzen", unterordner,
    )  # fmt: skip

    effekt = ww.homogenisierungseffekt(von=trend_von)
    ergebnis.tabellen["homogenisierung_stationen"] = effekt
    untertitel = (
        f"Trend {trend_von}–heute je Station: homogenisiert minus unbereinigt; "
        f"{len(effekt):,} Stationen".replace(",", ".")
    )
    ergebnis.dateien += statisch.speichern(
        statisch.histogramm(effekt["differenz"], "Wie stark verändert die Homogenisierung den "
                            "Trend einzelner Stationen?", "°C/Dekade", untertitel,
                            quelle=QUELLE_GHCNM),
        "homogenisierung_histogramm", unterordner,
    )  # fmt: skip
    ergebnis.dateien += statisch.speichern(
        statisch.stationskarte(effekt, "differenz", "Trendänderung durch Homogenisierung",
                               "°C/Dekade (homogenisiert minus unbereinigt)", untertitel,
                               ausdehnung=None, quelle=QUELLE_GHCNM),
        "homogenisierung_karte", unterordner, formate=("png",),
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.weltkarte_stationen(effekt, "differenz", "Trendänderung durch "
                                           "Homogenisierung", "°C/Dekade", untertitel),
            "homogenisierung_karte", unterordner,
        )
    )  # fmt: skip

    # 4) Stationstrends weltweit (homogenisiert)
    trends_qcf = effekt.rename(columns={"trend_qcf": "trend"})
    ergebnis.dateien += statisch.speichern(
        statisch.stationskarte(trends_qcf, "trend", f"Temperaturtrend je Station seit {trend_von}",
                               "°C/Dekade", f"GHCNm homogenisiert, {len(trends_qcf):,} Stationen "
                               "mit mind. 80 % vollständigen Jahren".replace(",", "."),
                               ausdehnung=None, quelle=QUELLE_GHCNM),
        "stationstrends_karte", unterordner, formate=("png",),
    )  # fmt: skip

    # 5) Abdeckung
    ergebnis.dateien += statisch.speichern(
        statisch.abdeckung(abdeckung, "Wie gut ist die Erde mit Stationen abgedeckt?",
                           f"GHCNm homogenisiert, Stationen mit Referenzwerten {ref_text}; "
                           f"{groesse:g}°-Gitterzellen", quelle=QUELLE_GHCNM),
        "abdeckung", unterordner,
    )  # fmt: skip

    # 6) Gitterkarten: letztes Jahrzehnt statisch, alle Jahrzehnte interaktiv
    jahrzehnte = ww.jahrzehntmittel(gitter["qcf"])
    jahrzehnte = jahrzehnte[jahrzehnte["jahrzehnt"] >= (ab_jahr // 10) * 10]
    ergebnis.tabellen["jahrzehnte"] = jahrzehnte
    letztes = int(jahrzehnte["jahrzehnt"].max())
    letztes_jahr = int(gitter["qcf"]["jahr"].max())
    ergebnis.dateien += statisch.speichern(
        statisch.gitterkarte(jahrzehnte[jahrzehnte["jahrzehnt"] == letztes],
                             f"Temperaturanomalie {letztes}–{letztes_jahr}",
                             untertitel=f"Mittel je {groesse:g}°-Zelle, Abweichung von {ref_text}; "
                             "nur Zellen mit mind. 5 Jahren Daten", zellgroesse=groesse,
                             quelle=QUELLE_GHCNM),
        "gitterkarte_letztes_jahrzehnt", unterordner, formate=("png",),
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.gitterkarte_zeitregler(
                jahrzehnte, "jahrzehnt", "Temperaturanomalie je Jahrzehnt",
                untertitel=f"GHCNm homogenisiert, {groesse:g}°-Zellen, Abweichung von {ref_text}",
                zellgroesse=groesse,
                beschriftung=lambda z: f"{z}–{min(z + 9, letztes_jahr)}",
            ),
            "gitterkarte_jahrzehnte", unterordner,
        )
    )  # fmt: skip
    return ergebnis


QUELLE_LAND_OZEAN = (
    "Daten: NOAA NCEI GHCN-Monthly v4 und ERSST v5; "
    "Vergleich: NASA GISTEMP v4, Met Office HadCRUT 5.2"
)
EIGENE_LO = "Land + Ozean (eigene Berechnung)"
GISTEMP_LO = "NASA GISTEMP"
HADCRUT_NICHT = "HadCRUT5 nicht aufgefüllt"
HADCRUT_AUF = "HadCRUT5 aufgefüllt"
FARBEN_LAND_OZEAN = {
    GISTEMP_LO: "#2a78d6",
    EIGENE_LO: "#1baf7a",
    HADCRUT_NICHT: "#eb6834",
    HADCRUT_AUF: "#eda100",
    "Land": "#eb6834",
    "Ozean": "#2a78d6",
    "Land + Ozean": "#1baf7a",
}


def _hadcrut_jahre(gebiet: str, variante: str, referenz: tuple[int, int]) -> pd.Series:
    """HadCRUT5 auf die eigene Referenzperiode umgerechnet (Original: 1961–1990)."""
    reihe = de.einlesen.hadcrut5(gebiet=gebiet, variante=variante).set_index("jahr")["anomalie"]
    reihe = reihe.astype("float64")
    return reihe - reihe.loc[referenz[0] : referenz[1]].mean()


def land_ozean(
    trend_von: int = 1951,
    referenz: tuple[int, int] | None = None,
    ab_jahr: int = 1880,
    unterordner: str = "global",
) -> Ergebnis:
    """Globale Temperatur aus Land (GHCNm, homogenisiert) und Ozean (ERSST) vs. GISTEMP/HadCRUT5."""
    from klima import land_ozean as lo
    from klima import weltweit as ww

    referenz = referenz or standard_referenzperiode()
    ref_text = f"{referenz[0]}–{referenz[1]}"
    groesse = ww.standard_zellgroesse()
    ergebnis = Ergebnis()

    land = ww.gitter_mittel(ww.stationsanomalien("qcf", referenz), groesse=groesse)
    ozean = lo.ozeananomalien(referenz, groesse)
    kombiniert = lo.kombinieren(land, ozean, lo.landanteil(groesse))
    jahre_land = ww.jahresanomalien(land)
    jahre_ozean = ww.jahresanomalien(ozean)
    jahre = ww.jahresanomalien(kombiniert)
    ergebnis.tabellen["jahresanomalien"] = jahre
    # Nur Jahre, die in der eigenen Reihe vollständig sind (HadCRUT enthält das laufende Jahr)
    letztes = int(jahre.index.max())

    def zuschnitt(reihe: pd.Series) -> pd.Series:
        return reihe.loc[ab_jahr:letztes]

    # 1) Globale Kurve im Vergleich
    vergleich = pd.DataFrame(
        {
            GISTEMP_LO: zuschnitt(_gistemp_jahre("global", "land_ozean")),
            EIGENE_LO: zuschnitt(jahre["global"]),
            HADCRUT_NICHT: zuschnitt(_hadcrut_jahre("global", "nicht_aufgefuellt", referenz)),
            HADCRUT_AUF: zuschnitt(_hadcrut_jahre("global", "aufgefuellt", referenz)),
        }
    )
    ergebnis.tabellen["global_land_ozean"] = vergleich
    for name in vergleich.columns:
        ergebnis.trends[f"Global: {name}"] = linearer_trend(vergleich[name], von=trend_von)
        ergebnis.trends[f"Global seit {ab_jahr}: {name}"] = linearer_trend(vergleich[name])
    trend = ergebnis.trends[f"Global: {EIGENE_LO}"]
    titel = "Globale Temperatur – eigene Berechnung aus Land- und Meeresdaten"
    untertitel = (
        f"Jahresmittel, Abweichung von {ref_text} (HadCRUT umgerechnet). "
        f"Eigener Trend: {trend.text()}"
    )
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(vergleich, titel, untertitel=untertitel, referenz=referenz,
                            farben=FARBEN_LAND_OZEAN, quelle=QUELLE_LAND_OZEAN),
        "global_land_ozean", unterordner,
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.zeitreihen(vergleich, titel, untertitel=f"Jahresmittel, Abweichung von "
                                  f"{ref_text}", referenz=referenz, farben=FARBEN_LAND_OZEAN),
            "global_land_ozean", unterordner,
        )
    )  # fmt: skip

    # 2) Land, Ozean, kombiniert
    anteile = pd.DataFrame(
        {
            "Land": zuschnitt(jahre_land["global"]),
            "Ozean": zuschnitt(jahre_ozean["global"]),
            "Land + Ozean": zuschnitt(jahre["global"]),
        }
    )
    ergebnis.tabellen["land_ozean_anteile"] = anteile
    for name in ("Land", "Ozean"):
        ergebnis.trends[f"Nur {name}"] = linearer_trend(anteile[name], von=trend_von)
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(anteile, "Land erwärmt sich schneller als der Ozean",
                            untertitel="Eigene Berechnung, Jahresmittel, Abweichung von "
                            f"{ref_text}",
                            referenz=referenz, farben=FARBEN_LAND_OZEAN, quelle=QUELLE_LAND_OZEAN),
        "land_ozean_anteile", unterordner,
    )  # fmt: skip

    # 3) Halbkugeln im Vergleich
    for gebiet, name in (("nordhalbkugel", "Nordhalbkugel"), ("suedhalbkugel", "Südhalbkugel")):
        halbkugel = pd.DataFrame(
            {
                GISTEMP_LO: zuschnitt(_gistemp_jahre(gebiet, "land_ozean")),
                EIGENE_LO: zuschnitt(jahre[gebiet]),
                HADCRUT_NICHT: zuschnitt(_hadcrut_jahre(gebiet, "nicht_aufgefuellt", referenz)),
            }
        )
        ergebnis.tabellen[f"{gebiet}_land_ozean"] = halbkugel
        ergebnis.trends[f"{name}: {EIGENE_LO}"] = linearer_trend(halbkugel[EIGENE_LO], trend_von)
        ergebnis.dateien += statisch.speichern(
            statisch.zeitreihen(halbkugel, f"{name}: Land und Ozean",
                                untertitel=f"Jahresmittel, Abweichung von {ref_text}",
                                referenz=referenz, farben=FARBEN_LAND_OZEAN,
                                quelle=QUELLE_LAND_OZEAN),
            f"{gebiet}_land_ozean", unterordner,
        )  # fmt: skip

    # 4) Differenzen zu den Referenzdatensätzen
    differenz = pd.DataFrame(
        {
            "eigene minus GISTEMP": vergleich[EIGENE_LO] - vergleich[GISTEMP_LO],
            "eigene minus HadCRUT5 nicht aufgefüllt": vergleich[EIGENE_LO]
            - vergleich[HADCRUT_NICHT],
        }
    )
    ergebnis.tabellen["differenzen"] = differenz
    ergebnis.dateien += statisch.speichern(
        statisch.zeitreihen(differenz, "Eigene Berechnung minus Referenzdatensätze",
                            untertitel="Jahresmittel Land + Ozean in °C; 0 = gleiche Anomalie",
                            quelle=QUELLE_LAND_OZEAN),
        "global_land_ozean_differenzen", unterordner,
    )  # fmt: skip

    # 5) Karten
    jahrzehnte = ww.jahrzehntmittel(kombiniert)
    jahrzehnte = jahrzehnte[jahrzehnte["jahrzehnt"] >= (ab_jahr // 10) * 10]
    ergebnis.tabellen["jahrzehnte"] = jahrzehnte
    letztes_jahrzehnt = int(jahrzehnte["jahrzehnt"].max())
    letzter_monat = int(kombiniert["jahr"].max())
    ergebnis.dateien += statisch.speichern(
        statisch.gitterkarte(jahrzehnte[jahrzehnte["jahrzehnt"] == letztes_jahrzehnt],
                             f"Temperaturanomalie Land und Ozean {letztes_jahrzehnt}–"
                             f"{letzter_monat}",
                             untertitel=f"Mittel je {groesse:g}°-Zelle, Abweichung von {ref_text}; "
                             "Meereis ohne Wert", zellgroesse=groesse, quelle=QUELLE_LAND_OZEAN),
        "gitterkarte_land_ozean_letztes_jahrzehnt", unterordner, formate=("png",),
    )  # fmt: skip
    ergebnis.dateien.append(
        interaktiv.speichern(
            interaktiv.gitterkarte_zeitregler(
                jahrzehnte, "jahrzehnt", "Temperaturanomalie Land und Ozean je Jahrzehnt",
                untertitel=f"GHCNm homogenisiert + ERSST v5, {groesse:g}°-Zellen, Abweichung "
                f"von {ref_text}", zellgroesse=groesse,
                beschriftung=lambda z: f"{z}–{min(z + 9, letzter_monat)}",
            ),
            "gitterkarte_land_ozean_jahrzehnte", unterordner,
        )
    )  # fmt: skip
    return ergebnis
