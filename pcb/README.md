# ⚡ pcbforge — generator schematów i PCB dla KiCad (A→Z)

Profesjonalny przepływ projektowania PCB sterowany opisem układu: **ty mówisz co chcesz
→ powstaje schemat KiCad bez błędów → płytka z footprintami i rozmieszczeniem →
eksport do autoroutingu (Freerouting) → gotowy projekt do otwarcia w KiCad.**
Do tego interfejs **web**, w którym uczysz toolkit, jakie footprinty i reguły
rozmieszczania stosować na przyszłość.

```
opis (czat / YAML)  ─►  Design (model)  ─►  .kicad_sch  (ERC czyste)
                                          ─►  .kicad_pcb (footprinty + placement)
                                          ─►  .dsn       (Specctra → Freerouting)
                          ▲                                   │
                          └──── baza wiedzy (kb.json) ◄────────┘  uczenie z web
```

## Dlaczego to działa bez instalacji KiCada
Toolkit generuje **samowystarczalne pliki KiCad 7**: wbudowane symbole + footprinty
i **jawną listę sieci** w PCB. Dzięki temu projekt otwiera się bez brakujących bibliotek.
Poprawność strukturalną potwierdza biblioteka `kiutils` (realny parser formatu KiCad),
a spójność elektryczną — wbudowane **ERC/DRC-lite**.

## Routing — czy trzeba uciekać z KiCada? Nie.
- **Ręcznie:** interaktywny router KiCada (push-and-shove) jest topowy — do większości
  płytek wystarcza i daje najlepszą jakość.
- **Automatycznie:** KiCad nie ma własnego autoroutera, ale **Freerouting** (Java)
  integruje się przez `.dsn` → trasowanie → `.ses`. To standardowa darmowa droga.
- **Inny program** (Altium/Allegro) ma sens dopiero przy bardzo gęstych, szybkich
  projektach (BGA, DDR, impedancja kontrolowana). Dla prototypów: KiCad + Freerouting.

pcbforge **eksportuje gotowy `.dsn`** i potrafi uruchomić Freerouting. Wynik `.ses`
wczytujesz w KiCad: **PCB Editor → File → Import → Specctra Session**.

---

## Szybki start

```bash
cd pcb
pip install -r requirements.txt          # opcjonalne (web/walidacja/YAML)

# 1) Wygeneruj przykładową płytkę ESP32 (kod):
python -m boards.esp32_devboard

# 2) Albo z deklaratywnego speca:
python -m pcbforge.cli build specs/ESP32_DevBoard.json
python -m pcbforge.cli check specs/ESP32_DevBoard.json
python -m pcbforge.cli route specs/ESP32_DevBoard.json --passes 20   # wymaga freerouting.jar

# 3) Podgląd graficzny (SVG/PNG, bez KiCada):
python -m pcbforge.cli preview specs/SmartSwitch.json

# 4) Pełna produkcja przez prawdziwy KiCad (Gerbery + STEP + ERC/DRC):
bash scripts/setup_kicad.sh                 # instaluje kicad-cli (raz na środowisko)
python -m pcbforge.cli fab specs/SmartSwitch.json

# 5) Interfejs web (przegląd + uczenie + podgląd inline + produkcja):
python -m web.app      # http://127.0.0.1:5000
```

> **KiCad:** eksport Gerberów/STEP/SVG działa od KiCad 7. **ERC/DRC z linii poleceń
> wymaga KiCad ≥ 8** — bez niego używane są kontrole wbudowane (`checks.py` + `rules.py`).

Pliki lądują w `pcb/out/<NazwaPłytki>/` — otwórz `*.kicad_pro` w KiCad.

## Autorouting — Freerouting
```bash
# pobierz jar z https://github.com/freerouting/freerouting/releases
export FREEROUTING_JAR=/sciezka/freerouting.jar
python -m pcbforge.cli route specs/ESP32_DevBoard.json
# -> out/ESP32_DevBoard/ESP32_DevBoard.ses  (import w KiCad)
```

---

## Katalog części
Obecnie ~35 części (rozszerzalne w `pcbforge/library/catalog.py`):
- **Bierne/dyskretne:** R, C, CP (elektrolit), L (cewki + cewka mocy 6×6), FB (ferryt),
  F (bezpiecznik), Y (kwarc), LED, diody (D_Schottky, D_Rectifier, D_TVS/ESD),
  tranzystory/MOSFETy (Q_NPN/PNP/NMOS/PMOS).
- **Układy:** ESP32-WROOM-32, AMS1117-3.3/5.0, MP1584 (buck), MCP23017 (ekspander I²C 16 IO),
  24LCxx (EEPROM), MAX485 (RS485), DS18B20 (czujnik temp 1-wire).
- **Złącza:** RJ45 8P8C, listwy zaciskowe, JST-XH, USB-C (zasilanie), USB Micro-B,
  gniazdo DC, goldpiny/sockety `Header_RxC` (też board-to-board), przyciski tact.
