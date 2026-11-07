# Preparación de datos para la entrega 2

## Objetivo y estado

El objetivo original es predecir admisión formal a un proceso de insolvencia durante los doce meses siguientes a una evaluación. Las fuentes recuperadas todavía no permiten validar ese evento ni la disponibilidad histórica de los reportes. Para avanzar, el equipo construyó un piloto retrospectivo de **aparición observada en el inventario anual siguiente**, entre empresas sin presencia en los cortes consultados hasta el origen. Ausencia en ese inventario no equivale a solvencia.

La etiqueta operativa, los primeros modelos y su evaluación ya están implementados y registrados en MLflow con recuperación verificada del ganador. Quedan integrar la interfaz predictiva y preparar capturas de evidencia para la entrega. El puntaje del piloto no está calibrado y no debe presentarse como probabilidad de quiebra. Ver el [protocolo, resultados y comandos del piloto](piloto_retrospectivo.md).

El avance del 7 de noviembre de 2026 recuperó 2.703.117 registros contables seleccionados de 2019–2024 y ocho inventarios oficiales de insolvencia. Reconstruyó 176.666 observaciones empresa-año de 37.231 empresas. Hay 161.425 observaciones con los cuatro indicadores, 713 con importes en conflicto y 2.490 que requieren revisar coherencia entre reportes. Son controles de preparación y no medidas de desempeño predictivo.

La extracción recuperada constituye una versión distinta de la base preliminar referenciada por DVC. Se conservan el puntero y el remoto originales. El filtro descriptivo estricto de la primera entrega y el conteo de cuatro indicadores de esta extracción tienen reglas diferentes.

## Preparar el entorno

Desde la raíz del repositorio, usar Python 3.12. Las versiones existentes de pandas, NumPy y MLflow se conservan. El archivo adicional incorpora lectura de Excel y scikit-learn.

```powershell
$env:PYTHONUTF8 = "1"
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-entrega2.txt
```

## Recuperar y consolidar los datos

Ejecutar en este orden. La descarga financiera completa del avance ocupa aproximadamente 85 MB comprimidos y requiere conexión a las fuentes públicas. Su contenido actual puede diferir del capturado el 7 de noviembre.

```powershell
.\.venv\Scripts\python.exe src/descargar_financieros.py
.\.venv\Scripts\python.exe src/descargar_insolvencia.py
.\.venv\Scripts\python.exe src/auditar_insolvencia.py
.\.venv\Scripts\python.exe src/consolidar_recuperacion.py
```

Los catálogos de conceptos versionados están en `configs/entrega2/`. El descargador financiero consulta primero el esquema, los periodos y los conteos. Conserva columnas originales y el identificador Socrata, descarga por páginas, verifica huellas al reanudar y comprueba que los metadatos no cambien durante la extracción. Esta comprobación no prueba disponibilidad histórica.

Las salidas operativas se generan fuera del control de Git.

| Ruta | Contenido |
| --- | --- |
| `data/raw/financieros/` | Fragmentos originales comprimidos, filtrados por conceptos y periodos actuales |
| `data/raw/insolvencia/` | Ocho cortes oficiales XLSX |
| `reports/preparacion/` | Manifiestos, perfiles y auditoría de insolvencia de la ejecución actual |
| `data/processed/recuperacion/` | Panel sin etiquetas y auditorías de candidatos y coherencia |
| `data/processed/piloto_retrospectivo/` | Exportación opcional de microdatos etiquetados y auditoría de cohortes |
| `.cache/finrisk/` | SQLite temporal y archivos locales de trabajo |

Si los metadatos financieros cambian respecto de una ejecución anterior, conservar esa extracción y comenzar en otro directorio con `--raiz RUTA_NUEVA`. Los catálogos y el código siguen tomándose del repositorio. El descargador de insolvencia conserva un archivo existente cuando sus bytes coinciden y rechaza reemplazarlo si el proveedor cambió su contenido. Para esa situación usar un directorio nuevo con `--destino` y un manifiesto separado con `--reporte`. El auditor admite `--entrada` y `--salida`.

## Ejecutar el notebook

Abrir [02_Preparacion_Datos_FINRISK.ipynb](../../notebooks/02_Preparacion_Datos_FINRISK.ipynb) con un editor compatible con Jupyter y seleccionar el entorno preparado. GitHub muestra las salidas guardadas. Para volver a ejecutarlo es necesario completar antes los cuatro pasos de recuperación y consolidación.

El notebook puede iniciarse desde la raíz o desde `notebooks/`. Sus tablas muestran cobertura, faltantes, conflictos y coincidencias observadas con inventarios. El avance incorpora el piloto retrospectivo y usa los módulos compartidos de etiqueta y modelado para mantener las mismas reglas en la ejecución por consola. Las métricas guardadas corresponden a datos reales recuperados, no a Iris.

## Construir la etiqueta y entrenar

