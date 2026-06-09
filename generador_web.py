"""
generador_web.py  v2
Motor PDF con diseño fiel a PLANTILLA_HOJA.png:
- Header con fondo de color + polígono blanco esquina der. con logo
- Nombre producto arriba izquierda
- Resumen descripción bajo el nombre
- Certificación DOT/ECE en esquina superior derecha bajo el logo
- Imagen de perfil centrada (sin frontal)
- Tabla inferior: circulo color + nombre, fila TALLA/CÓDIGO/INVENTARIO
- Portada y contraportada según tipo de catálogo
- Período en portada esquina superior derecha bajo logo
"""
import os
import re
import textwrap
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage

from descargador import descargar_imagen
from lector_excel import color_hex

# ── Config por marca ─────────────────────────────────────────────────────────
MARCAS_CONFIG = {
    'xtrong': {
        'color_principal': '#005654',
        'color_acento':    '#B6FF00',
        'color_texto':     '#000000',
        'color_precio':    '#444444',
        'font_titulo':     'Helvetica-Bold',
        'font_cuerpo':     'Helvetica',
        'font_italic':     'Helvetica-BoldOblique',
        'nombre_display':  'XTRONG',
    },
    'xecuro': {
        'color_principal': '#303830',
        'color_acento':    '#FFAD40',
        'color_texto':     '#000000',
        'color_precio':    '#444444',
        'font_titulo':     'Helvetica-Bold',
        'font_cuerpo':     'Helvetica',
        'font_italic':     'Helvetica-BoldOblique',
        'nombre_display':  'XECURO',
    },
}

# Portadas y contraportadas por tipo de catálogo
ASSETS_POR_TIPO = {
    'abatibles_abiertos': {
        'portada':      'PORTADA_ABATIBLESABIERTOS.png',
        'contraportada':'CONTRAPORTADA_ABATIBLESABIERTOS.png',
    },
    'integrales': {
        'portada':      'PORTADA_INTEGRALES.png',
        'contraportada':'CONTRA_PORTADA_INTEGRALES.png',
    },
    'textiles_accesorios': {
        'portada':      'PORTADA_TEXTILES_Y_ACCESORIOS.png',
        'contraportada':'CONTRA_PORTADA_TEXTILES_Y_ACCESORIOS.png',
    },
}

# Logos de certificación
CERT_ASSETS = {
    'dot_ece': 'CERTIFICACIÓN_DOTECE.png',
    'dot':     'CERTIFICACIÓN_DOT.png',
}

PAGE_W, PAGE_H = 595, 1060
HEADER_H       = 50
TABLA_ROW_H    = 24
TABLA_COLOR_H  = 22    # encabezado de color


def _hx(s):
    return HexColor(s)


# ── Header ───────────────────────────────────────────────────────────────────

def _draw_header(c, cfg, categoria, logo_path=None):
    y_bot = PAGE_H - HEADER_H

    # Fondo principal
    c.setFillColor(_hx(cfg['color_principal']))
    c.rect(0, y_bot, PAGE_W, HEADER_H, fill=1, stroke=0)

    # Polígono blanco esquina derecha
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

    # Línea acento
    c.setStrokeColor(_hx(cfg['color_acento']))
    c.setLineWidth(2)
    c.line(px_bot, y_bot, PAGE_W, y_bot)

    # Logo en polígono blanco
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

    # Categoría en zona verde
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


# ── Zona de nombre + descripción ─────────────────────────────────────────────

def _draw_nombre_zona(c, cfg, nombre, descripcion_corta='', precio=None, mostrar_precio=False):
    """Dibuja nombre del producto y resumen de descripción. Devuelve y inferior."""
    y_base = PAGE_H - HEADER_H - 12
    fs = 26 if len(nombre) < 22 else (20 if len(nombre) < 32 else 16)

    c.setFillColor(_hx(cfg['color_texto']))
    c.setFont(cfg['font_titulo'], fs)
    c.drawString(16, y_base - fs, nombre)
    y_cur = y_base - fs - 6

    if mostrar_precio and precio and precio > 0:
        try:
            pf = f"${int(float(str(precio))):,}".replace(',', '.')
            c.setFillColor(_hx(cfg['color_precio']))
            c.setFont('Helvetica-Bold', 13)
            c.drawString(16, y_cur - 13, pf)
            y_cur -= 20
        except Exception:
            pass

    # Resumen de descripción (máx 2 líneas, ancho ~350pt)
    desc = _limpiar_html(descripcion_corta or '')
    if desc:
        desc_corta = desc[:180]
        lineas = textwrap.wrap(desc_corta, width=62)[:2]
        c.setFillColor(HexColor('#555555'))
        c.setFont('Helvetica', 10)
        for linea in lineas:
            c.drawString(16, y_cur - 11, linea)
            y_cur -= 14

    return y_cur - 8


