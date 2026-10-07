# SPEC: Klimadaten-Auswertung

> Status: **Entwurf v0.3** – wird gemeinsam weiterentwickelt. Getroffene Entscheidungen stehen in
> [Abschnitt 9](#9-entscheidungen), offene Punkte in [Abschnitt 10](#10-offene-fragen).

## 1. Ziel

Wir wollen die Erwärmung der Erde **selbst aus den Rohdaten der Wetterstationen und Meeresmessungen**
nachvollziehen, also mit denselben Daten, die auch NASA, NOAA, das britische Met Office und Berkeley Earth nutzen.
Am Ende sollen eigene globale Temperaturkurven (Land und Land+Ozean) stehen, die wir mit den
offiziellen Reihen vergleichen können. Ergänzend analysieren wir Deutschland im Detail,
werten Tageswerte aus (Hitzetage, Tropennächte, Frosttage) und untersuchen den **Niederschlag**
(Summen, Starkregen, Trockenperioden).

Teilziele:

1. Ein Download-Tool, das die benötigten Rohdaten reproduzierbar herunterlädt und lokal ablegt.
2. Parser, die die Rohformate in saubere `pandas`-/`xarray`-Strukturen überführen.
3. Analysen: Stationsreihen, Anomalien, regionale und globale Mittel, Trends, Extremwert-Indizes
   für Temperatur und Niederschlag.
4. Visualisierungen: statisch und – wo sinnvoll – interaktiv.
5. Nutzung sowohl über eine Kommandozeile (CLI) als auch in Jupyter-Notebooks.

## 2. Hintergrund: Welche Daten nutzen Klimawissenschaftler?

Die großen globalen Temperaturdatensätze setzen sich aus zwei Teilen zusammen:
**Landstationen** (Lufttemperatur in ca. 2 m Höhe) und **Meeresoberflächentemperatur** (SST, von Schiffen und Bojen).
Da ca. 70 % der Erdoberfläche Ozean sind, braucht man für eine echte *globale* Kurve beides.

| Datensatz (Betreiber) | Landdaten | Ozeandaten | Referenzperiode |
|---|---|---|---|
| **GISTEMP v4** (NASA GISS) | GHCN-Monthly v4 (+ SCAR-Antarktis) | ERSST v5 | 1951–1980 |
| **NOAAGlobalTemp** (NOAA NCEI) | GHCN-Monthly v4 | ERSST v5 | 1901–2000 / 1991–2020 |
| **HadCRUT5** (Met Office / UEA CRU) | CRUTEM5 | HadSST4 | 1961–1990 |
| **Berkeley Earth** | eigene Zusammenführung (~40.000 Stationen, u. a. GHCN-Daily) | HadSST4 | 1951–1980 |

### 2.1 Landstationen, monatlich: GHCN-Monthly v4 (NOAA NCEI)

- ~27.000 Stationen weltweit, monatliche Mitteltemperatur (`tavg`), teils ab dem 18. Jahrhundert.
- Zwei Varianten, **wir nutzen beide**:
  - **QCU** – *quality controlled, unadjusted*: nur grobe Fehler entfernt, sonst Originalwerte.
  - **QCF** – *quality controlled, adjusted*: zusätzlich homogenisiert (Korrektur von Stationsumzügen,
    Instrumentenwechseln, Beobachtungszeitänderungen per Pairwise Homogenization Algorithm).
- Format: Fixed-Width-Textdateien (`.dat` mit Messwerten, `.inv` mit Stationsmetadaten).
- Download: `https://www.ncei.noaa.gov/pub/data/ghcn/v4/`
  (`ghcnm.tavg.latest.qcu.tar.gz`, `ghcnm.tavg.latest.qcf.tar.gz`)

### 2.2 Ozean: ERSST v5 (NOAA NCEI)

- *Extended Reconstructed Sea Surface Temperature*: monatliche SST auf einem 2°×2°-Gitter ab 1854.
- Basis: ICOADS (Schiffs- und Bojenmessungen), bereits gegittert und bias-korrigiert –
  Roh-Einzelmessungen auf See sind deutlich aufwendiger und nicht Teil des Projekts.
- Format: NetCDF, eine Datei pro Monat.
- Download: `https://www.ncei.noaa.gov/pub/data/cmb/ersst/v5/netcdf/`
- Alternative/Vergleich (optional): HadSST4 (Met Office).

### 2.3 Tageswerte

| Quelle | Inhalt | URL |
|---|---|---|
| **GHCN-Daily** (NOAA) | >100.000 Stationen, u. a. `TMAX`, `TMIN`, `TAVG`, `PRCP`; Format `.dly` (Fixed-Width) bzw. CSV pro Station | `https://www.ncei.noaa.gov/pub/data/ghcn/daily/` |
| **DWD CDC, täglich** | Deutsche Stationen, Tagesmittel/-max/-min, Niederschlag u. v. m., ZIP mit CSV pro Station | `https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/` |

Hinweis: Der Gesamtbestand von GHCN-Daily ist sehr groß (mehrere GB komprimiert).
Wir laden daher gezielt einzelne Stationen bzw. gefilterte Auswahlen.

**Niederschlag** ist in beiden Quellen enthalten (`PRCP` bzw. DWD `RSK`). Monatssummen bilden wir
aus den Tageswerten; zusätzlich liefert der DWD fertige Monatswerte und Gebietsmittel für Niederschlag.
Ob NOAA eine monatliche Niederschlagsvariante von GHCNm v4 bereitstellt, prüfen wir bei der Implementierung.

### 2.4 Höhere Auflösungen (stündlich und feiner)

| Quelle | Auflösung | Abdeckung | URL |
|---|---|---|---|
| **DWD CDC** | stündlich, 10-minütig (Niederschlag auch 1-minütig) | Deutschland | `https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/hourly/` bzw. `.../10_minutes/` |
| **GHCNh** (NOAA, Nachfolger der *Integrated Surface Database* ISD) | stündlich / synoptisch | weltweit, ~20.000 Stationen | über NCEI, URL wird bei Implementierung geprüft |

Einordnung: Für Klimatrends über Jahrzehnte bringen Stundenwerte kaum Mehrwert gegenüber
Tageswerten. Spannend sind sie für Tagesgang-Analysen (z. B. erwärmen sich Nächte schneller als Tage?),
Hitzewellen-Dynamik und Starkregen. Die Reihen sind zudem meist erst ab ca. 1950–1990 dicht.
→ Geplant als **optionaler späterer Meilenstein**, zunächst nur für DWD-Daten.

Nicht-Stationsdaten wie die Reanalyse **ERA5** (ECMWF, stündlich, global gegittert) sind Modell-Daten
mit Messdaten-Assimilation – bewusst *nicht* Teil der Rohdatenauswertung, höchstens als späterer Vergleich.

### 2.5 Deutschland: DWD Climate Data Center

- Sehr dichtes Stationsnetz, lange Reihen (einige seit dem 19. Jahrhundert), frei unter `opendata.dwd.de`.
- Monats-, Tages-, Stunden- und 10-Minuten-Werte, jeweils als `historical` (geprüft) und `recent` (aktuell, vorläufig).
- Stationslisten als Textdatei pro Produkt; Metadaten (Stationsumzüge, Gerätewechsel) separat verfügbar.
- Zusätzlich offizielle Gebietsmittel für Deutschland und die Bundesländer (`regional_averages_DE`) – ideal als Vergleichsreihe.
  Neben Temperatur und Niederschlag (monatlich, saisonal, jährlich) gibt es jährliche Gebietsmittel für
  Kenntage: Sommertage, heiße Tage, Tropennächte, Frost- und Eistage sowie Tage mit ≥ 10 mm bzw. ≥ 20 mm
  Niederschlag – ideal zur Prüfung unserer eigenen Kenntage-Auswertung (M6).

### 2.6 Vergleichsreihen (fertige Ergebnisse der Wissenschaft)

| Reihe | URL |
|---|---|
| GISTEMP global (Land+Ozean) | `https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv` |
| GISTEMP nur Land | `https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts.csv` |
| HadCRUT5 | `https://www.metoffice.gov.uk/hadobs/hadcrut5/` |
| Berkeley Earth | `https://berkeleyearth.org/data/` |
| DWD Gebietsmittel Deutschland | `https://opendata.dwd.de/climate_environment/CDC/regional_averages_DE/` |

> Alle URLs werden bei der Implementierung nochmals geprüft und zentral in `konfiguration/quellen.toml` gepflegt.

### 2.7 Zugriffswege und zeitliche Einschränkung (geprüft am 2026-10-07)

| Quelle | Ablage auf dem Server | Zeitliche Einschränkung beim Download | Umfang |
|---|---|---|---|
| **GHCNm v4** | ein Archiv je Variante (`qcu`, `qcf`, zusätzlich `qfe`*) | **keine** – immer Gesamtbestand, Filterung erst beim Aufbereiten | je ~45 MB |
| **ERSST v5** (NCEI) | eine NetCDF-Datei **pro Monat** (`ersst.v5.JJJJMM.nc`, 1854-01 bis aktuell) | **monatsgenau** über Dateiauswahl | ~0,2 MB/Monat, gesamt ~2.070 Dateien |
| ERSST v5 (NOAA PSL) | eine Gesamtdatei `sst.mnmean.nc`, zusätzlich per **OPeNDAP** | OPeNDAP: Ausschnitt nach Zeit, Breite, Länge ohne Gesamtdownload | ~153 MB gesamt |
| **GHCN-Daily** `by_station/` | eine CSV pro Station, komplette Historie | keine – aber pro Station klein | ~0,1–2 MB/Station |
| **GHCN-Daily** `by_year/` | eine CSV pro **Jahr**, alle Stationen | **jahresgenau** über Dateiauswahl | 20 MB (1900) bis 170 MB (2024) pro Jahr |
| GHCN-Daily `ghcnd_all.tar.gz` | Gesamtarchiv | keine | ~3,6 GB |
| **NCEI Access Data Service** (`/access/services/data/v1`) | REST-Schnittstelle, u. a. `daily-summaries`, `global-summary-of-the-month` | **tagesgenau** (`startDate`, `endDate`), zusätzlich nach Stationen und Elementen (`TMAX,TMIN,PRCP`) | nur die angefragten Werte; Stations-IDs sind Pflicht |
| **DWD CDC** täglich/monatlich | ZIP pro Station, getrennt in `historical` (geprüft, bis Ende Vorjahr) und `recent` (ca. letzte 500 Tage) | keine Abfrage – aber der **Zeitraum steht im Dateinamen** (`tageswerte_KL_00011_19800901_20251231_hist.zip`), so dass nur Stationen mit passendem Zeitraum geladen werden; `historical`/`recent` je nach Zeitraum | klein pro Station, ~1.280 Stationen täglich |
| DWD Gebietsmittel | eine Textdatei pro Monat bzw. Saison/Jahr und Größe | keine (klein) | wenige KB |
| GISTEMP | eine CSV pro Reihe | keine (klein) | ~13 KB |
| GHCNh (stündlich) | Ablageort noch zu klären (alte Pfade liefern 404) | – | erst für M7 relevant |

\* `qfe`: homogenisiert **und** Lücken aus Nachbarstationen geschätzt, nur 1961–2010 – gedacht für die Berechnung von Klimanormalwerten.
Für uns nicht im Standardumfang, aber als optionaler Datensatz konfigurierbar.

Weitere Befunde:
- Alle geprüften Server liefern `ETag` und `Last-Modified` → **bedingte Downloads** (`If-None-Match` / `If-Modified-Since`),
  d. h. unveränderte Dateien werden nicht erneut übertragen.
- Alle unterstützen `Accept-Ranges: bytes` → abgebrochene große Downloads können **fortgesetzt** werden.
- Die NCEI-Schnittstelle `global-summary-of-the-month` ist aus GHCN-Daily abgeleitet und **nicht identisch mit GHCNm v4**
  (keine Homogenisierung) – für die globale Kurve nutzen wir daher die GHCNm-Archive.

Daraus folgende Strategie für Tageswerte:
- **Ausgewählte Stationen** (Normalfall, z. B. Deutschland, Europa): GHCN-Daily `by_station/` bzw. DWD-ZIPs – komplette Historie, Zeitfilter beim Aufbereiten.
- **Kleine, gezielte Abfragen** (wenige Stationen, kurzer Zeitraum): NCEI Access Data Service.
- **Alle Stationen weltweit für wenige Jahre**: GHCN-Daily `by_year/`.

## 3. Methodik

### 3.1 Globale Kurve aus Monatswerten

1. **Qualitätsfilter**: Fehlwerte (`-9999`) und QC-Flags auswerten, Stationen mit zu wenigen Daten verwerfen.
2. **Anomalien statt Absolutwerte**: Pro Station und Kalendermonat den Mittelwert einer Referenzperiode
   abziehen. Dadurch werden Stationen in Bergen und Tälern vergleichbar, und der Jahresgang verschwindet.
   **Standard-Referenzperiode: 1951–1980** (wie GISTEMP), konfigurierbar in `konfiguration/analyse.toml`
   und per Parameter überschreibbar (z. B. 1961–1990, 1991–2020).
3. **Gitterung**: Stationen einem Gitter zuordnen (z. B. 5°×5°), Anomalien pro Zelle mitteln.
   Verhindert, dass dicht besetzte Regionen (USA, Europa) das Ergebnis dominieren.
4. **Ozean**: ERSST-Werte (2°×2°) ebenfalls in Anomalien umrechnen und auf dasselbe Gitter aggregieren.
5. **Land+Ozean kombinieren**: Pro Gitterzelle Land- und Ozeananomalie nach Landanteil der Zelle
   gewichten (Land-See-Maske, z. B. aus Natural Earth oder abgeleitet aus der ERSST-Abdeckung).
   Meereis-Zellen werden wie in den Referenzdatensätzen als fehlend behandelt.
6. **Flächengewichtung**: Zellen mit `cos(Breitengrad)` gewichten, da Gitterzellen zu den Polen hin kleiner werden.
7. **Mittelung**: Gewichtetes Mittel über alle besetzten Zellen → monatliche/jährliche Anomalie
   (global, Nord-/Südhalbkugel, nur Land, nur Ozean, Land+Ozean).
8. **Trend**: Lineare Regression (°C/Dekade) für wählbare Zeiträume, gleitende Mittel.

### 3.2 Tageswerte: Klimakenntage und Extremindizes

Angelehnt an die DWD-Definitionen bzw. die ETCCDI-Indizes:

| Kenngröße | Definition |
|---|---|
| Sommertag | `TMAX ≥ 25 °C` |
| Heißer Tag | `TMAX ≥ 30 °C` |
| Tropennacht | `TMIN ≥ 20 °C` |
| Frosttag | `TMIN < 0 °C` |
| Eistag | `TMAX < 0 °C` |
| Hitzewelle | z. B. ≥ 3 aufeinanderfolgende heiße Tage (Definition konfigurierbar) |
| Tagesspanne (DTR) | `TMAX − TMIN` – zeigt, ob sich Nächte schneller erwärmen als Tage |

Auswertung: jährliche Anzahl pro Station/Region, Trend, Vergleich von Perioden (z. B. 1961–1990 vs. 1991–2020).

### 3.3 Niederschlag

Niederschlag verhält sich statistisch anders als Temperatur und braucht eigene Methoden:

- **Relative Anomalien**: Abweichung in **% des Mittels der Referenzperiode** statt in mm,
  da sich Niederschlagsmengen regional um Größenordnungen unterscheiden.
- **Schwerpunkt regional** (Deutschland, Europa, einzelne Stationen). Ein globales Mittel aus
  Stationsdaten ist wegen fehlender Ozeanabdeckung und hoher räumlicher Variabilität nur
  eingeschränkt aussagekräftig – wenn, dann als Land-Mittel mit deutlichem Hinweis.
- **Indizes** (angelehnt an ETCCDI/DWD):

| Kenngröße | Definition |
|---|---|
| Jahres-/Jahreszeitensumme | Summe `PRCP` pro Jahr bzw. Saison (DJF, MAM, JJA, SON) |
| Niederschlagstage | Tage mit `PRCP ≥ 1 mm` |
| Starkniederschlagstage | Tage mit `PRCP ≥ 10 mm` bzw. `≥ 20 mm` (Schwellen konfigurierbar) |
| Rx1day / Rx5day | höchste 1-Tages- bzw. 5-Tages-Summe im Jahr |
| R95p | Niederschlagsmenge aus sehr nassen Tagen (> 95. Perzentil der Referenzperiode) |
| SDII | mittlere Intensität an Niederschlagstagen (Summe / Anzahl Tage ≥ 1 mm) |
| CDD | längste Trockenperiode (aufeinanderfolgende Tage `< 1 mm`) |
| CWD | längste Nassperiode (aufeinanderfolgende Tage `≥ 1 mm`) |

### 3.4 Bekannte Fallstricke, die wir sichtbar machen wollen

- Sich verändernde Stationsabdeckung über die Zeit (vor 1900 sehr dünn, v. a. Südhalbkugel und Arktis).
- Städtische Wärmeinseln (Urban Heat Island) – Vergleich ländlich vs. städtisch.
- Effekt der Homogenisierung: **QCU vs. QCF** systematisch vergleichen (global, regional, einzelne Stationen).
- Bei Tageswerten: fehlende Tage verfälschen Zählwerte → Mindestvollständigkeit pro Jahr fordern.
- DWD `historical` vs. `recent`: Überlappung sauber zusammenführen.
- Niederschlag: Messverluste durch Wind (v. a. bei Schnee), Gerätewechsel; GHCN-Niederschlag ist
  nicht homogenisiert. Einzelne Extremwerte auf Plausibilität prüfen.

## 4. Funktionale Anforderungen

### 4.1 Download-Tool (`klima laden`)

- F-DL-1: Lädt konfigurierte Datensätze per HTTPS herunter:
  GHCNm v4 (QCU + QCF), ERSST v5, GHCN-Daily (Stationsliste + ausgewählte Stationen),
  DWD (Monats- und Tageswerte, Gebietsmittel für Temperatur und Niederschlag), Vergleichsreihen (GISTEMP, ggf. HadCRUT5, Berkeley Earth).
- F-DL-2: Ablage unter `daten/roh/<datensatz>/`, Archive werden entpackt.
- F-DL-3: Bereits vorhandene, unveränderte Dateien werden nicht erneut übertragen (siehe F-DL-9), `--erzwingen` erzwingt Neuladen.
- F-DL-4: Fortschrittsanzeige, Retry bei Netzwerkfehlern, parallele Downloads für viele kleine Dateien (ERSST, DWD).
- F-DL-5: Ein Manifest (`daten/roh/manifest.json`) protokolliert Quelle, URL, Download-Zeitpunkt, SHA-256 – für Reproduzierbarkeit.
- F-DL-6: Auswahl von Stationen für Tageswerte per Filter (Stations-IDs, Land, Bounding Box, Mindestlänge der Reihe).
- F-DL-7: `klima laden --liste` zeigt verfügbare Datensätze und deren lokalen Status.
- F-DL-8: Zeitliche Einschränkung mit `--von` / `--bis` (Jahr oder Jahr-Monat). Umsetzung je Quelle nach Abschnitt 2.7:
  Dateiauswahl (ERSST, GHCN-Daily `by_year`, DWD), Abfrageparameter (NCEI Access Data Service) oder –
  wo der Server nichts anbietet (GHCNm) – Gesamtdownload mit Hinweis, dass erst beim Aufbereiten gefiltert wird.
- F-DL-9: Bedingte Downloads über `ETag`/`Last-Modified` und Fortsetzen abgebrochener Downloads über HTTP-Range.

### 4.2 Einlesen / Aufbereitung

- F-IO-1: Parser GHCNm `.inv` und `.dat` (QCU und QCF) → Stationen-`DataFrame` und Long-Format `stations_id, jahr, monat, tavg, flags`.
- F-IO-2: Parser ERSST-NetCDF → `xarray.Dataset` (Zeit × Lat × Lon).
- F-IO-3: Parser GHCN-Daily `.dly` → Long-Format `stations_id, datum, element, wert, flags`.
- F-IO-4: Parser DWD (Stationslisten, Monats-/Tageswerte, Gebietsmittel), inkl. Zusammenführung `historical` + `recent`.
- F-IO-5: Parser Vergleichsreihen (GISTEMP-CSV, ggf. HadCRUT5/Berkeley Earth).
- F-IO-6: Zwischenspeicherung als Parquet (tabellarisch) bzw. NetCDF/Zarr (gegittert) unter `daten/aufbereitet/`.
- F-IO-7: Einheitliche Lade-API für Notebooks, z. B. `klima.einlesen.ghcnm(variante="qcf")`.

### 4.3 Analyse

- F-AN-1: Einzelstation: Zeitreihe, Jahresmittel, Anomalie, Trend.
- F-AN-2: Stationen nach Region filtern (Land, Bundesland, Bounding Box, Radius um Koordinate).
- F-AN-3: Globale/hemisphärische Anomalie nach Abschnitt 3.1 – nur Land, nur Ozean, Land+Ozean;
  Gittergröße und Referenzperiode konfigurierbar.
- F-AN-4: Vergleich QCU vs. QCF (Differenzkurven, Verteilung der Trendänderungen pro Station).
- F-AN-5: Vergleich der eigenen Kurven mit GISTEMP/HadCRUT5 (Differenz, Korrelation).
- F-AN-6: Statistik zur Abdeckung (aktive Stationen bzw. besetzte Zellen pro Jahr).
- F-AN-7: Deutschland: Gebietsmittel aus Stationsdaten selbst berechnen und mit DWD-Gebietsmittel vergleichen.
- F-AN-8: Tageswerte: Klimakenntage und Indizes nach Abschnitt 3.2 pro Station/Region und Jahr.
- F-AN-9: Niederschlag: Summen, relative Anomalien und Indizes nach Abschnitt 3.3 pro Station/Region,
  Jahr und Jahreszeit; Vergleich mit DWD-Gebietsmitteln.
- F-AN-10: Zentrale Analyse-Konfiguration (`konfiguration/analyse.toml`) mit Standardwerten
  (Referenzperiode 1951–1980, Gittergröße, Schwellenwerte, Mindestvollständigkeit); jeder Wert
  ist per CLI-Option bzw. Funktionsparameter überschreibbar.

### 4.4 Visualisierung

Statisch mit `matplotlib`, interaktiv mit `plotly` – interaktiv vor allem dort, wo Zoomen,
Hovern oder Auswählen echten Mehrwert bringt.

| ID | Grafik | statisch | interaktiv |
|---|---|---|---|
| F-VIS-1 | Zeitreihe Anomalie inkl. gleitendem Mittel und Vergleichsreihen | ✓ | ✓ (Zoom, Reihen ein-/ausblenden) |
| F-VIS-2 | Weltkarte der Stationen (Farbe nach Trend/Datenlänge) | ✓ | ✓ (Hover mit Stationsinfo, Klick → Zeitreihe) |
| F-VIS-3 | Gitterkarte der Anomalie für Jahr/Dekade | ✓ | ✓ (Zeitschieberegler) |
| F-VIS-4 | „Warming Stripes“ für Station, Region, global | ✓ | – |
| F-VIS-5 | Stationsabdeckung über die Zeit | ✓ | – |
| F-VIS-6 | QCU vs. QCF Differenzplot | ✓ | ✓ |
| F-VIS-7 | Klimakenntage pro Jahr (Balken + Trend) | ✓ | ✓ |
| F-VIS-8 | Deutschlandkarte mit DWD-Stationen | ✓ | ✓ |
| F-VIS-9 | Niederschlag: Jahres-/Saisonsummen als relative Anomalie, Starkregentage, Trockenperioden | ✓ | ✓ |

- F-VIS-10: Export statisch als PNG/SVG, interaktiv als eigenständige HTML-Datei nach `ausgabe/`.
- F-VIS-11: Alle Beschriftungen (Titel, Achsen, Legenden) auf Deutsch, Zahlen im deutschen Format (Dezimalkomma).

### 4.5 Nutzung: CLI und Notebooks

- F-UI-1: CLI `klima` mit deutschen Unterbefehlen, z. B. `laden`, `aufbereiten`, `analysieren global`,
  `analysieren station`, `grafik …`.
- F-UI-2: Alle CLI-Funktionen sind dünne Hüllen um eine Python-API, die auch in Notebooks genutzt wird.
- F-UI-3: Beispiel-Notebooks in `notebooks/`, je Meilenstein mindestens eines.

## 5. Nicht-funktionale Anforderungen

- NF-1: Reproduzierbar – gleiche Rohdaten + gleiche Konfiguration → gleiches Ergebnis.
- NF-2: Läuft auf einem normalen Laptop; große Datensätze (GHCN-Daily, Stundenwerte) nur gefiltert laden.
- NF-3: Rohdaten werden nie verändert; alle Ableitungen landen in `daten/aufbereitet/`.
- NF-4: Kernfunktionen (Parser, Anomalie, Gitterung, Gewichtung, Kenntage, Niederschlagsindizes) mit `pytest` getestet.
- NF-5: **Durchgängig Deutsch**: Bezeichner (Module, Funktionen, Variablen, Spalten), Kommentare,
  Docstrings, CLI, Fehlermeldungen, Dokumentation, Notebooks und Grafiken.
  - In Bezeichnern und Dateinamen werden Umlaute transkribiert (`ae`, `oe`, `ue`, `ss`),
    z. B. `flaechengewichtung()` – für Kompatibilität mit Werkzeugen und Dateisystemen.
  - In Kommentaren, Docstrings und Texten stehen echte Umlaute.
  - Etablierte Fachkürzel und Namen aus den Datenquellen bleiben im Original (`TMAX`, `PRCP`, `QCU`, `SST`),
    ebenso die APIs externer Bibliotheken.

## 6. Technologie-Stack

| Zweck | Werkzeug |
|---|---|
| Python / Paketverwaltung | Python 3.12, `uv` |
| Daten | `pandas`, `numpy`, `pyarrow` (Parquet), `xarray` + `netCDF4` (ERSST) |
| Download | `httpx`, `tqdm` |
| CLI | `typer` |
| Statistik | `scipy`, `statsmodels` |
| Visualisierung statisch | `matplotlib`, `seaborn`, Karten mit `cartopy` |
| Visualisierung interaktiv | `plotly` (Zeitreihen, Karten); ggf. `folium` für detaillierte Stationskarten |
| Land-See-Maske | `regionmask` oder `geopandas` + Natural Earth |
| Explorative Arbeit | `jupyterlab` |
| Qualität | `pytest`, `ruff` |

## 7. Projektstruktur

```
klimadaten-auswertung/
├── SPEC.md
├── README.md
├── pyproject.toml
├── konfiguration/
│   ├── quellen.toml          # URLs und Datensatz-Definitionen
│   └── analyse.toml          # Standardwerte, z. B. Referenzperiode 1951–1980
├── src/klima/
│   ├── kommandozeile.py      # Einstiegspunkt `klima`
│   ├── herunterladen.py      # Download-Tool
│   ├── einlesen.py           # Lade-API für Notebooks
│   ├── parser/               # ghcnm, ghcnd, ersst, dwd, vergleichsreihen
│   ├── anomalien.py          # Referenzperiode, Anomalien (absolut und relativ)
│   ├── gitter.py             # Gitterung, Land-See-Maske, Flächengewichtung
│   ├── kenntage.py           # Temperatur-Kenntage / Extremindizes
│   ├── niederschlag.py       # Niederschlagsindizes
│   └── grafik/               # statisch.py (matplotlib), interaktiv.py (plotly)
├── notebooks/                # explorative Analysen, je Meilenstein
├── tests/
├── daten/                    # nicht im Git
│   ├── roh/
│   └── aufbereitet/
└── ausgabe/                  # Grafiken, nicht im Git
```

## 8. Meilensteine

| # | Inhalt | Ergebnis |
|---|---|---|
| M1 | Projekt-Setup, Download-Tool: GHCNm v4 (QCU+QCF), ERSST v5, GISTEMP, DWD-Stationslisten | Rohdaten liegen lokal |
| M2 | Parser + Cache für GHCNm, ERSST, Vergleichsreihen | Daten als DataFrame/Dataset |
| M3 | Einzelstation & Deutschland (GHCNm + DWD-Monatswerte, Gebietsmittel für Temperatur und Niederschlag), Warming Stripes | erste Plots |
| M4 | Globale Land-Anomalie, QCU vs. QCF, Vergleich mit GISTEMP Land | eigene Landkurve |
| M5 | ERSST-Integration, Land+Ozean, Vergleich mit GISTEMP/HadCRUT5 | eigene globale Kurve |
| M6 | Tageswerte: GHCN-Daily + DWD täglich, Klimakenntage, Tagesspanne, Niederschlagsindizes | Extremwert-Analysen |
| M7 *(optional)* | Stundenwerte DWD (ggf. GHCNh), Tagesgang; Stadt vs. Land; ggf. kleines Dashboard | vertiefende Analysen |

## 9. Entscheidungen

| # | Frage | Entscheidung |
|---|---|---|
| E-1 | Umfang | Land **und** Ozean (ERSST v5) von Anfang an |
| E-2 | Rohdatenvariante | **QCU und QCF**, systematischer Vergleich |
| E-3 | Deutschland-Fokus | **Ja**, mit DWD-Daten |
| E-4 | Zeitauflösung | Monats- **und Tageswerte**; Stundenwerte optional in M7 |
| E-5 | Arbeitsweise | **CLI und Notebooks** auf gemeinsamer Python-API |
| E-6 | Visualisierung | Statisch + **interaktiv (plotly)**, wo sinnvoll |
| E-7 | Sprache | **Durchgängig Deutsch**, auch Code und Kommentare (Details: NF-5) |
| E-8 | Niederschlag | **Wird mit ausgewertet** (Abschnitt 3.3) |
| E-9 | Referenzperiode | Standard **1951–1980**, konfigurierbar |
| E-10 | Versionsverwaltung | Git, GitHub-Repository `steffenb-dev/klimadaten-auswertung` |

## 10. Offene Fragen

Derzeit keine. Neue Fragen, die während der Umsetzung entstehen, werden hier gesammelt.
