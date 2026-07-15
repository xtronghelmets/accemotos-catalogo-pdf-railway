# -*- coding: utf-8 -*-
"""
paginas_sku.py

Motor de páginas pre-armadas que viven en assets/paginas/ (una imagen JPG por
grupo), nombradas con el formato del generador de páginas:

    {sku1}_{sku2}_..._{Grupo_Foto}_{modelo}.jpg
    ej: 14735_14698_G-441_XTR-4205.jpg

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


# ── Índice de páginas de assets/paginas ──────────────────────────────────────
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


def construir_indice_paginas(carpeta_paginas, callback_log=None):
    """Escanea assets/paginas/ y arma dos índices:
        'grupo': Grupo_Foto (mayúsculas) -> ruta_jpg
        'sku':   SKU (str)               -> ruta_jpg
    Devuelve {'grupo': {...}, 'sku': {...}}."""
    def log(m):
        if callback_log:
            callback_log(m)

    idx = {'grupo': {}, 'sku': {}}
    if not os.path.isdir(carpeta_paginas):
        log(f"  ⚠️ No existe carpeta de páginas: {carpeta_paginas}")
        return idx

    n = 0
    for f in os.listdir(carpeta_paginas):
        if not f.lower().endswith(('.jpg', '.jpeg', '.png')):
            continue
        ruta = os.path.join(carpeta_paginas, f)
        grupo, skus = _tokens_archivo(f)
        if grupo and grupo not in idx['grupo']:
            idx['grupo'][grupo] = ruta
        for s in skus:
            idx['sku'].setdefault(s, ruta)
        n += 1
    log(f"  🗂️ assets/paginas: {n} páginas indexadas "
        f"({len(idx['grupo'])} grupos, {len(idx['sku'])} SKUs)")
    return idx


def buscar_pagina(grupo, indice):
    """Devuelve la ruta de la página del grupo (por Grupo_Foto, o por cualquier
    SKU del grupo), o None si no existe."""
    gf = str(grupo.get('grupo_foto') or '').upper()
    if gf and gf in indice['grupo']:
        return indice['grupo'][gf]
    for s in grupo.get('skus', []):
        r = indice['sku'].get(str(s.get('sku')))
        if r:
            return r
    return None


def tiene_pagina(grupo, indice):
    return buscar_pagina(grupo, indice) is not None


# ── Dibujo / estampado ───────────────────────────────────────────────────────

def dibujar_pagina_sku(c, cfg, grupo, ruta_pagina,
                       mostrar_precio_mayor=False, mostrar_precio_detal=False,
                       num=None, total=None, callback_log=None):
    """Dibuja la página pre-armada full-bleed y estampa precio + tabla
    talla/código/inventario + número de página, usando los datos del Excel."""
    import generador_web as gw

    def log(m):
        if callback_log:
            callback_log(m)

    page_w, page_h = gw.PAGE_W, gw.PAGE_H

    # 1) Página full-bleed (estirada al tamaño del PDF, sin preservar aspecto,
    #    igual que portadas — el lienzo del diseñador es full-bleed).
    try:
        c.drawImage(ImageReader(ruta_pagina), 0, 0, page_w, page_h,
                    preserveAspectRatio=False)
    except Exception as e:
        log(f"  ⚠️ No se pudo dibujar {os.path.basename(ruta_pagina)}: {e}")
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

    # 3) Tabla talla / código / inventario (siempre), en la zona inferior.
    filas = [
        {'talla': s.get('talla', ''), 'codigo': s.get('sku'),
         'inventario': s.get('inventario'), 'nombre': s.get('nombre_producto', '')}
        for s in grupo.get('skus', [])
    ]
    if filas:
        _, y_top_tabla = _img_a_pdf(0, TABLA_Y_TOP_IMG, page_w, page_h)
        gw.dibujar_tabla_maestra(
            c, cfg, y_top_tabla, filas,
            x_center=page_w / 2, max_width=page_w - 40, escala=TABLA_ESCALA,
            mostrar_color=False, marcar_adicionales=True,
            precios_debajo=False,   # los precios ya se pintaron arriba
        )

    # 4) Número de página
    if num is not None and total is not None:
        _, y_pie = _img_a_pdf(0, PIE_Y_IMG, page_w, page_h)
        try:
            gw._draw_numero_pagina(c, num, total)
        except Exception:
            pass

    return True
