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
    'xtrong_integrales': {
        'marca':  'xtrong',
        'nombre': 'XTRONG — Cascos integrales (cerrados)',
    },
    'xtrong_otros_cascos': {
        'marca':  'xtrong',
        'nombre': 'XTRONG — Otros cascos (abiertos, cross, abatibles)',
    },
    'xtrong_accesorios': {
        'marca':  'xtrong',
        'nombre': 'XTRONG — Accesorios y complementos',
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


def catalogo_asignado(marca, categoria_catalogo):
    """
    Decide en qué catálogo (id de CATALOGOS) cae un producto a partir de su
    marca normalizada y el texto de la columna I. Devuelve None si no aplica.

    - XECURO: siempre 'xecuro_general' (un solo catálogo para la marca).
    - XTRONG: según la columna I (integrales / otros cascos / accesorios).
    - Marca None: se infiere de la columna I (las categorías de casco XTRONG
      van a XTRONG; el resto, a XECURO general).
    """
    cat = _norm(categoria_catalogo)

    if marca == 'xecuro':
        return 'xecuro_general'
    if marca == 'xtrong':
        return CATEGORIA_CATALOGO_XTRONG.get(cat)

    # Marca no reconocida: inferir por la columna I para no perder el producto.
    if cat in ('cascos integrales', 'otros cascos'):
        return CATEGORIA_CATALOGO_XTRONG.get(cat)
    return 'xecuro_general'


# ── Orden de secciones (columna J) dentro de cada PDF ────────────────────────
# El texto de la columna J se usa TAL CUAL como encabezado de sección. Esta
# lista solo fija el ORDEN; las subcategorías no listadas van al final, en
# orden alfabético. Se compara normalizado (sin tildes/mayúsculas).

ORDEN_SUBCATEGORIA = [
    # Cascos
    'cascos integrales',
    'cascos',
    'cascos abatibles',
    'cascos multiproposito',
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
