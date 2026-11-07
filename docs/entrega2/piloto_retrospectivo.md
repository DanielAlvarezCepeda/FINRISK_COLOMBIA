# Piloto retrospectivo de FINRISK

## Qué se está prediciendo

Este piloto estudia la **aparición observada de una empresa en el inventario de insolvencia de diciembre del año siguiente**, entre reportantes financieros sin presencia en los cortes consultados hasta diciembre del año de origen. Es una aproximación observable distinta del objetivo original de primera admisión formal durante los doce meses siguientes a una evaluación.

- `evento = 1`: el NIT aparece en el inventario de diciembre del año siguiente.
- `evento = 0`: el NIT no aparece en ese inventario. No demuestra solvencia ni ausencia de un proceso durante el intervalo.

El año de origen `T` usa indicadores del ejercicio financiero `T−1` y el inventario de diciembre de `T+1`. Las ventanas son nominalmente de doce meses entre cierres anuales. No se ha verificado cuándo estuvieron disponibles los reportes, sus revisiones o las etiquetas. Por eso la separación cronológica es una evaluación retrospectiva y **no acredita una simulación operativa con información disponible en cada fecha**.

No se utilizan la fecha del auto ni el año de apertura para inferir una primera admisión. Los inventarios pueden omitir procesos que comenzaron y terminaron entre cortes. El piloto apoya una revisión académica; no decide préstamos ni diagnostica quiebra.

## Población, controles y particiones

Se parte del panel recuperado de 176.666 observaciones empresa-año y 37.231 NIT. Para cada origen se selecciona el ejercicio anterior. Se excluyen, en este orden, las empresas presentes en cualquier inventario consultado hasta el origen, las filas marcadas `requiere_revision_coherencia` y las filas sin ninguno de los cuatro indicadores. Se conservan valores negativos y faltantes parciales. La imputación se ajusta únicamente con entrenamiento.

| Origen | Ejercicio financiero | Inventario objetivo | Partición | Filas financieras | Excluidas por antecedente | Excluidas por coherencia | Sin indicadores | Filas del piloto | Positivas |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 2021 | 2020 | Diciembre de 2022 | Entrenamiento | 29.949 | 1.690 | 337 | 132 | 27.790 | 125 |
| 2022 | 2021 | Diciembre de 2023 | Entrenamiento | 29.200 | 1.785 | 359 | 1 | 27.055 | 137 |
| 2023 | 2022 | Diciembre de 2024 | Validación | 31.149 | 1.843 | 627 | 2 | 28.677 | 164 |
| 2024 | 2023 | Diciembre de 2025 | Prueba | 31.396 | 1.952 | 493 | 2 | 28.949 | 155 |

Resultado: **112.471 filas y 33.608 NIT diferentes**. Los controles de coherencia excluyen respectivamente 1, 2, 1 y 4 presencias objetivo, después de retirar antecedentes. La exclusión por falta total de indicadores no retira positivos en estas cohortes. Estas reglas cambian la población evaluada y sus efectos quedan en la auditoría por clase.

El constructor exige los cortes históricos 2019-12 y 2020-09, y los cortes de diciembre de 2021 a 2025. Si falta un corte completo, detiene el proceso; no convierte su ausencia en etiquetas cero. Contrasta los conteos con `auditoria_insolvencia.json` cuando está disponible. El corte de octubre de 2026 no interviene en las etiquetas de estas cohortes.

Una empresa puede repetirse en varios años: hay 25.807 NIT compartidos entre entrenamiento y validación, 24.929 entre entrenamiento y prueba, y 26.960 entre validación y prueba. Es una evaluación con reportantes conocidos y no mide exclusivamente empresas nunca vistas. El NIT se usa para cruces y auditoría; nunca como predictor.

## Variables y modelos

Las únicas entradas del modelo son `liquidez_corriente`, `endeudamiento`, `roa` y `margen_neto`. Liquidez se expresa en veces; las otras tres se ingresan como razones, no como porcentajes: por ejemplo, 0,35 representa 35 %. Las fechas, el NIT, la etiqueta y los campos de insolvencia no son entradas.

Se compararon tres alternativas con semilla 42:

- Referencia que asigna a todas las filas la prevalencia de entrenamiento.
- Regresión logística con imputación por mediana, indicadores de faltantes, transformación `arcsinh`, estandarización y ponderación balanceada de clases.
- Bosque aleatorio con la misma imputación e indicadores de faltantes, 300 árboles, profundidad máxima 8, mínimo de 20 observaciones por hoja y ponderación `balanced_subsample`.

