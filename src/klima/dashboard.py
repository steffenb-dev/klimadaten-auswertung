"""Übersichtsseite `ausgabe/index.html` mit allen erzeugten Grafiken (Meilenstein M7).

Die Seite wird aus den vorhandenen Dateien in `ausgabe/` erzeugt: Jede bekannte Grafik
erscheint mit Vorschaubild, Beschreibung und Links (PNG, SVG, interaktiv). Nicht erzeugte
Grafiken werden ausgelassen, unbekannte unter „Weitere Grafiken“ angezeigt. Alle Pfade sind
relativ – die Seite funktioniert ohne Server (Doppelklick genügt).
"""

from __future__ import annotations

import html
from datetime import datetime
from pathlib import Path

from klima.konfiguration import projektwurzel

# Abschnitt -> [(Pfad ohne Endung, Titel, Beschreibung, erzeugender Befehl)]
KATALOG: dict[str, list[tuple[str, str, str]]] = {
    "Deutschland": [
        ("deutschland/temperatur_quellenvergleich", "Temperatur – vier Wege zum Gebietsmittel",
         "Eigene Gebietsmittel aus DWD- und GHCNm-Stationen im Vergleich zum DWD"),
        ("deutschland/warming_stripes", "Warming Stripes Deutschland", "Jahresmittel seit 1881"),
        ("deutschland/temperatur_abweichung_vom_dwd", "Abweichung vom DWD",
         "Eigene Berechnung minus offizielles Gebietsmittel"),
        ("deutschland/niederschlag", "Niederschlag", "Jahressumme, Abweichung in Prozent"),
        ("deutschland/niederschlag_quellenvergleich", "Niederschlag – eigene vs. DWD", ""),
        ("deutschland/jahresverlauf_temperatur", "Jahresverlauf der Tagesmitteltemperatur",
         "Jedes Jahr eine Linie, die letzten Jahre farbig"),
        ("deutschland/kenntage_temperatur", "Temperatur-Kenntage",
         "Sommertage, heiße Tage, Tropennächte, Hitzewellen, Frost- und Eistage"),
        ("deutschland/kenntage_niederschlag", "Niederschlagsextreme",
         "Starkregentage, größte Tagessummen, Trockenperioden"),
        ("deutschland/tag_nacht", "Tage oder Nächte?", "Tmax, Tmin und Tagesspanne"),
        ("deutschland/karte_trend_tmittel", "Temperaturtrend je Station", "seit 1951"),
        ("deutschland/karte_trend_niederschlag", "Niederschlagstrend je Station", "seit 1951"),
        ("deutschland/karte_trend_heisse_tage", "Zunahme der heißen Tage je Station", "seit 1951"),
    ],
    "Global": [
        ("global/global_land_ozean", "Globale Temperatur Land + Ozean",
         "Eigene Berechnung vs. NASA GISTEMP und HadCRUT5"),
        ("global/land_ozean_anteile", "Land vs. Ozean",
         "Land erwärmt sich etwa doppelt so schnell"),
        ("global/nordhalbkugel_land_ozean", "Nordhalbkugel", ""),
        ("global/suedhalbkugel_land_ozean", "Südhalbkugel", ""),
        ("global/global_land_ozean_differenzen", "Differenzen zu den Referenzdatensätzen", ""),
        ("global/gitterkarte_land_ozean_letztes_jahrzehnt", "Anomalie Land + Ozean, 2020er",
         "Interaktiv mit Zeitregler: siehe Link"),
        ("global/gitterkarte_land_ozean_jahrzehnte", "Anomalie je Jahrzehnt (Zeitregler)", ""),
        ("global/global_land", "Globale Landtemperatur", "Unbereinigt, homogenisiert, GISTEMP"),
        ("global/halbkugeln_land", "Landtemperatur nach Halbkugel", ""),
        ("global/global_land_differenzen", "Effekt der Homogenisierung (global)", ""),
        ("global/homogenisierung_histogramm", "Homogenisierung je Station", "Verteilung"),
        ("global/homogenisierung_karte", "Homogenisierung je Station", "Weltkarte"),
        ("global/stationstrends_karte", "Temperaturtrend je Station weltweit", "seit 1951"),
        ("global/abdeckung", "Stationsabdeckung", "Aktive Stationen und abgedeckte Fläche"),
        ("global/gitterkarte_letztes_jahrzehnt", "Landanomalie 2020er", ""),
        ("global/gitterkarte_jahrzehnte", "Landanomalie je Jahrzehnt (Zeitregler)", ""),
    ],
    "Tagesgang und Wärmeinsel": [
        ("tagesgang/trend_je_stunde", "Erwärmung je Uhrzeit", "Trend seit 1951 je Stunde (MEZ)"),
        ("tagesgang/potsdam_jahrzehnt_stunde", "Potsdam: Uhrzeit × Jahrzehnt", ""),
        ("tagesgang/waermeinsel_tagesgang", "Städtische Wärmeinsel im Tagesverlauf",
         "Stadt minus Umland, Sommer und Winter"),
    ],
    "Stadt und Land": [
        ("stadt_land/global_stadt_land", "Global: städtische vs. ländliche Stationen", ""),
        ("stadt_land/global_stadt_minus_land", "Global: Stadt minus Land", ""),
        ("stadt_land/deutschland_stadt_land", "Deutschland: Stadt vs. Land",
         "Tmin, Tmax, Tropennächte"),
    ],
}  # fmt: skip

