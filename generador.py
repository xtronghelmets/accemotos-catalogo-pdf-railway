import os
from datetime import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.colors import HexColor, white, black
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image as PILImage
from io import BytesIO

from lector_excel import color_hex
from descargador import descargar_imagen

# ── Dimensiones y colores ───────────────────────────────────────────────────
PAGE_W, PAGE_H = 595, 1060

COLOR_VERDE  = HexColor('#0D4A3C')
COLOR_LIMA   = HexColor('#C8FF00')
COLOR_BLANCO = white
COLOR_NEGRO  = black
COLOR_GRIS   = HexColor('#DDDDDD')
COLOR_GRIS_MED = HexColor('#BBBBBB')
COLOR_PRECIO = HexColor('#555555')
COLOR_NUM    = HexColor('#888888')
COLOR_FONDO_CODIGO = HexColor('#F0F0F0')

HEADER_H = 50   # altura del header en pt
_logo_path = None  # se establece en generar_catalogo


# ── Utilidades de dibujo ────────────────────────────────────────────────────

def _rgb_from_hex(hex_str):
    h = hex_str.lstrip('#')
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return r/255, g/255, b/255


def draw_header(c, categoria, tiene_ce=False):
    """Header compacto 50pt: verde izquierda + polígono blanco con logo + categoría."""
    y_bottom = PAGE_H - HEADER_H   # 1010 con HEADER_H=50

    # Fondo verde completo
    c.setFillColor(COLOR_VERDE)
    c.rect(0, y_bottom, PAGE_W, HEADER_H, fill=1, stroke=0)

    # Polígono blanco en la derecha (ancho ~180pt)
    px_top = PAGE_W - 180
    px_bot = PAGE_W - 195
    c.setFillColor(COLOR_BLANCO)
    p = c.beginPath()
    p.moveTo(px_top, PAGE_H)
    p.lineTo(PAGE_W, PAGE_H)
    p.lineTo(PAGE_W, y_bottom)
    p.lineTo(px_bot, y_bottom)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    # Línea lima en borde inferior del polígono
    c.setStrokeColor(COLOR_LIMA)
    c.setLineWidth(2)
    c.line(px_bot, y_bottom, PAGE_W, y_bottom)

    # Logo: imagen PNG si existe, si no texto
    logo_area_x = px_top + 6
    logo_area_w = PAGE_W - logo_area_x - 6
    logo_area_h = HEADER_H - 8
    logo_y = y_bottom + 4

    if _logo_path and os.path.exists(_logo_path):
        try:
            from reportlab.lib.utils import ImageReader
            logo_img = ImageReader(_logo_path)
            iw, ih = logo_img.getSize()
            ratio = iw / ih
            draw_h = logo_area_h
            draw_w = draw_h * ratio
            if draw_w > logo_area_w:
                draw_w = logo_area_w
                draw_h = draw_w / ratio
            logo_x = logo_area_x + (logo_area_w - draw_w) / 2
            logo_dy = logo_y + (logo_area_h - draw_h) / 2
            c.drawImage(_logo_path, logo_x, logo_dy, draw_w, draw_h,
                        mask='auto', preserveAspectRatio=False)
        except Exception:
            _draw_xtrong_logo_compacto(c, logo_area_x, PAGE_H - 4, PAGE_W - 6)
    else:
        _draw_xtrong_logo_compacto(c, logo_area_x, PAGE_H - 4, PAGE_W - 6)

    # Badge CE pequeño (dentro del polígono blanco)
    if tiene_ce:
        c.setFillColor(COLOR_VERDE)
        c.setFont('Helvetica-Bold', 14)
        c.drawRightString(PAGE_W - 8, y_bottom + 6, 'CE')

    # Categoría en la zona verde (izquierda)
    cat_text = categoria.title() if categoria.isupper() else categoria
    c.setFillColor(COLOR_BLANCO)
    c.setFont('Helvetica-BoldOblique', 16)
    c.drawString(16, y_bottom + 16, cat_text)


