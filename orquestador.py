# -*- coding: utf-8 -*-
"""
orquestador.py

Punto de entrada único para generar un catálogo PDF completo (uno de los 4
definidos en categorias_config.CATALOGOS). Por cada grupo del Excel
(data/data.xlsx):

1. Si existe página pre-hecha (assets/paginas_prehechas/{marca}/) → se usa
   esa, con inventario y precio estampados encima (paginas_prehechas.py).
2. Si no existe → se genera dinámicamente. La imagen del producto sale de
   la URL de la columna K del Excel (una por grupo); el inventario, el
   precio y la talla salen de las columnas E, C/D y H respectivamente.

El Excel (lector_maestro.py) es la única fuente de verdad: define qué entra
al catálogo (columna I + marca), en qué sección (columna J), con qué
inventario, precio, talla e imagen. Ya NO se consulta la API de WooCommerce.
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
import paginas_sku
from fuentes_marca import registrar_fuentes_marca
from descargador import descargar_imagen
from lector_excel import limpiar_nombre

# Reusa exactamente los mismos assets (portada/contraportada/fondo de
# página) que ya existen en el repo para los tipos de catálogo "viejos".
# No hace falta subir ningún asset nuevo para esto.
TIPO_LEGADO_POR_CATALOGO = {
    'xecuro_general':       'cascos',
    'xtrong_integrales':    'integrales',
    'xtrong_otros_cascos':  'abatibles_abiertos',
    'xtrong_accesorios':    'textiles_accesorios',
}


def _grupo_a_producto_dinamico(grupo):
    """Convierte un grupo del Excel en el dict 'producto' que espera
    generador_web._pagina_producto(). La imagen sale de la columna K del Excel
    (una sola por grupo), así que todas las variaciones comparten imagen y no
    se separan por color: una única tabla talla/código/inventario por página."""
    variaciones = []
    for s in grupo['skus']:
        variaciones.append({
            'nombre':     s['nombre_producto'],
            'sku':        str(s['sku']),
            'talla':      s['talla'],
            'color':      '',                      # sin separación por color
            'imagenes':   grupo.get('imagen_url', ''),
            'inventario': s['inventario'],
        })
    return {
        'nombre':      limpiar_nombre(grupo['nombre_producto']),
        'desc_corta':  '',
        'descripcion': '',
        'variaciones': variaciones,
    }


def _resolver_imagen_grupo(grupo, carpeta_cache, callback_log=None,
                           carpeta_locales=None):
    """Devuelve la ruta a una imagen para el grupo, o None.

    Fuente única: la URL de la columna K del Excel (grupo['imagen_url']). Se
    admite un respaldo manual por SKU en assets/imagenes_locales/{marca}/ para
    casos puntuales, pero ya NO se consulta WooCommerce."""
    def log(m):
        if callback_log:
            callback_log(m)

    # 1) Respaldo manual: imagen local por SKU
    if carpeta_locales and os.path.isdir(carpeta_locales):
        for s in grupo['skus']:
            for ext in ('.jpg', '.jpeg', '.png', '.webp', '.JPG', '.JPEG', '.PNG'):
                cand = os.path.join(carpeta_locales, f"{s['sku']}{ext}")
                if os.path.exists(cand):
                    log(f"  🖼️ Imagen local: {os.path.basename(cand)}")
                    return cand

    # 2) URL de la columna K del Excel
    url = grupo.get('imagen_url', '')
    if url:
        path = descargar_imagen(
            url, f"grp_{grupo['grupo_foto']}",
            grupo['nombre_producto'], carpeta_cache, callback_log=callback_log,
        )
        if path:
            return path
        log(f"  ⚠️ {grupo['grupo_foto']}: la URL de la columna K existe pero la "
            f"descarga falló: {str(url)[:70]}")
        return None

    # Sin URL (no debería ocurrir: el lector ya excluye grupos sin imagen)
    log(f"  ⚠️ {grupo['grupo_foto']} ({grupo['nombre_producto'][:40]}): sin URL de imagen")
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
    dinamico_si_falta=False,  # True: si falta la página, descarga la foto (col K)
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
            "Verifica el Excel (data/data.xlsx)."
        )
    log(f"  ✅ {total_grupos} productos a incluir")
    prog(10)

    # 2) Índices de páginas: (a) pre-armadas por SKU en assets/paginas/,
    #    (b) pre-hechas por JSON (legado). Prioridad: assets/paginas → prehechas
    #    JSON → generación dinámica (descarga columna K).
    log("🗂️ Indexando páginas...")
    carpeta_paginas_sku = os.path.join(base_dir, 'assets', 'paginas')
    indice_sku = paginas_sku.construir_indice_paginas(carpeta_paginas_sku, callback_log=log)
    indice_prehechas = construir_indice(carpeta_assets_raiz, marca, callback_log=log)
    prog(15)

    def _tiene_alguna_pagina(g):
        return paginas_sku.tiene_pagina(g, indice_sku) or tiene_pagina_prehecha(g, indice_prehechas)

    todos_los_grupos = [g for _, _, gs in buckets for g in gs]
    faltantes = [g for g in todos_los_grupos if not _tiene_alguna_pagina(g)]
    con_pagina = len(todos_los_grupos) - len(faltantes)

    if faltantes:
        detalle = ", ".join(
            f"{g.get('grupo_foto')}[{'/'.join(str(s.get('sku')) for s in g.get('skus', []))}]"
            for g in faltantes[:40]
        )
        log(f"  ⚠️ {len(faltantes)} producto(s) SIN página en assets/paginas: {detalle}"
            + (" ..." if len(faltantes) > 40 else ""))

    if not dinamico_si_falta and faltantes:
        # Por defecto NO se descargan imágenes: se omiten los productos sin página
        # (así el catálogo se arma solo con las páginas listas y nunca se cuelga
        # esperando descargas). Los que faltan quedan logueados arriba para que
        # agregues su página a assets/paginas y vuelvas a generar.
        omitidos_gf = {id(g) for g in faltantes}
        buckets = [(k, lbl, [g for g in gs if id(g) not in omitidos_gf])
                   for (k, lbl, gs) in buckets]
        buckets = [(k, lbl, gs) for (k, lbl, gs) in buckets if gs]
        log(f"  🚫 {len(faltantes)} producto(s) omitido(s) por no tener página "
            f"(usa dinamico_si_falta=True para generarlos descargando la foto).")

    total_grupos = sum(len(gs) for _, _, gs in buckets)
    if total_grupos == 0:
        raise ValueError(
            f"Ningún producto de '{cfg_catalogo['nombre']}' tiene página en "
            f"assets/paginas. Revisa que los nombres de archivo incluyan el "
            f"Grupo_Foto o el SKU del Excel."
        )
    log(f"  📄 {con_pagina} con página en assets/paginas"
        + (f"; {len(faltantes)} sin página" if faltantes else ""))
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
    # Fecha de última actualización = mtime del Excel de catálogo (data/data.xlsx)
    fecha_excel = None
    try:
        import datetime as _dt
        for _cand in (
            datos.get('ruta_excel') if isinstance(datos, dict) else None,
            os.path.join(base_dir, 'data', 'data.xlsx'),
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

            ruta_pagina_sku = paginas_sku.buscar_pagina(grupo, indice_sku)
            if ruta_pagina_sku:
                paginas_sku.dibujar_pagina_sku(
                    c, cfg, grupo, ruta_pagina_sku,
                    mostrar_precio_mayor=mostrar_precio_mayor,
                    mostrar_precio_detal=mostrar_precio_detal,
                    num=idx, total=total_grupos,
                    carpeta_cache=os.path.join(carpeta_cache, 'paginas_render'),
                    callback_log=log,
                )
            elif tiene_pagina_prehecha(grupo, indice_prehechas):
                dibujar_pagina_prehecha(
                    c, cfg, grupo, indice_prehechas, carpeta_assets_raiz,
                    mostrar_precio_mayor=mostrar_precio_mayor,
                    mostrar_precio_detal=mostrar_precio_detal,
                    callback_log=log,
                )
            else:
                producto = _grupo_a_producto_dinamico(grupo)
                img_path = _resolver_imagen_grupo(grupo, carpeta_cache,
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
    _msg_falta = (f", {len(faltantes)} omitido(s) sin página" if (faltantes and not dinamico_si_falta)
                  else (f", {len(faltantes)} dinámico(s)" if faltantes else ""))
    log(f"✅ Catálogo generado: {total_grupos} página(s){_msg_falta}")
    return ruta_salida
