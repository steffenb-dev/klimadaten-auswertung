# Klimadaten-Auswertung

Eigene Auswertung der globalen Temperaturentwicklung aus den Rohdaten von Wetterstationen
(GHCN, DWD) und Meeresmessungen (ERSST) – mit Python, pandas, xarray, matplotlib und plotly.

Anforderungen und Planung: siehe [SPEC.md](SPEC.md).

## Einrichtung

Voraussetzung: [uv](https://docs.astral.sh/uv/).

```bash
uv sync
```

## Rohdaten herunterladen

```bash
uv run klima laden --liste              # verfügbare Datensätze und lokaler Stand
uv run klima laden                      # Standardumfang (GHCNm, ERSST, GISTEMP, DWD)
uv run klima laden ersst_v5 --von 1951 --bis 1980
uv run klima laden ghcnd_stationen      # einzelner Datensatz außerhalb des Standardumfangs
uv run klima ghcnd-suchen --land US --name "NY CITY"           # GHCN-Daily-Stationen finden …
uv run klima laden ghcnd_tageswerte --station USW00094728     # … und gezielt laden
```

Die Daten landen in `daten/roh/<datensatz>/`, ein Manifest mit Prüfsummen in `daten/roh/manifest.json`.
Erneute Aufrufe übertragen nur geänderte Dateien. Die Quellen sind in `konfiguration/quellen.toml` definiert.

## Aufbereiten und Einlesen

```bash
uv run klima aufbereiten                # alle geladenen Datensätze nach daten/aufbereitet/
```

Rohdaten bleiben als Archiv liegen. `klima aufbereiten` liest sie im Arbeitsspeicher und legt
Tabellen als Parquet und Gitterdaten (ERSST) als NetCDF ab. In Notebooks:

```python
from klima import einlesen

stationen = einlesen.ghcnm_stationen(laender=["GM"])
werte = einlesen.ghcnm_monatswerte("qcf", stationen=stationen.stations_id, von=1951, bis=1980)
sst = einlesen.ersst(von=1951, bis=1980, breite=(0, 60))
gistemp = einlesen.gistemp(gebiet="global", art="land_ozean")
deutschland = einlesen.dwd_gebietsmittel("niederschlag")
```

Fehlt die Aufbereitung oder haben sich die Rohdaten geändert, wird automatisch neu aufbereitet.

## Bestand: welche Stationen liegen lokal vor?

```bash
uv run klima stationen --land GM                 # alle Stationen in Deutschland (FIPS-Code)
uv run klima stationen --land germ --name hamburg  # Ländername und Stationsname als Teilstring
uv run klima stationen --quelle dwd_monat --export stationen.csv   # Export (CSV für Excel oder .parquet)
```

Je Quelle, Station und zeitlicher Auflösung: Name, Land, Region, Koordinaten, Messgrößen,
Zeitraum und Vollständigkeit. In Notebooks: `klima.bestand.stationsuebersicht(...)`.

## Auswertungen

```bash
uv run klima analysieren deutschland    # Temperatur/Niederschlag DE, eigene Berechnung vs. DWD
uv run klima analysieren station 3987   # DWD-Station per ID …
uv run klima analysieren station Potsdam   # … oder per Namensteil
uv run klima analysieren jahresverlauf   # Tagesmitteltemperatur DE, jedes Jahr eine Linie
uv run klima analysieren global          # globale Landtemperatur aus GHCNm vs. GISTEMP
uv run klima analysieren land-ozean      # globale Temperatur Land + Ozean vs. GISTEMP/HadCRUT5
uv run klima analysieren kenntage        # Kenntage und Niederschlagsextreme Deutschland vs. DWD
uv run klima analysieren kenntage-station USW00094728   # Kenntage einer Station (DWD oder GHCN-Daily)
uv run klima analysieren tagesgang       # Erwärmung je Uhrzeit, Wärmeinsel (DWD-Stundenwerte)
uv run klima analysieren stadt-land      # Trends städtischer vs. ländlicher Stationen
uv run klima dashboard                   # ausgabe/index.html – Übersicht aller Grafiken
```

Grafiken landen in `ausgabe/` – statisch als PNG/SVG, interaktiv als HTML (plotly).
Optionen wie `--trend-von`, `--referenz-von`/`--referenz-bis` siehe `--help`.

## Dokumentation einzelner Auswertungen

- [Jahresverlauf der Tagesmitteltemperatur in Deutschland](docs/jahresverlauf_deutschland.md) –
  Methode, Umgang mit Schaltjahren, Validierung gegen DWD, Extremtage
- [Globale Landtemperatur aus Stationsdaten](docs/global_land.md) – Methode, Vergleich mit GISTEMP,
  Effekt der Homogenisierung, Abdeckung
- [Globale Temperatur aus Land und Ozean](docs/global_land_ozean.md) – ERSST, Landanteil,
  Vergleich mit GISTEMP und HadCRUT5
- [Kenntage und Extreme aus Tageswerten](docs/kenntage.md) – Definitionen, Vergleich mit DWD,
  Stationen weltweit aus GHCN-Daily
- [Tagesgang, Wärmeinsel und Stadt/Land](docs/tagesgang_stadt_land.md) – Stundenwerte (MEZ/UTC),
  Erwärmung je Uhrzeit, Wärmeinsel, Einfluss der Städte auf Trends, Dashboard

## Notebooks

```bash
uv run jupyter lab notebooks/
```

- `01_deutschland.ipynb` – Gebietsmittel Deutschland: vier Berechnungswege im Vergleich, Niederschlag, Stationstrends, Potsdam
- `02_global_land.ipynb` – globale Landtemperatur: QCU vs. QCF, Vergleich mit GISTEMP, Homogenisierung, Abdeckung
- `03_global_land_ozean.ipynb` – Land + Ozean (ERSST), Vergleich mit GISTEMP und HadCRUT5
- `04_kenntage.ipynb` – Kenntage und Niederschlagsextreme, Deutschland und GHCN-Daily-Stationen

## Tests

```bash
uv run pytest
```