STIL = """
:root { --flaeche:#fcfcfb; --seite:#f9f9f7; --tinte:#0b0b0b; --tinte2:#52514e;
  --gedaempft:#898781; --linie:rgba(11,11,11,.10); --akzent:#2a78d6; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --flaeche:#1a1a19; --seite:#0d0d0d; --tinte:#fff; --tinte2:#c3c2b7; --gedaempft:#898781;
  --linie:rgba(255,255,255,.10); --akzent:#3987e5; } }
:root[data-theme="dark"] { --flaeche:#1a1a19; --seite:#0d0d0d; --tinte:#fff; --tinte2:#c3c2b7;
  --gedaempft:#898781; --linie:rgba(255,255,255,.10); --akzent:#3987e5; }
* { box-sizing:border-box; }
body { margin:0; background:var(--seite); color:var(--tinte);
  font-family:system-ui,-apple-system,"Segoe UI",sans-serif; line-height:1.45; }
header, main { max-width:1200px; margin:0 auto; padding:0 16px; }
header { padding-top:32px; padding-bottom:8px; }
h1 { font-size:1.6rem; margin:0 0 4px; }
header p { color:var(--tinte2); margin:0; }
nav { margin:16px 0 0; display:flex; flex-wrap:wrap; gap:8px 16px; }
nav a, .links a { color:var(--akzent); text-decoration:none; }
nav a:hover, .links a:hover { text-decoration:underline; }
h2 { font-size:1.2rem; margin:36px 0 12px; }
.raster { display:grid; grid-template-columns:repeat(auto-fill,minmax(320px,1fr)); gap:16px; }
.karte { background:var(--flaeche); border:1px solid var(--linie); border-radius:10px;
  overflow:hidden; display:flex; flex-direction:column; }
.karte img { width:100%; aspect-ratio:16/10; object-fit:contain; background:#fcfcfb;
  border-bottom:1px solid var(--linie); }
.karte .ohne-bild { aspect-ratio:16/10; display:grid; place-items:center; color:var(--gedaempft);
  border-bottom:1px solid var(--linie); }
.inhalt { padding:12px 14px 14px; }
.inhalt h3 { font-size:1rem; margin:0 0 4px; }
.inhalt p { color:var(--tinte2); font-size:.9rem; margin:0 0 8px; }
.links { display:flex; gap:12px; font-size:.9rem; }
footer { max-width:1200px; margin:40px auto 32px; padding:0 16px; color:var(--gedaempft);
  font-size:.85rem; }
"""


