# -*- coding: utf-8 -*-
"""
fuentes_marca.py

Registra en ReportLab las fuentes TTF de cada marca (Kanit para Xtrong,
Sora para Xecuro), buscándolas de forma flexible dentro de assets/ —
la carpeta real se llama "Fuentes de texto" (con espacios y mayúscula),
pero también se prueban 'fonts' y 'Fuentes' por si cambia a futuro.

Si no encuentra los .ttf, cae en Helvetica sin romper la generación.
"""
import os
import unicodedata
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

_CACHE = {}


def _sin_tildes(s):
    return ''.join(c for c in unicodedata.normalize('NFD', s)
                   if unicodedata.category(c) != 'Mn')


def _norm(s):
    return _sin_tildes(s).upper().replace(' ', '').replace('_', '').replace('-', '')


def _buscar_ttf(carpeta, patrones):
    """Busca un .ttf cuyo nombre normalizado contenga alguno de los patrones."""
    if not os.path.isdir(carpeta):
        return None
    for archivo in os.listdir(carpeta):
        if not archivo.lower().endswith('.ttf'):
            continue
        norm = _norm(archivo)
        for patron in patrones:
            if patron in norm:
                return os.path.join(carpeta, archivo)
    return None


def _carpeta_fuentes(carpeta_assets):
    candidatos = [
        os.path.join(carpeta_assets, 'Fuentes de texto'),
        os.path.join(carpeta_assets, 'fonts'),
        os.path.join(carpeta_assets, 'Fuentes'),
        carpeta_assets,
    ]
    for c in candidatos:
        if os.path.isdir(c) and any(f.lower().endswith('.ttf') for f in os.listdir(c)):
            return c
    return carpeta_assets


def registrar_fuentes_marca(marca, carpeta_assets, callback_log=None):
    """
    Devuelve {'bold': nombre_fuente_reportlab, 'regular': nombre_fuente_reportlab}
    para la marca dada, registrando los TTF encontrados. Cachea por
    (marca, carpeta_assets) para no releer disco en cada página.
    """
    def log(m):
        if callback_log:
            callback_log(m)

    cache_key = (marca, carpeta_assets)
    if cache_key in _CACHE:
        return _CACHE[cache_key]

    carpeta = _carpeta_fuentes(carpeta_assets)
    familia = 'KANIT' if marca == 'xtrong' else 'SORA'
    resultado = {'bold': 'Helvetica-Bold', 'regular': 'Helvetica'}

    especificaciones = [
        ('bold',    [familia + 'BOLD'],                       f'{familia.title()}-Bold'),
        ('regular', [familia + 'REGULAR', familia + 'MEDIUM', familia], f'{familia.title()}-Regular'),
    ]
    for peso, patrones, nombre_reg in especificaciones:
        ruta = _buscar_ttf(carpeta, patrones)
        if ruta:
            try:
                pdfmetrics.registerFont(TTFont(nombre_reg, ruta))
                resultado[peso] = nombre_reg
                log(f"  ✅ Fuente {nombre_reg} ({os.path.basename(ruta)})")
            except Exception as e:
                log(f"  ⚠️ No se pudo registrar {nombre_reg}: {e}")
        else:
            log(f"  ⚠️ No se encontró .ttf de {familia} ({peso}) en {carpeta} — uso Helvetica")

    _CACHE[cache_key] = resultado
    return resultado
