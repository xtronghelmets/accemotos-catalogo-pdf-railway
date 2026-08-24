GENERADOR DE CATÁLOGOS — XTRONG / XECURO
==========================================
App web Flask para generar catálogos PDF desde la API de WooCommerce.
Deploy en Vercel (serverless).

ESTRUCTURA DEL PROYECTO
------------------------
catalogo_web/
├── api/
│   └── index.py              ← Entry point Vercel (serverless)
├── app_web.py                ← Lógica Flask principal
├── woo_api.py                ← Integración API WooCommerce
├── generador_web.py          ← Motor de generación PDF
├── generador.py              ← Utilidades de dibujo (heredado)
├── lector_excel.py           ← Limpieza de datos
├── descargador.py            ← Descargador de imágenes con caché
├── vercel.json               ← Configuración de Vercel
├── requirements.txt          ← Dependencias Python
├── templates/
│   └── index.html
├── static/
│   ├── css/style.css
│   └── js/app.js
└── assets/
    ├── xtrong/               ← logo.png, PORTADA.jpg, CONTRAPORTADA.jpg, fuentes TTF
    └── xecuro/               ← logo.png, PORTADA.jpg, CONTRAPORTADA.jpg, fuentes TTF

ASSETS REQUERIDOS POR MARCA
-----------------------------
assets/xtrong/
  - logo.png
  - PORTADA.jpg
  - CONTRAPORTADA.jpg
  - Kanit-Bold.ttf

assets/xecuro/
  - logo.png
  - PORTADA.jpg
  - CONTRAPORTADA.jpg
  - Sora-Regular.ttf

DEPLOY EN VERCEL
-----------------
1. Crear cuenta en https://vercel.com (gratis)
2. Instalar Vercel CLI:
     npm install -g vercel
3. En la carpeta del proyecto, ejecutar:
     vercel login
     vercel --prod
4. Configurar variables de entorno en el dashboard de Vercel
   (Settings → Environment Variables):
     XTRONG_URL  = https://xtronghelmets.com
     XTRONG_CK   = ck_188b0143...
     XTRONG_CS   = cs_211c60d8...
     XECURO_URL  = https://xecurohelmets.com
     XECURO_CK   = ck_55ad8fee...
     XECURO_CS   = cs_3d38ae6a...
5. Subir los assets a la carpeta assets/ antes del deploy
   (las fuentes TTF y portadas NO van en el repo si es público)

ALTERNATIVA: Deploy desde GitHub
----------------------------------
1. Subir el proyecto a un repo de GitHub
2. En vercel.com → "New Project" → importar el repo
3. Vercel detecta automáticamente el vercel.json
4. Configurar las variables de entorno en el dashboard
5. Cada push a main hace deploy automático

NOTAS IMPORTANTES DE VERCEL
-----------------------------
- Los PDFs se generan en /tmp y se descargan en la misma sesión.
  No quedan almacenados de forma permanente.
- El caché de imágenes también vive en /tmp (se pierde entre deploys,
  pero acelera múltiples generaciones en la misma sesión).
- Límite de tiempo: plan gratuito = 10 seg, plan Pro = 60 seg.
  Para catálogos grandes (>50 productos con imágenes nuevas) 
  se recomienda el plan Pro o pre-cachear las imágenes.

DESARROLLO LOCAL
-----------------
pip install -r requirements.txt
python app_web.py
→ Abrir http://localhost:5000

NOMBRE DEL PDF GENERADO
-------------------------
CatalogoXTRONG_CascosIntegrales_Junio2025-S1_20250603-1042.pdf
