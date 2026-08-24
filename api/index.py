import sys
import os

# Agregar el directorio raíz del proyecto al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app_web import app

# Vercel busca esta variable
handler = app
