"""
CumbiaPad - Todo el teclado (QWERTY + numérico) convertido en multipad/sintetizador.

Ejecutar:
    pip install flask
    python app.py
Abrir http://127.0.0.1:5050

Distribución:
  Teclado numérico  -> 16 pads de percusión cumbiera
  Fila de números   -> Bajos (grados de la escala)
  Fila Q W E R...   -> Melodía, octava alta
  Fila A S D F...   -> Melodía, octava base
  Fila < Z X C...   -> Acordes (acordeón/teclado)
  Shift + nota      -> sube medio tono (sostenido)

Extras: 8 bases de cumbia con bajo automático, looper por capas y grabación
de la sesión (se guarda en ./grabaciones, descargable también en WAV).
"""
from datetime import datetime
from pathlib import Path

from flask import Flask, render_template, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 300 * 1024 * 1024  # hasta 300 MB por grabación
REC_DIR = Path(__file__).parent / "grabaciones"
REC_DIR.mkdir(exist_ok=True)

# --- Pads del teclado numérico. 'area' ubica el pad en la grilla CSS (forma de numpad).
PADS = [
    {"code": "NumpadDivide",   "label": "/", "name": "Timbal alto",      "sound": "timbalAlto",  "color": "#e040fb", "area": "1 / 2"},
    {"code": "NumpadMultiply", "label": "*", "name": "Timbal bajo",      "sound": "timbalBajo",  "color": "#d500f9", "area": "1 / 3"},
    {"code": "NumpadSubtract", "label": "-", "name": "Platillo",         "sound": "platillo",    "color": "#ffffff", "area": "1 / 4"},
    {"code": "Numpad7",        "label": "7", "name": "Guacharaca larga", "sound": "guachaLarga", "color": "#00e5ff", "area": "2 / 1"},
    {"code": "Numpad8",        "label": "8", "name": "Guacharaca corta", "sound": "guachaCorta", "color": "#2979ff", "area": "2 / 2"},
    {"code": "Numpad9",        "label": "9", "name": "Maracas",          "sound": "maracas",     "color": "#ff1744", "area": "2 / 3"},
    {"code": "NumpadAdd",      "label": "+", "name": "Redoble alegre",   "sound": "redoble",     "color": "#ff6d00", "area": "2 / 4 / 4 / 5"},
    {"code": "Numpad4",        "label": "4", "name": "Tambora",          "sound": "tambora",     "color": "#00e676", "area": "3 / 1"},
    {"code": "Numpad5",        "label": "5", "name": "Llamador",         "sound": "llamador",    "color": "#ff4081", "area": "3 / 2"},
    {"code": "Numpad6",        "label": "6", "name": "Alegre abierto",   "sound": "alegre",      "color": "#ffab00", "area": "3 / 3"},
    {"code": "Numpad1",        "label": "1", "name": "Alegre slap",      "sound": "slap",        "color": "#c6ff00", "area": "4 / 1"},
    {"code": "Numpad2",        "label": "2", "name": "Cencerro",         "sound": "cencerro",    "color": "#76ff03", "area": "4 / 2"},
    {"code": "Numpad3",        "label": "3", "name": "Palmas",           "sound": "palmas",      "color": "#ffc400", "area": "4 / 3"},
    {"code": "NumpadEnter",    "label": "↵", "name": "Clave",            "sound": "clave",       "color": "#18ffff", "area": "4 / 4 / 6 / 5"},
    {"code": "Numpad0",        "label": "0", "name": "Bombo sub",        "sound": "sub",         "color": "#651fff", "area": "5 / 1 / 6 / 3"},
    {"code": "NumpadDecimal",  "label": ".", "name": "Aro tambora",      "sound": "aro",         "color": "#ff9100", "area": "5 / 3"},
]

# --- Filas QWERTY (etiquetas de teclado latinoamericano; se usa event.code, así que
#     funciona con cualquier distribución física).
ROW_NUM = [("Digit1", "1"), ("Digit2", "2"), ("Digit3", "3"), ("Digit4", "4"), ("Digit5", "5"),
           ("Digit6", "6"), ("Digit7", "7"), ("Digit8", "8"), ("Digit9", "9"), ("Digit0", "0"),
           ("Minus", "'"), ("Equal", "¿")]
