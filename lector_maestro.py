# -*- coding: utf-8 -*-
"""
lector_maestro.py

Lee data/SKU_grupos_precios.xlsx (la fuente de verdad de inventario, precios,
marca y categoría) y produce, para cada catálogo definido en
categorias_config.CATALOGOS, la lista de grupos (Grupo_Foto) que deben
aparecer, ya ordenada.

Reglas aplicadas (confirmadas con el usuario):
- Solo entran grupos con AL MENOS un SKU con inventario > 0.
- Categorías excluidas (repuestos sueltos, visor) se descartan por completo.
- Filas sin marca definida ("Sin marca" / vacío) se asignan a XECURO,
  y solo si tienen inventario > 0.
- Un mismo Grupo_Foto siempre tiene una sola marca y una sola categoría
  (según diseño ya validado del Excel); si llegara a haber inconsistencia
  se usa la de la fila con mayor inventario y se loguea como aviso.
"""
import os
import re
import openpyxl

from categorias_config import (
    normalizar_categoria, normalizar_marca, CATALOGOS, BUCKET_LABELS,
)

HOJA_PREFERIDA = 'SKUs_Totales'

# Rutas donde puede vivir el Excel maestro, en orden de preferencia.
# El patrón replica el mismo enfoque defensivo que ya usa generador_web.py
# para encontrar la carpeta assets/.
def _rutas_candidatas(base_dir):
    return [
        os.path.join(base_dir, 'data', 'SKU_grupos_precios.xlsx'),
        os.path.join(base_dir, '..', 'data', 'SKU_grupos_precios.xlsx'),
        os.path.join('/var/task', 'data', 'SKU_grupos_precios.xlsx'),
        os.path.join(base_dir, 'SKU_grupos_precios.xlsx'),  # fallback raíz
    ]


_RE_TALLA_SLASH = re.compile(r'/\s*(3XL|2XL|3XS|2XS|XXL|XL|XS|XM|[SML])\s*/', re.IGNORECASE)
_RE_TALLA_FIN   = re.compile(r'\b(3XL|2XL|3XS|2XS|XXL|XL|XS|XM|[SML])\b\s*$', re.IGNORECASE)
_RE_TALLA_ANY   = re.compile(r'\b(3XL|2XL|3XS|2XS|XXL|XL|XS|XM|[SML])\b', re.IGNORECASE)


def extraer_talla(nombre_producto):
    """Extrae la talla de un nombre de producto. Devuelve '' si no encuentra."""
    if not nombre_producto:
        return ''
    texto = str(nombre_producto)
    m = _RE_TALLA_SLASH.search(texto)
    if m:
        return m.group(1).upper()
    m = _RE_TALLA_FIN.search(texto)
    if m:
        return m.group(1).upper()
    # Última opción: cualquier ocurrencia, pero evitamos falsos positivos
    # tipo "45L" (litros de maletero) exigiendo que NO esté pegado a un dígito.
    for m in _RE_TALLA_ANY.finditer(texto):
        antes = texto[m.start() - 1] if m.start() > 0 else ' '
        if not antes.isdigit():
            return m.group(1).upper()
    return ''


def _encontrar_excel(base_dir, ruta_excel_forzada=None, log=lambda m: None):
    if ruta_excel_forzada and os.path.exists(ruta_excel_forzada):
        return ruta_excel_forzada
    for cand in _rutas_candidatas(base_dir):
        if os.path.exists(cand):
            log(f"  📊 Excel maestro: {cand}")
            return cand
    return None


