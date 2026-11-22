"""Aplicación local integrada. Los endpoints de inferencia no se modifican."""
from pathlib import Path
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from api.main import app

DASHBOARD = Path(__file__).resolve().parents[1] / 'dashboard'

@app.get('/', include_in_schema=False)
def home():
    return RedirectResponse('/dashboard/')

app.mount('/dashboard', StaticFiles(directory=DASHBOARD, html=True), name='dashboard')
