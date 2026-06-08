"""
generador_web.py
Motor de generación de PDF adaptado para la app web.
Soporta dos marcas: xtrong y xecuro, con paletas y assets propios.
"""
import os
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

from descargador import descargar_imagen
from lector_excel import color_hex

# ── Configuración por marca ─────────────────────────────────────────────────

MARCAS_CONFIG = {
    'xtrong': {
        'color_principal': '#005654',
        'color_acento':    '#B6FF00',
        'color_fondo':     '#FFFFFF',
        'color_texto':     '#000000',
        'color_precio':    '#444444',
        'font_titulo':     'Helvetica-Bold',       # reemplazar por Kanit cuando esté disponible
        'font_cuerpo':     'Helvetica',
        'font_italic':     'Helvetica-BoldOblique',
        'nombre_display':  'XTRONG',
    },
    'xecuro': {
        'color_principal': '#303830',
        'color_acento':    '#FFAD40',
        'color_fondo':     '#FFFFFF',
        'color_texto':     '#000000',
        'color_precio':    '#444444',
        'font_titulo':     'Helvetica-Bold',       # reemplazar por Sora cuando esté disponible
        'font_cuerpo':     'Helvetica',
        'font_italic':     'Helvetica-BoldOblique',
        'nombre_display':  'XECURO',
    },
}

PAGE_W, PAGE_H = 595, 1060
HEADER_H       = 50
TABLA_ROW_H    = 24
TABLA_HEADER_H = 22
TABLA_H_POR_GRUPO = TABLA_ROW_H * 3 + TABLA_HEADER_H


# ── Helpers de dibujo ───────────────────────────────────────────────────────

def _hx(s):
    return HexColor(s)


def _draw_header(c, cfg, categoria, tiene_ce=False, logo_path=None):
    y_bot = PAGE_H - HEADER_H

    # Fondo principal
    c.setFillColor(_hx(cfg['color_principal']))
    c.rect(0, y_bot, PAGE_W, HEADER_H, fill=1, stroke=0)

    # Polígono blanco para logo (esquina sup. derecha)
    px_top = PAGE_W - 180
    px_bot = PAGE_W - 195
    c.setFillColor(white)
    p = c.beginPath()
    p.moveTo(px_top, PAGE_H)
    p.lineTo(PAGE_W, PAGE_H)
    p.lineTo(PAGE_W, y_bot)
    p.lineTo(px_bot, y_bot)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Línea acento en borde inferior del polígono
    c.setStrokeColor(_hx(cfg['color_acento']))
    c.setLineWidth(2)
    c.line(px_bot, y_bot, PAGE_W, y_bot)

    # Logo
    logo_area_x = px_top + 6
    logo_area_w = PAGE_W - logo_area_x - 6
    logo_area_h = HEADER_H - 8
    logo_y      = y_bot + 4

    if logo_path and os.path.exists(logo_path):
        try:
            img  = ImageReader(logo_path)
            iw, ih = img.getSize()
            ratio = iw / ih
            dh = logo_area_h
            dw = dh * ratio
            if dw > logo_area_w:
                dw = logo_area_w
                dh = dw / ratio
            lx = logo_area_x + (logo_area_w - dw) / 2
            ly = logo_y + (logo_area_h - dh) / 2
            c.drawImage(logo_path, lx, ly, dw, dh, mask='auto')
        except Exception:
            _draw_logo_texto(c, cfg, logo_area_x, PAGE_H - 4, PAGE_W - 6)
    else:
        _draw_logo_texto(c, cfg, logo_area_x, PAGE_H - 4, PAGE_W - 6)

    # Badge CE
    if tiene_ce:
        c.setFillColor(_hx(cfg['color_principal']))
        c.setFont('Helvetica-Bold', 14)
        c.drawRightString(PAGE_W - 8, y_bot + 6, 'CE')

    # Categoría
    cat_text = categoria.title() if categoria.isupper() else categoria
    c.setFillColor(white)
    c.setFont(cfg['font_italic'], 16)
    c.drawString(16, y_bot + 16, cat_text)


