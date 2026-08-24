# -*- coding: utf-8 -*-
"""
paginas_sku.py

Motor de páginas pre-armadas (una imagen JPG por grupo), nombradas con el
formato del generador de páginas:

    {sku1}_{sku2}_..._{Grupo_Foto}_{modelo}.jpg
    ej: 14735_14698_G-441_XTR-4205.jpg

Fuente de las páginas (en este orden de prioridad):
  1. Manifiesto de Cloudinary (data/paginas_manifest.json), generado por
     Generar_paginas/subir_cloudinary.py. Cada entrada mapea el nombre de
     archivo (sin extensión) a su URL pública en Cloudinary. Esto reemplaza
     a la carpeta assets/paginas/ que antes viajaba completa en el repo git
     (~250 MB, crecía sin límite en el historial).
  2. Fallback: carpeta local assets/paginas/ (uso local/desarrollo, si no
     hay manifiesto).

Esas páginas ya traen foto, nombre, categoría, íconos y certificación, pero
DEJAN EN BLANCO el espacio de:
  - líneas de precio (debajo del título), y
  - tabla talla / código / inventario (zona inferior),
  - número de página.

Este módulo, dado un grupo del Excel (lector_maestro), localiza su página por
Grupo_Foto (o por SKU) y estampa encima el precio y la tabla usando los datos
del Excel (precios columnas C/D, tallas columna H, inventario columna E).

El lienzo original de las páginas es 3001x5334. Todas las posiciones de
estampado se definen en ESAS coordenadas (arriba-izquierda) y se convierten a
las del PDF (595x1060, origen abajo-izquierda) automáticamente. Así, ajustar la
maqueta es solo cambiar las constantes de abajo.
"""
import os
import re
import json
from urllib.parse import urlparse

from reportlab.lib.utils import ImageReader

# Lienzo original de las páginas de assets/paginas
IMG_W, IMG_H = 3001.0, 5334.0

# ── Posiciones de estampado (en coordenadas de la imagen 3001x5334) ──────────
# Precio: justo debajo del título (misma referencia que plantillas.json del
# generador de páginas: xtrong [195,1250], xecuro [195,1233]).
PRECIO_XY_IMG      = {'xtrong': (195, 820), 'xecuro': (195, 880)}
PRECIO_FS_IMG      = 96      # tamaño de fuente del precio en px de la imagen

# Tabla talla/código/inventario: zona inferior en blanco (bajo las miniaturas).
TABLA_Y_TOP_IMG    = 4180    # borde superior de la tabla, en px de la imagen
TABLA_ESCALA       = 1.7     # escala de la tabla (1.0 = tamaño base del PDF)

# Número de página
PIE_Y_IMG          = 5200


def _sx(page_w): return page_w / IMG_W
def _sy(page_h): return page_h / IMG_H


def _img_a_pdf(x_img, y_img, page_w, page_h):
    """Convierte un punto (x,y) desde coordenadas de imagen (arriba-izq) a
    coordenadas del PDF de reportlab (abajo-izq)."""
    return x_img * _sx(page_w), page_h - y_img * _sy(page_h)


# ── Índice de páginas ─────────────────────────────────────────────────────
_RE_GRUPO = re.compile(r'\bG-?\d+\b', re.IGNORECASE)


def _tokens_archivo(nombre):
    """Devuelve (grupo_foto, set_de_skus) a partir del nombre de archivo
    {sku..}_{G-xxx}_{modelo}.jpg. Los SKUs son los tokens numéricos que van
    antes del token de grupo."""
    base = os.path.splitext(nombre)[0]
    partes = base.split('_')
    grupo = None
    skus = set()
    for p in partes:
        if _RE_GRUPO.fullmatch(p):
            grupo = p.upper()
            break
        if p.isdigit():
            skus.add(p)
    return grupo, skus


def _norm_grupo(g):
    """Normaliza un Grupo_Foto para comparar sin importar guiones/espacios/caso:
    'G-352' / 'g 352' / 'G352' -> 'G352'."""
    return re.sub(r'[^A-Z0-9]', '', str(g or '').upper())


