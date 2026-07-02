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
    de stock — de eso ya se encarga el Excel) y arma un índice
    SKU -> {imagen, desc_corta, descripcion, color} para el fallback dinámico.
    Solo se llama si de verdad hay grupos sin página pre-hecha.
    """
    def log(m):
        if callback_log:
            callback_log(m)
    from woo_api import obtener_productos_woo
    productos = obtener_productos_woo(
        base_url, ck, cs, categorias_filtro=None, solo_stock=False, callback_log=log,
    )
    indice = {}
    for p in productos:
        for v in p.get('variaciones', []):
            sku = str(v.get('sku') or '').strip()
            if not sku:
                continue
            indice[sku] = {
                'imagen':      v.get('imagenes') or p.get('imagenes', ''),
                'desc_corta':  p.get('desc_corta', ''),
                'descripcion': p.get('descripcion', ''),
                'color':       v.get('color', ''),
            }
    log(f"  🔎 Índice SKU↔WooCommerce: {len(indice)} SKUs")
    return indice


def _grupo_a_producto_dinamico(grupo, sku_index):
    """Convierte un grupo del Excel maestro en el dict 'producto' que espera
    generador_web._pagina_producto(), tomando imagen/desc de WooCommerce."""
    variaciones = []
    desc_corta = descripcion = ''
    for s in grupo['skus']:
        meta = sku_index.get(str(s['sku']), {})
        if not desc_corta and meta.get('desc_corta'):
            desc_corta = meta['desc_corta']
        if not descripcion and meta.get('descripcion'):
            descripcion = meta['descripcion']
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


def _resolver_imagen_grupo(grupo, sku_index, carpeta_cache, callback_log=None,
                           carpeta_locales=None):
    # 1) Respaldo manual: imagen local por SKU (assets/imagenes_locales/{marca}/{sku}.jpg)
    #    Sirve para productos sin página pre-hecha cuya foto no está en WooCommerce
    #    (p.ej. XTR-802 DISCOVER). Basta con dejar el archivo con el nombre del SKU.
    if carpeta_locales and os.path.isdir(carpeta_locales):
        for s in grupo['skus']:
            for ext in ('.jpg', '.jpeg', '.png', '.webp'):
                cand = os.path.join(carpeta_locales, f"{s['sku']}{ext}")
                if os.path.exists(cand):
                    return cand
    # 2) Imagen desde WooCommerce (variación o producto padre)
    for s in grupo['skus']:
        meta = sku_index.get(str(s['sku']))
        if meta and meta.get('imagen'):
            path = descargar_imagen(
                meta['imagen'], f"grp_{grupo['grupo_foto']}",
                grupo['nombre_producto'], carpeta_cache, callback_log=callback_log,
            )
            if path:
                return path
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

    # 3) Solo si hace falta, traer índice de SKUs de WooCommerce (imagen/desc)
    sku_index = {}
    if faltantes:
        if marcas_woo and marca in marcas_woo and marcas_woo[marca].get('ck'):
            m = marcas_woo[marca]
            log("🔗 Conectando a WooCommerce para imágenes de grupos sin página...")
            try:
                sku_index = _construir_indice_sku_woo(m['url'], m['ck'], m['cs'], callback_log=log)
            except Exception as e:
                log(f"  ⚠️ No se pudo consultar WooCommerce: {e} — esos grupos saldrán sin imagen")
        else:
            log("  ⚠️ Sin credenciales de WooCommerce — los grupos sin página pre-hecha "
                "saldrán sin imagen de producto")
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
                producto = _grupo_a_producto_dinamico(grupo, sku_index)
                img_path = _resolver_imagen_grupo(grupo, sku_index, carpeta_cache,
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
