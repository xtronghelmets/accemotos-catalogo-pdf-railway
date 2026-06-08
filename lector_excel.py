import hashlib
import math
import pandas as pd
import re

TALLAS_SUFIJOS = ['4XL', '3XL', '2XL', 'XL', 'XS', 'S', 'M', 'L']
COLORES_SUFIJOS = ['NEGRO', 'GRIS', 'AZUL', 'ROSADO', 'ROJO', 'BLANCO',
                   'NARANJA', 'MORADO', 'VERDE', 'AMARILLO', 'CAMUFLADO',
                   'CAFE', 'BEIGE', 'PLATEADO', 'DORADO',
                   # Colores de visor / lente
                   'HUMO', 'TRANSPARENTE', 'IRIDIUM', 'CROMADO',
                   'OCRE', 'OSCURO', 'VIOLETA']
GENERO_SUFIJOS = ['DAMA', 'MUJER', 'HOMBRE', 'CABALLERO']

# Palabras de marca/specs que no aportan al nombre corto
MARCA_SPECS = ['XTRONG', 'BRILLO', 'MATE', 'SP', 'VISOR', 'LENTE',
               'NEON', 'UNISEX',
               # Tratamientos ópticos de visor (no son nombres de diseño)
               'FOTO', 'REVO']

COLOR_MAP = {
    'NEGRO': '#111111', 'GRIS': '#888888', 'AZUL': '#0055CC',
    'ROSADO': '#FF69B4', 'ROJO': '#DD0000', 'BLANCO': '#EEEEEE',
    'NARANJA': '#FF8800', 'MORADO': '#7700AA', 'VERDE': '#006600',
    'VERDE NEON': '#00CC00', 'AMARILLO': '#DDCC00', 'CAFE': '#6B3A2A',
    'BEIGE': '#C8A87C', 'PLATEADO': '#AAAAAA', 'DORADO': '#CC9900',
    'CAMUFLADO': '#556B2F',
}


def _get_strip_set():
    return set(COLORES_SUFIJOS + GENERO_SUFIJOS + MARCA_SPECS)

def _es_descartable(token):
    """Token compuesto de colores (NEGRO-ROJO) o cert. (ECE-2206, ECE-2205)."""
    strip = _get_strip_set()
    if token in strip:
        return True
    # Certificaciones ECE-XXXX o DOT
    if re.match(r'^ECE-\d+$', token) or token == 'DOT':
        return True
    # Variantes de marca: XTRONG-GP, XTRONG-PRO, etc.
    if token.startswith('XTRONG'):
        return True
    # Colores/specs compuestos con guión: NEGRO-ROJO, REVO-AZUL, FOTO-MORADO
    partes = token.split('-')
    if len(partes) >= 2 and all(p in strip for p in partes):
        return True
    return False

def limpiar_nombre(nombre):
    if not isinstance(nombre, str):
        return str(nombre)
    # Eliminar contenido entre paréntesis (ej: "(VISOR ADICIONAL PLATEADO)")
    nombre = re.sub(r'\([^)]*\)', '', nombre).strip()
    tokens = nombre.upper().split()
    # Eliminar tallas del final
    while tokens:
        if TALLAS_SUFIJOS and (tokens[-1] in TALLAS_SUFIJOS or
                               re.match(r'^\d+L$', tokens[-1])):
            tokens.pop()
        else:
            break
    # Eliminar colores, géneros, marca y specs técnicas de cualquier posición
    tokens = [t for t in tokens if not _es_descartable(t)]
    # Eliminar tokens duplicados preservando orden
    seen = set()
    tokens_unique = []
    for t in tokens:
        if t not in seen:
            seen.add(t)
            tokens_unique.append(t)
    return ' '.join(tokens_unique)


def detectar_genero(nombre):
    n = nombre.upper()
    if any(g in n for g in ['DAMA', 'MUJER']):
        return 'Mujer'
    if any(g in n for g in ['HOMBRE', 'CABALLERO']):
        return 'Hombre'
    return ''


def detectar_color(nombre):
    n = nombre.upper()
    # Multi-color primero (ej: NEGRO-GRIS, NEGRO-VERDE NEON)
    for c1 in COLORES_SUFIJOS:
        for c2 in COLORES_SUFIJOS:
            if c1 != c2 and f'{c1}-{c2}' in n:
                return f'{c1}-{c2}'
            if c1 != c2 and f'{c1} {c2}' in n and c2 == 'NEON':
                return f'{c1} {c2}'
    for c in COLORES_SUFIJOS:
        if c in n.split():
            return c
    return ''