def _draw_xtrong_logo_compacto(c, x_left, y_top, x_right):
    """Logo de texto compacto para header de 50pt."""
    x_right_margin = x_right - 6
    y_xtrong = y_top - 18
    y_gear = y_xtrong - 13

    c.setFillColor(COLOR_VERDE)
    c.setFont('Helvetica-Bold', 15)
    c.drawRightString(x_right_margin, y_xtrong, 'XTRONG')
    c.setFont('Helvetica-Bold', 8)
    c.drawRightString(x_right_margin, y_gear, 'HELMETS & GEAR')


def draw_nombre_zona(c, nombre, genero_spec='', precio=None, mostrar_precio=False,
                     codigo=None, mostrar_codigo_aqui=False):
    """Zona nombre: NOMBRE (negro) → PRECIO → especificación género."""
    y_base = PAGE_H - HEADER_H - 12

    # Línea 1: nombre del modelo
    nombre_limpio = nombre.strip()
    font_size = 28 if len(nombre_limpio) < 20 else (22 if len(nombre_limpio) < 30 else 17)
    c.setFillColor(COLOR_NEGRO)
    c.setFont('Helvetica-Bold', font_size)
    c.drawString(16, y_base - font_size, nombre_limpio)

    y_cur = y_base - font_size - 4

    # Línea 2: precio (inmediatamente bajo el título)
    if mostrar_precio and precio and precio > 0:
        try:
            precio_fmt = f"${int(float(str(precio))):,}".replace(',', '.')
        except Exception:
            precio_fmt = ''
        if precio_fmt:
            c.setFillColor(COLOR_PRECIO)
            c.setFont('Helvetica-Bold', 13)
            c.drawString(16, y_cur - 13, precio_fmt)
            y_cur -= 22

    # Línea 3: especificación género/uso
    if genero_spec:
        c.setFillColor(HexColor('#444444'))
        c.setFont('Helvetica-Bold', 12)
        c.drawString(16, y_cur - 12, genero_spec)
        y_cur -= 20

    if mostrar_codigo_aqui and codigo:
        _draw_codigo_top_right(c, codigo)

    return y_cur - 6


def _draw_codigo_top_right(c, codigo):
    """Dibuja el bloque CÓDIGO en la esquina superior derecha del área de nombre."""
    # Caja verde oscuro con código blanco, alineada a la derecha
    box_w = 85
    box_h = 24
    x = PAGE_W - box_w - 16
    y_label = PAGE_H - HEADER_H - 26
    y_box = y_label - box_h - 3

    c.setFillColor(COLOR_NEGRO)
    c.setFont('Helvetica-Bold', 10)
    c.drawRightString(PAGE_W - 16, y_label, 'CODIGO')

    c.setFillColor(COLOR_VERDE)
    c.roundRect(x, y_box, box_w, box_h, 4, fill=1, stroke=0)
    c.setFillColor(COLOR_BLANCO)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(x + box_w / 2, y_box + 7, str(codigo))


def draw_imagen(c, img_path, x, y_top, w, h_max):
    """Dibuja la imagen centrada manteniendo aspect ratio. Devuelve y_bottom."""
    y_bottom = y_top - h_max
    if not img_path or not os.path.exists(img_path):
        c.setFillColor(HexColor('#F4F4F4'))
        c.setStrokeColor(COLOR_GRIS_MED)
        c.setLineWidth(0.5)
        c.rect(x, y_bottom, w, h_max, fill=1, stroke=1)
        return y_bottom

    try:
        img = PILImage.open(img_path)
        img_w, img_h = img.size
        ratio = img_w / img_h

        # Calcular dimensiones manteniendo aspect ratio dentro del área disponible
        if ratio >= (w / h_max):
            draw_w = w
            draw_h = w / ratio
        else:
            draw_h = h_max
            draw_w = h_max * ratio

        # Centrar en el área disponible
        draw_x = x + (w - draw_w) / 2
        draw_y = y_bottom + (h_max - draw_h) / 2

        # Usar mask='auto' para PNGs con transparencia, sin preserveAspectRatio
        # (ya calculamos las dimensiones manualmente)
        ext = os.path.splitext(img_path)[1].lower()
        if ext == '.png':
            c.drawImage(img_path, draw_x, draw_y, draw_w, draw_h, mask='auto')
        else:
            c.drawImage(img_path, draw_x, draw_y, draw_w, draw_h)
        return y_bottom
    except Exception as e:
        return y_bottom


