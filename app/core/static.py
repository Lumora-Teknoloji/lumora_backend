from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import os

def mount_static_files(app: FastAPI):
    """Statik dosyaları monte eder."""
    from app.routers.scraper_bots import get_scrapper_dir
    
    # Scraper screenshotları Scrapper/static/captures altında
    static_dir = os.path.join(str(get_scrapper_dir()), "static")
    
    os.makedirs(static_dir, exist_ok=True)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