Todos los ajustes de imputación, transformación y modelo usan solamente entrenamiento. Se elige el modelo con mayor **precisión media (AP, average precision)** en validación. El umbral de cada modelo maximiza F2 en esa misma partición. F2 da mayor peso a sensibilidad, pero no representa costos bancarios ni una capacidad de revisión acordada. La selección y el modelo se sellan antes de consultar la prueba. El ganador no se vuelve a ajustar antes de esa evaluación.

## Resultados observados

Validación: 28.677 filas, 164 positivas y prevalencia de 0,572 %. Las métricas por umbral corresponden al máximo F2 de cada alternativa.

| Modelo | AP de validación | Umbral | Sensibilidad | Precisión de alertas | Alertas |
| --- | ---: | ---: | ---: | ---: | ---: |
| Referencia de prevalencia | 0,005719 | 0,004777 | 100,00 % | 0,572 % | 28.677 |
| Regresión logística | 0,012903 | 0,682823 | 24,39 % | 1,516 % | 2.638 |
| Bosque aleatorio | 0,017315 | 0,744843 | 16,46 % | 2,977 % | 907 |

El bosque aleatorio obtuvo la mayor AP y quedó seleccionado con umbral exacto `0.7448425229939636`. La prueba reservada se evaluó una vez, después de esa selección:

| Medida del ganador en prueba | Resultado |
| --- | ---: |
| Filas / positivas observadas | 28.949 / 155 |
| Prevalencia | 0,535 % |
| AP | 0,020718 |
| Sensibilidad | 16,77 % |
| Precisión de alertas | 2,978 % |
| Alertas | 873 (3,016 % de las filas) |
| Positivos detectados / omitidos | 26 / 129 |
| Alertas sin presencia observada / casos sin presencia y sin alerta | 847 / 27.947 |

**El resultado aún es débil para uso práctico:** se omiten 129 de las 155 presencias observadas y solo 26 de las 873 alertas son correctas. La mejora de ordenamiento frente a la referencia no demuestra utilidad crediticia. Estas son métricas de la etiqueta observada, no de primera admisión formal ni de incumplimiento de crédito. La exactitud global no se usa para justificar el modelo por el fuerte desbalance.

## Reproducir el piloto

Usar Python 3.12 y seguir primero la [preparación de fuentes](preparacion_datos.md). Se requieren el panel en `data/processed/recuperacion/` y los cruces auditados en `reports/preparacion/`. Desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-entrega2.txt
.\.venv\Scripts\python.exe src/finrisk_piloto_modelos.py --raiz . --salida .cache/finrisk/piloto_retrospectivo
```

El programa construye las etiquetas y escribe protocolo, configuración, selección, métricas agregadas, modelos y predicciones en la carpeta local indicada. Para exportar además la base etiquetada y su auditoría, sin entrenar:

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_datos.py --raiz . --salida data/processed/piloto_retrospectivo
```

Las huellas SHA-256 identifican los insumos, el protocolo, la base, la configuración, el código y los modelos. La base se ordena de forma determinista y su exportación comprimida evita una fecha variable en la cabecera. Las fechas de registro de ejecución se conservan como metadatos, separadas de esas huellas de contenido.

Con los mismos datos, código, configuración y versiones, el modelado reutiliza una ejecución completa ya guardada. No cambiar modelos o umbrales después de observar esta prueba y presentarla como una nueva prueba independiente. Si cambian las fuentes o el protocolo, documentar la nueva versión y conservar los resultados anteriores.

Los microdatos, las predicciones individuales y los modelos quedan fuera de Git. Los resúmenes de la ejecución que se compartan se conservan en `results/piloto_retrospectivo/`. La evidencia original de recuperación sigue en `docs/entrega2/evidencia_20261107/`.

## Inferencia para el prototipo

El prototipo debe recuperar el modelo sellado y su umbral; no volver a entrenarlos al consultar una empresa. La regla es `predict_proba(X)[:, 1] >= umbral`. Ejemplo sobre las salidas locales del piloto, con una entrada ilustrativa:

```python
import json
from pathlib import Path
import joblib
import pandas as pd

carpeta = Path(".cache/finrisk/piloto_retrospectivo")
seleccion = json.loads((carpeta / "seleccion_sellada.json").read_text(encoding="utf-8"))
modelo = joblib.load(carpeta / "modelos" / f"{seleccion['modelo']}.joblib")
variables = ["liquidez_corriente", "endeudamiento", "roa", "margen_neto"]
entrada = pd.DataFrame([[1.2, 0.6, 0.03, 0.05]], columns=variables)
puntaje = float(modelo.predict_proba(entrada[variables])[0, 1])
alerta = puntaje >= float(seleccion["umbral"])
```

