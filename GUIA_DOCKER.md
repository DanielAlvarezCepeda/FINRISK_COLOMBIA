# FINRISK Colombia | Entrega final – Docker local

## Componentes

Se conserva el modelo sellado, la API validada y el HTML integrado. El Dockerfile.api de la versión anterior carga `api.main:app`. El nuevo Dockerfile.dashboard sirve el HTML por Nginx y reenvía las consultas a la API por la red interna de Compose. No se requiere CORS ni cambio de URL en JavaScript. Solo se publica el puerto del tablero, por defecto en 127.0.0.1:8080. La API no publica un puerto independiente. Swagger sigue accesible a través de Nginx en /docs. No se modifica el entrenamiento ni la etiqueta.

## Requisitos

Windows con Docker Desktop en ejecución, motor Linux de contenedores (WSL 2 si corresponde), y los dos paquetes previos de FINRISK (API e integración). En Linux, Docker Engine y el plugin Compose. El archivo models/bosque_aleatorio.joblib debe permanecer local, con SHA-256 55fe564eaec27a1db78546895b3076db791e8ce3ee0155ce3e3ba264cb509f4f. No subir el modelo, imágenes que lo contienen, datos individuales ni credenciales a registros públicos.

## Comandos desde la raíz del proyecto (PowerShell)

```powershell
cd "C:\Users\User\Desktop\FINRISK_COLOMBIA"
docker --version
docker compose version
docker info --format '{{.OSType}}'
```

El último comando debe indicar linux. Si no responde el motor, iniciar Docker Desktop. Si no está instalado, seguir las instrucciones oficiales para Windows y reiniciar si el instalador lo solicita. No hace falta activar .venv-api para Docker.

Descomprimir este paquete en la raíz, conservando los archivos anteriores. Si aún está ejecutándose Uvicorn local, se puede detener con Ctrl+C. Es independiente del puerto 8080 de Docker.

```powershell
Test-Path .\Dockerfile.api
Test-Path .\dashboard\index.html
Get-FileHash .\models\bosque_aleatorio.joblib -Algorithm SHA256
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Esperar a que ambos servicios estén healthy. El tablero está en http://127.0.0.1:8080/dashboard/ y Swagger en http://127.0.0.1:8080/docs. Si 8080 está ocupado, establecer `$env:FINRISK_PORT = '8081'` antes de ejecutar `docker compose up -d` y cambiar la URL de prueba.

## Verificación de extremo a extremo

```powershell
Invoke-RestMethod http://127.0.0.1:8080/health | ConvertTo-Json
$body = @{liquidez_corriente=0.60; endeudamiento=0.95; roa=-0.12; margen_neto=-0.10} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8080/predict -ContentType 'application/json' -Body $body | ConvertTo-Json
```

Se espera `status: ok`, hash sellado, puntaje cercano a 0.6066, umbral 0.458623 y `alerta: true`. Desde el tablero probar A (0.2820, sin alerta), B (0.6066, con alerta), métricas y navegación. Capturar `docker compose ps`, respuesta de salud/predicción y el tablero con URL visible. No interpretar puntajes como probabilidades calibradas.

Si falla:

```powershell
docker compose ps -a
docker compose logs --tail=100 api dashboard
```

Si falla la compilación de dependencias, conservar el error exacto: la disponibilidad de ruedas Linux con las versiones fijadas debe comprobarse durante el build. No sustituir versiones automáticamente, ya que la API verifica las versiones del entrenamiento. Si el nombre de imagen Nginx se actualiza, documentar el digest usado para reproducibilidad después de la construcción.

Para detener conservando contenedores: `docker compose stop`. Para reiniciar: `docker compose start`.

## Git y AWS

No usar `git add .` indiscriminadamente. Agregar únicamente rutas de código, documentos y configuración, comprobar `git status` y que el modelo siga excluido con `git check-ignore models/bosque_aleatorio.joblib`. Añadir `.venv-api/` al .gitignore si falta. Si el repositorio local no contiene el último trabajo del grupo, reconciliar antes de publicar. Los comandos de publicación y despliegue se deben coordinar con el equipo. Para AWS, se puede reutilizar esta composición, pero la publicación debe configurarse con acceso restringido y/o HTTPS, sin exponer MLflow ni puertos privados a Internet. No hay despliegue en la nube ni build real de Docker verificado aún.