def _titel_aus_name(basis: str) -> str:
    """`stationen/03987_potsdam_kenntage` -> `03987 Potsdam – Kenntage`."""
    teile = Path(basis).name.split("_")
    if len(teile) >= 3:
        name = " ".join(teile[1:-1]).title()
        return f"{teile[0].upper()} {name} – {teile[-1].replace('-', ' ').title()}"
    return Path(basis).name.replace("_", " ")


def _karte(ordner: Path, basis: str, titel: str, beschreibung: str) -> str | None:
    vorhanden = {e: (ordner / f"{basis}.{e}").exists() for e in ("png", "svg", "html")}
    if not any(vorhanden.values()):
        return None
    links = [f'<a href="{basis}.{e}">{n}</a>' for e, n in
             (("html", "interaktiv"), ("png", "PNG"), ("svg", "SVG")) if vorhanden[e]]  # fmt: skip
    bild = (
        f'<a href="{basis}.png"><img src="{basis}.png" alt="{html.escape(titel)}" '
        'loading="lazy"></a>'
        if vorhanden["png"]
        else f'<a class="ohne-bild" href="{basis}.html">nur interaktiv – öffnen</a>'
    )
    text = f"<p>{html.escape(beschreibung)}</p>" if beschreibung else ""
    return (
        f'<article class="karte">{bild}<div class="inhalt"><h3>{html.escape(titel)}</h3>'
        f'{text}<div class="links">{" ".join(links)}</div></div></article>'
    )


def erzeugen(ordner: Path | None = None) -> Path:
    """Schreibt `ausgabe/index.html` und gibt den Pfad zurück."""
    ordner = ordner or projektwurzel() / "ausgabe"
    ordner.mkdir(parents=True, exist_ok=True)
    bekannt = {basis for eintraege in KATALOG.values() for basis, *_ in eintraege}

    abschnitte = []
    for abschnitt, eintraege in KATALOG.items():
        karten = [k for b, t, d in eintraege if (k := _karte(ordner, b, t, d))]
        if karten:
            abschnitte.append((abschnitt, karten))

    weitere = sorted(
        {p.relative_to(ordner).with_suffix("").as_posix()
         for p in ordner.rglob("*") if p.suffix in (".png", ".html") and p.name != "index.html"}
        - bekannt
    )  # fmt: skip
    stationen = [b for b in weitere if b.startswith("stationen/")]
    sonstige = [b for b in weitere if b not in stationen]
    for name, basen in (("Einzelstationen", stationen), ("Weitere Grafiken", sonstige)):
        karten = [k for b in basen if (k := _karte(ordner, b, _titel_aus_name(b), ""))]
        if karten:
            abschnitte.append((name, karten))

    def anker(name: str) -> str:
        return name.lower().replace(" ", "-")

    navigation = " ".join(f'<a href="#{anker(a)}">{html.escape(a)}</a>' for a, _ in abschnitte)
    inhalt = "".join(
        f'<section id="{anker(a)}"><h2>{html.escape(a)}</h2><div class="raster">'
        f"{''.join(k)}</div></section>"
        for a, k in abschnitte
    )
    anzahl = sum(len(k) for _, k in abschnitte)
    seite = f"""<!doctype html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Klimadaten-Auswertung</title>
<style>{STIL}</style>
</head>
<body>
<header>
<h1>Klimadaten-Auswertung</h1>
<p>{anzahl} Grafiken aus eigener Auswertung von Stations- und Meeresrohdaten
(DWD, NOAA GHCN, ERSST) im Vergleich mit NASA GISTEMP und HadCRUT5.</p>
<nav>{navigation}</nav>
</header>
<main>{inhalt}</main>
<footer>Erzeugt am {datetime.now():%d.%m.%Y um %H:%M} mit <code>klima dashboard</code>.
Interaktive Grafiken laden plotly aus dem Internet.</footer>
</body>
</html>
"""
    ziel = ordner / "index.html"
    ziel.write_text(seite, encoding="utf-8")
    return ziel
