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

## Tests

```bash
uv run pytest
```
