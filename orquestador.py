# -*- coding: utf-8 -*-
"""
orquestador.py

Punto de entrada único para generar un catálogo PDF completo (uno de los 4
definidos en categorias_config.CATALOGOS). Por cada grupo del Excel maestro:

1. Si existe página pre-hecha (assets/paginas_prehechas/{marca}/) → se usa
   esa, con inventario y precio estampados encima (paginas_prehechas.py).
2. Si no existe → se genera dinámicamente vía API de WooCommerce, pero
   SOLO para imagen y descripción — el inventario y el precio siempre
   salen del Excel maestro, nunca de WooCommerce (es la fuente de verdad
   acordada).

El Excel maestro (lector_maestro.py) manda en: qué entra al catálogo, en
qué orden, con qué inventario y con qué precio. La API de WooCommerce es
un proveedor de imágenes de respaldo, nada más.
"""
import os
from reportlab.pdfgen import canvas
from reportlab.lib.colors import white
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

import generador_web as gw
from categorias_config import CATALOGOS
from lector_maestro import cargar_grupos_activos, armar_catalogo
from paginas_prehechas import construir_indice, tiene_pagina_prehecha, dibujar_pagina_prehecha
from fuentes_marca import registrar_fuentes_marca
from descargador import descargar_imagen
from lector_excel import limpiar_nombre, color_hex as _color_hex_lookup

# Reusa exactamente los mismos assets (portada/contraportada/fondo de
# página) que ya existen en el repo para los tipos de catálogo "viejos".
# No hace falta subir ningún asset nuevo para esto.
TIPO_LEGADO_POR_CATALOGO = {
    'xecuro_general':       'cascos',
    'xtrong_integrales':    'integrales',
    'xtrong_otros_cascos':  'abatibles_abiertos',
    'xtrong_accesorios':    'textiles_accesorios',
}


def _construir_indice_sku_woo(base_url, ck, cs, callback_log=None):
    """
    Descarga TODOS los productos de WooCommerce (sin filtro de categoría ni
    de stock — de eso ya se encarga el Excel) y arma TRES índices para resolver
    la imagen de un grupo aunque el SKU de variación no cuadre:

      - 'sku':    SKU de variación   -> {imagen, desc, color}
      - 'padre':  SKU del producto   -> {imagen, desc}   (para tiendas donde las
                                        variaciones no tienen SKU propio)
      - 'nombre': nombre limpio      -> {imagen, desc}   (último respaldo)

    Devuelve {'sku':{}, 'padre':{}, 'nombre':{}}. Solo se llama si de verdad hay
    grupos sin página pre-hecha.
    """
    def log(m):
        if callback_log:
            callback_log(m)
    from woo_api import obtener_productos_woo
    productos = obtener_productos_woo(
        base_url, ck, cs, categorias_filtro=None, solo_stock=False, callback_log=log,
    )
    idx_sku, idx_padre, idx_nombre = {}, {}, {}
    n_var = 0
    for p in productos:
        img_padre = p.get('imagenes', '') or ''
        sku_padre = str(p.get('sku') or '').strip()
        nom = limpiar_nombre(p.get('nombre', ''))
        meta_base = {'desc_corta': p.get('desc_corta', ''),
                     'descripcion': p.get('descripcion', '')}
        if sku_padre and img_padre:
            idx_padre[sku_padre] = {**meta_base, 'imagen': img_padre}
        if nom and img_padre:
            idx_nombre.setdefault(nom, {**meta_base, 'imagen': img_padre})
        for v in p.get('variaciones', []):
            sku = str(v.get('sku') or '').strip()
            if not sku:
                continue
            n_var += 1
            idx_sku[sku] = {
                **meta_base,
                'imagen': v.get('imagenes') or img_padre,
                'color':  v.get('color', ''),
            }
    log(f"  🔎 Índice Woo ({base_url}): {n_var} SKUs de variación, "
        f"{len(idx_padre)} SKUs padre, {len(idx_nombre)} nombres")
    if n_var == 0 and not idx_padre:
        log("  ⚠️ El índice de WooCommerce quedó VACÍO: la tienda respondió pero "
            "sin productos/imágenes utilizables (revisa credenciales, permisos de "
            "lectura de la API, o que los productos estén publicados).")
    return {'sku': idx_sku, 'padre': idx_padre, 'nombre': idx_nombre}


