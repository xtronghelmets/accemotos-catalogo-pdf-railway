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
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
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
        'color_secundario':'#515949',
        'color_beige':     '#E5E0D8',
        'color_texto':     '#000000',
        'color_precio':    '#515949',
        'font_titulo':     'Helvetica-Bold',
        'font_cuerpo':     'Helvetica',
        'font_italic':     'Helvetica-BoldOblique',
        'nombre_display':  'XECURO',
    },
}

# Portadas y contraportadas por tipo de catálogo
ASSETS_POR_TIPO = {
    # XTRONG — nombres exactos como están en assets/xtrong/
    'abatibles_abiertos': {
        'portada':       'PORTADA ABATIBLES-ABIERTOS.png',
        'contraportada': 'CONTRAPORTADA ABATIBLES-ABIERTOS.png',
        'pagina_bg':     'PLANTILLA HOJA.png',
        'pagina_bg_pro': None,
    },
    'integrales': {
        'portada':       'PORTADA INTEGRALES.png',
        'contraportada': 'CONTRA PORTADA INTEGRALES.png',
        'pagina_bg':     'PLANTILLA HOJA.png',
        'pagina_bg_pro': None,
    },
    'textiles_accesorios': {
        'portada':       'PORTADA TEXTILES Y ACCESORIOS.png',
        'contraportada': 'CONTRA PORTADA TEXTILES Y ACCESORIOS.png',
        'pagina_bg':     'PLANTILLA HOJA.png',
        'pagina_bg_pro': None,
    },
    # XECURO — nombres exactos como están en assets/xecuro/
    'cascos': {
        'portada':       'PORTADA XECURO.png',
        'contraportada': 'CONTRAPORTADA XECURO.png',
        'pagina_bg':     'PÁGINA XECURO.png',
        'pagina_bg_pro': 'PÁGINA XECURO PRO.png',
    },
    'impermeables': {
        'portada':       'PORTADA XECURO.png',
        'contraportada': 'CONTRAPORTADA XECURO.png',
        'pagina_bg':     'PÁGINA XECURO.png',
        'pagina_bg_pro': 'PÁGINA XECURO PRO.png',
    },
    'intercomunicadores': {
        'portada':       'PORTADA XECURO.png',
        'contraportada': 'CONTRAPORTADA XECURO.png',
        'pagina_bg':     'PÁGINA XECURO.png',
        'pagina_bg_pro': 'PÁGINA XECURO PRO.png',
    },
}