ROW_Q = [("KeyQ", "Q"), ("KeyW", "W"), ("KeyE", "E"), ("KeyR", "R"), ("KeyT", "T"), ("KeyY", "Y"),
         ("KeyU", "U"), ("KeyI", "I"), ("KeyO", "O"), ("KeyP", "P"), ("BracketLeft", "´"), ("BracketRight", "+")]
ROW_A = [("KeyA", "A"), ("KeyS", "S"), ("KeyD", "D"), ("KeyF", "F"), ("KeyG", "G"), ("KeyH", "H"),
         ("KeyJ", "J"), ("KeyK", "K"), ("KeyL", "L"), ("Semicolon", "Ñ"), ("Quote", "{"), ("Backslash", "}")]
ROW_Z = [("KeyZ", "Z"), ("KeyX", "X"), ("KeyC", "C"), ("KeyV", "V"), ("KeyB", "B"),
         ("KeyN", "N"), ("KeyM", "M"), ("Comma", ","), ("Period", "."), ("Slash", "-"),
         ("IntlBackslash", "<")]

ROWS = [
    {"role": "bass",   "title": "Bajos",          "color": "#7c4dff", "octave": -2,
     "keys": [{"code": c, "label": l, "degree": i} for i, (c, l) in enumerate(ROW_NUM)]},
    {"role": "melody", "title": "Melodía alta",   "color": "#00e5ff", "octave": 1,
     "keys": [{"code": c, "label": l, "degree": i} for i, (c, l) in enumerate(ROW_Q)]},
    {"role": "melody", "title": "Melodía",        "color": "#ffb300", "octave": 0,
     "keys": [{"code": c, "label": l, "degree": i} for i, (c, l) in enumerate(ROW_A)]},
    {"role": "chord",  "title": "Acordes",        "color": "#00e676", "octave": -1,
     "keys": [{"code": c, "label": l, "chord": i} for i, (c, l) in enumerate(ROW_Z)]},
]

# Escalas (semitonos) y acordes (intervalos desde la tónica) para cada modo.
SCALES = {
    "Mayor": {
        "steps": [0, 2, 4, 5, 7, 9, 11],
        "chords": [["I", [0, 4, 7]], ["ii", [2, 5, 9]], ["iii", [4, 7, 11]], ["IV", [5, 9, 12]],
                   ["V", [7, 11, 14]], ["vi", [9, 12, 16]], ["V7", [7, 11, 14, 17]], ["I7", [0, 4, 7, 10]],
                   ["II7", [2, 6, 9, 12]], ["♭VII", [10, 14, 17]], ["iv", [5, 8, 12]]],
    },
    "Menor": {
        "steps": [0, 2, 3, 5, 7, 8, 10],
        "chords": [["i", [0, 3, 7]], ["ii°", [2, 5, 8]], ["III", [3, 7, 10]], ["iv", [5, 8, 12]],
                   ["V", [7, 11, 14]], ["VI", [8, 12, 15]], ["V7", [7, 11, 14, 17]], ["VII", [10, 14, 17]],
                   ["i7", [0, 3, 7, 10]], ["IV", [5, 9, 12]], ["♭II", [1, 5, 8]]],
    },
}

