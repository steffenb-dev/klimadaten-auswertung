# Globale Temperatur aus Land und Ozean (M5)

Stand: 08.10.2026 – GHCN-Monthly v4 vom 06.10.2026, ERSST v5 bis 09/2026, GISTEMP v4 vom
08.09.2026, HadCRUT 5.2

Aus den **Landstationen** (GHCN-Monthly v4, homogenisiert) und der **Meeresoberflächentemperatur**
(ERSST v5) entsteht eine eigene globale Temperaturkurve. Verglichen wird mit **NASA GISTEMP v4**
und **Met Office HadCRUT 5.2**.

## Erzeugen

```bash
uv run klima laden ghcnm_qcf ersst_v5 gistemp hadcrut5
uv run klima analysieren land-ozean        # Grafiken nach ausgabe/global/
```

Notebook: `notebooks/03_global_land_ozean.ipynb`. Beim ersten Lauf lädt cartopy einmalig die
Landmaske von Natural Earth (1:50 Mio.) herunter.

| Datei in `ausgabe/global/` | Inhalt |
|---|---|
| `global_land_ozean.png/.svg/.html` | eigene Kurve vs. GISTEMP und HadCRUT5 (nicht aufgefüllt / aufgefüllt) |
| `land_ozean_anteile.png/.svg` | Land, Ozean und Kombination (eigene Berechnung) |
| `nordhalbkugel_land_ozean.png/.svg`, `suedhalbkugel_land_ozean.png/.svg` | Halbkugeln im Vergleich |
| `global_land_ozean_differenzen.png/.svg` | eigene minus GISTEMP bzw. HadCRUT5 |
| `gitterkarte_land_ozean_letztes_jahrzehnt.png` | Anomalie je 5°-Zelle 2020–2026 |
| `gitterkarte_land_ozean_jahrzehnte.html` | Anomalie je Zelle und Jahrzehnt mit Zeitregler |

## Methode

Implementiert in `src/klima/land_ozean.py`.

1. **Ozean**: ERSST v5 liefert die Meeresoberflächentemperatur je 2°-Zelle und Monat.
   - Unter **Meereis** setzt ERSST den Gefrierpunkt des Meerwassers (−1,8 °C) ein. Diese Werte
     sind keine Messungen der Lufttemperatur und gelten – wie bei HadCRUT – als fehlend.
   - Anomalie je 2°-Zelle und Kalendermonat gegenüber 1951–1980 (mind. 20 Referenzjahre).
   - Flächengewichtetes Mittel der 2°-Zellen innerhalb jeder 5°-Zelle; Längen von 0–358° auf
     −180–180° umgerechnet.
2. **Land**: 5°-Gitteranomalien aus GHCNm (homogenisiert), siehe [M4](global_land.md).
3. **Landanteil** je 5°-Zelle aus der Landmaske von Natural Earth (Stichprobengitter mit
   400 Punkten je Zelle). Summe über die Erde: 28,7 % Land – erwartet sind rund 29 %.
4. **Kombination** je Zelle und Monat: Landanteil × Land + (1 − Landanteil) × Ozean. Liegt nur
   einer der beiden Werte vor (z. B. Inselstation in einer Meereszelle), wird dieser verwendet.
5. **Flächengewichtetes Mittel** über alle besetzten Zellen; Jahresmittel aus 12 Monaten.
6. **HadCRUT5** bezieht sich auf 1961–1990 und wird auf 1951–1980 umgerechnet (Mittel 1951–1980
   abgezogen). Das laufende, unvollständige Jahr wird im Vergleich weggelassen.

Hinweis: ERSST ist eine **Rekonstruktion** – Lücken im Ozean sind statistisch aufgefüllt, der
Ozean ist daher fast vollständig abgedeckt. Über Land wird nicht interpoliert. Weil der Ozean die
Erde fast überall abdeckt, sind globales Mittel und Halbkugelmittel praktisch identisch.

