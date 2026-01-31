from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

def mount_static_files(app: FastAPI):
    """Statik dosyaları monte eder."""
    # Static dosyalar için klasör (AI tarafından üretilen görseller için)
    # app/core/static.py -> app/core -> app -> root -> static
    # Yani 3 seviye yukarı çıkmamız lazım proje yapısına göre.
    # Ancak güvenli bir şekilde app klasörünün bir üstüne çıkıp 'static' bulmak daha doğru.
    
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    static_dir = os.path.join(project_root, "static")
    
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
