import sys
import os

# Ajustar path al directorio de la app
app_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, app_dir)

from app_web import app as application
