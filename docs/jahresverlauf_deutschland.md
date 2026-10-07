# Jahresverlauf der Tagesmitteltemperatur in Deutschland

Stand: 07.10.2026 – Daten bis 06.10.2026

Diese Auswertung dient als **manueller Validierungstest** vor dem globalen Teil (M4): Sie zeigt
das selbst berechnete tägliche Gebietsmittel für Deutschland, sodass einzelne Tage und Jahre mit
bekannten Wetterereignissen und den offiziellen DWD-Werten verglichen werden können.

![Jahresverlauf](../ausgabe/deutschland/jahresverlauf_temperatur.png)

*(Die Grafik liegt nicht im Repository, siehe „Erzeugen“.)*

## Erzeugen

```bash
uv run klima laden dwd_tag_historisch dwd_tag_aktuell dwd_stationen dwd_gebietsmittel_temperatur
uv run klima analysieren jahresverlauf                 # Standard: letzte 5 Jahre farbig
uv run klima analysieren jahresverlauf --hervorheben 3 --ab-jahr 1951
```

Ausgabe in `ausgabe/deutschland/`:

- `jahresverlauf_temperatur.png` / `.svg` – statische Grafik
- `jahresverlauf_temperatur.html` – interaktiv: Überfahren einer Linie zeigt Jahr, Datum und Wert

## Was die Grafik zeigt

- **x-Achse**: die 365 Tage eines Jahres (01.01.–31.12.), **y-Achse**: Tagesmitteltemperatur in °C.
- **Jede Linie ist ein Jahr.**
- **Dünn, grau**: alle Jahre 1881–2021 (141 Jahre).
- **Farbig**: die letzten fünf Jahre 2022, 2023, 2024, 2025 und 2026 (bis 06.10.).
- **Schwarz**: Mittel der Referenzperiode 1951–1980 (zusätzlich zur ursprünglichen Anforderung,
  um die Abweichung der letzten Jahre einordnen zu können).

## Wie viele Jahre liegen für Deutschland vor?

- DWD-Tageswerte reichen bis **1759** zurück – anfangs aber nur von **einer** Station.
- Ein belastbares Deutschlandmittel gibt es ab etwa **1880**: Ab dann sind an jedem Tag mindestens
  15 von 65 möglichen 1°-Gitterzellen mit Stationen besetzt.
- Dargestellt wird ab **1881**, dem Beginn der offiziellen DWD-Gebietsmittel:
  **145 vollständige Jahre (1881–2025)** plus das laufende Jahr 2026.

| Jahr | besetzte 1°-Zellen (Minimum über alle Tage) |
|---|---|
| 1781 | 2 |
| 1850 | 3 |
| 1870 | 6 |
| 1881 | 16 |
| 1900 | 29 |
| 1945 | 26 |
| 1950 | 64 |
| 2025 | 60 |

## Umgang mit Schaltjahren

Es gibt **keinen allgemeinen Standard**, aber zwei verbreitete Verfahren:

1. **365-Tage-Kalender** (`noleap` bzw. `365_day` in den CF-Konventionen für Klimadaten): Der
   29. Februar kommt nicht vor. Klimamodelle verwenden diesen Kalender, weil der Jahresgang in
   jedem Jahr identisch auf derselben Achse liegt.
2. **NOAA, tägliche Klimanormalwerte**: Für den 29. Februar wird kein eigener Normalwert
   berechnet; bei Temperatur wird der Mittelwert der Normalwerte von 28. Februar und 1. März
   verwendet.

**Umsetzung im Projekt:**

- In der Grafik gilt der **365-Tage-Kalender**: Der 29. Februar entfällt, jedes Datum liegt in
  jedem Jahr an derselben Stelle (1. März = Tag 60, 31. Dezember = Tag 365).
- In Monats- und Jahresmitteln ist der 29. Februar **enthalten**. Seine Anomalie wird wie bei der
  NOAA gegen das Mittel der Referenzwerte von 28.02. und 01.03. berechnet.

Quellen:

- [GFDL CM2.x FAQ – Kalender ohne Schalttage](https://data1.gfdl.noaa.gov/CM2.X/faq/question_1.html)
- [CFtime – Kalender der CF-Konventionen (`noleap`, `365_day`)](https://pvanlaake.r-universe.dev/CFtime/doc/CFtime.html)
- [NOAA NCEI – Behandlung des 29. Februar in den täglichen Klimanormalwerten](https://www.ncei.noaa.gov/node/5551)
- [Ferret-Mailingliste (NOAA PMEL) – Diskussion zu täglichen Klimatologien und Schaltjahren](https://pmel.noaa.gov/maillists/tmap/ferret_users/fu_2011/msg00267.html)

## Methode: tägliches Gebietsmittel

Implementiert in `src/klima/jahresverlauf.py`.

1. **Datengrundlage**: DWD-Tageswerte (Klima-Kollektiv KL), historische und aktuelle Dateien
   zusammengeführt; bei Überschneidung haben die geprüften historischen Werte Vorrang.
   Messgröße: Tagesmittel der Lufttemperatur (`TMK`).
2. **Referenzmittel je Station und Kalendertag** über 1951–1980; mindestens 20 Jahre je
   Kalendertag. Weil 30 Einzelwerte je Kalendertag stark streuen, wird über **31 Tage zirkulär
   geglättet** (der 31.12. ist Nachbar des 01.01.).
3. **Tägliche Anomalie** je Station = Tageswert − Referenzmittel des Kalendertags.
4. **Gitterung** auf 1°×1°-Zellen und **Flächengewichtung** mit dem Kosinus der Breite – damit
   dichte Stationsnetze nicht dominieren.
5. **Absolute Temperatur** = Referenzmittel für Deutschland (ebenfalls gegittert) + Anomalie.

## Validierung

**Monatsmittel aus dem eigenen Tagesmittel vs. offizielles DWD-Gebietsmittel**
(`jahresverlauf.monatsvergleich_mit_dwd`):

| Zeitraum | Monate | Korrelation | mittl. Differenz | Std.-Abw. | größte Abweichung |
|---|---|---|---|---|---|
| 1881–2026 | 1.749 | 0,9999 | −0,05 °C | 0,11 °C | 0,59 °C (Jan. 1887) |
| 1951–2026 | 909 | 0,9999 | −0,05 °C | 0,11 °C | 0,39 °C |

Die leichte Kälteabweichung von −0,05 °C liegt vermutlich daran, dass der DWD auf ein
höhenkorrigiertes 1-km-Raster interpoliert, während wir Stationswerte über Gitterzellen mitteln.

**Extreme zum Abgleich mit bekannten Ereignissen** (ab 1881):

| | Datum | Tagesmittel | Anomalie |
|---|---|---|---|
| wärmster Tag | 27.06.2026 | 28,7 °C | +12,6 °C |
| | 25.07.2019 | 26,7 °C | +9,8 °C (Hitzewelle, Rekord 42,6 °C in Lingen) |
| | 04.07.2015 | 26,6 °C | +10,2 °C |
| kältester Tag | 11.02.1929 | −19,3 °C | −19,4 °C (Kältewinter 1929) |
| | 01.02.1956 | −17,3 °C | −17,1 °C (Kältewelle Februar 1956) |
| | 18.01.1893 | −16,9 °C | −16,2 °C |

## Grenzen und Hinweise

- **Überlagerung**: Tageswerte schwanken stark; die farbigen Linien überdecken sich besonders im
  Sommer. Eine Variante mit 7-tägigem gleitendem Mittel wäre ruhiger.
- **Speicherbedarf**: Die Berechnung verarbeitet alle ~25 Mio. Tageswerte auf einmal und braucht
  kurzzeitig etwa 3 GB Arbeitsspeicher (Laufzeit rund 10 s).
- **Frühe Jahre**: Vor 1881 bzw. in Teilen der 1940er-Jahre sind deutlich weniger Gitterzellen
  besetzt; das Gebietsmittel ist dort unsicherer.
- **Laufendes Jahr**: 2026 enthält vorläufig geprüfte Werte (`recent`) und endet am letzten
  Messtag (06.10.2026).
