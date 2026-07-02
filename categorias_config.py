# -*- coding: utf-8 -*-
"""
categorias_config.py

Fuente única de verdad para:
- Cómo se normaliza la columna Categoria del Excel maestro hacia "buckets" comerciales.
- En qué orden aparecen esos buckets dentro de cada PDF.
- Cómo se reparten los buckets entre los catálogos de XTRONG (3 PDFs) y XECURO (1 PDF).
- Qué categorías se excluyen por completo (repuestos sueltos, visores).

Editar este archivo es la única forma en que debería cambiar la organización
de los catálogos — el resto del código (lector_maestro.py, generador_web.py)
no debe tener nombres de categorías "quemados".
"""

# ── Buckets comerciales (claves internas estables) ─────────────────────────
# Las claves nunca cambian aunque cambie el texto que se muestra en el PDF.

CASCOS_INTEGRALES = 'cascos_integrales'
CASCOS_ABATIBLES  = 'cascos_abatibles'
CASCOS_ABIERTOS   = 'cascos_abiertos'
CASCOS_CROSS      = 'cascos_cross'          # Cross / Enduro / Multipropósito
IMPERMEABLES      = 'impermeables'
GUANTES           = 'guantes'
CHAQUETAS         = 'chaquetas'
BOTAS             = 'botas'
PROTECCION        = 'proteccion'            # rodilleras, coderas, body armor
INTERCOMUNICADORES = 'intercomunicadores'
MALETEROS         = 'maleteros'
GAFAS             = 'gafas'
CANDADOS          = 'candados'
ACCESORIOS        = 'accesorios'
COMPLEMENTOS      = 'complementos'

BUCKET_LABELS = {
    CASCOS_INTEGRALES:  'Integrales',
    CASCOS_ABATIBLES:   'Abatibles',
    CASCOS_ABIERTOS:    'Abiertos',
    CASCOS_CROSS:       'Cross / Enduro / Multipropósito',
    IMPERMEABLES:       'Impermeables',
    GUANTES:            'Guantes',
    CHAQUETAS:          'Chaquetas',
    BOTAS:              'Botas',
    PROTECCION:         'Protección',
    INTERCOMUNICADORES: 'Intercomunicadores',
    MALETEROS:          'Maleteros',
    GAFAS:              'Gafas',
    CANDADOS:           'Candados',
    ACCESORIOS:         'Accesorios',
    COMPLEMENTOS:       'Complementos',
}

# Buckets que corresponden a "tipo de casco" (tienen su propio sub-orden
# dentro de la categoría Cascos). El resto son buckets planos.
BUCKETS_CASCO = [CASCOS_INTEGRALES, CASCOS_ABATIBLES, CASCOS_ABIERTOS, CASCOS_CROSS]

# ── Mapeo Categoria (texto crudo del Excel, en minúsculas y sin espacios
#    extra) → bucket. Incluye las variantes con typo que aparecen en los
#    datos reales (mecnismos, spiler) para que no se cuelen como huérfanas. ──
CATEGORIA_A_BUCKET = {
    'integral':            CASCOS_INTEGRALES,
    'abatible':             CASCOS_ABATIBLES,
    'abierto':              CASCOS_ABIERTOS,
    'multiproposito':       CASCOS_CROSS,
    'impermeables':         IMPERMEABLES,
    'guantes':               GUANTES,
    'chaquetas':             CHAQUETAS,
    'botas':                 BOTAS,
    'rodilleras':            PROTECCION,
    'body armor':            PROTECCION,
    'intercomunicadores':    INTERCOMUNICADORES,
    'maleteros':             MALETEROS,
    'gafas':                 GAFAS,
    'candados':              CANDADOS,
    'accesorios':            ACCESORIOS,
    'complementos':          COMPLEMENTOS,
}

