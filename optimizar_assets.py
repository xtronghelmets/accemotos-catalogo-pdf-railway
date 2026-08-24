"""
optimizar_assets.py
Ejecutar UNA VEZ localmente para convertir los PNGs de portadas/fondos a JPEG optimizados.
Deja los archivos originales intactos y crea versiones _opt.jpg en la misma carpeta.

USO:
    python optimizar_assets.py

Luego subir los archivos _opt.jpg al repo (reemplazar las referencias en generador_web.py).
"""
import os
from PIL import Image

# Archivos a optimizar — ajusta la ruta si es necesario
CARPETAS = [
    'assets/xtrong',
    'assets/xecuro',
]

# Archivos objetivo (portadas, contraportadas, fondos de página)
TARGETS = [
    'PORTADA ABATIBLES-ABIERTOS.png',
    'CONTRAPORTADA ABATIBLES-ABIERTOS.png',
    'PORTADA INTEGRALES.png',
    'CONTRA PORTADA INTEGRALES.png',
    'PORTADA TEXTILES Y ACCESORIOS.png',
    'CONTRA PORTADA TEXTILES Y ACCESORIOS.png',
    'PLANTILLA HOJA.png',
    'PORTADA XECURO.png',
    'CONTRAPORTADA XECURO.png',
    'PÁGINA XECURO.png',
    'PÁGINA XECURO PRO.png',
]

MAX_PX = 1200  # px máximo en el lado mayor — suficiente para PDF A4

def optimizar(src_path):
    base, _ = os.path.splitext(src_path)
    dest = base + '_opt.jpg'
    if os.path.exists(dest):
        print(f'  ✓ Ya existe: {dest}')
        return dest
    try:
        img = Image.open(src_path)
        w, h = img.size
        print(f'  Abriendo {os.path.basename(src_path)} ({w}x{h}, {img.mode})')
        # Reducir si necesario
        if max(w, h) > MAX_PX:
            if w >= h:
                new_w, new_h = MAX_PX, int(h * MAX_PX / w)
            else:
                new_w, new_h = int(w * MAX_PX / h), MAX_PX
            img = img.resize((new_w, new_h), Image.LANCZOS)
            print(f'    → Redimensionado a {new_w}x{new_h}')
        # Aplanar alpha
        if img.mode in ('RGBA', 'LA', 'P'):
            if img.mode == 'P':
                img = img.convert('RGBA')
            fondo = Image.new('RGB', img.size, (255, 255, 255))
            fondo.paste(img.convert('RGB'), mask=img.split()[-1])
            img = fondo
        else:
            img = img.convert('RGB')
        img.save(dest, 'JPEG', quality=90, optimize=True)
        size_kb = os.path.getsize(dest) / 1024
        print(f'  ✅ Guardado: {dest} ({size_kb:.0f} KB)')
        return dest
    except Exception as e:
        print(f'  ❌ Error: {e}')
        return None

if __name__ == '__main__':
    base_dir = os.path.dirname(os.path.abspath(__file__))
    convertidos = []
    for carpeta in CARPETAS:
        carpeta_abs = os.path.join(base_dir, carpeta)
        if not os.path.isdir(carpeta_abs):
            print(f'⚠️  Carpeta no encontrada: {carpeta_abs}')
            continue
        print(f'\n📁 {carpeta}')
        archivos = os.listdir(carpeta_abs)
        for fname in TARGETS:
            # Buscar por nombre exacto o similar
            match = None
            for a in archivos:
                if a.lower().replace(' ', '') == fname.lower().replace(' ', ''):
                    match = a
                    break
            if match:
                src = os.path.join(carpeta_abs, match)
                result = optimizar(src)
                if result:
                    convertidos.append(result)
            # else: no está en esta carpeta, ignorar

    print(f'\n✅ {len(convertidos)} archivos optimizados.')
    print('\nPróximo paso:')
    print('  1. Sube los archivos _opt.jpg al repo de GitHub')
    print('  2. Actualiza ASSETS_POR_TIPO en generador_web.py para usar los _opt.jpg')