def cargar_grupos_activos(base_dir, ruta_excel=None, callback_log=None):
    """
    Lee el Excel maestro completo y devuelve:
    {
      'grupos': { grupo_foto: {...} },   # solo grupos activos y válidos
      'omitidos': {
          'categoria_excluida': int,
          'categoria_no_reconocida': set([...]),
          'sin_marca_sin_inventario': int,
          'sin_grupo_foto': int,
      }
    }
    """
    def log(m):
        if callback_log:
            callback_log(m)

    ruta = _encontrar_excel(base_dir, ruta_excel, log)
    if not ruta:
        raise FileNotFoundError(
            "No se encontró data/SKU_grupos_precios.xlsx. "
            "Verifica que el archivo esté en la carpeta data/ del repo."
        )

    wb = openpyxl.load_workbook(ruta, data_only=True)
    ws = wb[HOJA_PREFERIDA] if HOJA_PREFERIDA in wb.sheetnames else wb.worksheets[0]
    filas = list(ws.iter_rows(values_only=True))
    headers = [str(h).strip() if h else '' for h in filas[0]]

    def idx(nombre):
        return headers.index(nombre) if nombre in headers else -1

    i_sku   = idx('SKU')
    i_nom   = idx('Nombre_Producto')
    i_grupo = idx('Grupo_Foto')
    i_inv   = idx('inventario')
    i_pmay  = idx('Precio_Mayor')
    i_pdet  = idx('Precio_Detal')
    i_marca = idx('Marca')
    i_cat   = idx('Categoria')

    grupos = {}
    omitidos = {
        'categoria_excluida': 0,
        'categoria_no_reconocida': set(),
        'sin_marca_sin_inventario': 0,
        'sin_grupo_foto': 0,
    }

    for fila in filas[1:]:
        if not fila or all(v is None for v in fila):
            continue

        grupo_foto = fila[i_grupo] if i_grupo >= 0 else None
        if not grupo_foto:
            omitidos['sin_grupo_foto'] += 1
            continue
        grupo_foto = str(grupo_foto).strip()

        sku          = fila[i_sku] if i_sku >= 0 else None
        nombre       = (fila[i_nom] or '').strip() if i_nom >= 0 else ''
        inventario   = fila[i_inv] if i_inv >= 0 else 0
        inventario   = int(inventario) if isinstance(inventario, (int, float)) else 0
        precio_mayor = fila[i_pmay] if i_pmay >= 0 else None
        precio_detal = fila[i_pdet] if i_pdet >= 0 else None
        marca_raw    = fila[i_marca] if i_marca >= 0 else None
        categoria_raw = fila[i_cat] if i_cat >= 0 else None

        # Categoría: excluida o no reconocida → se descarta la fila entera.
        bucket = normalizar_categoria(categoria_raw)
        if categoria_raw and str(categoria_raw).strip().lower() in _categorias_excluidas_set():
            omitidos['categoria_excluida'] += 1
            continue
        if bucket is None:
            if categoria_raw:
                omitidos['categoria_no_reconocida'].add(str(categoria_raw).strip())
            continue

        # Marca: si no está definida, solo entra si esta fila tiene inventario.
        marca = normalizar_marca(marca_raw)
        if marca is None:
            if inventario > 0:
                marca = 'xecuro'
            else:
                omitidos['sin_marca_sin_inventario'] += 1
                continue

        if grupo_foto not in grupos:
            grupos[grupo_foto] = {
                'grupo_foto': grupo_foto,
                'marca':      marca,
                'bucket':     bucket,
                'nombre_producto': nombre,
                'skus': [],
            }
        g = grupos[grupo_foto]
        # Si hay inconsistencia de marca/bucket dentro del mismo grupo, se
        # conserva la de la fila con mayor inventario (heurística simple).
        if inventario > sum(s['inventario'] for s in g['skus']) if g['skus'] else False:
            g['marca']  = marca
            g['bucket'] = bucket

        g['skus'].append({
            'sku':          sku,
            'nombre_producto': nombre,
            'talla':        extraer_talla(nombre),
            'inventario':   inventario,
            'precio_mayor': precio_mayor,
            'precio_detal': precio_detal,
        })

    # Filtrar: solo grupos con al menos un SKU con inventario > 0
    grupos_activos = {
        gf: g for gf, g in grupos.items()
        if any(s['inventario'] > 0 for s in g['skus'])
    }

    log(f"  ✅ {len(grupos_activos)} grupos activos de {len(grupos)} grupos totales en el Excel")
    if omitidos['categoria_no_reconocida']:
        log(f"  ⚠️ Categorías no reconocidas (revisar categorias_config.py): "
            f"{sorted(omitidos['categoria_no_reconocida'])}")

    return {'grupos': grupos_activos, 'omitidos': omitidos}


def _categorias_excluidas_set():
    from categorias_config import CATEGORIAS_EXCLUIDAS
    return CATEGORIAS_EXCLUIDAS


def _nombre_para_ordenar(grupo):
    """Nombre 'limpio' usado para ordenar alfabéticamente por referencia."""
    nombre = grupo['nombre_producto'] or ''
    # Quita la talla del final/medio para que no distorsione el orden
    talla = grupo['skus'][0]['talla'] if grupo['skus'] else ''
    if talla:
        nombre = re.sub(re.escape(talla), '', nombre, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', nombre).strip().upper()


def armar_catalogo(catalogo_id, grupos_activos, callback_log=None):
    """
    Devuelve una lista ordenada de grupos para un catálogo específico:
    [(bucket_key, bucket_label, [grupo, grupo, ...]), ...]
    respetando el orden de buckets definido en categorias_config.CATALOGOS.
    """
    def log(m):
        if callback_log:
            callback_log(m)

    cfg = CATALOGOS.get(catalogo_id)
    if not cfg:
        raise ValueError(f"Catálogo desconocido: {catalogo_id}")

    marca = cfg['marca']
    grupos_de_marca = [g for g in grupos_activos.values() if g['marca'] == marca]

    resultado = []
    for bucket in cfg['buckets']:
        del_bucket = [g for g in grupos_de_marca if g['bucket'] == bucket]
        del_bucket.sort(key=_nombre_para_ordenar)
        if del_bucket:
            resultado.append((bucket, BUCKET_LABELS.get(bucket, bucket), del_bucket))

    total_grupos = sum(len(x[2]) for x in resultado)
    log(f"  📚 Catálogo '{cfg['nombre']}': {total_grupos} grupos en {len(resultado)} categorías")
    return resultado
