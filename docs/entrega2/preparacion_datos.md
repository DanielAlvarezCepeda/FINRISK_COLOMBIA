# Preparación de datos para la entrega 2

## Objetivo y estado

Se mantiene la predicción de admisión a un proceso formal de insolvencia durante los doce meses siguientes a la evaluación. El tablero previsto permitirá consultar la predicción por empresa, mostrar el riesgo estimado y la alerta y apoyar la revisión crediticia. El modelo supervisado, la etiqueta y la interfaz predictiva siguen en desarrollo.

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
| `.cache/finrisk/` | SQLite temporal y archivos locales de trabajo |

Si los metadatos financieros cambian respecto de una ejecución anterior, conservar esa extracción y comenzar en otro directorio con `--raiz RUTA_NUEVA`. Los catálogos y el código siguen tomándose del repositorio. El descargador de insolvencia conserva un archivo existente cuando sus bytes coinciden y rechaza reemplazarlo si el proveedor cambió su contenido. Para esa situación usar un directorio nuevo con `--destino` y un manifiesto separado con `--reporte`. El auditor admite `--entrada` y `--salida`.

## Ejecutar el notebook

Abrir [02_Preparacion_Datos_FINRISK.ipynb](../../notebooks/02_Preparacion_Datos_FINRISK.ipynb) con un editor compatible con Jupyter y seleccionar el entorno preparado. GitHub muestra las salidas guardadas de las ocho celdas de código. Para volver a ejecutarlas es necesario completar antes los cuatro pasos de recuperación y consolidación.

El notebook puede iniciarse desde la raíz o desde `notebooks/`. Sus tablas muestran cobertura, faltantes, conflictos y coincidencias observadas con inventarios. No crea una variable objetivo ni entrena modelos.

## Reglas contables y trazabilidad

El nuevo consolidador reutiliza el diccionario y las prioridades del programa original `src/finrisk_etapa4_consolidar.py`. Conserva ese archivo. Cuando los candidatos de mejor prioridad discrepan, el importe queda ausente. Se exportan los candidatos con identificador Socrata, radicado, taxonomía, tipo de reporte, fecha de corte y archivo de origen.

La selección por variable puede combinar reportes o fechas. La columna `requiere_revision_coherencia` identifica combinaciones que requieren revisión antes del modelado. Los valores negativos se conservan. Endeudamiento, ROA y margen son razones y se multiplican por cien al presentarse como porcentajes. Liquidez se expresa en veces.

## Validaciones pendientes con el tutor

La decisión del equipo es mantener el objetivo a doce meses y validar estas brechas antes del entrenamiento.

- Identificar la primera admisión formal y distinguirla de procesos posteriores o cambios de etapa.
- Verificar seguimiento y cobertura para asignar una clase sin evento. La ausencia de un inventario no basta.
- Fijar una fecha de evaluación que respete cuándo estaban disponibles los reportes financieros. La fecha de corte contable no prueba disponibilidad.

La auditoría encontró empresas presentes en cortes antiguos que no aparecen en el actual y fechas de admisión posteriores a una presencia antigua. Las fuentes financieras consultadas no incluyen fecha de disponibilidad histórica.

El [borrador de consulta al tutor](consulta_tutor.txt) puede compartirse para resolverlo. No se ha enviado automáticamente. Tras esa validación se podrán preparar particiones temporales y comparar una referencia de prevalencia, regresión logística y Random Forest. El modelo y el umbral se elegirán con validación antes de abrir la prueba reservada.

## Evidencia histórica y MLflow

La carpeta [evidencia_20261107](evidencia_20261107/) conserva manifiestos y resúmenes agregados del avance original. Sus rutas describen aquella extracción y no indican que los datos estén incluidos en Git. Las nuevas ejecuciones escriben en `reports/preparacion/` y conservan separada esa evidencia. Los datos individuales y archivos grandes se recuperan mediante los programas.

El [registro con MLflow](mlflow.md) utiliza el servidor informado por Jairo, `http://52.91.138.185:8050`, y el experimento `Proyecto-MIAD`. La conexión AWS quedó pendiente de comprobar. El notebook con Iris de Jairo se conserva como prueba técnica y sus métricas corresponden a ese conjunto.

## Fuentes

- [Estado de situación financiera](https://www.datos.gov.co/d/pfdp-zks5).
- [Estado de resultado integral](https://www.datos.gov.co/d/prwj-nzxa).
- [Informes e inventarios de insolvencia de Supersociedades](https://www.supersociedades.gov.co/web/procedimientos-de-insolvencia/informes).
