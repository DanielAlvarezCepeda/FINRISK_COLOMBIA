"""Serving del pipeline sellado; no entrena ni modifica los datos."""
from contextlib import asynccontextmanager
from hashlib import sha256
from importlib.metadata import version
from pathlib import Path
from typing import Annotated
import json
import math
import os

import joblib
import pandas as pd
from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

HERE = Path(__file__).resolve().parent
INFO = json.loads((HERE / 'model_info.json').read_text(encoding='utf-8'))
METRICS = json.loads((HERE / 'metrics.json').read_text(encoding='utf-8'))
FEATURES = INFO['variables']
MODEL_PATH = Path(os.environ.get('FINRISK_MODEL_PATH', HERE.parent / 'models' / 'bosque_aleatorio.joblib'))
# sklearn convierte entradas a float32; límites técnicos, no filtros económicos.
Ratio = Annotated[float, Field(allow_inf_nan=False, ge=-1e30, le=1e30)]

class Entrada(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True, json_schema_extra={'examples': [
        {'liquidez_corriente': 1.2, 'endeudamiento': 0.6, 'roa': 0.03, 'margen_neto': 0.05},
        {'liquidez_corriente': 0.6, 'endeudamiento': 0.95, 'roa': -0.12, 'margen_neto': -0.1}]})
    liquidez_corriente: Ratio = Field(description='Veces; ej. 1.2')
    endeudamiento: Ratio = Field(description='Razón, no porcentaje; 60% = 0.60')
    roa: Ratio = Field(description='Razón; 3% = 0.03. Admite pérdidas.')
    margen_neto: Ratio = Field(description='Razón; 5% = 0.05. Admite pérdidas.')

class Prediccion(BaseModel):
    modelo: str
    version: str
    objetivo: str
    puntaje: float
    umbral: float
    alerta: bool
    clasificacion: str
    puntaje_calibrado: bool
    advertencia: str


def load_pipeline():
    if not MODEL_PATH.is_file():
        raise RuntimeError('Modelo no encontrado: ' + str(MODEL_PATH))
    actual = sha256(MODEL_PATH.read_bytes()).hexdigest()
    if actual != INFO['sha256_modelo']:
        raise RuntimeError('SHA-256 no coincide con el pipeline optimizado. No se cargará.')
    mismatch = {p: {'esperada': v, 'instalada': version(p)} for p, v in INFO['versiones_entrenamiento'].items() if version(p) != v}
    if mismatch:
        raise RuntimeError('Entorno distinto del entrenamiento: ' + json.dumps(mismatch) + '. Instale requirements-api.txt.')
    # joblib solo se usa con el artefacto confiable, identificado por su hash sellado.
    model = joblib.load(MODEL_PATH)
    if list(model.feature_names_in_) != FEATURES or list(model.classes_) != [0, 1]:
        raise RuntimeError('Esquema o clases del modelo incompatibles.')
    score(model, {'liquidez_corriente': 1.2, 'endeudamiento': .6, 'roa': .03, 'margen_neto': .05})
    return model


def score(model, values):
    frame = pd.DataFrame([[values[name] for name in FEATURES]], columns=FEATURES)
    s = float(model.predict_proba(frame)[0, 1])
    if not math.isfinite(s) or not 0 <= s <= 1:
        raise RuntimeError('Puntaje inválido del pipeline.')
    return s


def create_app(loader=load_pipeline):
    @asynccontextmanager
    async def lifespan(app):
        app.state.pipeline = loader()
        yield
    app = FastAPI(title='FINRISK Colombia API', version='1.0.0', description=INFO['advertencia'], lifespan=lifespan)

    @app.get('/health', tags=['Servicio'])
    def health(request: Request):
        if getattr(request.app.state, 'pipeline', None) is None:
            raise HTTPException(status_code=503, detail='Modelo no disponible')
        return {'status': 'ok', 'modelo': INFO['modelo'], 'version': INFO['version'], 'sha256_modelo': INFO['sha256_modelo']}

    @app.get('/model/info', tags=['Modelo'])
    def model_info():
        return INFO

    @app.get('/metrics', tags=['Modelo'])
    def metrics():
        return METRICS

    @app.post('/predict', response_model=Prediccion, tags=['Inferencia'])
    def predict(entrada: Entrada, request: Request):
        try:
            s = score(request.app.state.pipeline, entrada.model_dump())
        except (ValueError, OverflowError, RuntimeError) as exc:
            raise HTTPException(status_code=500, detail='No fue posible calcular un puntaje válido.') from exc
        alerta = s >= INFO['umbral']
        return Prediccion(modelo=INFO['modelo'], version=INFO['version'], objetivo=INFO['objetivo'], puntaje=s, umbral=INFO['umbral'], alerta=alerta, clasificacion='Con alerta para revisión' if alerta else 'Sin alerta según el umbral', puntaje_calibrado=False, advertencia=INFO['advertencia'])

    return app

app = create_app()
