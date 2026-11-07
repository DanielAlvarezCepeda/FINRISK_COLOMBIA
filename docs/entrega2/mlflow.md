# MLflow para la entrega 2

El piloto académico ya tiene una etiqueta de **presencia en el siguiente inventario anual**, tres modelos entrenados localmente y seguimiento remoto en el EC2 de Jairo. No es una validación de primera admisión formal en doce meses. La disponibilidad histórica, la madurez de etiquetas y los eventos entre inventarios siguen sin comprobarse.

El tablero debe presentar un puntaje y una alerta demostrativa para revisión. El puntaje no está calibrado como probabilidad de quiebra. Consulte el [protocolo y los resultados reales](piloto_retrospectivo.md).

## Estado comprobado el 7 de noviembre de 2026

- Servidor: [http://54.163.35.181:8050](http://54.163.35.181:8050/), MLflow 3.18.0.
- Experimento: [Proyecto-MIAD · ID 2](http://54.163.35.181:8050/#/experiments/2).
- Prueba técnica: subida y recuperación de verificacion.txt, 59 bytes, con SHA-256 idéntico. [Soporte](evidencia_20261107/prueba_artefactos_mlflow.json).
- Piloto real: tres corridas de validación con sus pipelines y una corrida de prueba del ganador, todas finalizadas.
- Recuperación del joblib ganador: SHA-256 idéntico al entrenado.
- Las predicciones individuales y los NIT permanecen locales. Las entradas ilustrativas de los modelos son sintéticas.

La [consulta inicial](evidencia_20261107/diagnostico_mlflow_5416335181.json) es una fotografía anterior a la creación del experimento: su respuesta 404 no describe el estado actual. El notebook de Iris y Test-MLflow de Jairo se conservan como evidencia técnica separada.

## Corridas reales del piloto

| Modelo | Fase | Corrida |
| --- | --- | --- |
| referencia_prevalencia | validacion | [FINISHED · 88f119e414c2476dbecb67e8f394f36a](http://54.163.35.181:8050/#/experiments/2/runs/88f119e414c2476dbecb67e8f394f36a) |
| regresion_logistica | validacion | [FINISHED · 0c70c9e248844e0b9889810ea97abbf0](http://54.163.35.181:8050/#/experiments/2/runs/0c70c9e248844e0b9889810ea97abbf0) |
| bosque_aleatorio | validacion | [FINISHED · 93c4cd9117da48debbdabf1422454c09](http://54.163.35.181:8050/#/experiments/2/runs/93c4cd9117da48debbdabf1422454c09) |
| bosque_aleatorio | prueba | [FINISHED · b4940092f90648d8a7714fcce8b37d1a](http://54.163.35.181:8050/#/experiments/2/runs/b4940092f90648d8a7714fcce8b37d1a) |

El [manifiesto de registro](../../results/piloto_retrospectivo/registro_mlflow.json) contiene los identificadores, las URI de modelo y las comprobaciones. La [verificación remota](../../results/piloto_retrospectivo/verificacion_mlflow.json) comprueba estados, parámetros, métricas y uso del modelo recuperado.

El commit fuente del entrenamiento es `4cd8f32162b5349919c911445a4caa0de67ebc8a`. Su código de modelado coincide con el SHA guardado en el protocolo. Los cambios posteriores en documentación y serialización del registro no reajustan los modelos ni cambian las métricas.

Los tres pipelines están guardados como modelos de MLflow; no se les asignó una etapa de producción ni una versión aprobada en Model Registry. La corrida de prueba enlaza el mismo modelo ganador usado en validación.

## Qué muestran los resultados

Se seleccionó Random Forest por AP de validación, con umbral F2 sellado `0.7448425229939636`. La prueba reservada, consultada después de elegir, obtuvo:

| Medida | Resultado |
| --- | ---: |
| Filas / presencias observadas | 28.949 / 155 |
| AP | 0,020718 |
| Sensibilidad | 16,77 % |
| Precisión de alertas | 2,978 % |
| Alertas | 873 |
| Presencias detectadas / omitidas | 26 / 129 |
| Alertas sin presencia en el siguiente inventario | 847 |

El desempeño es limitado. Estas métricas describen registros observados, no solvencia ni incumplimiento de crédito. La selección temporal sigue siendo retrospectiva: no acredita que reportes y etiquetas hubieran estado disponibles en cada origen.

## Entorno desde la raíz del repositorio

Python 3.12 y dependencias fijadas para reproducir la ejecución:

```powershell
$env:PYTHONUTF8 = "1"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-entrega2.txt
```

La [preparación de datos](preparacion_datos.md) recupera las fuentes y genera el panel. Construir y entrenar con la carpeta explícita:

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_modelos.py --raiz . --salida .cache/finrisk/piloto_retrospectivo
```

La caché íntegra se reutiliza sin reentrenar ni evaluar nuevamente la prueba. Si cambian fuentes, código o versiones, conservar la ejecución anterior y documentar una nueva versión.

## Comprobar y registrar una ejecución

El diagnóstico siguiente no escribe en el servidor:

```powershell
python -X utf8 src/finrisk_comprobar_mlflow.py --tracking-uri http://54.163.35.181:8050 --experimento Proyecto-MIAD --salida salidas/diagnostico_conexion.json
```

Para auditar el registro local sin red, sustituir el commit por el que contiene exactamente el entrenamiento correspondiente:

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_mlflow.py --resumen .cache/finrisk/piloto_retrospectivo/resumen_piloto.json --commit COMMIT_FUENTE_DE_40_CARACTERES --solo-preflight
```

El preflight contrasta protocolo, código, versiones, hashes de los modelos, selección AP y umbral F2; recalcula las métricas de los puntajes guardados sin hacer nuevas predicciones de prueba. Usa lectura de coma flotante round_trip para conservar el umbral de la referencia constante.

El registro escribe en el experimento:

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_mlflow.py --tracking-uri http://54.163.35.181:8050 --experimento Proyecto-MIAD --resumen .cache/finrisk/piloto_retrospectivo/resumen_piloto.json --commit COMMIT_FUENTE_DE_40_CARACTERES --autor joaquinrovi --salida results/piloto_retrospectivo/registro_mlflow.json
```

La identidad de ejecución y los IDs se guardan en estado_mlflow.json dentro de la caché. Si la ejecución ya está completa, comprueba sus parámetros y métricas y reutiliza las mismas corridas. Una interrupción propia se puede reanudar. No cambiar el commit ni borrar ese estado para duplicar resultados.

Cada validación conserva pipeline, hiperparámetros, métricas, selección y protocolo. Los modelos propios se serializan con cloudpickle; este formato se probó con los tres pipelines de esta ejecución. La corrida de prueba conserva las métricas reservadas y el enlace al modelo seleccionado. El notebook no escribe automáticamente en MLflow al reejecutarlo.

## Recuperar el ganador para el prototipo

Usar la URI sellada del manifiesto. El flavor pyfunc devuelve dos columnas, clases [0, 1]; la alerta usa la columna 1 y el umbral publicado.

```python
import json
from pathlib import Path
import mlflow
import mlflow.pyfunc
import pandas as pd

registro = json.loads(Path("results/piloto_retrospectivo/registro_mlflow.json").read_text(encoding="utf-8"))
ganador = registro["corrida_prueba"]
mlflow.set_tracking_uri(registro["tracking_uri"])
modelo = mlflow.pyfunc.load_model(ganador["model_uri"])
variables = ["liquidez_corriente", "endeudamiento", "roa", "margen_neto"]
entrada = pd.DataFrame([[1.2, 0.6, 0.03, 0.05]], columns=variables)
puntaje = float(modelo.predict(entrada)[0, 1])
alerta = puntaje >= ganador["umbral"]
```

Es una entrada sintética. Los indicadores se ingresan como razones y liquidez en veces. Un puntaje de 0,75 no es una probabilidad validada del 75 %. El predict() del flavor sklearn usa por defecto otro umbral; para ese flavor usar predict_proba y aplicar el umbral sellado.

## Scripts técnicos anteriores

`src/finrisk_registrar_corrida.py` se conserva para la prueba de humo y evaluaciones a partir de un manifiesto manual. Para este piloto se usa `src/finrisk_piloto_mlflow.py`, que conoce sus archivos, sellos y reglas. No utilizar el manifiesto del objetivo formal para atribuirle al piloto validaciones que no tiene.

La comprobación técnica puede repetirse con la opción `--humo` del registrador anterior, aunque crea una corrida adicional de prueba técnica. El intercambio original ya está comprobado y no requiere repetirse para revisar los resultados.

## Pendientes de integración y evidencia

Conectar el tablero con el modelo y umbral sellados, mostrar el alcance y las métricas, validar entradas y capturar la consulta predictiva. Revisar con Jairo las capturas de usuario e IP de EC2 y la conservación de datos y artefactos. La guía pide evidencia de la instancia detenida para revisión: coordinarlo al cerrar el trabajo, sin interrumpir el servicio compartido durante la integración.

Para recuperar el objetivo formal de primera admisión siguen pendientes las verificaciones históricas y de cobertura. Los resultados actuales requieren más señal predictiva y una evaluación posterior antes de afirmar utilidad operativa.

## Referencias

- [Arquitectura del servidor de MLflow](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)
- [API de seguimiento](https://mlflow.org/docs/latest/ml/tracking/tracking-api/)
- [Precisión promedio en scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