def _draw_logo_texto(c, cfg, x_left, y_top, x_right):
    c.setFillColor(_hx(cfg['color_principal']))
    c.setFont('Helvetica-Bold', 15)
    c.drawRightString(x_right - 6, y_top - 18, cfg['nombre_display'])
    c.setFont('Helvetica-Bold', 8)
    c.drawRightString(x_right - 6, y_top - 31, 'HELMETS & GEAR')


def _draw_nombre_zona(c, cfg, nombre, genero_spec='', precio=None,
                      mostrar_precio=False, codigo=None):
    y_base = PAGE_H - HEADER_H - 12
    fs = 28 if len(nombre) < 20 else (22 if len(nombre) < 30 else 17)

    c.setFillColor(_hx(cfg['color_texto']))
    c.setFont(cfg['font_titulo'], fs)
    c.drawString(16, y_base - fs, nombre)
    y_cur = y_base - fs - 4

    if mostrar_precio and precio and precio > 0:
        try:
            pf = f"${int(float(str(precio))):,}".replace(',', '.')
        except Exception:
            pf = ''
        if pf:
            c.setFillColor(_hx(cfg['color_precio']))
            c.setFont('Helvetica-Bold', 13)
            c.drawString(16, y_cur - 13, pf)
            y_cur -= 22

    if genero_spec:
        c.setFillColor(HexColor('#444444'))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(16, y_cur - 12, genero_spec)
        y_cur -= 20

    if codigo:
        bw, bh = 85, 24
        x = PAGE_W - bw - 16
        y_label = PAGE_H - HEADER_H - 26
        y_box   = y_label - bh - 3
        c.setFillColor(_hx(cfg['color_texto']))
        c.setFont('Helvetica-Bold', 10)
        c.drawRightString(PAGE_W - 16, y_label, 'CODIGO')
        c.setFillColor(_hx(cfg['color_principal']))
        c.roundRect(x, y_box, bw, bh, 4, fill=1, stroke=0)
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 13)
        c.drawCentredString(x + bw / 2, y_box + 7, str(codigo))

    return y_cur - 6


def _draw_imagen(c, img_path, x, y_top, w, h_max):
    y_bottom = y_top - h_max
    if not img_path or not os.path.exists(img_path):
        c.setFillColor(HexColor('#F4F4F4'))
        c.setStrokeColor(HexColor('#CCCCCC'))
        c.setLineWidth(0.5)
        c.rect(x, y_bottom, w, h_max, fill=1, stroke=1)
        return y_bottom
    try:
        img = PILImage.open(img_path)
        iw, ih = img.size
        ratio = iw / ih
        if ratio >= w / h_max:
            dw, dh = w, w / ratio
        else:
            dh, dw = h_max, h_max * ratio
        dx = x + (w - dw) / 2
        dy = y_bottom + (h_max - dh) / 2
        ext = os.path.splitext(img_path)[1].lower()
        if ext == '.png':
            c.drawImage(img_path, dx, dy, dw, dh, mask='auto')
        else:
            c.drawImage(img_path, dx, dy, dw, dh)
    except Exception:
        pass
    return y_bottom


