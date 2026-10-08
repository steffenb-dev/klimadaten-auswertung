# Globale Landtemperatur aus Stationsdaten (M4)

Stand: 08.10.2026 – GHCN-Monthly v4 vom 06.10.2026, GISTEMP v4 vom 08.09.2026

Wir berechnen die globale Landtemperatur selbst aus den Rohdaten der Wetterstationen von
**GHCN-Monthly v4** (NOAA) – einmal aus den **unbereinigten** (QCU), einmal aus den
**homogenisierten** (QCF) Daten – und vergleichen mit **NASA GISTEMP v4 „nur Land“**.

## Erzeugen

```bash
uv run klima laden ghcnm_qcu ghcnm_qcf ghcnm_laender gistemp
uv run klima analysieren global            # Grafiken nach ausgabe/global/
```

Notebook: `notebooks/02_global_land.ipynb`

| Datei in `ausgabe/global/` | Inhalt |
|---|---|
| `global_land.png/.svg/.html` | globale Landkurven: eigene Berechnung (QCF, QCU, Halbkugelmittel) vs. GISTEMP |
| `halbkugeln_land.png/.svg` | Nord- und Südhalbkugel (homogenisiert) |
| `global_land_differenzen.png/.svg` | Differenzen: homogenisiert − unbereinigt, GISTEMP − eigene |
| `homogenisierung_histogramm.png/.svg` | Trendänderung je Station durch Homogenisierung |
| `homogenisierung_karte.png/.html` | dieselbe Trendänderung als Weltkarte |
| `stationstrends_karte.png` | Temperaturtrend je Station seit 1951 |
| `abdeckung.png/.svg` | aktive Stationen und abgedeckte Erdoberfläche je Jahr |
| `gitterkarte_letztes_jahrzehnt.png` | Anomalie je 5°-Zelle 2020–2026 |
| `gitterkarte_jahrzehnte.html` | Anomalie je Zelle und Jahrzehnt mit Zeitregler |

## Methode

Implementiert in `src/klima/weltweit.py`.

1. **Anomalien** je Station und Kalendermonat gegenüber 1951–1980. Eine Station braucht für den
   jeweiligen Kalendermonat mindestens 20 Jahre in der Referenzperiode – das erfüllen
   **11.068** (QCF) bzw. **11.627** (QCU) der ~28.000 Stationen. Stationen ohne ausreichende
   Referenz (v. a. sehr junge oder sehr kurze Reihen) fließen nicht ein.
2. **Gitterung** auf 5°×5°-Zellen: Mittel der Stationsanomalien je Zelle und Monat.
3. **Flächengewichtetes Mittel** über alle besetzten Zellen (Gewicht = cos der Breite);
   es wird **nicht** in leere Zellen interpoliert.
4. **Jahresmittel** nur aus vollständigen Jahren (12 Monate).
5. **Halbkugelmittel** = (Nordhalbkugel + Südhalbkugel) / 2 – wie bei CRUTEM, um die
   Nordlastigkeit des Stationsnetzes auszugleichen.

## Ergebnisse

### Trends

| Reihe | 1951–2025 | 1880–2025 |
|---|---|---|
| NASA GISTEMP nur Land | +0,21 ± 0,02 °C/Dekade | +0,11 ± 0,01 °C/Dekade |
| eigene, homogenisiert, global | +0,24 ± 0,02 °C/Dekade | +0,13 ± 0,01 °C/Dekade |
| eigene, unbereinigt, global | +0,23 ± 0,02 °C/Dekade | +0,11 ± 0,01 °C/Dekade |
| eigene, homogenisiert, Halbkugelmittel | +0,22 ± 0,02 °C/Dekade | +0,12 ± 0,01 °C/Dekade |
| Nordhalbkugel (homogenisiert) | +0,27 ± 0,03 °C/Dekade | |
| Südhalbkugel (homogenisiert) | +0,18 ± 0,02 °C/Dekade | |