# Categorías que se excluyen por completo de la generación de catálogos
# (repuestos sueltos y visores, por decisión explícita del negocio).
CATEGORIAS_EXCLUIDAS = {
    'mecanismo', 'mecnismos', 'spiler', 'spoiler',
    'tapas', 'tornillos', 'sistemas', 'visor',
}


def normalizar_categoria(valor_crudo):
    """
    Convierte el texto crudo de la columna Categoria en un bucket interno.
    Devuelve None si la categoría está excluida o no se reconoce
    (no reconocida = se trata igual que excluida, pero se loguea aparte
    para que el usuario la revise).
    """
    if not valor_crudo:
        return None
    limpio = str(valor_crudo).strip().lower()
    if limpio in CATEGORIAS_EXCLUIDAS:
        return None
    return CATEGORIA_A_BUCKET.get(limpio)  # None si no está mapeada


# ── Normalización de Marca ──────────────────────────────────────────────────

def normalizar_marca(valor_crudo):
    """
    Devuelve 'xtrong', 'xecuro', o None (marca ambigua / vacía / 'Sin marca').
    Trata 'XECURO PRO' como xecuro y 'XTRONG GP' como xtrong: son líneas de
    la marca base, no marcas distintas.
    """
    if not valor_crudo:
        return None
    limpio = str(valor_crudo).strip().lower()
    if limpio.startswith('xtrong'):
        return 'xtrong'
    if limpio.startswith('xecuro'):
        return 'xecuro'
    return None  # 'sin marca', vacío, o cualquier otra cosa no reconocida


# ── Estructura de catálogos ──────────────────────────────────────────────────
# Cada catálogo es: (id, nombre_display, marca, lista_de_buckets_en_orden)
# El orden de la lista de buckets ES el orden final en el PDF.

ORDEN_BUCKETS_XECURO = [
    CASCOS_INTEGRALES, CASCOS_ABATIBLES, CASCOS_ABIERTOS, CASCOS_CROSS,
    IMPERMEABLES, GUANTES, CHAQUETAS, BOTAS, PROTECCION,
    INTERCOMUNICADORES, MALETEROS, GAFAS, CANDADOS, ACCESORIOS, COMPLEMENTOS,
]

ORDEN_BUCKETS_XTRONG_PDF2 = [CASCOS_ABIERTOS, CASCOS_CROSS, CASCOS_ABATIBLES]

ORDEN_BUCKETS_XTRONG_PDF3 = [
    IMPERMEABLES, GUANTES, CHAQUETAS, BOTAS, PROTECCION,
    INTERCOMUNICADORES, MALETEROS, GAFAS, CANDADOS, ACCESORIOS, COMPLEMENTOS,
]

CATALOGOS = {
    'xecuro_general': {
        'marca':   'xecuro',
        'nombre':  'XECURO — Catálogo general',
        'buckets': ORDEN_BUCKETS_XECURO,
    },
    'xtrong_integrales': {
        'marca':   'xtrong',
        'nombre':  'XTRONG — Cascos integrales (cerrados)',
        'buckets': [CASCOS_INTEGRALES],
    },
    'xtrong_otros_cascos': {
        'marca':   'xtrong',
        'nombre':  'XTRONG — Otros cascos (abiertos, cross, abatibles)',
        'buckets': ORDEN_BUCKETS_XTRONG_PDF2,
    },
    'xtrong_accesorios': {
        'marca':   'xtrong',
        'nombre':  'XTRONG — Accesorios y complementos',
        'buckets': ORDEN_BUCKETS_XTRONG_PDF3,
    },
}


def catalogos_de_marca(marca):
    """Devuelve [(catalogo_id, config), ...] para una marca dada."""
    return [(k, v) for k, v in CATALOGOS.items() if v['marca'] == marca]


def bucket_de(marca, categoria_bucket):
    """Encuentra en qué catálogo(s) de esa marca cae un bucket dado."""
    resultado = []
    for cat_id, cfg in catalogos_de_marca(marca):
        if categoria_bucket in cfg['buckets']:
            resultado.append(cat_id)
    return resultado
