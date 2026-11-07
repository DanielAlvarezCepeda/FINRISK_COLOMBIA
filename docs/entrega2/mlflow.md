# MLflow para la entrega 2

FINRISK mantiene el objetivo de estimar la admisión a un proceso formal de insolvencia durante los doce meses siguientes a la evaluación. La base financiera y los cortes de insolvencia ya se recuperaron y auditaron. Quedan por validar con el tutor la primera admisión, la cobertura del seguimiento y la disponibilidad histórica de los reportes antes de construir la etiqueta y entrenar.

El tablero previsto será la interfaz para consultar una predicción por empresa, presentar el riesgo y la alerta, y apoyar la revisión crediticia. Su respuesta predictiva requiere integrar un modelo entrenado y evaluado. Los scripts de este documento registran evaluaciones ya calculadas.

## Servidor y estado de comprobación

Jairo compartió el servidor `http://52.91.138.185:8050` y el experimento `Proyecto-MIAD`. La consulta desde el entorno de preparación agotó el tiempo de espera el 7 de noviembre de 2026. Quedan pendientes su disponibilidad actual, versión y recuperación de artefactos desde el equipo que lo utilizará.

El notebook existente `notebooks/models/test_mlflow.ipynb` usa Iris y `Test-MLflow`. Sus corridas son evidencia técnica de integración. Los resultados de FINRISK se registrarán por separado con su etiqueta validada.

## Entorno desde la raíz del repositorio

Usar Python 3.12. El entorno de la entrega 2 conserva MLflow 3.18.0 y añade los paquetes de preparación y evaluación.

```powershell
$env:PYTHONUTF8 = "1"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-entrega2.txt
```

## Diagnóstico de solo lectura

El diagnóstico utiliza la biblioteca estándar y puede ejecutarse antes de instalar MLflow.

```powershell
python -X utf8 src/finrisk_comprobar_mlflow.py --tracking-uri http://52.91.138.185:8050 --experimento Proyecto-MIAD --salida salidas/diagnostico_conexion.json
```

Consulta `/health`, `/version` y el experimento por nombre. Guarda las respuestas y la ubicación declarada de artefactos. No crea experimentos, corridas ni archivos remotos. Una respuesta correcta confirma lectura básica, pero la escritura y la recuperación se comprueban con la prueba siguiente.

Si aparece `mlflow-artifacts:/...`, el experimento declara un proxy de artefactos. Una ubicación `file:/...` o local necesita revisión con Jairo para compartir archivos con Windows. El uso directo de `s3://...` requiere acceso al almacenamiento desde el cliente. Si el diagnóstico falla, confirmar con Jairo que la instancia y el servicio estén activos, la dirección siga vigente y el puerto sea accesible desde el equipo.

## Prueba de escritura y recuperación

Esta orden crea una corrida en `Proyecto-MIAD`, sube un archivo pequeño y lo recupera para comparar su contenido. La etiqueta `finrisk.tipo=prueba_tecnica` distingue la comprobación de las evaluaciones reales.

```powershell
.\.venv\Scripts\python.exe -X utf8 src/finrisk_registrar_corrida.py --tracking-uri http://52.91.138.185:8050 --experimento Proyecto-MIAD --ip-ec2 52.91.138.185 --humo
```

Guardar el run ID y revisar el artefacto en la interfaz. Resolver cualquier fallo de almacenamiento antes de enviar modelos. Esta prueba queda preparada para el equipo. Durante la integración del repositorio solo se comprobaron servidores locales.

## Evaluaciones reales

Preparar estos insumos después de validar la etiqueta y las particiones temporales.

- Versión o huella de la base etiquetada, regla del evento, horizonte de doce meses y cortes de entrenamiento, validación y prueba.
- Commit del entrenamiento, modelo e hiperparámetros. Las etiquetas deben estar maduras antes de la siguiente partición y los predictores disponibles en la fecha de evaluación.
- CSV de la partición evaluada con `evento` (0 o 1) y `puntaje` finito que crece con el riesgo. La partición requiere ambas clases.
- Archivo del modelo o pipeline ajustado en formato joblib, pickle, skops u ONNX. Se adjunta sin deserializarlo.

Copiar la plantilla a una carpeta local ignorada por Git. Completarla antes de registrar resultados.

```powershell
New-Item -ItemType Directory -Force .cache/finrisk | Out-Null
Copy-Item -LiteralPath configs/entrega2/corrida.plantilla.json -Destination .cache/finrisk/corrida.json
.\.venv\Scripts\python.exe -X utf8 src/finrisk_registrar_corrida.py --tracking-uri http://52.91.138.185:8050 --experimento Proyecto-MIAD --ip-ec2 52.91.138.185 --manifiesto .cache/finrisk/corrida.json
```

Las rutas de modelos y predicciones se interpretan respecto de la carpeta del manifiesto. Las fechas usan AAAA-MM-DD. Las salidas locales se guardan en `salidas/` o en la ruta indicada mediante `--salidas`.

Comparar candidatos en validación sobre el mismo conjunto. Un `umbral` nulo registra precisión promedio (AP) y deja pendientes las métricas de alerta. Elegir modelo y umbral con validación antes de abrir la prueba reservada. Para registrar esta última, indicar `fase=prueba`, el umbral y `run_id_validacion`. El script comprueba que la validación finalizada corresponda al mismo experimento, modelo, archivo, commit, versión de datos y protocolo.

Cada corrida registra AP, conteos y prevalencia. Con umbral añade sensibilidad, precisión de alertas, volumen y matriz de confusión. Si no hay alertas, la precisión queda sin valor. Se conservan el protocolo, la huella del modelo, su archivo y `resumen.json` vinculados al run ID. Las filas de predicciones y sus identificadores se mantienen como entradas locales.

Compartir el resumen agregado de la evaluación final con quien integre el tablero y el informe. Conservar el código, las dependencias y las fuentes para reproducir el entrenamiento.

## Evidencia de la entrega

Capturar usuario e IP de EC2 y la IP visible en MLflow, verificando con Jairo que ambas correspondan a la misma instancia. Guardar los soportes y los respaldos. Coordinar con él la detención de la instancia y la conservación de sus volúmenes al cerrar la evidencia. La guía solicita mantener la instancia detenida para revisión.

La QA local del 7 de noviembre comprobó experimento configurable, diagnóstico sin escrituras, carga y lectura de artefactos, métricas, matriz de confusión, vínculo entre validación y prueba y rechazo de otro experimento o umbral distinto. Usó datos sintéticos identificados como prueba técnica. Las corridas reales de FINRISK y el servidor de Jairo quedan pendientes de comprobar.

## Referencias

- [Servidor de seguimiento de MLflow](https://mlflow.org/docs/latest/self-hosting/architecture/tracking-server/)
- [API de seguimiento](https://mlflow.org/docs/latest/ml/tracking/tracking-api/)
- [Precisión promedio en scikit-learn](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.average_precision_score.html)
- [Detener e iniciar EC2](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/Stop_Start.html)
