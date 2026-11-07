# FINRISK Colombia

## Sistema Predictivo de Riesgo de Insolvencia Empresarial

Proyecto académico desarrollado para la asignatura
Despliegue de Soluciones Analíticas de la Maestría
en Inteligencia Analítica de Datos.

## 1. Descripción del proyecto

FINRISK Colombia tiene como objetivo desarrollar un
sistema de analítica predictiva que permita identificar
patrones financieros asociados con el riesgo de ingreso
a procesos de insolvencia empresarial en Colombia.

## 2. Fuentes de información

Se utilizan bases de datos públicas de la
Superintendencia de Sociedades de Colombia:

- Estado de situación financiera.
- Estado de resultado integral.
- Registros de procesos de insolvencia empresarial.

## 3. Información procesada

Periodo financiero: 2019-2024.

Resultados preliminares:

- 27.729.765 registros financieros procesados.
- 37.231 empresas identificadas.
- 176.666 observaciones empresa-año.
- 161.411 observaciones seleccionadas para el análisis
  descriptivo estricto.

## 4. Indicadores financieros

- Endeudamiento.
- Liquidez corriente.
- Rentabilidad sobre activos (ROA).
- Rentabilidad patrimonial (ROE).
- Margen neto.
- Capital de trabajo.

## 5. Tecnologías

- Python
- Pandas
- NumPy
- Matplotlib
- Scikit-learn
- Git y GitHub
- DVC
- MLflow
- FastAPI
- Plotly Dash
- Docker

## 6. Estructura del proyecto

- src/: programas de procesamiento.
- data/processed/: datos consolidados versionados.
- reports/: resultados y visualizaciones.
- dashboard/: aplicación web.
- api/: servicio de predicciones.
- docs/: documentación académica.

## 7. Estado actual

Completado:
- Recolección de información financiera.
- Exploración inicial.
- Consolidación preliminar.
- Cálculo preliminar de indicadores.
- Análisis descriptivo.
- Versionamiento inicial mediante Git y DVC.

Pendiente:
- Validación de la variable objetivo de insolvencia.
- Entrenamiento de modelos supervisados.
- Comparación de modelos con MLflow.
- Desarrollo de API.
- Implementación del dashboard.
- Despliegue mediante Docker.

## 8. Consideraciones

Los resultados corresponden a un prototipo académico.

La base financiera todavía requiere verificaciones
adicionales antes de utilizarse para entrenamiento.

No se ha validado ni calculado definitivamente la
variable objetivo de insolvencia futura.

Las predicciones no deben utilizarse como diagnósticos
financieros definitivos.

## 9. Revisión de la primera entrega: notebook y mockup

La revisión posterior a la retroalimentación del profesor se reúne en la rama
`correcciones/entrega1-20261105`, para revisión del equipo antes de su integración
a `main`. El código de procesamiento y la configuración DVC existentes se conservan.

Accesos de esta revisión:

- [Notebook ejecutado de exploración](notebooks/01_EDA_FINRISK.ipynb).
- [Mockup actualizado](dashboard/index.html). Para usarlo, abrir el archivo local con Chrome o Edge.
- [Insumos agregados](data/agregados/) y [resultados reproducibles](results/).
- [Dependencias del notebook](requirements.txt).

La pregunta se concreta en la proporción de eventos de insolvencia formal
detectados y la proporción de alertas correctas para priorizar la revisión
crediticia. El horizonte propuesto es de doce meses posteriores a la evaluación,
condicionado a validar fechas de admisión, disponibilidad de información y seguimiento.

El notebook explora seis insumos agregados y conserva salidas de trece celdas
de código ejecutadas, ocho controles iniciales, nueve tablas CSV y cinco figuras.
La revisión añade retención anual del filtro descriptivo, una matriz que conecta
hallazgos con preparación y límites, y un protocolo predictivo propuesto.

El mockup separa la respuesta individual de la evaluación global del modelo.
Los escenarios simbólicos de prioridad son ilustrativos; no calculan probabilidades
ni aprueban o rechazan crédito. AP, sensibilidad y precisión de alertas están
propuestas para evaluación futura. La etiqueta histórica y el modelo aún no
están validados, y no se presentan métricas predictivas calculadas.

## 10. Trabajar desde un clon local

El repositorio es privado: el usuario debe tener acceso en GitHub. Para obtener
esta revisión por primera vez, ejecutar desde la carpeta donde se guardan los proyectos:

```powershell
git clone https://github.com/DanielAlvarezCepeda/FINRISK_COLOMBIA.git
cd FINRISK_COLOMBIA
git switch correcciones/entrega1-20261105
```

Si el repositorio ya está clonado, abrir una terminal en su raíz y revisar el estado
local antes de actualizar. Para consultar esta rama sin cambios locales pendientes:

```powershell
git status
git fetch origin
git switch correcciones/entrega1-20261105
```

Las rutas siguientes parten de la raíz `FINRISK_COLOMBIA`, donde está este README.
No es necesario extraer el ZIP anterior ni entrar en una carpeta adicional `FINRISK/`.

### Preparar y ejecutar el notebook en Windows

