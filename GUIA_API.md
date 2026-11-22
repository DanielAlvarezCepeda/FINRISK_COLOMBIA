# FINRISK Colombia | Etapa 6: API de inferencia

La API forma parte de la entrega final del repositorio. No sustituye `requirements.txt` ni los scripts de entrenamiento. El modelo aportado coincide por SHA-256 con la selección sellada en la segunda entrega.

## 1. Preparación en Windows

Desde la raíz del repositorio actualizado, obtener el modelo optimizado de MLflow por un canal autorizado y guardarlo en `models/bosque_aleatorio.joblib`. No subir el joblib a GitHub público. La regla de `models/.gitignore` protege el archivo. Conservar el original también en un almacenamiento autorizado.

```powershell
py -0p
py -3.12 -m venv .venv-api
.\.venv-api\Scripts\python.exe -m pip install -r requirements-api-test.txt
Get-FileHash .\models\bosque_aleatorio.joblib -Algorithm SHA256
.\.venv-api\Scripts\python.exe -m unittest discover -s tests -p test_api_finrisk.py -v
.\.venv-api\Scripts\python.exe -m uvicorn api.main:app --host 127.0.0.1 --port 8000
```

Si Python 3.12 no está disponible, confirmar primero las versiones instaladas. No sustituir scikit-learn por otra versión silenciosamente. Si la instalación de las dependencias fijadas falla, conservar el error para revisar el entorno real de entrenamiento. La API comprueba versiones y hash antes de cargar el modelo. No se efectuó ningún nuevo entrenamiento.

## 2. Prueba manual

Navegar a http://127.0.0.1:8000/docs. Abrir POST /predict, Try it out, Execute. Ejemplo sintético:

```json
{"liquidez_corriente":1.2,"endeudamiento":0.60,"roa":0.03,"margen_neto":0.05}
```

Los índices de endeudamiento, ROA y margen son razones (60% = 0.60). Liquidez se expresa en veces. Los cuatro campos son obligatorios; no se envían NIT ni otros identificadores. El resultado se compara con el umbral sellado 0.4586231433634672 y se interpreta como puntaje no calibrado, no probabilidad de primera admisión. No usar para decisiones automáticas de crédito.

En otra ventana de PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
$body = @{liquidez_corriente=1.2;endeudamiento=0.60;roa=0.03;margen_neto=0.05} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/predict -ContentType 'application/json' -Body $body
```

Los endpoints /model/info y /metrics presentan la trazabilidad y métricas archivadas, no resultados recalculados. Guardar capturas de las pruebas y Swagger. La prueba de 2024 ya fue consultada en el piloto inicial: no es una evaluación independiente del modelo optimizado.

## 3. Docker (opcional, validado localmente y en EC2)

Desde la raíz: `docker build -f Dockerfile.api -t finrisk-api:1.0 .` y `docker run --rm -p 127.0.0.1:8000:8000 finrisk-api:1.0`. No ejecutar si ya hay otro servicio usando el puerto 8000. No subir la imagen con el modelo a un registro público sin autorización. Añadir al contexto de Docker un `.dockerignore` que excluya todos los datos, cachés, entornos virtuales, credenciales y archivos ajenos a esta API; se incluye `Dockerfile.api.dockerignore` específico para este Dockerfile. Para ejecutar la integración completa y el despliegue ver `GUIA_DOCKER.md`. Preferir proxy de mismo origen y HTTPS; no abrir MLflow a Internet sin autenticación.

## 4. Git

Antes de agregar archivos: verificar `git check-ignore models/bosque_aleatorio.joblib`. Agregar únicamente `api`, `models/.gitignore`, `tests/test_api_finrisk.py`, los dos nuevos requirements, Dockerfile.api, Dockerfile.api.dockerignore y esta guía. Excluir `.venv-api/` localmente. Revisar `git diff --cached --stat` y confirmar qué se publicará. No usar `git add .` sin revisar.

Fuente: `results/piloto_optimizado/seleccion_sellada.json`, `registro_mlflow.json`, `resultado_prueba.json`, `metricas_validacion.csv`, `README.md` de ese mismo directorio, y el pipeline remitido. Versiones y métricas conservadas del repositorio.
