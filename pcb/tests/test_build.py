"""Testy: generacja, poprawnosc S-expression i spojnosc netlisty."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pcbforge import Design, Component, checks
from pcbforge.sexpr import parse, S, Sym
from pcbforge import sch_writer, pcb_writer, freerouting
from boards.esp32_devboard import build


def _balanced(text):
    """Parser rzuca ValueError przy niezbilansowanych nawiasach."""
    parse(text)
    return True


def test_sexpr_roundtrip():
    expr = S("foo", 1, 2.5, Sym("yes"), "tekst", S("bar", 3))
    r = expr.render(2)
    tree = parse(r)
    assert tree[0] == "foo"


def test_schematic_valid_sexpr():
    d = build()
    text = sch_writer.build_schematic(d, d.name)
    assert _balanced(text)
    assert "kicad_sch" in text
    assert "lib_symbols" in text
    # kazdy uzyty lib_id ma definicje w lib_symbols
    assert "pcbforge:ESP32-WROOM-32" in text


def test_pcb_valid_sexpr_and_netlist():
    d = build()
    text = pcb_writer.build_pcb(d)
    assert _balanced(text)
    # tabela sieci zawiera wszystkie sieci z polaczen
    for net in d.all_net_names():
        assert f'"{net}"' in text
    # obrys plytki
    assert "Edge.Cuts" in text


def test_dsn_valid_sexpr():
    d = build()
    from pcbforge.placement import autoplace
    autoplace(d)
    path = "/tmp/_t.dsn"
    freerouting.export_dsn(d, path)
    with open(path) as f:
        text = f.read()
    assert _balanced(text)
    assert "(network" in text and "(placement" in text


def test_no_erc_errors():
    d = build()
    from pcbforge.placement import autoplace
    autoplace(d)
    issues = checks.run_erc(d) + checks.run_drc_lite(d)
    errors = [i for i in issues if i.severity == "error"]
    assert errors == [], "\n".join(str(i) for i in errors)


def test_pin_pad_consistency():
    """Kazdy podlaczony pin musi istniec jako pad w footprincie."""
    d = build()
    issues = checks.run_erc(d)
    mismatches = [i for i in issues if i.code == "PIN_PAD_MISMATCH"]
    assert mismatches == [], "\n".join(str(i) for i in mismatches)


def test_all_catalog_parts_pin_pad_consistent():
    """Kazdy pin symbolu musi miec odpowiadajacy pad w footprincie."""
    from pcbforge.library import catalog, footprints
    bad = []
    for name in catalog._STATIC:
        part = catalog.get_part(name)
        pads = set(footprints.get(part["footprint"]).pad_numbers())
        pins = set(p.number for p in part["symbol"].pins)
        if pins - pads:
            bad.append(f"{name}: {pins - pads}")
    assert not bad, "\n".join(bad)


def test_two_board_device_clean():
    """Dwuplytkowe urzadzenie (gora+dol) - 0 bledow ERC/DRC, poprawne S-expr."""
    from boards.home_controller import build_bottom, build_top
    from pcbforge.placement import autoplace
    for builder in (build_bottom, build_top):
        d = builder()
        autoplace(d)
        errors = [i for i in (checks.run_erc(d) + checks.run_drc_lite(d))
                  if i.severity == "error"]
        assert errors == [], f"{d.name}:\n" + "\n".join(str(i) for i in errors)
        assert _balanced(sch_writer.build_schematic(d, d.name))
        assert _balanced(pcb_writer.build_pcb(d))


def test_block_board_passes_all_rules():
    """Plytka zbudowana z blokow jest poprawna z definicji: ERC+DRC+reguly = 0 uwag."""
    from boards.smart_switch import build
    from pcbforge import rules
    from pcbforge.placement import autoplace
    d, _ = build()
    autoplace(d)
    issues = checks.run_erc(d) + checks.run_drc_lite(d) + rules.run_rules(d)
    assert issues == [], "\n".join(str(i) for i in issues)


def test_flagship_pair_rules_and_shared_geometry():
    """SmartHome230: obie plytki czyste; otwory i B2B w identycznych
    wspolrzednych; gorna plytka wezsza (obrys wciety)."""
    from boards.smart_home_230 import build_bottom, build_top, FRAME
    from pcbforge.layout import place_pair
    from pcbforge import rules
    f = FRAME
    bo, to = build_bottom(), build_top()
    place_pair(bo.design, to.design, f)
    for d in (bo.design, to.design):
        issues = checks.run_erc(d) + checks.run_drc_lite(d) + rules.run_rules(d)
        assert issues == [], f"{d.name}:\n" + "\n".join(str(i) for i in issues)
    holes_b = {(round(c.x), round(c.y)) for c in bo.design.components if c.role == "mount"}
    holes_t = {(round(c.x), round(c.y)) for c in to.design.components if c.role == "mount"}
    assert holes_b == holes_t and len(holes_b) == 4          # otwory pasuja
    b2b_b = [(c.x, c.y) for c in bo.design.components if c.role == "b2b"][0]
    b2b_t = [(c.x, c.y) for c in to.design.components if c.role == "b2b"][0]
    assert b2b_b == b2b_t                                    # zlacze pasuje
    # gorna plytka wezsza: obrys wciety wzgledem dolnej
    assert to.design.outline[1] > bo.design.outline[1]
    assert to.design.outline[3] < bo.design.outline[3]
    # sieci 230V oznaczone
    assert {"L", "N", "PE", "LAMP1", "LAMP2"} <= bo.design.mains_nets


def test_pro_controller_clean_and_complete():
    """HomeController PRO: 32 wej / 16 wyj, 2 plyty, 0 bledow/ostrzezen,
    poprawny netlist (RS485+CAN+TFT+ESP32-C3+przekazniki+MOSFETy)."""
    from boards.home_controller_pro import build_bottom, build_top, FRAME
    from pcbforge.layout import place_pair
    from pcbforge import rules
    bo, to = build_bottom(), build_top()
    place_pair(bo.design, to.design, FRAME)
    for d in (bo.design, to.design):
        issues = checks.run_erc(d) + checks.run_drc_lite(d) + rules.run_rules(d)
        assert issues == [], f"{d.name}:\n" + "\n".join(str(i) for i in issues)
    # 16 wyjsc (8 przekaznikow + 8 MOSFET)
    relays = [c for c in bo.design.components if c.part == "Relay_SPDT"]
    mosfets = [c for c in bo.design.components if c.part == "Q_NMOS_DPAK"]
    assert len(relays) == 8 and len(mosfets) == 8
    # 32 wejscia na 8 RJ45 + magistrale + TFT na gorze
    rj45 = [c for c in to.design.components if c.part == "RJ45"]
    assert len(rj45) >= 10  # 8 wejsc + RS485 + CAN
    assert any(c.part == "ESP32-C3" for c in to.design.components)
    assert any(c.part == "TJA1051" for c in to.design.components)   # CAN
    assert any(c.part == "MAX485" for c in to.design.components)    # RS485


def test_rule_engine_detects_missing_decoupling():
    """Silnik regul wykrywa brak dekapu przy IC."""
    from pcbforge import rules, Design, Component
    d = Design("t")
    u = Component("U1", "AMS1117-3.3", "x", "SOT-223")
    u.connect("3", "VIN").connect("1", "GND").connect("2", "3V3").connect("4", "3V3")
    d.add(u)
    d.add(Component("R1", "R", "1k", "R_0805").connect("1", "VIN").connect("2", "GND"))
    codes = {i.code for i in rules.run_rules(d)}
    assert "DECOUPLING" in codes


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    failed = 0
    for fn in fns:
        try:
            fn()
            print(f"PASS {fn.__name__}")
        except Exception as e:
            failed += 1
            print(f"FAIL {fn.__name__}: {e}")
    print(f"\n{len(fns) - failed}/{len(fns)} testow przeszlo.")
    raise SystemExit(1 if failed else 0)