def color_hex(color_str):
    c = color_str.upper().strip()
    if c in COLOR_MAP:
        return COLOR_MAP[c]
    # Para colores combinados, devolver el primer color
    partes = re.split(r'[-\s]', c)
    for p in partes:
        if p in COLOR_MAP:
            return COLOR_MAP[p]
    return '#555555'


def limpiar_sku(sku):
    s = str(sku).strip()
    if s.lower() in ('nan', 'none', ''):
        return ''
    try:
        return str(int(float(s)))
    except Exception:
        return s


def tiene_ce(descripcion_corta, descripcion):
    texto = f"{descripcion_corta} {descripcion}".upper()
    return 'CE' in texto.split() or ' CE ' in f' {texto} '


def extraer_talla(valor_talla):
    if not isinstance(valor_talla, str):
        return str(valor_talla).strip()
    val = valor_talla.strip()
    # "Talla L" → "L"
    if val.upper().startswith('TALLA '):
        return val[6:].strip()
    return val


def _extraer_talla_de_nombre(nombre):
    """Extrae la talla buscando tokens conocidos desde el final del nombre."""
    tokens = nombre.upper().split()
    for t in reversed(tokens):
        if t in TALLAS_SUFIJOS or re.match(r'^\d+L$', t):
            return t
    return ''


def leer_excel(ruta, categorias_filtro=None):
    """
    Lee el archivo y agrupa TODAS las filas por nombre base (limpiar_nombre).
    Funciona igual con productos 'simple', 'variable'+'variation', o mezcla.
    Cada grupo único de nombre → una página de catálogo con tabla de tallas.
    """
    if ruta.lower().endswith('.csv'):
        df = _leer_csv_autodetect(ruta)
    else:
        df = pd.read_excel(ruta)

    df.columns = df.columns.str.strip()

    col_map = {}
    busquedas = {
        'tipo':       ['tipo', 'type'],
        'nombre':     ['nombre', 'name'],
        'sku':        ['sku'],
        'categorias': ['categorías', 'categorias', 'categories'],
        'precio':     ['precio normal', 'regular price', 'precio', 'price'],
        'imagenes':   ['imágenes', 'imagenes', 'images'],
        'desc_corta': ['descripción corta', 'descripcion corta', 'short description'],
        'descripcion':['descripción', 'descripcion', 'description'],
        'attr1_nombre':['nombre del atributo 1', 'attribute 1 name'],
        'attr1_valor': ['valor(es) del atributo 1', 'attribute 1 value(s)',
                        'valores del atributo 1'],
        'inventario': ['inventario', 'stock', 'cantidad en stock', 'cantidad'],
    }
    for key, opciones in busquedas.items():
        for col in df.columns:
            if col.lower().strip() in opciones:
                col_map[key] = col
                break

    from collections import OrderedDict
    grupos = OrderedDict()   # nombre_limpio → dict de grupo

    for _, row in df.iterrows():
        tipo = str(row.get(col_map.get('tipo', ''), '')).lower().strip()

        nombre_raw = str(row.get(col_map.get('nombre', ''), '')).strip()
        if not nombre_raw or nombre_raw.lower() == 'nan':
            continue

        cat_raw = str(row.get(col_map.get('categorias', ''), '')).strip()
        categoria = cat_raw.split('>')[0].split(',')[0].strip().upper()

        if categorias_filtro and len(categorias_filtro) > 0:
            if not any(f.upper() in categoria for f in categorias_filtro):
                continue

        nombre_limpio = limpiar_nombre(nombre_raw)

        # Campos comunes de la fila
        sku = limpiar_sku(row.get(col_map.get('sku', ''), ''))
        precio_raw = row.get(col_map.get('precio', ''), '')
        try:
            precio = float(str(precio_raw).replace(',', '.'))
            if math.isnan(precio):
                precio = 0
        except Exception:
            precio = 0

        desc_corta  = str(row.get(col_map.get('desc_corta',  ''), '')).strip()
        descripcion = str(row.get(col_map.get('descripcion', ''), '')).strip()
        imagenes    = str(row.get(col_map.get('imagenes',    ''), '')).strip()
        attr1_val   = str(row.get(col_map.get('attr1_valor', ''), '')).strip()

        def _limpio(v):
            return v if v and v.lower() not in ('nan', 'none') else ''

        imagenes    = _limpio(imagenes)
        desc_corta  = _limpio(desc_corta)
        descripcion = _limpio(descripcion)
        attr1_val   = _limpio(attr1_val)

        # ── Crear o actualizar el grupo ──────────────────────────────────────
        if nombre_limpio not in grupos:
            grupos[nombre_limpio] = {
                'nombre':      nombre_limpio,
                'categoria':   categoria,
                'sku':         sku,
                'precio':      precio,
                'imagenes':    imagenes,
                'desc_corta':  desc_corta,
                'descripcion': descripcion,
                'variaciones': [],
            }
        g = grupos[nombre_limpio]

        # Rellenar campos vacíos del grupo con los de esta fila
        if g['precio'] == 0 and precio > 0:
            g['precio'] = precio
        if not g['imagenes'] and imagenes:
            g['imagenes'] = imagenes
        if not g['desc_corta'] and desc_corta:
            g['desc_corta'] = desc_corta
        if not g['descripcion'] and descripcion:
            g['descripcion'] = descripcion
        if not g['sku'] and sku:
            g['sku'] = sku

        # Las filas padre 'variable' solo aportan metadatos; no generan variación propia
        if tipo == 'variable':
            continue

        # ── Inventario ───────────────────────────────────────────────────────
        inv_raw = row.get(col_map.get('inventario', ''), '')
        try:
            inventario = int(float(str(inv_raw)))
        except Exception:
            inventario = -1          # sin columna → no filtrar
        if inventario == 0:
            continue                 # filtrar sin stock

        # ── Extraer talla ────────────────────────────────────────────────────
        if attr1_val:
            # attr1_val puede ser "L" o lista "S, M, L, XL"
            tallas_fila = [extraer_talla(t.strip())
                           for t in attr1_val.split(',') if t.strip()]
            tallas_fila = [t for t in tallas_fila if t]
        else:
            t = _extraer_talla_de_nombre(nombre_raw)
            tallas_fila = [t] if t else ['']

        color  = detectar_color(nombre_raw)
        genero = detectar_genero(nombre_raw)
        img_v  = imagenes if imagenes else g['imagenes']

        # Una variación por talla encontrada en esta fila
        for talla in tallas_fila:
            g['variaciones'].append({
                'nombre':    nombre_raw,
                'sku':       sku,
                'talla':     talla,
                'genero':    genero,
                'color':     color,
                'imagenes':  img_v,
                'inventario': inventario if inventario > 0 else None,
            })

    # ── Construir lista de productos ─────────────────────────────────────────
    productos = []
    for nombre_limpio, g in grupos.items():
        if not g['variaciones']:
            continue

        desc_corta  = g['desc_corta']
        descripcion = g['descripcion']
        ce = tiene_ce(desc_corta, descripcion)
        tiene_incluye = ('incluye' in descripcion.lower() or
                         'incluye' in desc_corta.lower())
        bullets = extraer_bullets(desc_corta, descripcion)
        generos = set(v['genero'] for v in g['variaciones'] if v['genero'])

        productos.append({
            'tipo':        'variable',   # siempre variable para el layout
            'nombre':      nombre_limpio,
            'categoria':   g['categoria'],
            'sku':         g['sku'],
            'precio':      g['precio'],
            'imagenes':    g['imagenes'],
            'desc_corta':  desc_corta,
            'descripcion': descripcion,
            'ce':          ce,
            'variaciones': g['variaciones'],
            'tallas_padre': [],
            'generos':     generos,
            'tiene_incluye': tiene_incluye,
            'bullets':     bullets,
        })

    return productos