def _limpiar_html(texto):
    texto = re.sub(r'<[^>]+>', ' ', texto)
    texto = re.sub(r'&[a-z]+;', ' ', texto)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto


# ── Certificación ─────────────────────────────────────────────────────────────

def _draw_cert(c, cfg, tiene_dot, tiene_ece, carpeta_assets):
    """Dibuja logo de certificación DOT/ECE en esquina superior derecha bajo logo."""
    if not tiene_dot and not tiene_ece:
        return

    key = 'dot_ece' if (tiene_dot and tiene_ece) else 'dot'
    fname = CERT_ASSETS.get(key, '')
    cert_path = os.path.join(carpeta_assets, fname)

    # Posición: esquina derecha, justo bajo el header
    cert_w = 90
    cert_h = 50
    x = PAGE_W - cert_w - 12
    y = PAGE_H - HEADER_H - cert_h - 8

    if cert_path and os.path.exists(cert_path):
        try:
            c.drawImage(cert_path, x, y, cert_w, cert_h,
                        mask='auto', preserveAspectRatio=True)
            return
        except Exception:
            pass

    # Fallback texto
    c.setFillColor(_hx(cfg['color_principal']))
    c.setFont('Helvetica-Bold', 9)
    label = 'DOT + ECE' if (tiene_dot and tiene_ece) else 'DOT'
    c.drawRightString(PAGE_W - 12, y + 18, 'CERTIFICACIÓN')
    c.setFont('Helvetica-Bold', 13)
    c.drawRightString(PAGE_W - 12, y + 4, label)


# ── Imagen ────────────────────────────────────────────────────────────────────

def _es_foto_frontal(url_o_path):
    """Heurística: si la URL contiene indicadores de vista frontal, es frontal."""
    nombre = (url_o_path or '').lower()
    indicadores = ['-front', '_front', '-frontal', '_frontal', '-adelante',
                   '-frente', '_frente', 'front-', 'front_']
    return any(ind in nombre for ind in indicadores)


def _draw_imagen(c, img_path, x, y_top, w, h_max):
    y_bottom = y_top - h_max
    if not img_path or not os.path.exists(img_path):
        c.setFillColor(HexColor('#F8F8F8'))
        c.setStrokeColor(HexColor('#E0E0E0'))
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


# ── Tabla de tallas/colores ───────────────────────────────────────────────────