TABLA_ROW_H = 24          # altura de cada fila de datos
TABLA_HEADER_H = 22       # altura del encabezado de color (círculo + nombre)
TABLA_H_POR_GRUPO = TABLA_ROW_H * 3 + TABLA_HEADER_H  # total por grupo: 94pt


def draw_tabla_tallas(c, y_top, talla_label, tallas_codigos,
                      color_hex_str=None, color_label=''):
    """
    Dibuja tabla TALLA / CÓDIGO / INVENTARIO con encabezado de color.
    tallas_codigos: lista de (talla, codigo, inventario)
    """
    if not tallas_codigos:
        return y_top

    label_w = 110
    n = len(tallas_codigos)
    col_w = min(68, (PAGE_W - label_w - 44) // max(n, 1))
    tabla_w = label_w + col_w * n
    x_start = (PAGE_W - tabla_w) / 2
    rh = TABLA_ROW_H

    # ── Encabezado de color (círculo + nombre) ────────────────────────────
    y_header = y_top - TABLA_HEADER_H
    c.setFillColor(HexColor('#EFEFEF'))
    c.setStrokeColor(HexColor('#CCCCCC'))
    c.setLineWidth(0.5)
    c.roundRect(x_start, y_header, tabla_w, TABLA_HEADER_H, 3, fill=1, stroke=1)

    cy_mid = y_header + TABLA_HEADER_H / 2
    cx_circle = x_start + 14

    # Círculo del color
    if color_hex_str:
        r, g, b = _rgb_from_hex(color_hex_str)
        from reportlab.lib.colors import Color
        c.setFillColor(Color(r, g, b, 1))
        c.setStrokeColor(HexColor('#777777'))
        c.setLineWidth(0.5)
        c.circle(cx_circle, cy_mid, 8, fill=1, stroke=1)

    # Texto del color a la derecha del círculo
    if color_label:
        c.setFillColor(HexColor('#222222'))
        c.setFont('Helvetica-Bold', 9)
        c.drawString(cx_circle + 13, cy_mid - 4, color_label.upper())

    # Las 3 filas de datos empiezan debajo del encabezado
    y1 = y_header - rh          # fila TALLA
    y2 = y_header - rh * 2      # fila CÓDIGO
    y3 = y_header - rh * 3      # fila INVENTARIO

    COLOR_INV_LABEL = HexColor('#1E6B55')
    COLOR_INV_FONDO = HexColor('#EEF7F3')

    # ── Etiquetas columna izquierda ──────────────────────────────────────
    for yy, txt, bg in [(y1, talla_label.upper(), COLOR_VERDE),
                         (y2, 'CÓDIGO', COLOR_VERDE),
                         (y3, 'INVENTARIO', COLOR_INV_LABEL)]:
        c.setFillColor(bg)
        c.rect(x_start, yy, label_w, rh, fill=1, stroke=0)
        c.setFillColor(COLOR_BLANCO)
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(x_start + label_w / 2, yy + 7, txt)

    # ── Columnas de datos ────────────────────────────────────────────────
    for idx, entry in enumerate(tallas_codigos):
        talla = entry[0]
        codigo = entry[1] if len(entry) > 1 else ''
        inventario = entry[2] if len(entry) > 2 else None
        cx = x_start + label_w + idx * col_w

        # Fila TALLA — verde oscuro
        c.setFillColor(COLOR_VERDE)
        c.setStrokeColor(COLOR_BLANCO)
        c.setLineWidth(0.5)
        c.rect(cx, y1, col_w, rh, fill=1, stroke=1)
        c.setFillColor(COLOR_BLANCO)
        c.setFont('Helvetica-Bold', 11)
        c.drawCentredString(cx + col_w / 2, y1 + 7, str(talla))

        # Fila CÓDIGO — blanco con borde verde
        c.setFillColor(COLOR_BLANCO)
        c.setStrokeColor(COLOR_VERDE)
        c.setLineWidth(0.8)
        c.rect(cx, y2, col_w, rh, fill=1, stroke=1)
        c.setFillColor(COLOR_NEGRO)
        c.setFont('Helvetica-Bold', 9)
        c.drawCentredString(cx + col_w / 2, y2 + 7, str(codigo) if codigo else '-')

        # Fila INVENTARIO — fondo verde muy claro
        c.setFillColor(COLOR_INV_FONDO)
        c.setStrokeColor(HexColor('#AACCBB'))
        c.setLineWidth(0.5)
        c.rect(cx, y3, col_w, rh, fill=1, stroke=1)
        c.setFillColor(HexColor('#1A5040'))
        c.setFont('Helvetica-Bold', 10)
        inv_txt = str(inventario) if inventario is not None else '-'
        c.drawCentredString(cx + col_w / 2, y3 + 7, inv_txt)

    return y3


def draw_codigo_banda(c, codigo):
    """Dibuja la banda CÓDIGO al fondo de la página (para productos simples)."""
    y = 70
    band_h = 36
    c.setFillColor(COLOR_FONDO_CODIGO)
    c.rect(0, y, PAGE_W, band_h, fill=1, stroke=0)

    # Label CÓDIGO
    c.setFillColor(COLOR_NEGRO)
    c.setFont('Helvetica-Bold', 13)
    label_w = c.stringWidth('CÓDIGO', 'Helvetica-Bold', 13)
    x_label = PAGE_W / 2 - 60
    c.drawString(x_label, y + 11, 'CÓDIGO')

    # Caja verde con SKU
    box_x = x_label + label_w + 12
    box_w = 80
    c.setFillColor(COLOR_VERDE)
    c.roundRect(box_x, y + 4, box_w, 28, 4, fill=1, stroke=0)
    c.setFillColor(COLOR_BLANCO)
    c.setFont('Helvetica-Bold', 13)
    c.drawCentredString(box_x + box_w / 2, y + 10, str(codigo))


def draw_incluye_banner(c, y_top, texto_items):
    """Dibuja el banner INCLUYE + items en grid."""
    banner_h = 28
    y_banner = y_top - banner_h

    # Franja lima
    c.setFillColor(COLOR_LIMA)
    c.rect(0, y_banner, PAGE_W, banner_h, fill=1, stroke=0)

    # Triángulo decorativo izquierdo
    c.setFillColor(HexColor('#AADD00'))
    p = c.beginPath()
    p.moveTo(0, y_banner)
    p.lineTo(18, y_banner + banner_h / 2)
    p.lineTo(0, y_banner + banner_h)
    p.close()
    c.drawPath(p, fill=1, stroke=0)

    c.setFillColor(COLOR_NEGRO)
    c.setFont('Helvetica-Bold', 14)
    c.drawCentredString(PAGE_W / 2, y_banner + 7, 'INCLUYE')

    return y_banner


def draw_bullets_dos_columnas(c, bullets, y_top, y_min):
    """Dibuja lista de bullets en dos columnas."""
    if not bullets:
        return y_top

    mitad = (len(bullets) + 1) // 2
    col1 = bullets[:mitad]
    col2 = bullets[mitad:]

    col_w = (PAGE_W - 40) / 2
    x1 = 20
    x2 = 20 + col_w

    # Cajas con borde
    filas = max(len(col1), len(col2))
    h_box = filas * 18 + 16
    y_box = y_top - h_box

    if y_box < y_min:
        y_box = y_min
        h_box = y_top - y_min

    c.setFillColor(HexColor('#FAFAFA'))
    c.setStrokeColor(HexColor('#CCCCCC'))
    c.setLineWidth(0.8)
    c.roundRect(x1, y_box, col_w - 5, h_box, 4, fill=1, stroke=1)
    c.roundRect(x2, y_box, col_w - 5, h_box, 4, fill=1, stroke=1)

    def draw_col(items, x, y_start):
        yy = y_start - 18
        for item in items:
            c.setFillColor(COLOR_VERDE)
            c.circle(x + 10, yy + 4, 3, fill=1, stroke=0)
            c.setFillColor(COLOR_NEGRO)
            c.setFont('Helvetica', 10)
            max_chars = int(col_w / 6)
            texto = item[:max_chars] + ('…' if len(item) > max_chars else '')
            c.drawString(x + 18, yy, texto)
            yy -= 18

    draw_col(col1, x1 + 4, y_top - 8)
    draw_col(col2, x2 + 4, y_top - 8)

    return y_box


def draw_numero_pagina(c, num, total):
    c.setFillColor(COLOR_NUM)
    c.setFont('Helvetica', 9)
    c.drawCentredString(PAGE_W / 2, 18, f'{num} / {total}')


def draw_full_bleed(c, img_path, periodo=''):
    """Dibuja imagen full-bleed (portada/contraportada).
    Si se pasa periodo, lo superpone en la portada en blanco."""
    if img_path and os.path.exists(img_path):
        c.drawImage(img_path, 0, 0, PAGE_W, PAGE_H, preserveAspectRatio=False)
    else:
        c.setFillColor(COLOR_VERDE)
        c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    # Texto del período superpuesto (solo en portada)
    if periodo:
        x_per = PAGE_W  - (PAGE_W  - 459) * 0.75   # ≈ 493
        y_per = 854     + (PAGE_H  - 854) * 0.15   # ≈ 885
        c.setFillColor(COLOR_BLANCO)
        c.setFont('Helvetica-BoldOblique', 15)
        c.drawRightString(x_per, y_per, periodo)


# ── Agrupación de variaciones para tablas ──────────────────────────────────

def agrupar_variaciones(variaciones):
    """
    Devuelve lista de grupos: {'genero': str, 'color': str, 'color_hex': str,
                                'tallas_codigos': [(talla, sku), ...]}
    """
    from collections import OrderedDict
    grupos = OrderedDict()
    for v in variaciones:
        g = v.get('genero', '')
        color = v.get('color', '')
        key = (g, color)
        if key not in grupos:
            grupos[key] = {'genero': g, 'color': color,
                           'color_hex': color_hex(color) if color else None,
                           'tallas_codigos': []}
        talla_val = v.get('talla') or '-'
        grupos[key]['tallas_codigos'].append(
            (talla_val, v.get('sku', ''), v.get('inventario', None))
        )
    return list(grupos.values())


def calcular_label_talla(genero, color):
    """Genera el label de la primera fila de la tabla."""
    if genero == 'Hombre':
        return 'TALLA HOMBRE'
    if genero == 'Mujer':
        return 'TALLA MUJER'
    if genero == 'Unisex':
        return 'TALLA UNISEX'
    return 'TALLA'


# ── Página de producto ─────────────────────────────────────────────────────

def pagina_variable_tallas(c, producto, img_paths, mostrar_precios, num, total):
    """Página producto variable: header + nombre/género + 2 imágenes + tabla 3 filas."""
    c.setFillColor(COLOR_BLANCO)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    draw_header(c, producto['categoria'], tiene_ce=producto.get('ce', False))

    generos = producto.get('generos', set())
    if 'Hombre' in generos and 'Mujer' in generos:
        genero_spec = 'Hombre – Mujer'
    elif 'Hombre' in generos:
        genero_spec = 'Hombre'
    elif 'Mujer' in generos:
        genero_spec = 'Mujer'
    else:
        genero_spec = ''

    precio = producto.get('precio', 0) if mostrar_precios else 0
    y_nombre_bottom = draw_nombre_zona(
        c, producto['nombre'],
        genero_spec=genero_spec,
        precio=precio, mostrar_precio=mostrar_precios,
    )

    grupos = agrupar_variaciones(producto.get('variaciones', []))
    if not grupos:
        avail = y_nombre_bottom - 10 - 60
        img_h = max(50, avail * 0.8)
        img1 = img_paths[0] if img_paths else None
        draw_imagen(c, img1, 20, y_nombre_bottom - 10, PAGE_W - 40, img_h)
        draw_codigo_banda(c, producto.get('sku', ''))
        draw_numero_pagina(c, num, total)
        return

    # ── Calcular zonas ────────────────────────────────────────────────────
    SEP = 8
    n = len(grupos)
    total_tablas_h = n * TABLA_H_POR_GRUPO + max(0, n - 1) * SEP

    BOTTOM_MARGIN = 55
    GAP_IMG_TABLA = 14

    y_img_top = y_nombre_bottom - 10
    available = y_img_top - total_tablas_h - GAP_IMG_TABLA - BOTTOM_MARGIN
    img_h = max(60, available * 0.8)

    # ── Dibujar 1 o 2 imágenes lado a lado ───────────────────────────────
    img1 = img_paths[0] if len(img_paths) > 0 else None
    img2 = img_paths[1] if len(img_paths) > 1 else None

    if img2:
        img_w = (PAGE_W - 44) / 2   # dos imágenes con gap de 4pt
        draw_imagen(c, img1, 20, y_img_top, img_w, img_h)
        draw_imagen(c, img2, 20 + img_w + 4, y_img_top, img_w, img_h)
    else:
        draw_imagen(c, img1, 20, y_img_top, PAGE_W - 40, img_h)

    # ── Tabla directamente debajo de las imágenes ─────────────────────────
    y_tabla_top = y_img_top - img_h - GAP_IMG_TABLA
    y_cur = y_tabla_top
    for grupo in grupos:
        label = calcular_label_talla(grupo['genero'], grupo['color'])
        draw_tabla_tallas(c, y_cur, label,
                          grupo['tallas_codigos'],
                          color_hex_str=grupo['color_hex'] if grupo['color'] else None,
                          color_label=grupo['color'])
        y_cur -= (TABLA_H_POR_GRUPO + SEP)

    draw_numero_pagina(c, num, total)


def pagina_simple(c, producto, img_path, mostrar_precios, num, total):
    """Página para productos simples (un SKU)."""
    c.setFillColor(COLOR_BLANCO)
    c.rect(0, 0, PAGE_W, PAGE_H, fill=1, stroke=0)

    draw_header(c, producto['categoria'], tiene_ce=producto.get('ce', False))

    tiene_incluye = producto.get('tiene_incluye', False)
    bullets = producto.get('bullets', [])
    tiene_bullets = len(bullets) > 0

    precio = producto.get('precio', 0) if mostrar_precios else 0
    sku = producto.get('sku', '')

    genero_spec = producto.get('genero', '') or ''
    y_nombre_bottom = draw_nombre_zona(
        c, producto['nombre'],
        genero_spec=genero_spec,
        precio=precio, mostrar_precio=mostrar_precios,
        codigo=sku, mostrar_codigo_aqui=True,
    )

    y_img_top = y_nombre_bottom - 8

    # ── Tabla CÓDIGO / INVENTARIO siempre al fondo ──────────────────────────
    color_p = producto.get('color', '') or ''
    inv_p = producto.get('inventario', None)
    talla_label_simple = 'COLOR' if color_p else 'TALLA'
    tallas_data_simple = [(color_p or '-', sku, inv_p)]
    # y_top de la tabla: TABLA_H_POR_GRUPO pts arriba del número de página
    TABLE_TOP = TABLA_H_POR_GRUPO + 35   # ≈107 pt desde el fondo

    if tiene_incluye or tiene_bullets:
        BULLETS_FILA_H = 18
        n_filas = max((len(bullets) + 1) // 2, 1) if tiene_bullets else 0
        bullets_h = n_filas * BULLETS_FILA_H + 24 if tiene_bullets else 0
        banner_h = 30 if tiene_incluye else 0

        # Los bullets se colocan entre TABLE_TOP y la imagen
        y_bottom_content = TABLE_TOP + 8
        y_bullets_top = y_bottom_content + bullets_h
        y_banner_top = y_bullets_top + (4 if tiene_bullets else 0)
        y_image_bottom = y_banner_top + banner_h + 10

        avail = y_img_top - y_image_bottom
        img_h = max(60, avail * 0.8)
        draw_imagen(c, img_path, 20, y_img_top, PAGE_W - 40, img_h)

        if tiene_incluye:
            draw_incluye_banner(c, y_banner_top + banner_h, bullets)
        if tiene_bullets:
            draw_bullets_dos_columnas(c, bullets, y_bullets_top, y_bottom_content)

    else:
        # Layout limpio: imagen arriba de la tabla
        avail = y_img_top - TABLE_TOP - 8
        img_h = max(60, avail * 0.8)
        draw_imagen(c, img_path, 20, y_img_top, PAGE_W - 40, img_h)

    draw_tabla_tallas(c, TABLE_TOP, talla_label_simple, tallas_data_simple,
                      color_hex_str=color_hex(color_p) if color_p else None,
                      color_label=color_p)
    draw_numero_pagina(c, num, total)


# ── Generador principal ────────────────────────────────────────────────────

def generar_catalogo(
    carpeta_proyecto,
    ruta_excel,
    periodo,
    categorias_filtro,
    mostrar_precios,
    callback_progreso,
    callback_log,
):
    from lector_excel import leer_excel

    callback_log("📖 Leyendo archivo Excel...")
    callback_progreso(2)

    productos = leer_excel(ruta_excel, categorias_filtro)
    total = len(productos)
    callback_log(f"✅ {total} productos encontrados")
    callback_progreso(5)

    if total == 0:
        raise ValueError("No se encontraron productos con los filtros seleccionados.")

    # Buscar logo PNG en la carpeta del proyecto
    global _logo_path
    _logo_path = None
    for fname in ('logo.png', 'logo_xtrong.png', 'LOGO.png', 'Logo.png'):
        candidate = os.path.join(carpeta_proyecto, fname)
        if os.path.exists(candidate):
            _logo_path = candidate
            callback_log(f"  🖼️ Logo encontrado: {fname}")
            break

    carpeta_cache = os.path.join(carpeta_proyecto, 'cache_imagenes')
    os.makedirs(carpeta_cache, exist_ok=True)

    # Descargar imágenes
    callback_log("🖼️ Descargando imágenes...")
    imagenes_paths = {}
    for i, producto in enumerate(productos):
        nombre = producto.get('nombre', '')
        sku_raw = producto.get('sku', '')

        # Cache key estable basado en nombre (no en índice del filtro actual)
        # para evitar colisiones de caché entre runs con distintos filtros
        if not sku_raw or sku_raw.lower() in ('nan', 'none', '0', ''):
            nombre_hash = __import__('hashlib').md5(
                nombre.encode('utf-8', errors='replace')).hexdigest()[:10]
            cache_key = f'p_{nombre_hash}'
        else:
            cache_key = sku_raw

        # Recopilar hasta 2 URLs distintas (una por color de variación)
        group_urls = []
        seen_colors = set()
        for v in producto.get('variaciones', []):
            color = v.get('color', '') or 'default'
            v_url = v.get('imagenes', '')
            if v_url and v_url not in ('nan', 'None', '') and color not in seen_colors:
                seen_colors.add(color)
                group_urls.append(v_url)
                if len(group_urls) >= 2:
                    break

        # Si no hay imágenes de variación, usar la del producto padre
        if not group_urls:
            parent_url = str(producto.get('imagenes', ''))
            if parent_url and parent_url not in ('nan', 'None', ''):
                group_urls.append(parent_url)

        img_list = []
        for j, url in enumerate(group_urls):
            ck = cache_key if j == 0 else f'{cache_key}_v{j}'
            suffix = ' (var2)' if j > 0 else ''
            callback_log(f"  🖼️ [{i+1}/{total}]{suffix} {nombre[:40]}")
            path = descargar_imagen(url, ck, nombre, carpeta_cache,
                                    callback_log=callback_log)
            img_list.append(path)

        if not img_list:
            callback_log(f"  ⚠️ [{i+1}/{total}] Sin imágenes: {nombre[:40]}")
            img_list.append(None)

        imagenes_paths[i] = img_list
        callback_progreso(5 + int(65 * (i + 1) / total))

    callback_log("📄 Generando páginas del PDF...")
    callback_progreso(70)

    ahora = datetime.now()
    nombre_archivo = f"catalogo_xtrong_{ahora.strftime('%Y-%m-%d_%I-%M%p')}.pdf"

    # Guardar en "📌Catalogo generado" dentro del directorio padre del proyecto
    carpeta_salida = os.path.join(os.path.dirname(carpeta_proyecto), '📌Catalogo generado')
    os.makedirs(carpeta_salida, exist_ok=True)
    ruta_salida = os.path.join(carpeta_salida, nombre_archivo)

    portada_path = os.path.join(carpeta_proyecto, 'PORTADA.jpg')
    contra_path = os.path.join(carpeta_proyecto, 'CONTRAPORTADA.jpg')

    # También buscar en subcarpeta de imágenes de referencia
    if not os.path.exists(portada_path):
        alt = os.path.join(carpeta_proyecto, 'catalogo paginas separadas JPEG', 'PORTADA.jpg')
        if os.path.exists(alt):
            portada_path = alt
    if not os.path.exists(contra_path):
        alt = os.path.join(carpeta_proyecto, 'catalogo paginas separadas JPEG', 'CONTRAPORTADA.jpg')
        if os.path.exists(alt):
            contra_path = alt

    c = canvas.Canvas(ruta_salida, pagesize=(PAGE_W, PAGE_H))

    # Portada
    callback_log("  📄 Portada...")
    draw_full_bleed(c, portada_path, periodo=periodo)
    c.showPage()
    callback_progreso(72)

    # Páginas de productos
    for i, producto in enumerate(productos):
        img_list = imagenes_paths.get(i, [None])
        num_pagina = i + 1

        callback_log(f"  📝 [{num_pagina}/{total}] {producto['nombre'][:45]}")

        if producto['tipo'] == 'variable':
            pagina_variable_tallas(c, producto, img_list, mostrar_precios,
                                   num_pagina, total)
        else:
            img_path = img_list[0] if img_list else None
            pagina_simple(c, producto, img_path, mostrar_precios,
                          num_pagina, total)

        c.showPage()
        callback_progreso(72 + int(23 * (i + 1) / total))

    # Contraportada
    callback_log("  📄 Contraportada...")
    draw_full_bleed(c, contra_path)
    c.showPage()
    callback_progreso(98)

    callback_log("💾 Guardando PDF...")
    c.save()
    callback_progreso(100)
    callback_log(f"✅ PDF guardado: {nombre_archivo}")

    return ruta_salida