- **Obudowy footprintów:** chip 0402/0603/0805/1206, SOT-23-3/5/6, SOT-223, SOIC-8/14/16/28,
  TO-92, SMA/SOD-123/SOD-323, kwarc 3225 i in.

## Przykład: urządzenie dwupłytkowe (góra/dół)
`boards/home_controller.py` — **kontroler automatyki domowej z dwóch PCB** łączonych
listwą board-to-board 2×10 (wspólne mapowanie pinów `B2B_MAP`):
- **Dół** (`HomeCtrl_Bottom`): wejście 12 V (listwa) → bezpiecznik + dioda zabezpieczająca
  → **buck MP1584 (5 V)** z cewką/diodą/dzielnikiem → **LDO AMS1117 (3V3)** → **ESP32**.
- **Góra** (`HomeCtrl_Top`): listwa B2B → **MCP23017** (16 wejść przycisków) → **4× RJ45**
  (przyciski ścienne + 1-wire), **DS18B20** (temperatura), **ochrona ESD (TVS)** i pull-upy.

RJ45 użyte jako **złącze okablowania** (cat-kabel do włączników i czujnika), bez magnetyki/PHY.
Obie płytki: **ERC 0 błędów, 0 ostrzeżeń**, zwalidowane `kiutils`.

## Przykład: ESP32-WROOM-32 DevBoard
Pełny, realny układ wygenerowany end-to-end (`boards/esp32_devboard.py`):
zasilanie USB 5 V → LDO **AMS1117-3.3** → 3V3, kondensatory bulk + odsprzęgające,
pull-upy EN/IO0, przyciski **EN/BOOT**, LED statusu na IO2, header programatora
1×6 (GND/3V3/EN/IO0/TX/RX) i breakout GPIO 1×10. **ERC: 0 błędów, 0 ostrzeżeń.**

## Opis płytki w YAML/JSON
```yaml
name: Migacz_555
components:
  - {ref: U1, part: NE555, footprint: ... , connections: {...}}
  - {ref: R1, part: R, value: 10k, connections: {"1": VCC, "2": THR}}
```
(rdzeń biblioteki części rozszerza się w `pcbforge/library/catalog.py`)

## Uczenie (baza wiedzy)
W web, na stronie płytki:
- **Zmień footprint części** → zapis do `knowledge/kb.json`, stosowany przy kolejnych generacjach.
- **Reguła „near"** → „umieść C3 blisko U1 o 3 mm" (autoplacement to uwzględni, jeśli nie powoduje kolizji).
- **Notatki** → wskazówki na przyszłość.

---

## Architektura
| Plik | Rola |
|---|---|
| `pcbforge/model.py` | model: `Component`, `Net`, `Design`, reguły |
| `pcbforge/library/symbols.py` | generatory symboli schematu (geometria pinów) |
| `pcbforge/library/footprints.py` | generatory footprintów (pady, kontur) |
| `pcbforge/library/catalog.py` | katalog części (symbol + footprint + piny) |
| `pcbforge/sch_writer.py` | `.kicad_sch` — symbole, etykiety sieci, PWR_FLAG |
| `pcbforge/pcb_writer.py` | `.kicad_pcb` — footprinty, jawna netlista, obrys |
| `pcbforge/placement.py` | autoplacement (pakowanie półkowe, bez kolizji) |
| `pcbforge/checks.py` | ERC + DRC-lite (bez KiCada) |
| `pcbforge/freerouting.py` | eksport `.dsn` + uruchamianie autoroutera |
| `pcbforge/knowledge.py` | baza wiedzy (uczone footprinty/reguły) |
| `pcbforge/spec.py` | deklaratywny opis płytki ↔ model |
| `web/` | interfejs przeglądu i uczenia |
| `boards/`, `specs/` | przykładowe płytki |

## Testy
```bash
python tests/test_build.py     # 6/6: S-expression, netlista, ERC, spójność pin↔pad
```

## Ograniczenia i plan rozwoju
- Biblioteka części jest celowo niewielka (R/C/LED/D/ESP32/AMS1117/USB/przyciski/goldpiny) —
  rozszerzamy „na życzenie" w czacie (ty mówisz część → dodaję symbol+footprint).
- Autoplacement jest bezkolizyjny, ale nie „produkcyjny" — reguły z bazy wiedzy go dostrajają.
- Import `.ses` (trasy) robi KiCad jednym kliknięciem; bezpośredni zapis tras do `.kicad_pcb`
  jest na liście „do zrobienia".
- Przy zainstalowanym `kicad-cli` można dołożyć **prawdziwe ERC/DRC/Gerbery/3D**.

> Format docelowy: **KiCad 7** (`.kicad_sch` v20230121, `.kicad_pcb` v20221018).
> Pliki otwiera też KiCad 8/9.