def _draw_tabla_tallas(c, cfg, y_top, talla_label, tallas_codigos,
                       color_hex_str=None, color_label=''):
    n = len(tallas_codigos)
    if n == 0:
        return

    COL_W   = min(70, (PAGE_W - 32) / (n + 1))
    tabla_w = COL_W * (n + 1)
    x0      = (PAGE_W - tabla_w) / 2
    y_cur   = y_top

    # Encabezado de color (si aplica)
    if color_hex_str or color_label:
        y_cur -= TABLA_HEADER_H
        c.setFillColor(_hx(cfg['color_principal']))
        c.roundRect(x0, y_cur, tabla_w, TABLA_HEADER_H, 4, fill=1, stroke=0)
        if color_hex_str:
            try:
                c.setFillColor(HexColor(color_hex_str))
                c.circle(x0 + 14, y_cur + TABLA_HEADER_H / 2, 7, fill=1, stroke=0)
            except Exception:
                pass
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 11)
        lbl = color_label.title() if color_label else ''
        c.drawString(x0 + 28, y_cur + 7, lbl)

    # Filas: TALLA / CÓDIGO / INVENTARIO
    filas = [
        (talla_label, [t[0] for t in tallas_codigos], cfg['color_principal'], True),
        ('CÓDIGO',    [t[1] for t in tallas_codigos], '#F0F0F0', False),
        ('INVENT.',   [str(t[2]) if t[2] is not None else '-'
                       for t in tallas_codigos], '#FAFAFA', False),
    ]
    for label, valores, fondo, es_header in filas:
        y_cur -= TABLA_ROW_H
        # Fondo celda label
        c.setFillColor(_hx(fondo) if es_header else HexColor(fondo))
        c.rect(x0, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
        c.setFillColor(white if es_header else _hx(cfg['color_texto']))
        c.setFont('Helvetica-Bold' if es_header else 'Helvetica', 9)
        c.drawCentredString(x0 + COL_W / 2, y_cur + 8, label)

        # Celdas de datos
        for k, val in enumerate(valores):
            cx = x0 + COL_W * (k + 1)
            c.setFillColor(_hx(cfg['color_acento']) if es_header else HexColor(fondo))
            c.rect(cx, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
            txt_color = _hx(cfg['color_principal']) if es_header else HexColor('#333333')
            c.setFillColor(txt_color)
            c.setFont('Helvetica-Bold' if es_header else 'Helvetica', 9)
            c.drawCentredString(cx + COL_W / 2, y_cur + 8, str(val)[:10])

    # Borde general
    c.setStrokeColor(HexColor('#DDDDDD'))
    c.setLineWidth(0.5)
    c.rect(x0, y_cur, tabla_w, y_top - y_cur, fill=0, stroke=1)


def _draw_numero_pagina(c, cfg, num, total):
    c.setFillColor(HexColor('#999999'))
    c.setFont('Helvetica', 9)
    c.drawCentredString(PAGE_W / 2, 14, f"{num} / {total}")


def _draw_full_bleed(c, img_path):
    if img_path and os.path.exists(img_path):
        try:
            c.drawImage(img_path, 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False)
            return
        except Exception:
            pass
    c.setFillColor(HexColor('#111111'))
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)


def _pagina_producto(c, cfg, producto, img_path, mostrar_precios, num, total):
    """Genera una página de producto."""
    c.setFillColor(white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    logo_path = cfg.get('_logo_path')
    _draw_header(c, cfg, producto['categoria'],
                 tiene_ce=producto.get('ce', False), logo_path=logo_path)

    variaciones = producto.get('variaciones', [])
    precio      = producto.get('precio', 0) if mostrar_precios else 0
    sku_padre   = producto.get('sku', '')

    y_nombre_bottom = _draw_nombre_zona(
        c, cfg, producto['nombre'],
        precio=precio, mostrar_precio=mostrar_precios,
        codigo=sku_padre if sku_padre else None,
    )

    # Imagen principal
    y_img_top = y_nombre_bottom - 8
    TABLE_TOP = TABLA_H_POR_GRUPO + 35

    avail = y_img_top - TABLE_TOP - 8
    img_h = max(60, avail * 0.82)
    _draw_imagen(c, img_path, 20, y_img_top, PAGE_W - 40, img_h)

    # Tabla de tallas agrupada por color
    from collections import OrderedDict
    grupos_color = OrderedDict()
    for v in variaciones:
        color = v.get('color', '') or 'default'
        if color not in grupos_color:
            grupos_color[color] = []
        grupos_color[color].append(v)

    y_cur = TABLE_TOP
    for color, vars_color in grupos_color.items():
        tallas_data = [
            (v.get('talla', '') or '-',
             v.get('sku', '') or '-',
             v.get('inventario', None))
            for v in vars_color
        ]
        label = 'COLOR' if color not in ('default', '') else 'TALLA'
        _draw_tabla_tallas(
            c, cfg, y_cur, label, tallas_data,
            color_hex_str=color_hex(color) if color not in ('default', '') else None,
            color_label=color if color not in ('default', '') else '',
        )
        y_cur -= (TABLA_H_POR_GRUPO + 8)

    _draw_numero_pagina(c, cfg, num, total)


# ── Función principal ────────────────────────────────────────────────────────

def generar_pdf_desde_productos(
    productos,
    ruta_salida,
    marca='xtrong',
    titulo='',
    periodo='',
    mostrar_precios=True,
    carpeta_assets='',
    carpeta_cache='',
    callback_log=None,
    callback_progreso=None,
):
    def log(m):
        if callback_log:
            callback_log(m)

    def prog(p):
        if callback_progreso:
            callback_progreso(p)

    cfg = dict(MARCAS_CONFIG.get(marca, MARCAS_CONFIG['xtrong']))

    # Intentar registrar fuentes TTF desde assets
    for font_name, font_file in [('Kanit', 'Kanit-Bold.ttf'), ('Sora', 'Sora-Regular.ttf')]:
        font_path = os.path.join(carpeta_assets, font_file)
        if os.path.exists(font_path):
            try:
                pdfmetrics.registerFont(TTFont(font_name, font_path))
                if marca == 'xtrong' and font_name == 'Kanit':
                    cfg['font_titulo'] = 'Kanit'
                elif marca == 'xecuro' and font_name == 'Sora':
                    cfg['font_titulo'] = 'Sora'
                log(f"  ✅ Fuente {font_name} registrada")
            except Exception as e:
                log(f"  ⚠️ No se pudo cargar fuente {font_name}: {e}")

    # Logo
    logo_path = None
    for fname in ('logo.png', 'logo_xtrong.png', 'logo_xecuro.png', 'LOGO.png'):
        candidate = os.path.join(carpeta_assets, fname)
        if os.path.exists(candidate):
            logo_path = candidate
            log(f"  🖼️ Logo: {fname}")
            break
    cfg['_logo_path'] = logo_path

    # Portada y contraportada
    portada_path  = os.path.join(carpeta_assets, 'PORTADA.jpg')
    contra_path   = os.path.join(carpeta_assets, 'CONTRAPORTADA.jpg')
    # Fallback: buscar por categoría/título
    if not os.path.exists(portada_path):
        for ext in ('.jpg', '.png', '.jpeg'):
            alt = os.path.join(carpeta_assets, f'PORTADA{ext}')
            if os.path.exists(alt):
                portada_path = alt
                break

    # Descargar imágenes de productos
    log("🖼️ Descargando imágenes de productos...")
    total = len(productos)
    imagenes_paths = {}

    for i, prod in enumerate(productos):
        prog(int(40 * i / max(total, 1)))
        nombre = prod.get('nombre', '')
        variaciones = prod.get('variaciones', [])

        group_urls = []
        seen = set()
        for v in variaciones:
            url = v.get('imagenes', '')
            color = v.get('color', 'default')
            if url and url not in seen and color not in seen:
                seen.add(color)
                group_urls.append(url)
                if len(group_urls) >= 2:
                    break
        if not group_urls:
            url = prod.get('imagenes', '')
            if url:
                group_urls.append(url)

        img_list = []
        sku_key  = prod.get('sku', '') or f'prod_{i}'
        for j, url in enumerate(group_urls):
            ck = sku_key if j == 0 else f'{sku_key}_v{j}'
            path = descargar_imagen(url, ck, nombre, carpeta_cache,
                                    callback_log=log)
            img_list.append(path)

        if not img_list:
            img_list.append(None)
        imagenes_paths[i] = img_list

    log("📄 Generando páginas PDF...")
    prog(40)

    c = canvas.Canvas(ruta_salida, pagesize=(PAGE_W, PAGE_H))

    # Portada
    log("  📄 Portada...")
    _draw_full_bleed(c, portada_path)
    # Texto de período sobre portada
    if periodo or titulo:
        overlay = f"{titulo}  {periodo}".strip()
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 14)
        c.drawCentredString(PAGE_W / 2, 40, overlay)
    c.showPage()
    prog(42)

    # Páginas de productos
    for i, prod in enumerate(productos):
        prog(42 + int(55 * i / max(total, 1)))
        img_list = imagenes_paths.get(i, [None])
        img_path = img_list[0] if img_list else None
        log(f"  📝 [{i+1}/{total}] {prod['nombre'][:45]}")
        _pagina_producto(c, cfg, prod, img_path, mostrar_precios, i + 1, total)
        c.showPage()

    # Contraportada
    log("  📄 Contraportada...")
    _draw_full_bleed(c, contra_path)
    c.showPage()

    log("💾 Guardando PDF...")
    c.save()
    prog(100)
    return ruta_salida
