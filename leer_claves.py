"""
leer_claves.py
Lee las credenciales de WooCommerce desde API_key.txt.
"""
import os
import re


def leer_claves(ruta=None):
    """
    Parsea API_key.txt y devuelve un dict con las claves de cada tienda.
    Formato esperado:
        https://xtronghelmets.com/
            clave del cliente: ck_...
            clave secreta del cliente: cs_...
        https://xecurohelmets.com/
            clave del cliente: ck_...
            clave secreta del cliente: cs_...
    """
    if ruta is None:
        base = os.path.dirname(os.path.abspath(__file__))
        ruta = os.path.join(base, 'API_key.txt')

    resultado = {}
    url_actual = None

    with open(ruta, 'r', encoding='utf-8') as f:
        for linea in f:
            linea = linea.strip()
            if not linea:
                continue

            # Detectar URL de tienda
            if linea.startswith('http'):
                url_actual = linea.rstrip('/')
                resultado[url_actual] = {'ck': '', 'cs': ''}
                continue

            if url_actual is None:
                continue

            # Clave del cliente (consumer key)
            m = re.search(r'clave del cliente[:\s]+(ck_\S+)', linea, re.IGNORECASE)
            if m:
                resultado[url_actual]['ck'] = m.group(1)
                continue

            # Clave secreta (consumer secret)
            m = re.search(r'clave secreta[:\s]+(cs_\S+)', linea, re.IGNORECASE)
            if m:
                resultado[url_actual]['cs'] = m.group(1)

    return resultado


def obtener_credenciales(marca):
    """
    Devuelve (url, ck, cs) para la marca indicada ('xtrong' o 'xecuro').
    """
    claves = leer_claves()
    mapping = {
        'xtrong': 'https://xtronghelmets.com',
        'xecuro': 'https://xecurohelmets.com',
    }
    url = mapping.get(marca, '')
    datos = claves.get(url, {})
    return url, datos.get('ck', ''), datos.get('cs', '')
