# Kenntage und Extreme aus Tageswerten (M6)

Stand: 08.10.2026 – DWD-Tageswerte bis 06.10.2026, DWD-Gebietsmittel der Kenntage bis 2025

Aus Tageswerten werden je Station und Jahr **Klimakenntage** und **Niederschlagsindizes**
berechnet. Für Deutschland entsteht daraus ein Gebietsmittel, das mit den offiziellen
DWD-Werten verglichen wird. Stationen weltweit kommen aus **GHCN-Daily** (NOAA).

## Erzeugen

```bash
uv run klima laden dwd_tag_historisch dwd_tag_aktuell dwd_stationen dwd_gebietsmittel_kenntage
uv run klima analysieren kenntage                    # Deutschland, nach ausgabe/deutschland/

# einzelne Stationen weltweit (GHCN-Daily)
uv run klima laden ghcnd_stationen                   # Stationsliste und Inventar
uv run klima ghcnd-suchen --land US --name "NY CITY" # Stationen suchen
uv run klima laden ghcnd_tageswerte --station USW00094728 --station SZ000002220
uv run klima analysieren kenntage-station USW00094728   # oder DWD-ID, z. B. 3987
```

Notebook: `notebooks/04_kenntage.ipynb`

| Datei | Inhalt |
|---|---|
| `ausgabe/deutschland/kenntage_temperatur.png/.svg/.html` | Sommertage, heiße Tage, Tropennächte, Hitzewellentage, Frost- und Eistage – eigene Berechnung vs. DWD |
| `ausgabe/deutschland/kenntage_niederschlag.png/.svg/.html` | Starkregentage (≥ 10/20 mm), Rx1day, Rx5day, Trockenperioden, Anteil sehr nasser Tage |
| `ausgabe/deutschland/tag_nacht.png/.svg` | Tageshöchst- und -tiefstwerte sowie Tagesspanne |
| `ausgabe/deutschland/karte_trend_heisse_tage.png/.html` | Zunahme der heißen Tage je Station seit 1951 |
| `ausgabe/stationen/<id>_<name>_kenntage.png/.svg/.html` | Kenntage und Extreme einer einzelnen Station |

## Definitionen

Schwellen in `konfiguration/analyse.toml`, angelehnt an DWD und ETCCDI.

| Index | Definition |
|---|---|
| Sommertag / heißer Tag | Tmax ≥ 25 °C / ≥ 30 °C |
| Tropennacht | Tmin ≥ 20 °C |
| Frosttag / Eistag | Tmin < 0 °C / Tmax < 0 °C |
| Hitzewelle | mind. 3 aufeinanderfolgende heiße Tage (Jahr = Jahr des ersten Tags) |
| Tagesspanne | Jahresmittel von Tmax − Tmin |
| Niederschlagstag / Starkniederschlag | ≥ 1 mm / ≥ 10 mm bzw. ≥ 20 mm |
| Rx1day / Rx5day | größte 1-Tages- bzw. 5-Tages-Summe |
| SDII | mittlere Menge an Niederschlagstagen |
| CDD / CWD | längste Folge von Tagen < 1 mm bzw. ≥ 1 mm (innerhalb des Kalenderjahres) |
| R95p | Summe an Tagen über dem 95. Perzentil der Niederschlagstage 1951–1980 |

**Vollständigkeit**: Ein Jahr zählt nur mit mindestens 90 % Tageswerten der jeweiligen Größe.
Fehlende Tage werden nicht hochgerechnet; ein fehlender Tag beendet eine Hitzewelle oder
Trockenperiode.

**Gebietsmittel Deutschland**: je Index Abweichung jeder Station von ihrem Mittel 1951–1980 →
1°-Gitter → Flächenmittel, dann das ebenso gegitterte Referenzmittel addiert. So verzerren
wechselnde Stationsnetze das Ergebnis kaum.

## Ergebnisse Deutschland

### Trends 1951–2025

