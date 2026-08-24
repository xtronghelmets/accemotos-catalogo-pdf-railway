# -*- coding: utf-8 -*-
"""
categorias_config.py

Fuente única de verdad para:
- Cómo se decide, a partir de la columna I del Excel ("categoria catalogo") y
  la marca, EN CUÁL de los 4 catálogos (botones del front) cae cada producto.
- Cómo se ordenan las secciones (subcategorías, columna J) dentro de cada PDF.

Diseño (nuevo Excel data/data.xlsx, hoja "Hoja Catalogo"):

    Columna I  → "categoria catalogo"  → define el catálogo/botón:
        · XTRONG + 'cascos integrales'          → xtrong_integrales
        · XTRONG + 'otros cascos'               → xtrong_otros_cascos
        · XTRONG + 'accesorios y complementos'  → xtrong_accesorios
        · XECURO + (cualquiera)                 → xecuro_general

    Columna J  → "subategoria Catalogo" → sección/encabezado DENTRO del PDF
                 (Guantes, Chaquetas, Cascos Integrales, etc.). El orden final
                 lo fija ORDEN_SUBCATEGORIA.

Editar este archivo es la única forma en que debería cambiar la organización
de los catálogos — el resto del código no debe tener nombres "quemados".
"""
import unicodedata


# ── Los 4 catálogos = 4 botones del front ────────────────────────────────────
# (id, nombre_display, marca). El id es estable aunque cambie el texto.

CATALOGOS = {
    'xecuro_general': {
        'marca':  'xecuro',
        'nombre': 'XECURO — Catálogo general',
    },
    'xecuro_repuestos': {
        'marca':  'xecuro',
        'nombre': 'Repuestos',
    },
    'xtrong_integrales': {
        'marca':  'xtrong',
        'nombre': 'Cascos cerrados',
    },
    'xtrong_otros_cascos': {
        'marca':  'xtrong',
        'nombre': 'Abiertos y abatibles',
    },
    'xtrong_accesorios': {
        'marca':  'xtrong',
        'nombre': 'Accesorios y complementos',
    },
    'xtrong_repuestos': {
        'marca':  'xtrong',
        'nombre': 'Repuestos',
    },
}


# ── Normalización de texto (para comparar sin tildes/mayúsculas/espacios) ─────

def _norm(s):
    if s is None:
        return ''
    s = str(s).strip().lower()
    s = ''.join(c for c in unicodedata.normalize('NFD', s)
                if unicodedata.category(c) != 'Mn')
    return ' '.join(s.split())  # colapsa espacios múltiples


# ── Columna I ("categoria catalogo") → catálogo, para XTRONG ─────────────────
# Para XECURO todo va al único catálogo general, sin importar la columna I.

CATEGORIA_CATALOGO_XTRONG = {
    'cascos integrales':        'xtrong_integrales',
    'otros cascos':             'xtrong_otros_cascos',
    'accesorios y complementos': 'xtrong_accesorios',
    'repuestos':                'xtrong_repuestos',
}


# ── Excepciones por subcategoría (columna J) que MANDAN sobre la columna I ────
# Los cascos multipropósito vienen marcados en la columna I como 'otros cascos',
# pero deben publicarse en el catálogo de cascos cerrados (integrales). Esta
# tabla fuerza ese enrutamiento a partir de la subcategoría (columna J).
SUBCATEGORIA_A_CATALOGO_XTRONG = {
    'cascos multiproposito': 'xtrong_integrales',
}


def normalizar_marca(valor_crudo):
    """
    Devuelve 'xtrong', 'xecuro', o None (marca ambigua / vacía).
    Trata 'XECURO PRO' / 'XECURO-PRO' como xecuro y 'XTRONG GP' como xtrong:
    son líneas de la marca base, no marcas distintas.
    """
    if not valor_crudo:
        return None
    limpio = str(valor_crudo).strip().lower()
    if limpio.startswith('xtrong'):
        return 'xtrong'
    if limpio.startswith('xecuro'):
        return 'xecuro'
    return None


def catalogo_asignado(marca, categoria_catalogo, subcategoria=None):
    """
    Decide en qué catálogo (id de CATALOGOS) cae un producto a partir de su
    marca normalizada, el texto de la columna I y (opcionalmente) la
    subcategoría de la columna J. Devuelve None si no aplica.

    - XECURO: 'xecuro_repuestos' si la columna I es 'repuestos'; en cualquier
      otro caso, 'xecuro_general' (un solo catálogo para el resto de la marca).
    - XTRONG: por defecto según la columna I (integrales / otros cascos /
      accesorios / repuestos), pero la subcategoría (columna J) puede forzar
      otro catálogo — p.ej. 'cascos multiproposito' va al catálogo de cascos
      cerrados.
    - Marca None: se infiere de las columnas para no perder el producto.
    """
    cat = _norm(categoria_catalogo)
    sub = _norm(subcategoria)

    if marca == 'xecuro':
        if cat == 'repuestos':
            return 'xecuro_repuestos'
        return 'xecuro_general'
    if marca == 'xtrong':
        # La subcategoría (columna J) manda sobre la columna I si aplica.
        if sub in SUBCATEGORIA_A_CATALOGO_XTRONG:
            return SUBCATEGORIA_A_CATALOGO_XTRONG[sub]
        return CATEGORIA_CATALOGO_XTRONG.get(cat)

    # Marca no reconocida: inferir por las columnas para no perder el producto.
    if sub in SUBCATEGORIA_A_CATALOGO_XTRONG:
        return SUBCATEGORIA_A_CATALOGO_XTRONG[sub]
    if cat in ('cascos integrales', 'otros cascos', 'repuestos'):
        return CATEGORIA_CATALOGO_XTRONG.get(cat)
    return 'xecuro_general'


# ── Orden de secciones (columna J) dentro de cada PDF ────────────────────────
# El texto de la columna J se usa TAL CUAL como encabezado de sección. Esta
# lista solo fija el ORDEN; las subcategorías no listadas van al final, en
# orden alfabético. Se compara normalizado (sin tildes/mayúsculas).

ORDEN_SUBCATEGORIA = [
    # Cascos — el catálogo de cerrados muestra primero los integrales y luego,
    # como bloque propio, los multipropósito.
    'cascos integrales',
    'cascos multiproposito',
    'cascos',
    'cascos abatibles',
    'cascos abiertos',
    # Accesorios y complementos
    'guantes',
    'chaquetas',
    'impermeables',
    'body armors',
    'rodilleras',
    'intercomunicadores',
    'candados',
    'antiempanantes',
    'bases maletero',
    # Repuestos
    'visores',
    'mecanismos',
    'ventilaciones',
    'repuestos intercomunicador',
    'spoilers',
    'tornillos',
]


def orden_subcategoria(subcategoria):
    """Clave de orden para una subcategoría (columna J)."""
    n = _norm(subcategoria)
    if n in ORDEN_SUBCATEGORIA:
        return (0, ORDEN_SUBCATEGORIA.index(n), n)
    return (1, 0, n)  # desconocidas al final, alfabético


def catalogos_de_marca(marca):
    """Devuelve [(catalogo_id, config), ...] para una marca dada."""
    return [(k, v) for k, v in CATALOGOS.items() if v['marca'] == marca]
