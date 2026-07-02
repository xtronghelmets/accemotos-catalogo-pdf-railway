import os
import json
import threading
import uuid
from datetime import datetime
from flask import Flask, render_template, jsonify, request, send_file

from categorias_config import CATALOGOS

app = Flask(
    __name__,
    template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
    static_folder=os.path.join(os.path.dirname(__file__), 'static'),
)

def _build_marcas():
    # Leer desde archivo como base
    try:
        from leer_claves import obtener_credenciales
        url_xt, ck_xt, cs_xt = obtener_credenciales('xtrong')
        url_xe, ck_xe, cs_xe = obtener_credenciales('xecuro')
    except Exception:
        url_xt = 'https://xtronghelmets.com'
        url_xe = 'https://xecurohelmets.com'
        ck_xt = cs_xt = ck_xe = cs_xe = ''

    # Variables de entorno tienen prioridad sobre el archivo
    return {
        'xtrong': {
            'url':    url_xt,
            'ck':     os.environ.get('XTRONG_CK', ck_xt),
            'cs':     os.environ.get('XTRONG_CS', cs_xt),
            'nombre': 'XTRONG',
            'color':  '#005654',
            'acento': '#B6FF00',
        },
        'xecuro': {
            'url':    url_xe,
            'ck':     os.environ.get('XECURO_CK', ck_xe),
            'cs':     os.environ.get('XECURO_CS', cs_xe),
            'nombre': 'XECURO',
            'color':  '#303830',
            'acento': '#FFAD40',
        },
    }

MARCAS = _build_marcas()

# ── Helpers de estado en /tmp ─────────────────────────────────────────────
TMP = '/tmp/catalogo_jobs'

def _job_path(job_id):
    os.makedirs(TMP, exist_ok=True)
    return os.path.join(TMP, f'{job_id}.json')

def _read_job(job_id):
    try:
        with open(_job_path(job_id), 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def _write_job(job_id, data):
    with open(_job_path(job_id), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False)


# ── Rutas ─────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/catalogos')
def catalogos():
    """Lista los 4 catálogos disponibles (1 XECURO general + 3 XTRONG),
    para que el frontend no tenga que hardcodear nada más que esto."""
    return jsonify({
        'catalogos': [
            {'id': cid, 'marca': cfg['marca'], 'nombre': cfg['nombre']}
            for cid, cfg in CATALOGOS.items()
        ]
    })


@app.route('/api/generar', methods=['POST'])
def generar():
    data = request.json or {}
    catalogo_id = data.get('catalogo_id', '')
    if catalogo_id not in CATALOGOS:
        return jsonify({'error': f"catalogo_id no válido: '{catalogo_id}'"}), 400

    job_id = str(uuid.uuid4())[:8]
    _write_job(job_id, {
        'progreso': 0,
        'logs':     [],
        'ruta_pdf': None,
        'error':    None,
    })

    hilo = threading.Thread(
        target=_ejecutar_generacion,
        args=(job_id, catalogo_id, data),
        daemon=True,
    )
    hilo.start()

    return jsonify({'job_id': job_id})


@app.route('/api/estado/<job_id>')
def estado(job_id):
    j = _read_job(job_id)
    if not j:
        return jsonify({'error': 'Job no encontrado'}), 404
    return jsonify({
        'progreso': j.get('progreso', 0),
        'logs':     j.get('logs', []),
        'listo':    bool(j.get('ruta_pdf')),
        'error':    j.get('error'),
    })


@app.route('/api/descargar/<job_id>')
def descargar(job_id):
    j = _read_job(job_id)
    if not j:
        return jsonify({'error': 'Job no encontrado'}), 404
    ruta = j.get('ruta_pdf')
    if not ruta or not os.path.exists(ruta):
        return jsonify({'error': 'PDF no disponible'}), 404
    nombre = os.path.basename(ruta)
    return send_file(
        ruta,
        as_attachment=True,
        download_name=nombre,
        mimetype='application/pdf',
    )


# ── Worker de generación ──────────────────────────────────────────────────

def _ejecutar_generacion(job_id, catalogo_id, data):
    logs_acum = []

    def log(msg):
        logs_acum.append(msg)
        j = _read_job(job_id) or {}
        j['logs'] = logs_acum[:]
        _write_job(job_id, j)

    def progreso(p):
        j = _read_job(job_id) or {}
        j['progreso'] = p
        j['logs'] = logs_acum[:]
        _write_job(job_id, j)

    try:
        cfg_catalogo   = CATALOGOS[catalogo_id]
        marca_key      = cfg_catalogo['marca']
        periodo        = data.get('periodo', '').strip()
        precio_mayor   = bool(data.get('precio_mayor', False))
        precio_detal   = bool(data.get('precio_detal', False))
        if not periodo:
            raise ValueError("El período es obligatorio. Ej: Junio 2025 · Semana 1")

        base_dir = os.path.dirname(os.path.abspath(__file__))
        carpeta_assets = os.path.join(base_dir, 'assets', marca_key)
        for candidate in [
            os.path.join(base_dir, 'assets', marca_key),
            os.path.join(base_dir, 'assets', marca_key.upper()),
            os.path.join('/var/task', 'assets', marca_key),
            os.path.join('/var/task', 'assets', marca_key.upper()),
        ]:
            if os.path.isdir(candidate):
                carpeta_assets = candidate
                break

        carpeta_cache = f'/tmp/cache_imagenes/{marca_key}'
        os.makedirs(carpeta_cache, exist_ok=True)

        ahora        = datetime.now()
        titulo_slug  = cfg_catalogo['nombre'].replace(' — ', '_').replace(' ', '_')
        periodo_slug = periodo.replace(' ', '_').replace('/', '-') if periodo else ''
        fecha_slug   = ahora.strftime('%Y%m%d-%H%M')
        nombre_pdf   = f"{titulo_slug}_{periodo_slug}_{fecha_slug}.pdf"
        ruta_pdf     = f'/tmp/{nombre_pdf}'

        from orquestador import generar_catalogo
        generar_catalogo(
            catalogo_id=catalogo_id,
            periodo=periodo,
            ruta_salida=ruta_pdf,
            mostrar_precio_mayor=precio_mayor,
            mostrar_precio_detal=precio_detal,
            carpeta_assets=carpeta_assets,
            carpeta_cache=carpeta_cache,
            marcas_woo={
                'xtrong': MARCAS['xtrong'],
                'xecuro': MARCAS['xecuro'],
            },
            callback_log=log,
            callback_progreso=progreso,
        )

        j = _read_job(job_id) or {}
        j['ruta_pdf'] = ruta_pdf
        j['progreso'] = 100
        j['logs']     = logs_acum
        _write_job(job_id, j)
        log(f"✅ PDF listo: {nombre_pdf}")

    except Exception as e:
        j = _read_job(job_id) or {}
        j['error'] = str(e)
        j['logs']  = logs_acum
        _write_job(job_id, j)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
