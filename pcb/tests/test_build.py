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