Entorno probado: Python 3.12. Los comandos usan el ejecutable del entorno para
evitar depender de la activación de scripts de PowerShell:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pip install jupyterlab
.\.venv\Scripts\python.exe -m jupyterlab
```

Abrir `notebooks/01_EDA_FINRISK.ipynb`, seleccionar el Python del entorno `.venv`
y ejecutar todas las celdas. También puede abrirse en VS Code con la extensión
de Jupyter, seleccionando ese mismo entorno.

El notebook localiza `data/agregados/` tanto desde la raíz como desde `notebooks/`.
Lee los seis insumos incluidos, sin descargarlos ni modificarlos, y escribe las
tablas y figuras en `results/`. No se necesita recuperar la base DVC para esta
exploración de agregados.

### Archivos incorporados para la exploración

```text
notebooks/01_EDA_FINRISK.ipynb     Notebook principal
data/agregados/                  Cuatro CSV y dos TXT originales del avance
data/privados/                   Entrada individual opcional, excluida de Git
src/auditoria_microdatos.py      Auditoría individual opcional
results/tablas/                  Nueve tablas reproducibles
results/figuras/                 Cinco figuras
results/manifiesto_ejecucion.json
requirements.txt                Dependencias del notebook
```

## 11. Agregados, datos individuales y DVC

Los agregados describen el panel financiero preliminar de 2019-2024. Su exploración
no reproduce íntegramente la consolidación original ni permite reconstruir filas
individuales, asignar clases de insolvencia o estimar el desempeño de un modelo.
El filtro descriptivo estricto no se trasladará automáticamente al entrenamiento.

La base individual continúa referenciada en
`data/processed/base_financiera_preliminar.csv.dvc`. El remoto DVC actualmente
configurado apunta a una ruta local del equipo de origen
(`C:\Users\User\Desktop\FINRISK_DVC_REMOTE`); esa ruta no se vuelve accesible
en otro computador por clonar Git. El equipo debe acordar una recuperación
verificable antes de ejecutar análisis que requieran el CSV individual.
No se cambió el remoto ni se incorporó una copia del CSV a Git.

La auditoría individual opcional del notebook busca
`data/privados/base_financiera_preliminar.csv`. Esa entrada no está incluida en
esta revisión; su código y resultados no deben confundirse con comprobaciones
realizadas sobre microdatos. Si el equipo obtiene la base, debe validar su
procedencia, esquema y correspondencia antes de habilitar esa sección.

Esta publicación reúne el EDA y el mockup en el repositorio principal del equipo.
La [publicación previa complementaria de Joaquín](https://github.com/joaquinrovi/FINRISK/tree/main/FINRISK)
se conserva como antecedente; las instrucciones de esta revisión corresponden
a la raíz del repositorio `DanielAlvarezCepeda/FINRISK_COLOMBIA`.

Antes de modelar, quedan por acordar la elegibilidad del evento, las fechas de
evaluación y disponibilidad, el seguimiento completo, las particiones temporales,
el umbral de alerta y los mínimos operativos de sensibilidad, precisión y capacidad
de revisión. La importancia de variables complementará la explicación, sin
sustituir la evaluación predictiva.

## 12. Preparación de datos y experimentos de la segunda entrega

El objetivo confirmado es estimar el riesgo de admisión a un proceso formal de
insolvencia durante los doce meses siguientes a la evaluación. El tablero previsto
permitirá consultar la predicción por empresa, mostrar el riesgo y la alerta
y apoyar la revisión crediticia. La etiqueta y los modelos de FINRISK continúan
pendientes de validación.

El avance del 7 de noviembre recuperó las fuentes públicas y reconstruyó un panel
preliminar sin etiquetas de 176.666 empresa-año y 37.231 empresas. Se separan las
evidencias históricas y las salidas de nuevas ejecuciones. Los datos individuales
y archivos grandes se recuperan con los programas y permanecen fuera de Git.
La configuración DVC anterior y el notebook técnico de Jairo se conservan.

- [Notebook ejecutado de preparación](notebooks/02_Preparacion_Datos_FINRISK.ipynb).
- [Instrucciones de descarga, auditoría y consolidación](docs/entrega2/preparacion_datos.md).
- [Conexión y registro en el MLflow de Jairo](docs/entrega2/mlflow.md).
- [Evidencia agregada del avance](docs/entrega2/evidencia_20261107/).
- [Consulta preparada para el tutor](docs/entrega2/consulta_tutor.txt).
- [Dependencias adicionales](requirements-entrega2.txt), que extienden el entorno existente.

Desde la raíz del repositorio, instalar el entorno adicional y ejecutar los pasos
de preparación antes de volver a correr el notebook.

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-entrega2.txt
.\.venv\Scripts\python.exe src/descargar_financieros.py
.\.venv\Scripts\python.exe src/descargar_insolvencia.py
.\.venv\Scripts\python.exe src/auditar_insolvencia.py
.\.venv\Scripts\python.exe src/consolidar_recuperacion.py
```

Para consultar el servidor informado por Jairo sin crear corridas, usar
`python src/finrisk_comprobar_mlflow.py --tracking-uri http://52.91.138.185:8050 --experimento Proyecto-MIAD`.
La guía de MLflow distingue esa consulta de la prueba técnica que sí escribe un
artefacto. El acceso AWS quedó pendiente de comprobar. Las pruebas del registrador
se realizaron con un servidor local y datos sintéticos.

Se mantiene el objetivo a doce meses y se validarán con el tutor la primera
admisión, el seguimiento de los casos sin evento y la disponibilidad histórica
de los reportes antes de entrenar. El cruce de inventarios es descriptivo.