## Ergebnisse

### Trends

| Reihe | 1951–2025 | 1880–2025 |
|---|---|---|
| **eigene Berechnung Land + Ozean** | **+0,15 ± 0,01 °C/Dekade** | **+0,08 ± 0,01 °C/Dekade** |
| NASA GISTEMP | +0,16 ± 0,01 °C/Dekade | +0,08 ± 0,01 °C/Dekade |
| HadCRUT5 nicht aufgefüllt | +0,16 ± 0,01 °C/Dekade | +0,08 ± 0,01 °C/Dekade |
| HadCRUT5 aufgefüllt | +0,16 ± 0,01 °C/Dekade | +0,09 ± 0,01 °C/Dekade |
| nur Land (eigene) | +0,24 ± 0,02 °C/Dekade | |
| nur Ozean (eigene) | +0,12 ± 0,01 °C/Dekade | |
| Nordhalbkugel (eigene) | +0,18 ± 0,02 °C/Dekade | |
| Südhalbkugel (eigene) | +0,11 ± 0,01 °C/Dekade | |

Die Unsicherheit (95 %) berücksichtigt keine Autokorrelation und ist eher zu schmal.

**Das Land erwärmt sich etwa doppelt so schnell wie der Ozean**; die Nordhalbkugel mit mehr
Landfläche schneller als die Südhalbkugel.

### Letzte Jahre (Abweichung von 1951–1980)

| Jahr | eigene | GISTEMP | HadCRUT5 nicht aufgefüllt |
|---|---|---|---|
| 2023 | +1,06 °C | +1,17 °C | +1,17 °C |
| 2024 | +1,15 °C | +1,29 °C | +1,22 °C |
| 2025 | +1,03 °C | +1,19 °C | +1,09 °C |

### Übereinstimmung mit den Referenzdatensätzen (1880–2025)

| eigene minus … | Korrelation | mittl. Differenz | Std.-Abw. | Spanne |
|---|---|---|---|---|
| GISTEMP | 0,996 | −0,01 °C | 0,05 °C | −0,16 … +0,11 °C |
| HadCRUT5 nicht aufgefüllt | 0,987 | −0,02 °C | 0,07 °C | −0,17 … +0,15 °C |
| HadCRUT5 aufgefüllt | 0,984 | −0,01 °C | 0,08 °C | −0,19 … +0,19 °C |

Die Abweichungen lassen sich zuordnen:

- **1925–1945 gegenüber HadCRUT (bis −0,13 °C)**: Während des Zweiten Weltkriegs änderte sich die
  Messpraxis auf Schiffen (Eimer- vs. Ansaugmessungen). ERSST und HadSST4 (Ozean in HadCRUT)
  korrigieren diese Verzerrung unterschiedlich – eine bekannte Stelle im Vergleich der Datensätze.
- **Seit etwa 1990 gegenüber GISTEMP (bis −0,1 °C)**: Wir lassen Meereisflächen aus, und über Land
  wird nicht interpoliert. GISTEMP überträgt Landwerte bis 1.200 km weit – auch in die sich am
  stärksten erwärmende Arktis.
- **Vor 1900 (bis +0,1 °C)**: wenige Landstationen; das Ergebnis hängt dann stark von der
  Rekonstruktion des Ozeans ab.

## Grenzen

- **Arktis und Meereis** fehlen; das unterschätzt die jüngste Erwärmung leicht.
- **Land ohne Interpolation**: Innere Teile von Afrika, Südamerika und Australien sind teils ohne
  Wert (siehe Gitterkarte).
- **Ozean als Rekonstruktion**: Die frühe Abdeckung des Ozeans beruht auf statistischer
  Auffüllung durch ERSST, nicht auf eigenen Berechnungen.
- **Speicherbedarf**: rund 2–3,5 GB Arbeitsspeicher während der Berechnung.