def _resolver_meta_grupo(grupo, woo_idx):
    """Busca la meta (imagen/desc) de un grupo en los índices de Woo, en orden:
    SKU de variación → SKU del padre → nombre limpio. Devuelve (meta, via)."""
    if not woo_idx:
        return None, None
    for s in grupo['skus']:
        m = woo_idx['sku'].get(str(s['sku']))
        if m and m.get('imagen'):
            return m, 'sku_variacion'
    for s in grupo['skus']:
        m = woo_idx['padre'].get(str(s['sku']))
        if m and m.get('imagen'):
            return m, 'sku_padre'
    m = woo_idx['nombre'].get(limpiar_nombre(grupo['nombre_producto']))
    if m and m.get('imagen'):
        return m, 'nombre'
    return None, None


def _grupo_a_producto_dinamico(grupo, woo_idx):
    """Convierte un grupo del Excel maestro en el dict 'producto' que espera
    generador_web._pagina_producto(), tomando imagen/desc de WooCommerce."""
    # Descripción a nivel de grupo: por sku de variación, luego padre, luego nombre
    meta_grupo, _ = _resolver_meta_grupo(grupo, woo_idx)
    desc_corta  = (meta_grupo or {}).get('desc_corta', '')
    descripcion = (meta_grupo or {}).get('descripcion', '')
    idx_sku = woo_idx['sku'] if woo_idx else {}

    variaciones = []
    for s in grupo['skus']:
        meta = idx_sku.get(str(s['sku']), {})
        variaciones.append({
            'nombre':     s['nombre_producto'],
            'sku':        str(s['sku']),
            'talla':      s['talla'],
            'color':      meta.get('color', ''),
            'imagenes':   meta.get('imagen', ''),
            'inventario': s['inventario'],
        })
    return {
        'nombre':      limpiar_nombre(grupo['nombre_producto']),
        'desc_corta':  desc_corta,
        'descripcion': descripcion,
        'variaciones': variaciones,
    }


def _resolver_imagen_grupo(grupo, woo_idx, carpeta_cache, callback_log=None,
                           carpeta_locales=None):
    """Devuelve la ruta a una imagen para el grupo, o None. Deja en el log
    EXACTAMENTE por qué no se resolvió, para que las páginas con foto en gris
    dejen de ser un misterio (punto 1)."""
    def log(m):
        if callback_log:
            callback_log(m)

    skus = [str(s['sku']) for s in grupo['skus']]

    # 1) Respaldo manual: imagen local por SKU
    #    (assets/imagenes_locales/{marca}/{sku}.jpg|jpeg|png|webp)
    if carpeta_locales and os.path.isdir(carpeta_locales):
        for s in grupo['skus']:
            for ext in ('.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG'):
                cand = os.path.join(carpeta_locales, f"{s['sku']}{ext}")
                if os.path.exists(cand):
                    log(f"  🖼️ Imagen local: {os.path.basename(cand)}")
                    return cand

    # 2) Imagen desde WooCommerce (variación → padre → nombre)
    if not woo_idx:
        log(f"  ⚠️ {grupo['grupo_foto']} ({grupo['nombre_producto'][:40]}): foto en gris "
            f"— sin índice de WooCommerce (sin credenciales o falló la conexión). "
            f"Respaldo: dejar la foto en {carpeta_locales}/{skus[0]}.jpg")
        return None

    meta, via = _resolver_meta_grupo(grupo, woo_idx)
    if meta and meta.get('imagen'):
        path = descargar_imagen(
            meta['imagen'], f"grp_{grupo['grupo_foto']}",
            grupo['nombre_producto'], carpeta_cache, callback_log=callback_log,
        )
        if path:
            if via != 'sku_variacion':
                log(f"  🖼️ {grupo['grupo_foto']}: imagen resuelta por {via}")
            return path
        log(f"  ⚠️ {grupo['grupo_foto']}: la URL existe ({via}) pero la descarga falló: "
            f"{str(meta['imagen'])[:70]}")
        return None

    # Nada cuadró: decir por qué
    log(f"  ⚠️ {grupo['grupo_foto']} ({grupo['nombre_producto'][:40]}): foto en gris "
        f"— SKUs {skus} no están en WooCommerce (ni como variación ni como padre) "
        f"y el nombre no cruzó. Respaldo: dejar la foto en {carpeta_locales}/{skus[0]}.jpg")
    return None