| Index | eigene Berechnung | DWD offiziell |
|---|---|---|
| Sommertage | +3,4 ± 0,9 Tage/Dekade | +3,6 ± 1,0 Tage/Dekade |
| Heiße Tage | +1,2 ± 0,4 Tage/Dekade | +1,2 ± 0,4 Tage/Dekade |
| Tropennächte | +0,07 ± 0,04 Tage/Dekade | +0,05 ± 0,04 Tage/Dekade |
| Tage in Hitzewellen | +0,65 ± 0,26 Tage/Dekade | – |
| Frosttage | −3,7 ± 1,5 Tage/Dekade | −3,4 ± 1,5 Tage/Dekade |
| Eistage | −2,1 ± 1,2 Tage/Dekade | −2,1 ± 1,2 Tage/Dekade |
| Tage mit ≥ 10 mm | +0,05 ± 0,37 Tage/Dekade | +0,08 ± 0,38 Tage/Dekade |
| Tage mit ≥ 20 mm | +0,03 ± 0,12 Tage/Dekade | +0,04 ± 0,11 Tage/Dekade |
| Größte Tagessumme | +0,1 ± 0,5 mm/Dekade | – |
| Längste Trockenperiode | ±0,0 ± 0,5 Tage/Dekade | – |

Die Unsicherheit (95 %) berücksichtigt keine Autokorrelation und ist eher zu schmal.

- **Hitze nimmt deutlich zu, Kälte ab**: Entlang der Trendgeraden der DWD-Werte gibt es 2025
  rund 26 Sommertage und 9 heiße Tage mehr, 26 Frosttage und 16 Eistage weniger pro Jahr als 1951.
  Die Tage in Hitzewellen haben sich etwa vervierfacht (11-jähriges Mittel von rund 1,5 auf rund 6).
- **Niederschlagsextreme**: Im Gebietsmittel kein signifikanter Trend bei Starkregentagen,
  größten Tagessummen und Trockenperioden.
- **Tage erwärmen sich schneller als Nächte**: Tmax +0,36 ± 0,08 °C/Dekade, Tmin
  +0,24 ± 0,06 °C/Dekade, die Tagesspanne wächst um +0,12 °C/Dekade. Der Anstieg setzt vor allem
  ab etwa 1980 ein – vermutlich durch mehr Sonnenschein (weniger Luftverschmutzung, weniger
  Bewölkung). Global ist eher das Gegenteil bekannt (Nächte erwärmen sich schneller).

### Vergleich mit den offiziellen DWD-Gebietsmitteln (1951–2025)

| Index | Korrelation | mittlere Differenz (eigene − DWD) |
|---|---|---|
| Sommertage | 0,999 | −1,7 Tage |
| Heiße Tage | 0,999 | −0,4 Tage |
| Tropennächte | 0,974 | +0,1 Tage |
| Frosttage | 0,998 | −0,7 Tage |
| Eistage | 0,999 | +0,3 Tage |
| Tage mit ≥ 10 mm | 0,988 | +1,3 Tage |
| Tage mit ≥ 20 mm | 0,976 | +0,6 Tage |

Erklärbare systematische Unterschiede:

- **Weniger Sommertage**: Fehlende Tage (bis 10 %) werden nicht hochgerechnet; zudem
  interpoliert der DWD auf ein höhenkorrigiertes 1-km-Raster.
- **Mehr Starkregentage**: Starkregen ist kleinräumig. Das Raster des DWD glättet einzelne
  Extremwerte von Stationen, unser Stationsmittel nicht.

## Stationen weltweit (GHCN-Daily)

Beispiele (Trend 1951–2025):

| Station | Auffälliges |
|---|---|
| New York Central Park (USW00094728, ab 1869) | Tropennächte +3,2 Tage/Dekade, heiße Tage −0,5 Tage/Dekade; Sprung der Tagesspanne um 1910–1920 |
| Säntis (SZ000002220, 2.502 m, ab 1882) | nie Sommertage; Frosttage −5,3, Eistage −5,8 Tage/Dekade |
| Sydney Observatory Hill (ASN00066062, 1858–2020) | Reihe endet in GHCN-Daily 2020 |

**Wichtig**: GHCN-Daily ist **nicht homogenisiert**. Sprünge durch Verlegungen, neue Messgeräte
oder veränderte Umgebung (z. B. Bäume, Bebauung) bleiben erhalten – der Sprung der Tagesspanne in
New York um 1910–1920 ist ein typisches Beispiel. Trends einzelner Stationen sind daher mit Vorsicht
zu lesen; die Zunahme der Tropennächte in New York spiegelt vermutlich auch die städtische
Wärmeinsel wider.

## Grenzen

- Speicherbedarf der Deutschland-Auswertung: rund 4 GB Arbeitsspeicher (alle ~19 Mio. Tageswerte).
- Offizielle DWD-Gebietsmittel für Kenntage gibt es erst ab 1951; die eigene Berechnung ist
  technisch früher möglich, aber mit deutlich weniger Stationen.