def _draw_tabla(c, cfg, y_top, tallas_data, color_nombre='', color_hex_str=None):
    """
    tallas_data: lista de (talla, codigo, inventario)
    Filas: encabezado color (si aplica) + TALLA / CÓDIGO / INVENTARIO
    """
    n = max(len(tallas_data), 1)
    COL_W   = min(68, (PAGE_W - 40) / (n + 1))
    tabla_w = COL_W * (n + 1)
    x0      = (PAGE_W - tabla_w) / 2
    y_cur   = y_top

    # Encabezado de color
    if color_nombre:
        y_cur -= TABLA_COLOR_H
        c.setFillColor(_hx(cfg['color_principal']))
        c.roundRect(x0, y_cur, tabla_w, TABLA_COLOR_H, 4, fill=1, stroke=0)
        # Círculo de color
        if color_hex_str:
            try:
                c.setFillColor(HexColor(color_hex_str))
                c.circle(x0 + 14, y_cur + TABLA_COLOR_H / 2, 7, fill=1, stroke=0)
            except Exception:
                pass
        c.setFillColor(white)
        c.setFont('Helvetica-Bold', 11)
        c.drawString(x0 + 28, y_cur + 7, color_nombre.title())

    # Fila TALLA
    y_cur -= TABLA_ROW_H
    c.setFillColor(_hx(cfg['color_principal']))
    c.rect(x0, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
    c.setFillColor(white)
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(x0 + COL_W / 2, y_cur + 8, 'TALLA')
    for k, (talla, _, _) in enumerate(tallas_data):
        cx = x0 + COL_W * (k + 1)
        c.setFillColor(_hx(cfg['color_acento']))
        c.rect(cx, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
        c.setFillColor(_hx(cfg['color_principal']))
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(cx + COL_W / 2, y_cur + 8, str(talla or '-')[:8])

    # Fila CÓDIGO
    y_cur -= TABLA_ROW_H
    c.setFillColor(HexColor('#F0F0F0'))
    c.rect(x0, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
    c.setFillColor(HexColor('#333333'))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(x0 + COL_W / 2, y_cur + 8, 'CÓDIGO')
    for k, (_, codigo, _) in enumerate(tallas_data):
        cx = x0 + COL_W * (k + 1)
        c.setFillColor(HexColor('#F8F8F8'))
        c.rect(cx, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
        c.setFillColor(HexColor('#333333'))
        c.setFont('Helvetica', 9)
        c.drawCentredString(cx + COL_W / 2, y_cur + 8, str(codigo or '-')[:10])

    # Fila INVENTARIO
    y_cur -= TABLA_ROW_H
    c.setFillColor(HexColor('#F0F0F0'))
    c.rect(x0, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
    c.setFillColor(HexColor('#333333'))
    c.setFont('Helvetica-Bold', 9)
    c.drawCentredString(x0 + COL_W / 2, y_cur + 8, 'INVENT.')
    for k, (_, _, inv) in enumerate(tallas_data):
        cx = x0 + COL_W * (k + 1)
        c.setFillColor(HexColor('#F8F8F8'))
        c.rect(cx, y_cur, COL_W, TABLA_ROW_H, fill=1, stroke=0)
        c.setFillColor(HexColor('#333333'))
        c.setFont('Helvetica', 9)
        inv_txt = str(inv) if inv is not None else '-'
        c.drawCentredString(cx + COL_W / 2, y_cur + 8, inv_txt)

    # Borde exterior
    total_h = (TABLA_COLOR_H if color_nombre else 0) + TABLA_ROW_H * 3
    c.setStrokeColor(HexColor('#DDDDDD'))
    c.setLineWidth(0.5)
    c.rect(x0, y_top - total_h, tabla_w, total_h, fill=0, stroke=1)


# ── Número de página ──────────────────────────────────────────────────────────

def _draw_numero_pagina(c, num, total):
    c.setFillColor(HexColor('#AAAAAA'))
    c.setFont('Helvetica', 9)
    c.drawCentredString(PAGE_W / 2, 14, f"{num} / {total}")


# ── Full bleed ────────────────────────────────────────────────────────────────

def _draw_full_bleed(c, img_path, texto_overlay=None, cfg=None):
    if img_path and os.path.exists(img_path):
        try:
            c.drawImage(img_path, 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False)
        except Exception:
            c.setFillColor(HexColor('#111111'))
            c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    else:
        c.setFillColor(HexColor('#111111'))
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Período sobre la portada (esquina superior derecha bajo polígono blanco)
    if texto_overlay and cfg:
        c.setFillColor(_hx(cfg['color_principal']))
        c.setFont('Helvetica-Bold', 11)
        c.drawRightString(PAGE_W - 14, PAGE_H - HEADER_H - 18, texto_overlay)


# ── Página de producto ────────────────────────────────────────────────────────

def _pagina_producto(c, cfg, producto, img_path, mostrar_precios, num, total, carpeta_assets):
    # Fondo blanco
    c.setFillColor(white)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    logo_path = cfg.get('_logo_path')
    _draw_header(c, cfg, producto['categoria'], logo_path=logo_path)

    # Certificación DOT/ECE
    desc_txt = producto.get('desc_corta', '') + ' ' + producto.get('descripcion', '')
    tiene_dot = 'DOT' in desc_txt.upper()
    tiene_ece = 'ECE' in desc_txt.upper()
    _draw_cert(c, cfg, tiene_dot, tiene_ece, carpeta_assets)

    # Nombre + descripción
    precio = producto.get('precio', 0) if mostrar_precios else 0
    desc_corta = producto.get('desc_corta', '') or producto.get('descripcion', '') or ''
    y_nombre_bottom = _draw_nombre_zona(
        c, cfg, producto['nombre'],
        descripcion_corta=desc_corta,
        precio=precio,
        mostrar_precio=mostrar_precios,
    )

    # Imagen
    y_img_top = y_nombre_bottom - 6
    TABLE_TOP = (TABLA_COLOR_H + TABLA_ROW_H * 3) + 40
    avail = y_img_top - TABLE_TOP - 8
    img_h = max(60, avail * 0.88)
    _draw_imagen(c, img_path, 20, y_img_top, PAGE_W - 40, img_h)

    # Tabla por color
    from collections import OrderedDict
    variaciones = producto.get('variaciones', [])
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
        color_label   = color if color != 'default' else ''
        color_hex_str = color_hex(color) if color not in ('default', '') else None
        _draw_tabla(c, cfg, y_cur, tallas_data,
                    color_nombre=color_label,
                    color_hex_str=color_hex_str)
        y_cur -= (TABLA_COLOR_H + TABLA_ROW_H * 3 + 10)

    _draw_numero_pagina(c, num, total)


# ── Función principal ─────────────────────────────────────────────────────────

def generar_pdf_desde_productos(
    productos,
    ruta_salida,
    marca='xtrong',
    titulo='',
    tipo_catalogo='',
    periodo='',
    mostrar_precios=True,
    carpeta_assets='',
    carpeta_cache='',
    callback_log=None,
    callback_progreso=None,
):
    def log(m):
        if callback_log: callback_log(m)
    def prog(p):
        if callback_progreso: callback_progreso(p)

    cfg = dict(MARCAS_CONFIG.get(marca, MARCAS_CONFIG['xtrong']))

    # Registrar fuentes TTF
    for font_name, font_file in [('Kanit', 'Kanit-Bold.ttf'), ('Sora', 'Sora-Regular.ttf')]:
        fp = os.path.join(carpeta_assets, font_file)
        if os.path.exists(fp):
            try:
                pdfmetrics.registerFont(TTFont(font_name, fp))
                if marca == 'xtrong' and font_name == 'Kanit':
                    cfg['font_titulo'] = 'Kanit'
                elif marca == 'xecuro' and font_name == 'Sora':
                    cfg['font_titulo'] = 'Sora'
                log(f"  ✅ Fuente {font_name} cargada")
            except Exception as e:
                log(f"  ⚠️ Fuente {font_name}: {e}")

    # Logo
    logo_path = None
    for fname in ('logo.png', 'logo_xtrong.png', 'logo_xecuro.png', 'LOGO.png'):
        candidate = os.path.join(carpeta_assets, fname)
        if os.path.exists(candidate):
            logo_path = candidate
            break
    cfg['_logo_path'] = logo_path

    # Portada y contraportada según tipo
    assets_tipo = ASSETS_POR_TIPO.get(tipo_catalogo, {})
    portada_fname  = assets_tipo.get('portada', 'PORTADA.jpg')
    contra_fname   = assets_tipo.get('contraportada', 'CONTRAPORTADA.jpg')
    portada_path   = os.path.join(carpeta_assets, portada_fname)
    contra_path    = os.path.join(carpeta_assets, contra_fname)
    # Fallback extensiones
    for ext in ('.png', '.jpg', '.jpeg'):
        if not os.path.exists(portada_path):
            portada_path = os.path.join(carpeta_assets, portada_fname.rsplit('.', 1)[0] + ext)
        if not os.path.exists(contra_path):
            contra_path  = os.path.join(carpeta_assets, contra_fname.rsplit('.', 1)[0] + ext)

    log(f"  📄 Portada: {portada_fname}")
    log(f"  📄 Contraportada: {contra_fname}")

    # Descargar imágenes (preferir foto de perfil, evitar frontal)
    log("🖼️ Descargando imágenes...")
    total = len(productos)
    imagenes_paths = {}

    for i, prod in enumerate(productos):
        prog(int(40 * i / max(total, 1)))
        variaciones = prod.get('variaciones', [])

        # Recolectar URLs únicas por color, priorizando no-frontales
        urls_por_color = {}
        for v in variaciones:
            color = v.get('color', 'default') or 'default'
            url   = v.get('imagenes', '')
            if not url:
                continue
            if color not in urls_por_color:
                urls_por_color[color] = url
            elif _es_foto_frontal(urls_por_color[color]) and not _es_foto_frontal(url):
                urls_por_color[color] = url

        if not urls_por_color:
            url = prod.get('imagenes', '')
            if url:
                urls_por_color['default'] = url

        img_list = []
        sku_key  = prod.get('sku', '') or f'prod_{i}'
        for j, (color, url) in enumerate(list(urls_por_color.items())[:2]):
            ck   = sku_key if j == 0 else f'{sku_key}_c{j}'
            path = descargar_imagen(url, ck, prod.get('nombre', ''),
                                    carpeta_cache, callback_log=log)
            img_list.append(path)

        imagenes_paths[i] = img_list if img_list else [None]

    log("📄 Generando páginas PDF...")
    prog(42)

    c = canvas.Canvas(ruta_salida, pagesize=(PAGE_W, PAGE_H))

    # Portada
    log("  📄 Portada...")
    _draw_full_bleed(c, portada_path, texto_overlay=periodo or None, cfg=cfg)
    c.showPage()
    prog(44)

    # Páginas de productos
    for i, prod in enumerate(productos):
        prog(44 + int(53 * i / max(total, 1)))
        img_list = imagenes_paths.get(i, [None])
        img_path = img_list[0] if img_list else None
        log(f"  📝 [{i+1}/{total}] {prod['nombre'][:45]}")
        _pagina_producto(c, cfg, prod, img_path, mostrar_precios,
                         i + 1, total, carpeta_assets)
        c.showPage()

    # Contraportada
    log("  📄 Contraportada...")
    _draw_full_bleed(c, contra_path)
    c.showPage()

    log("💾 Guardando PDF...")
    c.save()
    prog(100)
    return ruta_salida