El constructor selecciona indicadores del ejercicio `T−1`, excluye antecedentes observados en los cortes hasta diciembre de `T` y consulta diciembre de `T+1`. Requiere que existan los cortes históricos necesarios; si falta uno, detiene el proceso. Excluye incoherencias entre reportes y ausencia total de indicadores. Conserva faltantes parciales y valores negativos. No usa fecha del auto ni año de apertura para reconstruir una primera admisión.

El piloto resultante contiene 112.471 observaciones y 33.608 empresas. Los orígenes 2021–2022 son entrenamiento (54.845 filas, 262 positivas), 2023 es validación (28.677, 164) y 2024 es prueba (28.949, 155). Puede repetirse un NIT entre cohortes, pero nunca se usa como predictor. La imputación y las transformaciones se ajustan solo con entrenamiento.

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_modelos.py --raiz . --salida .cache/finrisk/piloto_retrospectivo
```

Ese comando construye la etiqueta, compara una referencia de prevalencia, regresión logística y bosque aleatorio en validación, fija el ganador y su umbral, y evalúa una vez la prueba reservada. Genera protocolo, configuración, selección y resultados con huellas de contenido. Los modelos y las predicciones individuales se quedan en la carpeta local ignorada por Git. Si se quiere exportar la base etiquetada por separado, usar `src/finrisk_piloto_datos.py --raiz . --salida data/processed/piloto_retrospectivo`.

La mayor AP de validación correspondió al bosque aleatorio. En prueba obtuvo AP de 0,020718, sensibilidad de 16,77 % y precisión de alertas de 2,978 %: 26 aciertos, 847 alertas sin presencia observada y 129 positivos omitidos. Este desempeño es débil para uso práctico. El [documento del piloto](piloto_retrospectivo.md) explica las métricas, la regla de inferencia y las limitaciones.

## Reglas contables y trazabilidad

El nuevo consolidador reutiliza el diccionario y las prioridades del programa original `src/finrisk_etapa4_consolidar.py`. Conserva ese archivo. Cuando los candidatos de mejor prioridad discrepan, el importe queda ausente. Se exportan los candidatos con identificador Socrata, radicado, taxonomía, tipo de reporte, fecha de corte y archivo de origen.

La selección por variable puede combinar reportes o fechas. La columna `requiere_revision_coherencia` identifica combinaciones que requieren revisión antes del modelado. Los valores negativos se conservan. Endeudamiento, ROA y margen son razones y se multiplican por cien al presentarse como porcentajes. Liquidez se expresa en veces.

## Validaciones pendientes del objetivo original

El piloto usa un objetivo observable para avanzar con el prototipo. Esto no resuelve las siguientes brechas del objetivo original de primera admisión formal a doce meses:

- Identificar la primera admisión formal y distinguirla de procesos posteriores o cambios de etapa.
- Verificar seguimiento y cobertura para asignar una clase sin evento. La ausencia de un inventario no basta.
- Fijar una fecha de evaluación que respete cuándo estaban disponibles los reportes financieros. La fecha de corte contable no prueba disponibilidad.

La auditoría encontró empresas presentes en cortes antiguos que no aparecen en el actual y fechas de admisión posteriores a una presencia antigua. Las fuentes financieras consultadas no incluyen fecha de disponibilidad histórica.

El [borrador de consulta al tutor](consulta_tutor.txt) conserva las preguntas. El equipo debe validar el cambio de alcance y mantener explícita la diferencia entre presencia observada y primera admisión. El piloto ya tiene particiones cronológicas, comparación y umbral seleccionado con validación; no se considera una prueba operativa libre de información posterior. También falta acordar costos de errores, capacidad de revisión y requisitos de calibración antes de un uso práctico.

## Evidencia histórica y MLflow

La carpeta [evidencia_20261107](evidencia_20261107/) conserva manifiestos y resúmenes agregados del avance original. Sus rutas describen aquella extracción y no indican que los datos estén incluidos en Git. Las nuevas ejecuciones escriben en `reports/preparacion/` y conservan separada esa evidencia. Los datos individuales y archivos grandes se recuperan mediante los programas.

El [registro con MLflow](mlflow.md) utiliza el servidor informado por Jairo, `http://54.163.35.181:8050`. El piloto quedó en [Proyecto-MIAD, experimento 2](http://54.163.35.181:8050/#/experiments/2), con cuatro corridas `FINISHED`: tres comparaciones de validación y la prueba reservada del ganador. Se guardaron tres pipelines y se recuperó el ganador con huella SHA-256 idéntica. El [manifiesto real](../../results/piloto_retrospectivo/registro_mlflow.json) enlaza las corridas y el commit fuente `4cd8f32162b5349919c911445a4caa0de67ebc8a`; confirma que no se subieron filas individuales. El notebook con Iris de Jairo se conserva como prueba técnica y sus métricas corresponden a ese conjunto.

## Fuentes

- [Estado de situación financiera](https://www.datos.gov.co/d/pfdp-zks5).
- [Estado de resultado integral](https://www.datos.gov.co/d/prwj-nzxa).
- [Informes e inventarios de insolvencia de Supersociedades](https://www.supersociedades.gov.co/web/procedimientos-de-insolvencia/informes).
