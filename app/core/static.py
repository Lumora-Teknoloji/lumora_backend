from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

def mount_static_files(app: FastAPI):
    """Statik dosyaları monte eder."""
    # app/core/static.py -> app/core -> app -> LangChain_backend -> Analiz-Motoru (Root)
    backend_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    project_root = os.path.dirname(backend_root) 
    
    # Scraper screenshotları Scrapper/static/captures altında
    static_dir = os.path.join(project_root, "Scrapper", "static")
    
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")