Die Unsicherheit (95 %) berücksichtigt keine Autokorrelation und ist eher zu schmal.

Jahresanomalien der letzten Jahre (homogenisiert, global): 2023 +1,74 °C, **2024 +1,92 °C**
(wärmstes Jahr), 2025 +1,78 °C gegenüber 1951–1980.

### Vergleich mit GISTEMP

- Bis etwa 1990 liegen alle Kurven sehr nahe beieinander (Korrelation 0,99).
- **Global** liegen unsere Werte seit 1990 zunehmend **über** GISTEMP – in den 2020er-Jahren um
  rund 0,25 °C. Grund: Das Mittel über besetzte Zellen ist nordlastig, und die Landflächen der
  Nordhalbkugel erwärmen sich am schnellsten.
- Das **Halbkugelmittel** liegt im Mittel 1880–2025 nur **0,01 °C** neben GISTEMP. Die verbleibende
  Abweichung nach 2000 erklärt sich vermutlich dadurch, dass GISTEMP Stationswerte bis 1.200 km weit
  überträgt – auch auf küstennahe Meeresflächen, die sich langsamer erwärmen.

### Effekt der Homogenisierung

- **Global** macht die Homogenisierung die Vergangenheit kälter: homogenisiert minus unbereinigt
  beträgt 1880 −0,18 °C, 1950 −0,02 °C, 2024 +0,13 °C. Der Landtrend seit 1880 steigt dadurch von
  +0,11 auf +0,13 °C/Dekade.
- **Je Station** (2.625 Stationen mit ≥ 80 % vollständigen Jahren 1951–2025): Median +0,012 °C/Dekade,
  55 % der Stationen erhalten einen größeren Trend, 45 % einen kleineren oder gleichen;
  bei rund 540 Stationen ändert sich nichts.
- **Je Land** sehr unterschiedlich (Median der Trendänderung, Länder mit ≥ 30 Stationen):

| Land | Stationen | Median (°C/Dekade) |
|---|---|---|
| USA | 863 | +0,050 |
| Deutschland | 179 | +0,035 |
| China | 191 | +0,026 |
| Australien | 64 | +0,022 |
| Spanien | 41 | +0,019 |
| Russland, Japan, Kanada, Norwegen, Schweden | | 0,000 |

  Die starke Wirkung in den USA passt zu den bekannten Korrekturen für den Wechsel der
  Beobachtungszeit (Time of Observation Bias) und der Messgeräte an US-Stationen.

### Abdeckung

| Jahr | aktive Stationen | besetzte 5°-Zellen | Erdoberfläche in besetzten Zellen |
|---|---|---|---|
| 1850 | 136 | 64 | 2,5 % |
| 1880 | 539 | 170 | 7,5 % |
| 1900 | 1.995 | 320 | 14,0 % |
| 1950 | 7.225 | 728 | 31,7 % |
| 1970 | 10.807 | 862 | 37,6 % (Maximum) |
| 2000 | 7.631 | 759 | 33,2 % |
| 2025 | 4.611 | 655 | 28,9 % |

Land bedeckt rund 29 % der Erdoberfläche; Küstenzellen reichen teilweise über das Meer. Der
Rückgang seit 1970 betrifft vor allem Stationen **mit Referenzwerten 1951–1980** – viele neuere
Stationen haben keine ausreichende Referenz und fließen daher nicht ein.

## Grenzen

- **Keine Interpolation** in leere Zellen: Arktis, Antarktis, Afrika und Südamerika sind früher
  kaum abgedeckt. Das globale Mittel steht für die besetzten Zellen, nicht für die gesamte Landfläche.
- **Feste Referenzperiode**: Stationen ohne 20 Jahre in 1951–1980 fehlen. Verfahren wie die
  „Reference Station Method“ (GISTEMP) oder Berkeley Earth nutzen auch kürzere Reihen.
- **Speicherbedarf**: Die Berechnung beider Varianten braucht kurzzeitig rund 3,5 GB Arbeitsspeicher.