def generar_catalogo(
    catalogo_id,
    periodo,
    ruta_salida,
    mostrar_precio_mayor=False,
    mostrar_precio_detal=False,
    carpeta_assets=None,
    carpeta_cache=None,
    marcas_woo=None,   # {'xtrong': {'url','ck','cs'}, 'xecuro': {...}}
    callback_log=None,
    callback_progreso=None,
):
    def log(m):
        if callback_log:
            callback_log(m)

    def prog(p):
        if callback_progreso:
            callback_progreso(p)

    cfg_catalogo = CATALOGOS.get(catalogo_id)
    if not cfg_catalogo:
        raise ValueError(f"Catálogo desconocido: {catalogo_id}")
    marca = cfg_catalogo['marca']

    base_dir = os.path.dirname(os.path.abspath(__file__))
    if not carpeta_assets or not os.path.isdir(carpeta_assets):
        for candidato in [
            os.path.join(base_dir, 'assets', marca),
            os.path.join(base_dir, 'assets', marca.upper()),
            os.path.join('/var/task', 'assets', marca),
        ]:
            if os.path.isdir(candidato):
                carpeta_assets = candidato
                break
        else:
            carpeta_assets = os.path.join(base_dir, 'assets', marca)
    log(f"  📁 Assets: {carpeta_assets} (existe: {os.path.isdir(carpeta_assets)})")

    # assets/ es la carpeta raíz de assets (para paginas_prehechas, que
    # espera assets/paginas_prehechas/{marca}/, no assets/{marca}/paginas_prehechas/)
    carpeta_assets_raiz = os.path.dirname(carpeta_assets) if os.path.basename(carpeta_assets) in ('xtrong', 'xecuro', 'XTRONG', 'XECURO') else carpeta_assets

    carpeta_cache = carpeta_cache or f'/tmp/cache_imagenes/{marca}'
    os.makedirs(carpeta_cache, exist_ok=True)

    # Carpeta opcional de imágenes locales de respaldo, por SKU:
    #   assets/imagenes_locales/{marca}/{sku}.jpg|png|...
    carpeta_locales = os.path.join(carpeta_assets_raiz, 'imagenes_locales', marca)

    # 1) Excel maestro → grupos activos → catálogo ordenado
    log("📊 Leyendo Excel maestro...")
    datos = cargar_grupos_activos(base_dir, callback_log=log)
    prog(5)

    buckets = armar_catalogo(catalogo_id, datos['grupos'], callback_log=log)
    total_grupos = sum(len(gs) for _, _, gs in buckets)
    if total_grupos == 0:
        raise ValueError(
            f"No hay grupos activos con inventario para '{cfg_catalogo['nombre']}'. "
            "Verifica el Excel maestro (data/SKU_grupos_precios.xlsx)."
        )
    log(f"  ✅ {total_grupos} productos a incluir")
    prog(10)

    # 2) Índice de páginas pre-hechas
    log("🗂️ Indexando páginas pre-hechas...")
    indice_prehechas = construir_indice(carpeta_assets_raiz, marca, callback_log=log)
    prog(15)

    todos_los_grupos = [g for _, _, gs in buckets for g in gs]
    faltantes = [g for g in todos_los_grupos if not tiene_pagina_prehecha(g, indice_prehechas)]
    log(f"  📄 {total_grupos - len(faltantes)} con página pre-hecha, "
        f"{len(faltantes)} necesitan generación dinámica")

    # 3) Solo si hace falta, traer índice de imágenes de WooCommerce
    woo_idx = None
    if faltantes:
        if marcas_woo and marca in marcas_woo and marcas_woo[marca].get('ck'):
            m = marcas_woo[marca]
            log(f"🔗 Conectando a WooCommerce ({m.get('url')}) para imágenes de "
                f"{len(faltantes)} grupos sin página...")
            try:
                woo_idx = _construir_indice_sku_woo(m['url'], m['ck'], m['cs'], callback_log=log)
            except Exception as e:
                import traceback
                log(f"  ⚠️ No se pudo consultar WooCommerce: {type(e).__name__}: {e}")
                log(f"     (revisa credenciales/permisos de la API. Detalle: "
                    f"{traceback.format_exc().splitlines()[-1]}) — esos grupos saldrán sin imagen")
        else:
            log("  ⚠️ Sin credenciales de WooCommerce (falta 'ck' en marcas_woo) — "
                "los grupos sin página pre-hecha saldrán sin imagen de producto")
    prog(25)

    # 4) Config de marca: colores + fuentes reales (Kanit/Sora) + logo
    cfg = dict(gw.MARCAS_CONFIG.get(marca, gw.MARCAS_CONFIG['xtrong']))
    cfg['_marca'] = marca
    fuentes = registrar_fuentes_marca(marca, carpeta_assets_raiz, callback_log=log)
    cfg['font_titulo'] = fuentes['bold']

    logo_path = None
    for fname in ('logo.png', 'logo_xtrong.png', 'logo_xecuro.png', 'LOGO.png'):
        cand = os.path.join(carpeta_assets, fname)
        if os.path.exists(cand):
            logo_path = cand
            break
    cfg['_logo_path'] = logo_path

    # 5) Reusar assets de portada/contraportada/fondo del tipo "legado" equivalente
    tipo_legado = TIPO_LEGADO_POR_CATALOGO.get(catalogo_id, '')
    assets_tipo = gw.ASSETS_POR_TIPO.get(tipo_legado, {})

    portada_path = gw._buscar_asset(carpeta_assets, assets_tipo.get('portada', 'PORTADA.jpg'))
    contra_path  = gw._buscar_asset(carpeta_assets, assets_tipo.get('contraportada', 'CONTRAPORTADA.jpg'))
    portada_reader = gw._cargar_image_reader_seguro(portada_path, "Portada", log=log)
    contra_reader  = gw._cargar_image_reader_seguro(contra_path, "Contraportada", log=log)

    bg_reader = bg_pro_reader = None
    if assets_tipo.get('pagina_bg'):
        bg_path = gw._buscar_asset(carpeta_assets, assets_tipo['pagina_bg'])
        log(f"  🔍 Fondo página (fallback dinámico) resuelto a: {bg_path} "
            f"(existe: {os.path.exists(bg_path)})")
        bg_reader = gw._cargar_image_reader_seguro(bg_path, f"Fondo página ({assets_tipo['pagina_bg']})", log=log)
    if assets_tipo.get('pagina_bg_pro'):
        bg_pro_path = gw._buscar_asset(carpeta_assets, assets_tipo['pagina_bg_pro'])
        bg_pro_reader = gw._cargar_image_reader_seguro(bg_pro_path, "Fondo PRO", log=log)
    prog(30)

    # 6) Generar el PDF
    c = canvas.Canvas(ruta_salida, pagesize=(gw.PAGE_W, gw.PAGE_H))

    log("  📄 Portada...")
    # Fecha de última actualización = mtime del Excel maestro (data/SKU_grupos_precios.xlsx)
    fecha_excel = None
    try:
        import datetime as _dt
        for _cand in (
            os.path.join(base_dir, 'data', 'SKU_grupos_precios.xlsx'),
            os.path.join(base_dir, 'data', 'SKU_grupos_precios.xlsm'),
            datos.get('ruta_excel') if isinstance(datos, dict) else None,
        ):
            if _cand and os.path.exists(_cand):
                fecha_excel = _dt.datetime.fromtimestamp(
                    os.path.getmtime(_cand)).strftime('%d/%m/%Y')
                break
    except Exception as _e:
        log(f"  ⚠️ No se pudo leer la fecha del Excel: {_e}")

    overlay = f"{cfg_catalogo['nombre'].upper()}|{periodo}" if periodo else cfg_catalogo['nombre'].upper()
    gw._draw_full_bleed(c, portada_reader or portada_path, texto_overlay=overlay, cfg=cfg,
                        fecha_actualizacion=fecha_excel)
    c.showPage()
    prog(33)

    log("📄 Generando páginas de producto...")
    idx = 0
    for bucket_key, bucket_label, grupos in buckets:
        log(f"  ── {bucket_label} ({len(grupos)}) ──")
        for grupo in grupos:
            idx += 1
            prog(33 + int(60 * idx / max(total_grupos, 1)))
            log(f"  📝 [{idx}/{total_grupos}] {grupo['nombre_producto'][:50]}")

            if tiene_pagina_prehecha(grupo, indice_prehechas):
                dibujar_pagina_prehecha(
                    c, cfg, grupo, indice_prehechas, carpeta_assets_raiz,
                    mostrar_precio_mayor=mostrar_precio_mayor,
                    mostrar_precio_detal=mostrar_precio_detal,
                    callback_log=log,
                )
            else:
                producto = _grupo_a_producto_dinamico(grupo, woo_idx)
                img_path = _resolver_imagen_grupo(grupo, woo_idx, carpeta_cache,
                                                  callback_log=log,
                                                  carpeta_locales=carpeta_locales)
                s0 = grupo['skus'][0]
                gw._pagina_producto(
                    c, cfg, producto, img_path,
                    mostrar_precios=(mostrar_precio_mayor or mostrar_precio_detal),
                    num=idx, total=total_grupos,
                    carpeta_assets=carpeta_assets, assets_tipo=assets_tipo,
                    bg_reader=bg_reader, bg_pro_reader=bg_pro_reader,
                    precio_mayor=s0.get('precio_mayor'),
                    precio_detal=s0.get('precio_detal'),
                    mostrar_precio_mayor=mostrar_precio_mayor,
                    mostrar_precio_detal=mostrar_precio_detal,
                )
            c.showPage()

    log("  📄 Contraportada...")
    gw._draw_full_bleed(c, contra_reader or contra_path)
    c.showPage()

    log("💾 Guardando PDF...")
    c.save()
    prog(100)
    log(f"✅ Catálogo generado: {total_grupos} productos "
        f"({total_grupos - len(faltantes)} pre-hechos, {len(faltantes)} dinámicos)")
    return ruta_salida
