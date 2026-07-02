# -*- coding: utf-8 -*-
"""
paginas_prehechas.py

Motor que dibuja las páginas ya diseñadas (extraídas de los catálogos PDF
pasados) en vez de generarlas dinámicamente. Por cada grupo:

1. Busca el JPG + JSON en assets/paginas_prehechas/{marca}/ que coincida
   con el Grupo_Foto.
2. Dibuja el JPG full-bleed, escalado del lienzo original (720x1280) al
   tamaño de página del PDF (595x1060).
3. Escribe el inventario de cada SKU justo debajo de su celda de código.
4. Si el grupo tiene SKUs que no están en la página (skus_faltantes),
   extiende la tabla hacia la derecha con columnas nuevas dibujadas por
   ReportLab, imitando el estilo del diseñador.
5. Si se pidieron precios, escribe 1-2 líneas debajo de la tabla.

Si no existe página pre-hecha para un grupo, devuelve False y quien llama
debe usar el generador dinámico (fallback vía API) como respaldo.
"""
import os
import json
import unicodedata

from reportlab.lib.colors import HexColor, white
from reportlab.lib.utils import ImageReader

from fuentes_marca import registrar_fuentes_marca

PAGE_W, PAGE_H = 595, 1060  # debe coincidir con generador_web.PAGE_W/PAGE_H

# ── Constantes de calibración ────────────────────────────────────────────
# Estas son las que se ajustan a ojo tras ver el primer PDF de prueba.
FILA_INVENTARIO_OFFSET = 24   # pt hacia abajo desde la celda de código
FILA_TALLA_OFFSET       = 24  # pt hacia abajo desde la celda de código (fila talla, si se dibuja)
ANCHO_COL_DEFECTO       = 58  # pt, cuando no se puede estimar de las columnas existentes
ALTO_CELDA_NUEVA        = 20  # pt, alto de las celdas que dibuja ReportLab al extender tabla
FONT_SIZE_INVENTARIO    = 9
FONT_SIZE_CODIGO_NUEVO  = 8
FONT_SIZE_TALLA_NUEVO   = 9
FONT_SIZE_PRECIO        = 10
PRECIO_LINE_H           = 14
PRECIO_Y_MARGEN         = 18   # pt entre el borde inferior de la tabla y la primera línea de precio


def _sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def _norm(s):
    return _sin_tildes(str(s)).upper().replace(' ', '').replace('_', '')


# ── Índice de páginas pre-hechas ─────────────────────────────────────────