def _norm_sku(s):
    """Normaliza un SKU a string entero cuando es numérico ('17222.0' -> '17222')."""
    s = str(s or '').strip()
    if not s:
        return ''
    try:
        return str(int(float(s)))
    except (TypeError, ValueError):
        return s


def _indexar_entrada(idx, nombre_archivo, valor):
    """Agrega una entrada (ruta local o URL) al índice, bajo su Grupo_Foto y
    sus SKUs, tal como se derivan del nombre de archivo."""
    grupo, skus = _tokens_archivo(nombre_archivo)
    if grupo:
        idx['grupo'].setdefault(grupo, valor)
        idx['grupo_norm'].setdefault(_norm_grupo(grupo), valor)
    for s in skus:
        idx['sku'].setdefault(_norm_sku(s), valor)
    return grupo is not None or bool(skus)


def _construir_indice_desde_manifest(ruta_manifest, callback_log=None):
    def log(m):
        if callback_log:
            callback_log(m)

    idx = {'grupo': {}, 'grupo_norm': {}, 'sku': {}}
    try:
        with open(ruta_manifest, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception as e:
        log(f"  ⚠️ No pude leer el manifiesto de páginas ({ruta_manifest}): {e}")
        return None

    archivos = data.get('files', data) if isinstance(data, dict) else {}
    n = 0
    for nombre_sin_ext, info in archivos.items():
        url = info.get('url') if isinstance(info, dict) else info
        if not url:
            continue
        if _indexar_entrada(idx, nombre_sin_ext + '.jpg', url):
            n += 1
    log(f"  🗂️ Manifiesto Cloudinary ({os.path.basename(ruta_manifest)}): "
        f"{n} páginas indexadas ({len(idx['grupo'])} grupos, {len(idx['sku'])} SKUs)")
    return idx


def _construir_indice_desde_carpeta(carpeta_paginas, callback_log=None):
    def log(m):
        if callback_log:
            callback_log(m)

    idx = {'grupo': {}, 'grupo_norm': {}, 'sku': {}}
    if not os.path.isdir(carpeta_paginas):
        log(f"  ⚠️ No existe carpeta de páginas: {carpeta_paginas}")
        return idx

    n = 0
    for f in os.listdir(carpeta_paginas):
        if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        ruta = os.path.join(carpeta_paginas, f)
        if _indexar_entrada(idx, f, ruta):
            n += 1
    log(f"  🗂️ assets/paginas (local): {n} páginas indexadas "
        f"({len(idx['grupo'])} grupos, {len(idx['sku'])} SKUs)")
    return idx


def construir_indice_paginas(carpeta_paginas, ruta_manifest=None, callback_log=None):
    """Escanea las páginas disponibles y arma índices para localizar la
    página de un grupo por Grupo_Foto (exacto o normalizado) o por cualquier
    SKU. Devuelve {'grupo': {...}, 'grupo_norm': {...}, 'sku': {...}}, donde
    los valores son URLs de Cloudinary si hay manifiesto, o rutas locales si
    se usa el fallback de carpeta.

    Prioridad: manifiesto de Cloudinary (ruta_manifest) → carpeta local
    (carpeta_paginas)."""
    if ruta_manifest and os.path.exists(ruta_manifest):
        idx = _construir_indice_desde_manifest(ruta_manifest, callback_log=callback_log)
        if idx is not None:
            return idx
    return _construir_indice_desde_carpeta(carpeta_paginas, callback_log=callback_log)


def buscar_pagina(grupo, indice):
    """Devuelve la ruta (o URL) de la página del grupo, buscando en orden:
    Grupo_Foto exacto → Grupo_Foto normalizado → cualquier SKU del grupo.
    Devuelve None si no existe."""
    gf = str(grupo.get('grupo_foto') or '').upper()
    if gf and gf in indice['grupo']:
        return indice['grupo'][gf]
    gn = _norm_grupo(gf)
    if gn and gn in indice.get('grupo_norm', {}):
        return indice['grupo_norm'][gn]
    for s in grupo.get('skus', []):
        r = indice['sku'].get(_norm_sku(s.get('sku')))
        if r:
            return r
    return None


def tiene_pagina(grupo, indice):
    return buscar_pagina(grupo, indice) is not None


# ── Descarga (si la "página" es una URL de Cloudinary) ───────────────────────
def _es_url(ruta):
    return str(ruta).lower().startswith(('http://', 'https://'))


def _descargar_pagina(url, carpeta_cache, log=lambda m: None):
    """Descarga (con caché en disco) una página servida desde Cloudinary y
    devuelve la ruta local. Mismo patrón que descargar_imagen() en
    descargador.py, simplificado (ya son JPEGs listos, no hace falta
    reconvertir)."""
    os.makedirs(carpeta_cache, exist_ok=True)
    nombre = os.path.basename(urlparse(url).path) or 'pagina.jpg'
    destino = os.path.join(carpeta_cache, '_src_' + nombre)
    if os.path.exists(destino) and os.path.getsize(destino) > 1000:
        return destino
    try:
        import requests
        r = requests.get(url, timeout=20)
        if r.status_code == 200 and len(r.content) > 1000:
            with open(destino, 'wb') as f:
                f.write(r.content)
            return destino
        log(f"  ⚠️ Cloudinary devolvió {r.status_code} para {url}")
    except Exception as e:
        log(f"  ⚠️ No pude descargar página de Cloudinary ({url}): {e}")
    return None


# ── Reducción de imagen (evita OOM en Railway al embeber 3001x5334) ──────────
# Altura objetivo de la página embebida (~2x del PDF de 1060 pt). Reduce el uso
# de memoria de ~48 MB por imagen (a resolución completa) a unos pocos MB.
ALTO_PAGINA_EMBEBIDA = 2120

def _preparar_pagina(ruta, carpeta_cache, log=lambda m: None):
    """Reduce la página a ALTO_PAGINA_EMBEBIDA px de alto y la deja en caché
    como JPEG liviano; reportlab luego embebe ese JPEG (poca RAM). Si algo
    falla, devuelve la ruta original."""
    try:
        os.makedirs(carpeta_cache, exist_ok=True)
        base = os.path.splitext(os.path.basename(ruta))[0]
        destino = os.path.join(carpeta_cache, base + '_r.jpg')
        if os.path.exists(destino) and os.path.getsize(destino) > 1000:
            return destino
        from PIL import Image
        im = Image.open(ruta)
        if im.mode not in ('RGB', 'L'):
            im = im.convert('RGB')
        if im.height > ALTO_PAGINA_EMBEBIDA:
            w = max(1, int(im.width * ALTO_PAGINA_EMBEBIDA / im.height))
            im = im.resize((w, ALTO_PAGINA_EMBEBIDA), Image.LANCZOS)
        im.save(destino, 'JPEG', quality=88, optimize=True)
        try:
            im.close()
        except Exception:
            pass
        return destino
    except Exception as e:
        log(f"  ⚠️ No pude reducir {os.path.basename(ruta)}: {e}")
        return ruta


# ── Dibujo / estampado ───────────────────────────────────────────────────────

def dibujar_pagina_sku(c, cfg, grupo, ruta_pagina,
                       mostrar_precio_mayor=False, mostrar_precio_detal=False,
                       num=None, total=None, carpeta_cache=None, callback_log=None):
    """Dibuja la página pre-armada full-bleed y estampa precio + tabla
    talla/código/inventario + número de página, usando los datos del Excel."""
    import generador_web as gw

    def log(m):
        if callback_log:
            callback_log(m)

    page_w, page_h = gw.PAGE_W, gw.PAGE_H
    carpeta_cache = carpeta_cache or '/tmp/paginas_render'

    # 1) Página full-bleed. Si viene de Cloudinary (URL), se descarga primero
    #    (con caché). Luego se reduce a un JPEG liviano y se embebe POR RUTA
    #    (reportlab incrusta el JPEG directo, sin decodificar a RAM), para no
    #    agotar la memoria de Railway al procesar decenas de páginas.
    ruta_local = _descargar_pagina(ruta_pagina, carpeta_cache, log) if _es_url(ruta_pagina) else ruta_pagina
    if not ruta_local:
        log(f"  ⚠️ No se pudo obtener la página: {ruta_pagina}")
        from reportlab.lib.colors import white
        c.setFillColor(white)
        c.rect(0, 0, page_w, page_h, fill=1, stroke=0)
    else:
        ruta_embeber = _preparar_pagina(ruta_local, carpeta_cache, log)
        try:
            c.drawImage(ruta_embeber, 0, 0, page_w, page_h,
                        preserveAspectRatio=False)
        except Exception as e:
            log(f"  ⚠️ No se pudo dibujar {os.path.basename(str(ruta_pagina))}: {e}")
            from reportlab.lib.colors import white
            c.setFillColor(white)
            c.rect(0, 0, page_w, page_h, fill=1, stroke=0)

    marca = cfg.get('_marca', 'xtrong')
    s0 = grupo['skus'][0] if grupo.get('skus') else {}

    # 2) Líneas de precio (solo si se pidió alguna), debajo del título.
    if mostrar_precio_mayor or mostrar_precio_detal:
        px_img, py_img = PRECIO_XY_IMG.get(marca, PRECIO_XY_IMG['xtrong'])
        x_pdf, y_pdf = _img_a_pdf(px_img, py_img, page_w, page_h)
        fs = max(7.0, PRECIO_FS_IMG * _sy(page_h))
        gw._draw_precios(
            c, cfg, x_pdf, y_pdf,
            precio_mayor=s0.get('precio_mayor'),
            precio_detal=s0.get('precio_detal'),
            mostrar_mayor=mostrar_precio_mayor,
            mostrar_detal=mostrar_precio_detal,
            fs=fs,
        )

    # 3) Tabla código / inventario (+ talla o capacidad), en la zona inferior.
    filas = [
        {'talla': s.get('talla', ''), 'codigo': s.get('sku'),
         'inventario': s.get('inventario'), 'nombre': s.get('nombre_producto', '')}
        for s in grupo.get('skus', [])
    ]
    # Decidir la fila superior de la tabla:
    #  - Maleteros / capacidades (ej. '45L', '60L') -> etiqueta 'CAPACIDAD'.
    #  - Productos sin talla ('Sin talla' -> '') -> NO se dibuja esa fila.
    #  - Resto -> 'TALLA'.
    tallas_no_vacias = [str(s.get('talla') or '').strip()
                        for s in grupo.get('skus', []) if str(s.get('talla') or '').strip()]
    subcat = (grupo.get('subcategoria') or '').lower()
    es_capacidad = ('maletero' in subcat
                    or any(re.match(r'^\d+\s*L$', t, re.IGNORECASE) for t in tallas_no_vacias))
    if es_capacidad:
        etiqueta_talla, mostrar_fila_talla = 'CAPACIDAD', True
    elif not tallas_no_vacias:
        etiqueta_talla, mostrar_fila_talla = 'TALLA', False
    else:
        etiqueta_talla, mostrar_fila_talla = 'TALLA', True

    if filas:
        _, y_top_tabla = _img_a_pdf(0, TABLA_Y_TOP_IMG, page_w, page_h)
        gw.dibujar_tabla_maestra(
            c, cfg, y_top_tabla, filas,
            x_center=page_w / 2, max_width=page_w - 40, escala=TABLA_ESCALA,
            mostrar_color=False, marcar_adicionales=True,
            precios_debajo=False,   # los precios ya se pintaron arriba
            etiqueta_talla=etiqueta_talla, mostrar_fila_talla=mostrar_fila_talla,
        )

    # 4) Número de página
    if num is not None and total is not None:
        _, y_pie = _img_a_pdf(0, PIE_Y_IMG, page_w, page_h)
        try:
            gw._draw_numero_pagina(c, num, total)
        except Exception:
            pass

    return True
