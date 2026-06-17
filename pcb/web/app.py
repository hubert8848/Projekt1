"""Webowy interfejs pcbforge: przeglad plytek + uczenie footprintow/regul.

Uruchom:  cd pcb && python -m web.app   (domyslnie http://127.0.0.1:5000)
"""
from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import (Flask, abort, redirect, render_template, request,
                   send_from_directory, url_for)

from pcbforge import checks, freerouting
from pcbforge.knowledge import Knowledge
from pcbforge.library import catalog, footprints
from pcbforge.project import build_project
from pcbforge.spec import load_design

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SPECS_DIR = os.path.join(ROOT, "specs")
OUT_DIR = os.path.join(ROOT, "out")
os.makedirs(SPECS_DIR, exist_ok=True)

app = Flask(__name__)


def list_specs():
    return sorted(f[:-5] for f in os.listdir(SPECS_DIR) if f.endswith(".json"))


def load_spec(name):
    path = os.path.join(SPECS_DIR, f"{name}.json")
    if not os.path.exists(path):
        abort(404)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    kb = Knowledge.load()
    return render_template("index.html", specs=list_specs(), kb=kb,
                           parts=catalog.known_parts(),
                           footprints=sorted(footprints.REGISTRY))


@app.route("/board/<name>")
def board(name):
    data = load_spec(name)
    kb = Knowledge.load()
    design = load_design(data)
    outdir = os.path.join(OUT_DIR, design.name)
    res = build_project(design, outdir, kb=kb)
    files = [os.path.basename(p) for p in res.files]
    ses = f"{design.name}.ses"
    has_ses = os.path.exists(os.path.join(outdir, ses))
    return render_template("board.html", name=name, design=design,
                           erc=res.erc, drc=res.drc, files=files,
                           board_w=design.board_w, board_h=design.board_h,
                           nets=design.all_net_names(), kb=kb,
                           footprints=sorted(footprints.REGISTRY),
                           jar=freerouting.find_jar(), has_ses=has_ses, ses=ses)


@app.route("/teach/footprint", methods=["POST"])
def teach_footprint():
    kb = Knowledge.load()
    part = request.form["part"].strip()
    fp = request.form["footprint"].strip()
    if part and fp:
        kb.set_footprint(part, fp)
        kb.add_note(f"footprint {part} -> {fp}")
        kb.save()
    return redirect(request.referrer or url_for("index"))


@app.route("/teach/rule", methods=["POST"])
def teach_rule():
    kb = Knowledge.load()
    part = request.form["part"].strip()
    target = request.form.get("target_ref", "").strip()
    dist = float(request.form.get("dist", 3.0) or 3.0)
    if part:
        kb.add_placement_rule(part, "near", target, dist)
        kb.save()
    return redirect(request.referrer or url_for("index"))


@app.route("/teach/note", methods=["POST"])
def teach_note():
    kb = Knowledge.load()
    text = request.form.get("text", "").strip()
    if text:
        kb.add_note(text)
        kb.save()
    return redirect(request.referrer or url_for("index"))


@app.route("/freeroute/<name>", methods=["POST"])
def freeroute(name):
    data = load_spec(name)
    design = load_design(data)
    outdir = os.path.join(OUT_DIR, design.name)
    build_project(design, outdir, kb=Knowledge.load())
    dsn = os.path.join(outdir, f"{design.name}.dsn")
    ses = os.path.join(outdir, f"{design.name}.ses")
    ok, log = freerouting.run_freerouting(dsn, ses)
    with open(os.path.join(outdir, "freerouting.log"), "w", encoding="utf-8") as f:
        f.write(log)
    return redirect(url_for("board", name=name))


@app.route("/download/<name>/<path:fname>")
def download(name, fname):
    data = load_spec(name)
    outdir = os.path.join(OUT_DIR, data["name"])
    return send_from_directory(outdir, fname, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="127.0.0.1", port=port, debug=True)