def construir_indice(carpeta_assets, marca, callback_log=None):
    """
    Escanea assets/paginas_prehechas/{marca}/*.json y arma un índice
    grupo_foto -> {'jpg': ruta, 'json': ruta, 'data': dict}.
    Los JSON sin campo grupo_foto se ignoran (páginas viejas del extractor
    de antes de que ese campo existiera) — se loguean para que se puedan
    re-generar con depurar_paginas.py.
    """
    def log(m):
        if callback_log:
            callback_log(m)

    carpeta = os.path.join(carpeta_assets, 'paginas_prehechas', marca)
    indice = {}
    sin_grupo = []
    if not os.path.isdir(carpeta):
        log(f"  ⚠️ No existe carpeta de páginas pre-hechas: {carpeta}")
        return indice

    for archivo in os.listdir(carpeta):
        if not archivo.lower().endswith('.json'):
            continue
        ruta_json = os.path.join(carpeta, archivo)
        try:
            with open(ruta_json, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            log(f"  ⚠️ No se pudo leer {archivo}: {e}")
            continue

        grupo_foto = data.get('grupo_foto')
        if not grupo_foto:
            sin_grupo.append(archivo)
            continue

        base = os.path.splitext(archivo)[0]
        ruta_jpg = os.path.join(carpeta, base + '.jpg')
        if not os.path.exists(ruta_jpg):
            log(f"  ⚠️ {archivo} no tiene JPG hermano ({base}.jpg) — se omite")
            continue

        indice[grupo_foto] = {'jpg': ruta_jpg, 'json': ruta_json, 'data': data}

    if sin_grupo:
        log(f"  ⚠️ {len(sin_grupo)} JSON sin campo grupo_foto (re-correr depurar_paginas.py): "
            f"{sin_grupo[:5]}{'...' if len(sin_grupo) > 5 else ''}")
    log(f"  🗂️ Índice de páginas pre-hechas ({marca}): {len(indice)} grupos")
    return indice


def _formatear_precio(valor):
    if valor is None:
        return None
    try:
        n = int(round(float(valor)))
    except (TypeError, ValueError):
        return None
    return '$' + f'{n:,}'.replace(',', '.')


def _color_principal(cfg):
    return HexColor(cfg['color_principal'])


def _color_acento(cfg):
    return HexColor(cfg['color_acento'])


def tiene_pagina_prehecha(grupo, indice):
    return grupo['grupo_foto'] in indice


def dibujar_pagina_prehecha(c, cfg, grupo, indice, carpeta_assets,
                             mostrar_precio_mayor=False, mostrar_precio_detal=False,
                             callback_log=None):
    """
    Dibuja la página pre-hecha correspondiente al grupo sobre el canvas c
    (ya posicionado, sin haber llamado showPage aún). Devuelve True si
    logró dibujar; False si el grupo no tiene página (el llamador debe
    usar el fallback dinámico).
    """
    def log(m):
        if callback_log:
            callback_log(m)

    entrada = indice.get(grupo['grupo_foto'])
    if not entrada:
        return False

    data = entrada['data']
    page_w_json = float(data.get('page_w') or 720.0)
    page_h_json = float(data.get('page_h') or 1280.0)
    sx = PAGE_W / page_w_json
    sy = PAGE_H / page_h_json

    # 1) Fondo full-bleed (misma técnica que portadas: stretch sin
    #    preservar aspecto, porque el lienzo del diseñador es full-bleed).
    try:
        reader = ImageReader(entrada['jpg'])
        c.drawImage(reader, 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False)
    except Exception as e:
        log(f"  ⚠️ No se pudo dibujar {entrada['jpg']}: {e}")
        c.setFillColor(white)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    fuentes = registrar_fuentes_marca(grupo['marca'], carpeta_assets, callback_log=log)

    skus_json = data.get('skus', {}) or {}
    # Coordenadas escaladas de cada SKU que SÍ está en la página
    coords_existentes = {}
    for sku_str, xy in skus_json.items():
        coords_existentes[sku_str] = (xy['x'] * sx, xy['y'] * sy)

    inventario_por_sku = {str(s['sku']): s for s in grupo['skus']}

    # 2) Fila de inventario para los SKUs que SÍ están en la página
    c.setFont(fuentes['bold'], FONT_SIZE_INVENTARIO)
    c.setFillColor(HexColor('#333333'))
    for sku_str, (x, y) in coords_existentes.items():
        s = inventario_por_sku.get(sku_str)
        inv_txt = str(s['inventario']) if s else '-'
        c.drawCentredString(x, y - FILA_INVENTARIO_OFFSET, inv_txt)

    # 3) Extender tabla para SKUs faltantes en la página
    skus_faltantes = [s for s in grupo['skus'] if str(s['sku']) not in coords_existentes]
    y_tabla_inferior = min((y for _, y in coords_existentes.values()), default=None)
    if skus_faltantes and coords_existentes:
        _extender_tabla(c, cfg, fuentes, coords_existentes, skus_faltantes, log)

    # 4) Precios debajo de la tabla
    if mostrar_precio_mayor or mostrar_precio_detal:
        _dibujar_precios(c, cfg, fuentes, grupo, coords_existentes,
                          mostrar_precio_mayor, mostrar_precio_detal)

    return True


def _extender_tabla(c, cfg, fuentes, coords_existentes, skus_faltantes, log):
    """Dibuja columnas nuevas (talla + código + inventario) a la derecha
    de la tabla existente, para los SKUs que la página del diseñador no
    contempla todavía."""
    xs_ordenados = sorted(x for x, _ in coords_existentes.values())
    y_codigo = list(coords_existentes.values())[0][1]  # todas comparten Y

    if len(xs_ordenados) >= 2:
        deltas = [b - a for a, b in zip(xs_ordenados, xs_ordenados[1:])]
        ancho_col = sum(deltas) / len(deltas)
    else:
        ancho_col = ANCHO_COL_DEFECTO

    x_actual = xs_ordenados[-1] + ancho_col
    margen_derecho = PAGE_W - 20

    for s in skus_faltantes:
        if x_actual > margen_derecho:
            log(f"  ⚠️ Tabla sin espacio para SKU {s['sku']} (se sale de la página) — "
                f"revisar manualmente o pedir página nueva al diseñador")
            break

        # Celda TALLA (fila arriba de código, estilo acento de marca)
        c.setFillColor(_color_acento(cfg))
        c.rect(x_actual - ANCHO_COL_DEFECTO / 2, y_codigo + FILA_TALLA_OFFSET - 4,
               ANCHO_COL_DEFECTO, ALTO_CELDA_NUEVA, fill=1, stroke=0)
        c.setFillColor(_color_principal(cfg))
        c.setFont(fuentes['bold'], FONT_SIZE_TALLA_NUEVO)
        c.drawCentredString(x_actual, y_codigo + FILA_TALLA_OFFSET, (s['talla'] or '-')[:6])

        # Celda CÓDIGO
        c.setFillColor(HexColor('#F8F8F8'))
        c.rect(x_actual - ANCHO_COL_DEFECTO / 2, y_codigo - 4,
               ANCHO_COL_DEFECTO, ALTO_CELDA_NUEVA, fill=1, stroke=0)
        c.setFillColor(HexColor('#333333'))
        c.setFont(fuentes['regular'], FONT_SIZE_CODIGO_NUEVO)
        c.drawCentredString(x_actual, y_codigo, str(s['sku']))

        # Inventario
        c.setFont(fuentes['bold'], FONT_SIZE_INVENTARIO)
        c.drawCentredString(x_actual, y_codigo - FILA_INVENTARIO_OFFSET, str(s['inventario']))

        x_actual += ancho_col


def _dibujar_precios(c, cfg, fuentes, grupo, coords_existentes,
                      mostrar_mayor, mostrar_detal):
    if not coords_existentes:
        return
    x0 = min(x for x, _ in coords_existentes.values())
    y_base = min(y for _, y in coords_existentes.values()) - FILA_INVENTARIO_OFFSET - PRECIO_Y_MARGEN

    s0 = grupo['skus'][0]
    precio_detal = _formatear_precio(s0.get('precio_detal'))
    precio_mayor = _formatear_precio(s0.get('precio_mayor'))

    lineas = []
    if mostrar_detal and precio_detal:
        lineas.append(f'PRECIO DETAL: {precio_detal}')
    if mostrar_mayor and precio_mayor:
        lineas.append(f'PRECIO MAYOR: {precio_mayor}')

    c.setFont(fuentes['bold'], FONT_SIZE_PRECIO)
    c.setFillColor(HexColor(cfg.get('color_precio', '#444444')))
    y = y_base
    for linea in lineas:
        c.drawString(x0 - 20, y, linea)
        y -= PRECIO_LINE_H
