"""
Módulo de integración con la API REST de WooCommerce.
Reemplaza al lector_excel.py para obtener productos directamente desde la tienda.
"""
import requests
from requests.auth import HTTPBasicAuth
from lector_excel import limpiar_nombre, detectar_color, detectar_genero, tiene_ce, extraer_bullets


def _api_get(base_url, ck, cs, endpoint, params=None):
    """GET autenticado a la API de WooCommerce."""
    url = f"{base_url.rstrip('/')}/wp-json/wc/v3/{endpoint}"
    resp = requests.get(
        url,
        auth=HTTPBasicAuth(ck, cs),
        params=params or {},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def obtener_categorias_woo(base_url, ck, cs):
    """Devuelve lista de nombres de categorías activas con productos."""
    cats = []
    page = 1
    while True:
        batch = _api_get(base_url, ck, cs, 'products/categories', {
            'per_page': 100,
            'page': page,
            'hide_empty': True,
        })
        if not batch:
            break
        for c in batch:
            if c.get('name') and c['name'].lower() not in ('uncategorized', 'sin categoría'):
                cats.append(c['name'])
        if len(batch) < 100:
            break
        page += 1
    return sorted(cats)


def obtener_productos_woo(
    base_url, ck, cs,
    categorias_filtro=None,
    solo_stock=True,
    callback_log=None,
    callback_progreso=None,
):
    """
    Descarga todos los productos de WooCommerce y los agrupa igual que leer_excel().
    Devuelve lista de productos con el mismo formato que espera generador.py.
    """
    def log(m):
        if callback_log:
            callback_log(m)

    def prog(p):
        if callback_progreso:
            callback_progreso(p)

    # 1. Obtener IDs de categorías si hay filtro
    cat_ids = []
    if categorias_filtro:
        log("🔍 Buscando IDs de categorías...")
        todas_cats = _api_get(base_url, ck, cs, 'products/categories', {'per_page': 100})
        for c in todas_cats:
            for f in categorias_filtro:
                if f.lower() in c['name'].lower():
                    cat_ids.append(c['id'])

    # 2. Descargar productos paginados (una llamada por tipo para evitar error 400)
    log("📦 Descargando productos desde WooCommerce...")
    productos_raw = []

    for tipo in ('variable', 'simple'):
        page = 1
        params_base = {
            'per_page': 100,
            'status':   'publish',
            'type':     tipo,
        }
        if solo_stock:
            params_base['stock_status'] = 'instock'
        if cat_ids:
            params_base['category'] = ','.join(str(i) for i in cat_ids)

        while True:
            params = {**params_base, 'page': page}
            batch = _api_get(base_url, ck, cs, 'products', params)
            if not batch:
                break
            productos_raw.extend(batch)
            log(f"  [{tipo}] Página {page}: {len(batch)} productos ({len(productos_raw)} total)")
            prog(int(30 * page / max(page + 1, 2)))
            if len(batch) < 100:
                break
            page += 1

    log(f"📦 {len(productos_raw)} productos descargados, procesando variaciones...")

    # 3. Para cada producto variable, obtener sus variaciones
    total = len(productos_raw)
    from collections import OrderedDict
    grupos = OrderedDict()

    for i, prod in enumerate(productos_raw):
        prog(30 + int(70 * i / max(total, 1)))

        nombre_raw  = prod.get('name', '').strip()
        if not nombre_raw:
            continue

        nombre_limpio = limpiar_nombre(nombre_raw)
        categorias    = [c['name'] for c in prod.get('categories', [])]
        categoria     = categorias[0].upper() if categorias else 'GENERAL'

        # Filtro manual de categorías (por si acaso la API no lo hizo perfectamente)
        if categorias_filtro:
            match = any(
                f.lower() in cat.lower()
                for f in categorias_filtro
                for cat in categorias
            )
            if not match:
                continue

        desc_corta  = prod.get('short_description', '') or ''
        descripcion = prod.get('description', '')       or ''
        precio_raw  = prod.get('regular_price', '0')    or '0'
        try:
            precio = float(precio_raw)
        except Exception:
            precio = 0.0

        sku        = str(prod.get('sku', ''))
        images     = prod.get('images', [])
        img_url    = images[0]['src'] if images else ''
        img_extras = [img['src'] for img in images[1:5] if img.get('src')]  # hasta 4 extras

        # Limpiar HTML de descripciones
        import re
        desc_corta  = re.sub(r'<[^>]+>', ' ', desc_corta).strip()
        descripcion = re.sub(r'<[^>]+>', ' ', descripcion).strip()

        ce            = tiene_ce(desc_corta, descripcion)
        tiene_incluye = ('incluye' in descripcion.lower() or 'incluye' in desc_corta.lower())
        bullets       = extraer_bullets(desc_corta, descripcion)

        variaciones = []

        if prod.get('type') == 'variable':
            log(f"  🔄 [{i+1}/{total}] Variaciones: {nombre_limpio[:40]}")
            try:
                vars_raw = _api_get(base_url, ck, cs,
                                    f"products/{prod['id']}/variations",
                                    {'per_page': 100, 'status': 'publish'})
            except Exception as e:
                log(f"  ⚠️ Error variaciones {nombre_limpio[:30]}: {e}")
                vars_raw = []

            for v in vars_raw:
                if solo_stock and v.get('stock_status') != 'instock':
                    continue
                inv_raw = v.get('stock_quantity')
                try:
                    inventario = int(inv_raw) if inv_raw is not None else None
                except Exception:
                    inventario = None

                # Atributos: talla, color, género
                talla  = ''
                color  = ''
                genero = ''
                for attr in v.get('attributes', []):
                    aname = attr.get('name', '').lower()
                    aval  = attr.get('option', '').strip()
                    if 'talla' in aname or 'size' in aname:
                        talla = aval
                    elif 'color' in aname:
                        color = aval.upper()
                    elif 'genero' in aname or 'género' in aname or 'gender' in aname:
                        genero = aval

                # Fallback: detectar del nombre
                if not color:
                    color  = detectar_color(nombre_raw)
                if not genero:
                    genero = detectar_genero(nombre_raw)

                v_images = v.get('image', {})
                v_img    = v_images.get('src', '') if v_images else ''
                if not v_img:
                    v_img = img_url

                v_precio_raw = v.get('regular_price', '0') or '0'
                try:
                    v_precio = float(v_precio_raw)
                except Exception:
                    v_precio = precio

                variaciones.append({
                    'nombre':     nombre_raw,
                    'sku':        str(v.get('sku', '')),
                    'talla':      talla,
                    'genero':     genero,
                    'color':      color,
                    'imagenes':   v_img,
                    'inventario': inventario,
                    'precio':     v_precio,
                })
        else:
            # Producto simple
            inv_raw = prod.get('stock_quantity')
            try:
                inventario = int(inv_raw) if inv_raw is not None else None
            except Exception:
                inventario = None

            color  = detectar_color(nombre_raw)
            genero = detectar_genero(nombre_raw)
            variaciones.append({
                'nombre':     nombre_raw,
                'sku':        sku,
                'talla':      '',
                'genero':     genero,
                'color':      color,
                'imagenes':   img_url,
                'inventario': inventario,
                'precio':     precio,
            })

        if not variaciones:
            continue

        grupos[nombre_limpio] = {
            'tipo':          'variable',
            'nombre':        nombre_limpio,
            'categoria':     categoria,
            'sku':           sku,
            'precio':        precio,
            'imagenes':      img_url,
            'imagenes_extra': img_extras,
            'desc_corta':    desc_corta,
            'descripcion':   descripcion,
            'ce':            ce,
            'variaciones':   variaciones,
            'tallas_padre':  [],
            'generos':       set(v['genero'] for v in variaciones if v['genero']),
            'tiene_incluye': tiene_incluye,
            'bullets':       bullets,
        }

    log(f"✅ {len(grupos)} grupos de productos procesados")
    return list(grupos.values())
