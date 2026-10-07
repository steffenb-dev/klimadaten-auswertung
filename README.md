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

## Tests

```bash
uv run pytest
```