# Logos de certificación
# Assets de certificación — nombres exactos del repo
CERT_ASSETS = {
    'xtrong': {
        'dot_ece': ['CERTIFICACIÓN DOT-ECE.png', 'CERTIFICACION DOT-ECE.png',
                    'CERTIFICACIÓN_DOT-ECE.png', 'CERTIFICACIÓN_DOTECE.png'],
        'dot':     ['CERTIFICACIÓN DOT.png', 'CERTIFICACION DOT.png',
                    'CERTIFICACIÓN_DOT.png'],
    },
    'xecuro': {
        'dot_ece': ['ÍCONO DOT.png', 'ICONO DOT.png', 'ÍCONO_DOT.png'],
        'dot':     ['ÍCONO DOT.png', 'ICONO DOT.png', 'ÍCONO_DOT.png'],
    },
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

    marca = cfg.get('_marca', 'xtrong')
    cert_map = CERT_ASSETS.get(marca, CERT_ASSETS['xtrong'])
    key = 'dot_ece' if (tiene_dot and tiene_ece) else 'dot'
    fnames = cert_map.get(key, [])
    cert_path = None
    for fname in fnames:
        candidate = os.path.join(carpeta_assets, fname)
        if os.path.exists(candidate):
            cert_path = candidate
            break
    if not cert_path:
        cert_path = ''

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


def _img_a_reader(img_path, timeout_seg=8):
    """Abre img_path como ImageReader en memoria (JPEG) con timeout.
    Evita que PIL o ReportLab se cuelguen con imágenes grandes."""
    if not img_path or not os.path.exists(img_path):
        return None, None, None
    result = [None]
    size   = [None]
    def _cargar():
        try:
            img = PILImage.open(img_path)
            iw, ih = img.size
            MAX = 900
            if max(iw, ih) > MAX:
                img.thumbnail((MAX, MAX), PILImage.LANCZOS)
                iw, ih = img.size
            if img.mode in ('RGBA', 'LA', 'P'):
                if img.mode == 'P':
                    img = img.convert('RGBA')
                bg = PILImage.new('RGB', img.size, (255, 255, 255))
                bg.paste(img.convert('RGB'), mask=img.split()[-1])
                img = bg
            else:
                img = img.convert('RGB')
            buf = BytesIO()
            img.save(buf, 'JPEG', quality=82)
            buf.seek(0)
            result[0] = ImageReader(buf)
            size[0] = (iw, ih)
        except Exception:
            pass
    t = threading.Thread(target=_cargar, daemon=True)
    t.start()
    t.join(timeout=timeout_seg)
    if result[0] and size[0]:
        return result[0], size[0][0], size[0][1]
    return None, None, None


def _draw_imagen(c, img_path, x, y_top, w, h_max):
    y_bottom = y_top - h_max
    if not img_path or not os.path.exists(img_path):
        c.setFillColor(HexColor('#F8F8F8'))
        c.setStrokeColor(HexColor('#E0E0E0'))
        c.setLineWidth(0.5)
        c.rect(x, y_bottom, w, h_max, fill=1, stroke=1)
        return y_bottom
    try:
        reader, iw, ih = _img_a_reader(img_path)
        if reader is None:
            return y_bottom
        ratio = iw / ih
        if ratio >= w / h_max:
            dw, dh = w, w / ratio
        else:
            dh, dw = h_max, h_max * ratio
        dx = x + (w - dw) / 2
        dy = y_bottom + (h_max - dh) / 2
        c.drawImage(reader, dx, dy, dw, dh, mask='auto')
    except Exception:
        pass
    return y_bottom


# ── Tabla de tallas/colores ───────────────────────────────────────────────────

def _draw_tabla(c, cfg, y_top, tallas_data, color_nombre='', color_hex_str=None):
    """
    tallas_data: lista de (talla, codigo, inventario)
    Filas: encabezado color (circulo+nombre) + TALLA / CÓDIGO / INVENTARIO
    Sin fila COLOR — el color se muestra solo en el encabezado verde
    """
    n = max(len(tallas_data), 1)
    COL_W   = min(68, (PAGE_W - 40) / (n + 1))
    tabla_w = COL_W * (n + 1)
    x0      = (PAGE_W - tabla_w) / 2
    y_cur   = y_top

    # Encabezado de color (solo circulo + nombre, fondo verde)
    if color_nombre:
        y_cur -= TABLA_COLOR_H
        c.setFillColor(_hx(cfg['color_principal']))
        c.roundRect(x0, y_cur, tabla_w, TABLA_COLOR_H, 4, fill=1, stroke=0)
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

def _draw_full_bleed(c, img_path_o_reader, texto_overlay=None, cfg=None):
    """Acepta ImageReader pre-cargado (rápido) o None (fallback color sólido).
    NUNCA intenta abrir un archivo PNG directamente — eso cuelga ReportLab en Vercel."""
    dibujado = False
    if isinstance(img_path_o_reader, ImageReader):
        try:
            c.drawImage(img_path_o_reader, 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False)
            dibujado = True
        except Exception:
            pass

    if not dibujado:
        # Fallback: fondo negro sólido (nunca se cuelga)
        c.setFillColor(HexColor('#111111'))
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    if texto_overlay and cfg:
        partes      = texto_overlay.split('|')
        cat_txt     = partes[0].strip() if len(partes) == 2 else ''
        periodo_txt = partes[1].strip() if len(partes) == 2 else texto_overlay.strip()
        marca       = cfg.get('_marca', 'xtrong')

        if marca == 'xtrong':
            # Solo período, en negro, en el área blanca debajo del logo (esquina superior derecha)
            if periodo_txt:
                y_periodo = PAGE_H * 0.815 + 140
                x_right   = PAGE_W - 20
                c.setFillColor(HexColor('#000000'))
                c.setFont(cfg.get('font_cuerpo', 'Helvetica'), 11)
                c.drawRightString(x_right, y_periodo, periodo_txt)
        else:
            # Comportamiento original para xecuro y otras marcas
            y_base  = PAGE_H * 0.78
            x_right = PAGE_W - 14
            c.setFillColor(_hx(cfg['color_acento']))
            if cat_txt:
                c.setFont(cfg.get('font_titulo', 'Helvetica-Bold'), 13)
                c.drawRightString(x_right, y_base, cat_txt)
                y_base -= 17
            if periodo_txt:
                c.setFont(cfg.get('font_cuerpo', 'Helvetica'), 11)
                c.drawRightString(x_right, y_base, periodo_txt)


# ── Página de producto ────────────────────────────────────────────────────────

def _es_pro(producto):
    """Detecta si un producto es de línea PRO por nombre o descripción."""
    texto = (producto.get('nombre','') + ' ' +
             producto.get('desc_corta','') + ' ' +
             producto.get('descripcion','')).lower()
    return bool(re.search(r'xecuro[\s\-]?pro', texto))


def _pagina_producto(c, cfg, producto, img_path, mostrar_precios, num, total,
                     carpeta_assets, assets_tipo=None, bg_reader=None, bg_pro_reader=None):
    # Fondo: imagen de plantilla para Xecuro, blanco para Xtrong
    # Usar reader pre-cargado si está disponible (evita releer disco en cada página)
    reader_a_usar = None
    pagina_bg = None
    if assets_tipo:
        if _es_pro(producto) and assets_tipo.get('pagina_bg_pro'):
            reader_a_usar = bg_pro_reader
            pagina_bg = os.path.join(carpeta_assets, assets_tipo['pagina_bg_pro'])
        elif assets_tipo.get('pagina_bg'):
            reader_a_usar = bg_reader
            pagina_bg = os.path.join(carpeta_assets, assets_tipo['pagina_bg'])

    if reader_a_usar:
        try:
            c.drawImage(reader_a_usar, 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False)
        except Exception:
            c.setFillColor(white)
            c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)
    else:
        # Fallback: fondo blanco — nunca intentar abrir PNG directamente (cuelga en Vercel)
        c.setFillColor(white)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    logo_path = cfg.get('_logo_path')
    # membrete eliminado — la plantilla de fondo ya incluye diseño de marca

    # Certificación DOT/ECE
    desc_txt = producto.get('desc_corta', '') + ' ' + producto.get('descripcion', '')
    tiene_dot = 'DOT' in desc_txt.upper()
    tiene_ece = 'ECE' in desc_txt.upper()
    _draw_cert(c, cfg, tiene_dot, tiene_ece, carpeta_assets)

    # Nombre + descripción
    precio = 0  # No mostrar precio en el catálogo
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
        tallas_data = []
        for v in vars_color:
            talla = v.get('talla', '') or ''
            if not talla:
                # Intentar extraer talla del nombre del producto o descripción
                import re as _re
                texto_buscar = (v.get('nombre', '') + ' ' +
                               producto.get('desc_corta', '')).upper()
                # Buscar patrones de talla: XS, S, M, L, XL, 2XL, 3XL
                m = _re.search(r'\b(3XL|2XL|XXL|XL|XS|[SML])\b', texto_buscar)
                if m:
                    talla = m.group(1)
                else:
                    talla = 'ÚNICA'
            tallas_data.append((talla, v.get('sku', '') or '-', v.get('inventario', None)))
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
    cfg['_marca'] = marca

    # Resolver carpeta de assets — buscar en múltiples rutas posibles
    base_dir = os.path.dirname(os.path.abspath(__file__))
    marca_upper = marca.upper()  # XTRONG / XECURO
    carpeta_assets_candidatos = [
        os.path.join(base_dir, 'assets', marca),         # assets/xtrong
        os.path.join(base_dir, 'assets', marca_upper),   # assets/XTRONG
        os.path.join(base_dir, '..', 'assets', marca),
        os.path.join(base_dir, '..', 'assets', marca_upper),
        os.path.join('/var/task', 'assets', marca),
        os.path.join('/var/task', 'assets', marca_upper),
    ]
    # carpeta_assets se sobreescribe abajo desde app_web, pero si llega vacía usamos detección
    _carpeta_assets_detectada = carpeta_assets
    if not os.path.isdir(_carpeta_assets_detectada):
        for c in carpeta_assets_candidatos:
            if os.path.isdir(c):
                _carpeta_assets_detectada = c
                break
    carpeta_assets = _carpeta_assets_detectada
    log(f"  📁 Assets dir: {carpeta_assets}")
    log(f"  📁 Assets existe: {os.path.isdir(carpeta_assets)}")
    if os.path.isdir(carpeta_assets):
        log(f"  📁 Archivos: {os.listdir(carpeta_assets)[:5]}")

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
    assets_tipo_dict = ASSETS_POR_TIPO.get(tipo_catalogo, {})
    portada_fname  = assets_tipo_dict.get('portada', 'PORTADA.jpg')
    contra_fname   = assets_tipo_dict.get('contraportada', 'CONTRAPORTADA.jpg')

    def _buscar_asset(carpeta, fname):
        """Busca asset probando guion bajo, espacios, sin tildes, distintas extensiones."""
        import unicodedata
        def sin_tildes(s):
            return ''.join(c for c in unicodedata.normalize('NFD', s)
                          if unicodedata.category(c) != 'Mn')
        base, ext_orig = fname.rsplit('.', 1) if '.' in fname else (fname, 'png')
        candidatos = []
        for base_v in [base, base.replace('_', ' '), sin_tildes(base), sin_tildes(base).replace('_', ' ')]:
            for ext in [ext_orig, 'png', 'jpg', 'jpeg', 'PNG', 'JPG']:
                candidatos.append(f"{base_v}.{ext}")
        # También listar carpeta y buscar por similitud
        if os.path.isdir(carpeta):
            archivos = os.listdir(carpeta)
            base_norm = sin_tildes(base.replace('_', '').replace(' ', '')).upper()
            for archivo in archivos:
                arch_norm = sin_tildes(archivo.replace('_', '').replace(' ', '')).upper()
                arch_norm = arch_norm.rsplit('.', 1)[0] if '.' in arch_norm else arch_norm
                if arch_norm == base_norm:
                    candidatos.insert(0, archivo)
        for c in candidatos:
            path = os.path.join(carpeta, c)
            if os.path.exists(path):
                return path
        return os.path.join(carpeta, fname)

    portada_path = _buscar_asset(carpeta_assets, portada_fname)
    contra_path  = _buscar_asset(carpeta_assets, contra_fname)

    def _cargar_image_reader_seguro(path, nombre, timeout_seg=8):
        """Carga ImageReader con timeout. Prefiere _opt.jpg si existe."""
        if not path or not os.path.exists(path):
            log(f"  ⚠️ No existe: {nombre} ({path})")
            return None
        # Preferir versión _opt.jpg pre-optimizada si existe (sin necesidad de PIL)
        base, _ = os.path.splitext(path)
        opt_path = base + '_opt.jpg'
        if os.path.exists(opt_path) and os.path.getsize(opt_path) > 1000:
            try:
                reader = ImageReader(opt_path)
                log(f"  ✅ {nombre} cargado (opt.jpg)")
                return reader
            except Exception:
                pass  # fallback al proceso normal
        result = [None]
        error  = [None]

        def _cargar():
            try:
                # Intentar primero con PIL para controlar el proceso
                from PIL import Image as _PIL
                from io import BytesIO
                img = _PIL.open(path)
                # Reducir resolución si es muy grande (>1500px en cualquier lado)
                w, h = img.size
                MAX = 1200
                if max(w, h) > MAX:
                    if w >= h:
                        img = img.thumbnail((MAX, int(h * MAX / w)), _PIL.LANCZOS)
                    else:
                        img = img.thumbnail((int(w * MAX / h), MAX), _PIL.LANCZOS)
                # Convertir a RGB sin alpha
                if img.mode in ('RGBA', 'LA', 'P'):
                    if img.mode == 'P':
                        img = img.convert('RGBA')
                    fondo = _PIL.new('RGB', img.size, (255, 255, 255))
                    fondo.paste(img.convert('RGB'), mask=img.split()[-1])
                    img = fondo
                else:
                    img = img.convert('RGB')
                buf = BytesIO()
                img.save(buf, 'JPEG', quality=88, optimize=True)
                buf.seek(0)
                result[0] = ImageReader(buf)
            except Exception as e:
                error[0] = str(e)

        t = threading.Thread(target=_cargar, daemon=True)
        t.start()
        t.join(timeout=timeout_seg)
        if t.is_alive():
            log(f"  ⚠️ Timeout cargando {nombre} — se usará fallback")
            return None
        if error[0]:
            log(f"  ⚠️ Error {nombre}: {error[0]}")
            return None
        log(f"  ✅ {nombre} pre-cargado")
        return result[0]

    portada_reader = _cargar_image_reader_seguro(portada_path, "Portada")
    contra_reader  = _cargar_image_reader_seguro(contra_path,  "Contraportada")

    # Pre-cargar fondos de página en memoria (se reusan en cada producto)
    bg_fname     = assets_tipo_dict.get('pagina_bg')
    bg_pro_fname = assets_tipo_dict.get('pagina_bg_pro')
    bg_reader     = None
    bg_pro_reader = None
    if bg_fname:
        bg_path   = _buscar_asset(carpeta_assets, bg_fname)
        bg_reader = _cargar_image_reader_seguro(bg_path, f"Fondo página ({bg_fname})")
    if bg_pro_fname:
        bg_pro_path   = _buscar_asset(carpeta_assets, bg_pro_fname)
        bg_pro_reader = _cargar_image_reader_seguro(bg_pro_path, f"Fondo PRO ({bg_pro_fname})")

    assets_tipo = assets_tipo_dict
    log(f"  📄 Portada: {portada_fname}")
    log(f"  📄 Contraportada: {contra_fname}")

    # Resolver imágenes — paralelo con hasta 8 workers
    log("🖼️ Descargando imágenes en paralelo...")
    total = len(productos)

    # Primero construir el mapa de tareas: {i: [(ck, url), ...]}
    tareas = {}
    for i, prod in enumerate(productos):
        variaciones = prod.get('variaciones', [])
        sku_key = prod.get('sku', '') or f'prod_{i}'
        skus_por_color = {}
        for vi, v in enumerate(variaciones):
            color = v.get('color', 'default') or 'default'
            url   = v.get('imagenes', '')
            vsku  = v.get('sku', '') or f'{sku_key}_v{vi}'
            if color not in skus_por_color:
                skus_por_color[color] = (vsku, url)
            elif _es_foto_frontal(skus_por_color[color][1]) and not _es_foto_frontal(url):
                skus_por_color[color] = (vsku, url)
        if not skus_por_color:
            skus_por_color['default'] = (sku_key, prod.get('imagenes', ''))
        tareas[i] = list(skus_por_color.items())[:2]  # máx 2 colores por producto

    # Función que resuelve UNA imagen (caché o descarga)
    def _resolver(i, j, color, vsku, url):
        ck = vsku if j == 0 else f'{vsku}_c{j}'
        cache_jpg = os.path.join(carpeta_cache, f'{ck}.jpg')
        if os.path.exists(cache_jpg) and os.path.getsize(cache_jpg) > 1000:
            return (i, j, cache_jpg)
        if url:
            path = descargar_imagen(url, ck, productos[i].get('nombre', ''),
                                    carpeta_cache, callback_log=log)
            return (i, j, path)
        return (i, j, None)

    # Lanzar todas en paralelo
    imagenes_paths = {i: [None] for i in range(total)}
    futures = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        for i, items in tareas.items():
            for j, (color, (vsku, url)) in enumerate(items):
                futures.append(executor.submit(_resolver, i, j, color, vsku, url))
        for fut in as_completed(futures):
            try:
                i, j, path = fut.result()
                if j == 0:
                    imagenes_paths[i] = [path]
                else:
                    imagenes_paths[i].append(path)
            except Exception:
                pass

    log(f"🖼️ Imágenes resueltas: {sum(1 for v in imagenes_paths.values() if v[0])} / {total}")

    log("📄 Generando páginas PDF...")
    prog(42)

    c = canvas.Canvas(ruta_salida, pagesize=(PAGE_W, PAGE_H))

    # Portada
    log("  📄 Portada...")
    overlay_portada = None
    if tipo_catalogo or periodo:
        partes_overlay = []
        if tipo_catalogo:
            partes_overlay.append(tipo_catalogo.upper())
        if periodo:
            partes_overlay.append(periodo)
        overlay_portada = '|'.join(partes_overlay)
    _draw_full_bleed(c, portada_reader or portada_path, texto_overlay=overlay_portada, cfg=cfg)
    c.showPage()
    prog(44)

    # Páginas de productos
    for i, prod in enumerate(productos):
        prog(44 + int(53 * i / max(total, 1)))
        img_list = imagenes_paths.get(i, [None])
        img_path = img_list[0] if img_list else None
        log(f"  📝 [{i+1}/{total}] {prod['nombre'][:45]}")
        _pagina_producto(c, cfg, prod, img_path, mostrar_precios,
                         i + 1, total, carpeta_assets, assets_tipo=assets_tipo,
                         bg_reader=bg_reader, bg_pro_reader=bg_pro_reader)
        c.showPage()

    # Contraportada
    log("  📄 Contraportada...")
    _draw_full_bleed(c, contra_reader or contra_path)
    c.showPage()

    log("💾 Guardando PDF...")
    c.save()
    prog(100)
    return ruta_salida
