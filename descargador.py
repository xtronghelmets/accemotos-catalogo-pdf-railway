import os
import requests
from urllib.parse import urlparse
from PIL import Image
from io import BytesIO


def _imagen_a_jpeg(img, cache_path, max_px=800, quality=82):
    """Convierte una imagen PIL a JPEG con fondo blanco, reducida a max_px."""
    w, h = img.size
    if max(w, h) > max_px:
        img.thumbnail((max_px, max_px), Image.LANCZOS)
    if img.mode in ('RGBA', 'LA', 'P'):
        if img.mode == 'P':
            img = img.convert('RGBA')
        fondo = Image.new('RGB', img.size, (255, 255, 255))
        alpha = img.split()[-1]
        fondo.paste(img.convert('RGB'), mask=alpha)
        img = fondo
    else:
        img = img.convert('RGB')
    img.save(cache_path, 'JPEG', quality=quality, optimize=True)
    return cache_path


def descargar_imagen(urls_str, sku, nombre, carpeta_cache, callback_log=None):
    os.makedirs(carpeta_cache, exist_ok=True)
    cache_path = os.path.join(carpeta_cache, f'{sku}.jpg')

    # 1. Verificar caché JPEG existente
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 1000:
        if callback_log:
            callback_log(f"  📦 Caché: {nombre[:40]}")
        return cache_path

    # 2. Buscar imagen local en cache_imagenes con cualquier extensión (PNG, WEBP…)
    for ext in ('.png', '.jpg', '.jpeg', '.webp', '.PNG', '.JPG'):
        local = os.path.join(carpeta_cache, f'{sku}{ext}')
        if os.path.exists(local) and os.path.getsize(local) > 1000:
            try:
                img = Image.open(local)
                _imagen_a_jpeg(img, cache_path)
                if callback_log:
                    callback_log(f"  📦 Local→JPEG: {nombre[:40]}")
                return cache_path
            except Exception:
                pass

    if not urls_str or str(urls_str).strip() in ('', 'nan', 'None'):
        if callback_log:
            callback_log(f"  ⚠️ Sin URL: {nombre[:40]}")
        return None

    urls = [u.strip() for u in str(urls_str).split(',')
            if u.strip() and u.strip().startswith('http')]

    # 3. Buscar por nombre de archivo de la URL en cache (imágenes descargadas manualmente)
    for url in urls[:1]:
        url_fname = url.split('?')[0].rstrip('/').split('/')[-1]
        for ext in ('', '.jpg', '.jpeg', '.png', '.webp'):
            local = os.path.join(carpeta_cache, url_fname if not ext else
                                 os.path.splitext(url_fname)[0] + ext)
            if os.path.exists(local) and os.path.getsize(local) > 1000:
                try:
                    img = Image.open(local)
                    _imagen_a_jpeg(img, cache_path)
                    if callback_log:
                        callback_log(f"  📦 Archivo local: {nombre[:40]}")
                    return cache_path
                except Exception:
                    pass

    # 4. Descargar desde URL
    for url in urls:
        try:
            parsed = urlparse(url)
            referer = f"{parsed.scheme}://{parsed.netloc}/"
            r = requests.get(url, timeout=15,
                             headers={
                                 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                               'AppleWebKit/537.36 (KHTML, like Gecko) '
                                               'Chrome/124.0.0.0 Safari/537.36',
                                 'Referer': referer,
                                 'Accept': 'image/avif,image/webp,image/apng,image/*,*/*;q=0.8',
                             })
            if r.status_code == 200 and len(r.content) > 1000:
                img = Image.open(BytesIO(r.content))
                _imagen_a_jpeg(img, cache_path)
                if callback_log:
                    callback_log(f"  ✅ Descargada: {nombre[:40]}")
                return cache_path
        except Exception:
            continue

    if callback_log:
        callback_log(f"  ⚠️ Sin imagen: {nombre[:40]}")
    return None