Aunque el método se llame `predict_proba`, estos puntajes de modelos con ponderación de clases **no están calibrados**. Mostrar “puntaje del piloto” y “alerta para revisión”, con su umbral y las limitaciones; no “probabilidad de quebrar”, aprobación automática de crédito o una certeza de solvencia. La aplicación debe validar unidades y entradas y limitar su uso a una población comparable a la estudiada.

## Registro en MLflow

El piloto quedó registrado y verificado en [Proyecto-MIAD, experimento 2](http://54.163.35.181:8050/#/experiments/2), con cuatro corridas terminadas (`FINISHED`). El [manifiesto de registro real](../../results/piloto_retrospectivo/registro_mlflow.json) conserva los identificadores, enlaces, huellas y la relación con el commit fuente `4cd8f32162b5349919c911445a4caa0de67ebc8a`.

| Modelo | Fase | Corrida verificada |
| --- | --- | --- |
| Referencia de prevalencia | Validación | [88f119e414c2476dbecb67e8f394f36a](http://54.163.35.181:8050/#/experiments/2/runs/88f119e414c2476dbecb67e8f394f36a) |
| Regresión logística | Validación | [0c70c9e248844e0b9889810ea97abbf0](http://54.163.35.181:8050/#/experiments/2/runs/0c70c9e248844e0b9889810ea97abbf0) |
| Bosque aleatorio | Validación | [93c4cd9117da48debbdabf1422454c09](http://54.163.35.181:8050/#/experiments/2/runs/93c4cd9117da48debbdabf1422454c09) |
| Bosque aleatorio seleccionado | Prueba reservada | [b4940092f90648d8a7714fcce8b37d1a](http://54.163.35.181:8050/#/experiments/2/runs/b4940092f90648d8a7714fcce8b37d1a) |

Se registraron tres pipelines; la corrida de prueba referencia el mismo modelo ganador de validación. Se recuperó su archivo y se comprobó que tiene la misma huella SHA-256 que el original. El registro verificó las métricas desde los puntajes guardados, sin generar nuevas predicciones de prueba ni subir filas individuales. La prueba técnica anterior con un archivo y el notebook Iris se conservan como antecedentes distintos de estas corridas de FINRISK.

La [verificación remota](../../results/piloto_retrospectivo/verificacion_mlflow.json) confirma estados, parámetros y métricas de las cuatro corridas. También cargó el ganador como modelo MLflow y comparó sus salidas de ambas clases para dos entradas sintéticas con el pipeline local: diferencia máxima 0,0. No creó corridas ni volvió a predecir la prueba reservada.

Para reproducir el registro de esta ejecución, usar el resumen y los archivos locales del piloto, sin reentrenar ni volver a seleccionar con prueba:

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_mlflow.py --tracking-uri http://54.163.35.181:8050 --experimento Proyecto-MIAD --resumen .cache/finrisk/piloto_retrospectivo/resumen_piloto.json --commit 4cd8f32162b5349919c911445a4caa0de67ebc8a --salida results/piloto_retrospectivo/registro_mlflow.json
```

En una nueva ejecución, el parámetro `--commit` debe identificar con 40 caracteres el código fuente que realmente produjo sus artefactos. Consultar la [guía de MLflow](mlflow.md) y el manifiesto para revisar la trazabilidad y la recuperación de artefactos.

## Pendientes que debe revisar el equipo

El piloto ya cuenta con etiquetas operativas, comparación, prueba reservada y registro verificado de artefactos en MLflow. Para completar el prototipo quedan implementar la consulta con el modelo sellado, presentar sus métricas y límites en el tablero y preparar capturas de evidencia. Los resultados actuales requieren mejorar la señal predictiva y revisar el volumen de alertas sin presencia observada antes de atribuirle utilidad práctica.

Para volver al objetivo original siguen pendientes: verificar primera admisión y cobertura de procesos entre cortes; comprobar publicación y revisiones históricas de reportes y etiquetas; definir el seguimiento de los casos negativos; y acordar costos, capacidad de revisión, umbral operativo y evaluación prospectiva. También requieren trabajo la calibración, la estabilidad entre cohortes y la generalización a empresas nuevas. Estas brechas no se presentan como resueltas por el entrenamiento del piloto.