# Bases rítmicas: 16 pasos (semicorcheas de un compás).
# 'bass' = bajo automático: [paso, semitonos respecto a la raíz del último acorde].
GUACHA_L = [0, 4, 8, 12]
GUACHA_C = [2, 3, 6, 7, 10, 11, 14, 15]
BASES = [
    {"name": "— Sin base (solo metrónomo del looper) —", "tempo": 92, "pattern": {}, "bass": []},
    {"name": "Cumbia clásica", "tempo": 92, "bass": [[0, 0], [8, -5]], "pattern": {
        "guachaLarga": GUACHA_L, "guachaCorta": GUACHA_C, "tambora": [0, 8], "llamador": [2, 6, 10, 14],
        "alegre": [7, 13, 15], "slap": [4, 12], "maracas": [1, 5, 9, 13]}},
    {"name": "Cumbia sabanera", "tempo": 100, "bass": [[0, 0], [6, 0], [8, -5], [14, -5]], "pattern": {
        "guachaLarga": GUACHA_L, "guachaCorta": GUACHA_C, "tambora": [0, 6, 8, 14], "llamador": [2, 6, 10, 14],
        "alegre": [3, 7, 11, 13, 15], "slap": [4, 12], "maracas": [1, 5, 9, 13]}},
    {"name": "Cumbia sonidera", "tempo": 88, "bass": [[0, 0], [3, 0], [8, -5], [11, -5]], "pattern": {
        "guachaLarga": GUACHA_L, "guachaCorta": GUACHA_C, "sub": [0, 8], "aro": [4, 12],
        "cencerro": [2, 6, 10, 14], "timbalAlto": [13], "timbalBajo": [14, 15]}},
    {"name": "Cumbia villera", "tempo": 98, "bass": [[0, 0], [6, 0], [8, -5], [14, -5]], "pattern": {
        "sub": [0, 6, 8, 14], "slap": [4, 12], "palmas": [4, 12], "guachaCorta": [2, 6, 10, 14],
        "maracas": [0, 2, 4, 6, 8, 10, 12, 14], "timbalBajo": [15]}},
    {"name": "Chucu-chucu", "tempo": 112, "bass": [[0, 0], [4, -5], [8, 0], [12, -5]], "pattern": {
        "tambora": [0, 8], "cencerro": [0, 4, 8, 12], "palmas": [4, 12], "guachaCorta": [2, 6, 10, 14],
        "maracas": [1, 3, 5, 7, 9, 11, 13, 15], "llamador": [2, 10]}},
    {"name": "Cumbia rebajada", "tempo": 72, "bass": [[0, 0], [8, -5]], "pattern": {
        "guachaLarga": GUACHA_L, "guachaCorta": GUACHA_C, "sub": [0, 8], "aro": [4, 12], "timbalBajo": [15]}},
    {"name": "Puya", "tempo": 132, "bass": [[0, 0], [4, -5], [8, 0], [12, -5]], "pattern": {
        "guachaLarga": GUACHA_L, "guachaCorta": GUACHA_C, "tambora": [0, 4, 8, 12], "llamador": [2, 6, 10, 14],
        "alegre": [3, 5, 7, 11, 13, 15], "slap": [6, 14]}},
]

INSTRUMENTS = ["Acordeón", "Piano", "Marimba", "Sinte", "Órgano"]
KEYS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/kit")
def kit():
    return jsonify(pads=PADS, rows=ROWS, scales=SCALES, bases=BASES,
                   instruments=INSTRUMENTS, keys=KEYS)


# --- Grabaciones de sesión: el navegador sube el audio y se guarda en ./grabaciones
@app.route("/api/grabaciones", methods=["GET"])
def listar_grabaciones():
    files = sorted((f for f in REC_DIR.iterdir() if f.is_file()), key=lambda f: f.stat().st_mtime, reverse=True)
    return jsonify([{"name": f.name, "url": f"/grabaciones/{f.name}",
                     "kb": round(f.stat().st_size / 1024)} for f in files])


@app.route("/api/grabaciones", methods=["POST"])
def subir_grabacion():
    f = request.files.get("audio")
    if not f:
        return jsonify(error="Falta el audio"), 400
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav"}.get(
        (f.mimetype or "").split(";")[0], "webm")
    name = f"sesion_{datetime.now():%Y-%m-%d_%H-%M-%S}.{ext}"
    f.save(REC_DIR / name)
    return jsonify(name=name, url=f"/grabaciones/{name}")


@app.route("/api/grabaciones/<path:name>", methods=["DELETE"])
def borrar_grabacion(name):
    p = REC_DIR / secure_filename(name)
    if p.exists():
        p.unlink()
    return jsonify(ok=True)


@app.route("/grabaciones/<path:name>")
def servir_grabacion(name):
    return send_from_directory(REC_DIR, secure_filename(name), as_attachment=request.args.get("dl") == "1")


if __name__ == "__main__":
    app.run(debug=True, port=5050)
