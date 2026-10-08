# Tagesgang, Wärmeinsel und Stadt/Land (M7)

Stand: 08.10.2026 – DWD-Stundenwerte bis 06.10.2026

## Erzeugen

```bash
# Stundenwerte nur für ausgewählte Stationen laden (gesamt wären ~800 MB)
uv run klima laden dwd_stunde_historisch dwd_stunde_aktuell \
  --station 3987 --station 1975 --station 2290 --station 5792 \
  --station 399 --station 3015 --station 3379 --station 1262 --station 4926 --station 4931
uv run klima analysieren tagesgang      # ausgabe/tagesgang/
uv run klima analysieren stadt-land     # ausgabe/stadt_land/
uv run klima dashboard                  # ausgabe/index.html – Übersicht aller Grafiken
```

## Stundenwerte: Achtung Zeitzone

Die Stundenwerte des DWD sind **nicht einheitlich** angegeben: Je Station und Zeitraum steht in
den Metadaten (`Metadaten_Parameter_tu_stunde_*.txt` im ZIP) „Stundenwerte in MEZ“ oder „in UTC“.
In Potsdam z. B. bis 1992 MEZ, danach UTC. Der Parser liest diese Angaben und rechnet alles auf
UTC um. Dargestellt wird in **MEZ** (UTC + 1, ohne Sommerzeit) – in Deutschland ungefähr Sonnenzeit.

Kontrolle: Das mittlere sommerliche Tagesmaximum in Potsdam liegt nach der Umrechnung in allen
Zeiträumen (1970–1990, 1993–2000, 2002–2020) um 15 Uhr MEZ, das Minimum um 5 Uhr.

## Tagesgang der Erwärmung

Methode (`src/klima/tagesgang.py`): Monatsmittel je Stunde (mind. 20 Tage), Anomalie gegenüber
demselben Monat und derselben Stunde 1951–1980, Jahresmittel aus 12 Monaten, linearer Trend je Stunde.

| Station | stärkste Erwärmung seit 1951 | schwächste |
|---|---|---|
| Potsdam | +0,39 °C/Dekade um 17 Uhr | +0,29 um 8 Uhr |
| Hamburg-Fuhlsbüttel | +0,42 °C/Dekade um 19 Uhr | +0,27 um 7 Uhr |
| Hohenpeißenberg | +0,42 °C/Dekade um 18 Uhr | +0,31 um 11 Uhr |
| Zugspitze | +0,30 °C/Dekade um 2 Uhr | +0,22 um 8 Uhr |

Im Flachland und Mittelgebirge erwärmen sich die **späten Nachmittags- und Abendstunden** am
stärksten, die **Morgenstunden** am schwächsten. Das passt zu längerem und stärkerem Sonnenschein
(siehe auch [Kenntage](kenntage.md): Tmax steigt schneller als Tmin). Auf der Zugspitze ist der
Tagesgang der Erwärmung flach. Das Wärmebild für Potsdam zeigt, dass die Erwärmung erst ab den
1980ern deutlich wird; die 2010er liegen zu jeder Uhrzeit 1,4–1,8 °C über 1951–1980.

## Städtische Wärmeinsel im Tagesverlauf

Differenz Stadt − Umland je Stunde, nur Stunden mit Werten an beiden Stationen. **Höhenbereinigt**
mit 0,65 °C pro 100 m (Standardatmosphäre) – sonst wäre z. B. Stuttgart-Neckartal allein wegen
147 m geringerer Höhe rund 1 °C wärmer. Die Bereinigung ist eine Näherung: In Tälern liegt nachts
oft Kaltluft.

| Paar (Zeitraum) | Sommer: größte Differenz | Winter: Mittel |
|---|---|---|
| Berlin-Alexanderplatz − Lindenberg (1969–2011) | +1,9 °C um 21 Uhr | +1,2 °C |
| München-Stadt − München-Flughafen (1997–2026) | +2,1 °C um 4 Uhr | +1,5 °C |
| Stuttgart (Neckartal) − Stuttgart-Echterdingen (2002–2013) | +1,2 °C um 5 Uhr | +0,7 °C |

Typisches Muster: Im **Sommer** ist die Wärmeinsel **nachts** am stärksten (Gebäude und Asphalt
geben gespeicherte Wärme ab) und **mittags** am schwächsten; im Winter ist sie gleichmäßiger.

## Stadt oder Land: Einfluss auf Trends

Einteilung (`src/klima/stadt_land.py`) nach Natural Earth „Populated Places“:
**städtisch** ≤ 10 km vom Zentrum einer Stadt ≥ 100.000 Einwohner, **ländlich** > 30 km von jedem
Ort ≥ 50.000 Einwohner, sonst Übergang. GHCNm: 2.910 städtische, 20.295 ländliche Stationen;
DWD-Tageswerte: 140 städtische, 791 ländliche.

| Trend 1951–2025 | städtisch | ländlich |
|---|---|---|
| Global Land, homogenisiert | +0,25 ± 0,02 °C/Dekade | +0,25 ± 0,02 °C/Dekade |
| Global Land, unbereinigt | +0,24 ± 0,02 °C/Dekade | +0,22 ± 0,02 °C/Dekade |
| Deutschland Tmin | +0,23 ± 0,06 °C/Dekade | +0,24 ± 0,06 °C/Dekade |
| Deutschland Tmax | +0,36 ± 0,09 °C/Dekade | +0,35 ± 0,08 °C/Dekade |
| Deutschland Tropennächte | +0,14 ± 0,08 Tage/Dekade | +0,06 ± 0,03 Tage/Dekade |

- **Der globale Erwärmungstrend ist kein Stadteffekt**: Ländliche Stationen allein ergeben denselben
  Trend. In den unbereinigten Daten erwärmen sich Stadtstationen etwas schneller (+0,02 °C/Dekade);
  die Homogenisierung gleicht das aus.
- **Wärmeinseln erhöhen das Niveau, kaum den Trend** der Mitteltemperatur – mit einer Ausnahme:
  **Tropennächte** nehmen in Städten mehr als doppelt so schnell zu, weil die Städte nachts ohnehin
  wärmer sind und die 20-°C-Schwelle dort häufiger überschritten wird.

## Dashboard

`klima dashboard` schreibt `ausgabe/index.html`: alle erzeugten Grafiken nach Abschnitten
(Deutschland, Global, Tagesgang und Wärmeinsel, Stadt und Land, Einzelstationen) mit Vorschaubild,
Beschreibung und Links auf PNG, SVG und interaktive Fassung. Die Seite braucht keinen Server
und passt sich hellem und dunklem Modus an. Nicht erzeugte Grafiken werden ausgelassen.

## Grenzen

- **Einteilung Stadt/Land** grob: Entfernung zum Stadtzentrum statt tatsächlicher Bebauung um die
  Station; Natural Earth enthält nicht jede Kleinstadt (viele „ländliche“ Stationen in den USA).
- **Wärmeinsel-Paare**: nur drei, mit unterschiedlichen Zeiträumen; Höhenbereinigung ist eine Näherung.
- **GHCNh** (stündliche Daten weltweit) ist nicht eingebunden – der Ablageort bei NOAA war bei der
  Prüfung nicht erreichbar (alte Pfade liefern 404).