def extraer_bullets(desc_corta, descripcion):
    bullets = []
    for texto in [desc_corta, descripcion]:
        if not texto or texto == 'nan':
            continue
        # Limpiar HTML tags
        texto_limpio = re.sub(r'<[^>]+>', '\n', texto)
        texto_limpio = re.sub(r'&[a-z]+;', ' ', texto_limpio)
        lineas = [l.strip() for l in texto_limpio.split('\n') if l.strip()]
        for linea in lineas:
            linea = linea.strip('•·-– ').strip()
            if linea and len(linea) > 3 and linea not in bullets:
                bullets.append(linea)
        if bullets:
            break
    return bullets[:8]


def _leer_csv_autodetect(ruta):
    try:
        df_test = pd.read_csv(ruta, sep=',', encoding='utf-8-sig', nrows=1)
        sep = ',' if len(df_test.columns) > 5 else ';'
    except Exception:
        sep = ','
    return pd.read_csv(ruta, sep=sep, encoding='utf-8-sig')


def obtener_categorias(ruta):
    try:
        if ruta.lower().endswith('.csv'):
            df = _leer_csv_autodetect(ruta)
        else:
            df = pd.read_excel(ruta)
        df.columns = df.columns.str.strip()
        for col in df.columns:
            if col.lower().strip() in ['categorías', 'categorias', 'categories']:
                cats = set()
                for val in df[col].dropna():
                    # Usar PRIMER nivel de jerarquía, igual que leer_excel
                    cat = str(val).split('>')[0].split(',')[0].strip().upper()
                    if cat:
                        cats.add(cat)
                return sorted(cats)
    except Exception:
        pass
    return []
