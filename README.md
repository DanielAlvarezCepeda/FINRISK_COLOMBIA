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
- Recuperación y auditoría de las fuentes públicas para la segunda entrega.
- Construcción de la etiqueta del piloto retrospectivo de presencia en inventario.
- Comparación de tres alternativas y evaluación reservada del ganador.
- Registro y recuperación verificados de los modelos del piloto en MLflow.

Pendiente:

- Validación de primera admisión formal y disponibilidad histórica para el objetivo original.
- Desarrollo de API.
- Implementación del dashboard.
- Despliegue mediante Docker.

## 8. Consideraciones

Los resultados corresponden a un prototipo académico.

El piloto ya se entrenó con una etiqueta de aparición observada en el inventario
anual siguiente. Esa etiqueta no demuestra primera admisión formal ni solvencia
de los casos sin presencia. La disponibilidad histórica de los reportes sigue
sin verificarse; la evaluación es retrospectiva.

El puntaje no está calibrado como probabilidad de insolvencia. El desempeño
actual es débil: el ganador detecta 26 de 155 presencias observadas en prueba,
con 847 alertas sin presencia observada. El detalle y el alcance están en la sección 12.

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

La sección 12 documenta una recuperación nueva y un piloto con una etiqueta
observable. Para el objetivo original siguen pendientes la elegibilidad del
evento, las fechas de disponibilidad y el seguimiento completo. El umbral del
piloto es técnico; los mínimos operativos y la capacidad de revisión siguen
por acordarse. La importancia de variables no sustituye la evaluación predictiva.

## 12. Preparación de datos y experimentos de la segunda entrega

El objetivo original es estimar el riesgo de admisión formal durante los doce
meses siguientes a una evaluación. Como las fuentes no permiten validarlo aún,
el equipo adelanta un **piloto retrospectivo de aparición observada en el
inventario anual siguiente**, entre empresas sin antecedentes en los cortes
consultados. El cero expresa ausencia en ese inventario, no solvencia. Las ventanas
anuales son nominales y no se ha verificado la disponibilidad histórica de datos.

El avance del 7 de noviembre recuperó las fuentes públicas y reconstruyó un panel
preliminar sin etiquetas de 176.666 empresa-año y 37.231 empresas. Se separan las
evidencias históricas y las salidas de nuevas ejecuciones. Los datos individuales
y archivos grandes se recuperan con los programas y permanecen fuera de Git.
La configuración DVC anterior y el notebook técnico de Jairo se conservan.

- [Notebook ejecutado de preparación](notebooks/02_Preparacion_Datos_FINRISK.ipynb).
- [Instrucciones de descarga, auditoría y consolidación](docs/entrega2/preparacion_datos.md).
- [Etiqueta, modelos, métricas y reproducción del piloto](docs/entrega2/piloto_retrospectivo.md).
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
`python src/finrisk_comprobar_mlflow.py --tracking-uri http://54.163.35.181:8050 --experimento Proyecto-MIAD`.
El piloto quedó registrado en [Proyecto-MIAD, experimento 2](http://54.163.35.181:8050/#/experiments/2).
Se verificaron cuatro corridas terminadas (`FINISHED`): validación de las tres
alternativas y prueba reservada del ganador. Se subieron tres pipelines y se
recuperó el ganador con la misma huella SHA-256. El [manifiesto de registro](results/piloto_retrospectivo/registro_mlflow.json)
contiene los identificadores, enlaces y huellas reales, vinculados al commit
fuente `4cd8f32162b5349919c911445a4caa0de67ebc8a`. No se subieron filas individuales.

Para reproducir el modelado con las fuentes recuperadas:

```powershell
.\.venv\Scripts\python.exe src/finrisk_piloto_modelos.py --raiz . --salida .cache/finrisk/piloto_retrospectivo
```

Se construyeron 112.471 observaciones con cuatro indicadores, se entrenaron una
referencia de prevalencia, regresión logística y bosque aleatorio, y se eligió
el bosque por AP de validación. El umbral F2 se fijó en validación antes de una
única evaluación en prueba. En prueba: AP de 0,020718, sensibilidad de 16,77 % y
precisión de alertas de 2,978 % (26 aciertos en 873 alertas; 129 casos omitidos).
Son resultados débiles y no justifican aprobar o rechazar crédito.

Los modelos y predicciones individuales se guardan localmente en `.cache/finrisk/`,
excluidos de Git. La documentación del piloto contiene las reglas de etiqueta,
la población, las huellas, la inferencia y los comandos de registro en MLflow.
El tablero debe consultar el modelo sellado, mostrar un puntaje no calibrado y
compararlo con su umbral para emitir una alerta de revisión. El objetivo original
de primera admisión y la disponibilidad histórica siguen pendientes de validación.
Queda integrar esa consulta en el tablero y preparar las capturas de evidencia
para la entrega.

## 13. Entrega final: servicio de inferencia y despliegue

Esta entrega integra la API y el tablero sobre la versión de la segunda entrega
(`fe7a05973bbf3a6ff3895923377fc8aca0ba47ed`). Los notebooks, scripts de
preparación y entrenamiento, resultados de experimentos y documentación de las
entregas anteriores se conservan. Las instrucciones de esta sección y sus guías
actualizadas corresponden al prototipo funcional; las secciones anteriores
documentan el desarrollo histórico.

### Modelo utilizado y alcance

Se reutiliza el bosque aleatorio optimizado `piloto_optimizado_20261107`, sin
reentrenar (300 árboles, profundidad 16, mínimo 20 observaciones por hoja y
semilla 42). El umbral técnico F2 es `0.4586231433634672`; la variable objetivo
es presencia observada en el inventario anual siguiente, no primera admisión
formal en doce meses. El puntaje no está calibrado ni sirve para aprobar o
rechazar créditos automáticamente.

En validación (origen 2023), AP = 0.021111; en prueba retrospectiva (origen 2024,
ejercicio financiero 2023), AP = 0.022821, sensibilidad = 40.00 %, precisión de
alertas = 2.48 % y 2.504 alertas entre 28.949 observaciones (62 VP, 2.442 FP,
93 FN, 26.352 VN). El conjunto de prueba ya se había consultado en el piloto
original; no es una validación independiente del optimizado ni prospectiva.

Fuentes de trazabilidad: [selección sellada](results/piloto_optimizado/seleccion_sellada.json),
[prueba](results/piloto_optimizado/resultado_prueba.json),
[registro MLflow](results/piloto_optimizado/registro_mlflow.json),
[validación](results/piloto_optimizado/metricas_validacion.csv).

### Instalación y ejecución

1. Clonar el repositorio y seleccionar la rama/commit de esta entrega.
2. Obtener por un canal autorizado el pipeline `bosque_aleatorio.joblib` de la
   corrida optimizada (MLflow, experimento `Proyecto-MIAD`, corrida de validación
   `e2a43491e3e9495ca38960daba236660`, artefacto `modelo_joblib/bosque_aleatorio.joblib`).
   Guardarlo en `models/bosque_aleatorio.joblib`. El archivo no está en Git;
   no es necesario descargar los microdatos ni repetir el entrenamiento para servirlo.
3. Confirmar la huella SHA-256:
   `55fe564eaec27a1db78546895b3076db791e8ce3ee0155ce3e3ba264cb509f4f`.
   La API verifica la huella, el esquema y las versiones de entrenamiento antes
   de cargar el artefacto. No cargar archivos joblib de origen desconocido.
4. Con Docker Engine/Desktop (contenedores Linux) y Docker Compose, desde la raíz:

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
```

Abrir `http://127.0.0.1:8080/dashboard/`. La API se ejecuta en la red interna de
Compose y Nginx sirve el tablero y el proxy. Swagger: `http://127.0.0.1:8080/docs`.
Para ejecución sin Docker y pruebas automáticas, ver [guía API](GUIA_API.md).
Para la instalación local y AWS, ver [guía Docker](GUIA_DOCKER.md) y
[guía de integración](GUIA_INTEGRACION.md).

### Contrato de la API y tablero

| Método y ruta | Función |
| --- | --- |
| GET `/health` | Estado, versión y huella del modelo cargado |
| GET `/model/info` | Variables, umbral, versiones y trazabilidad |
| GET `/metrics` | Métricas agregadas archivadas de la evaluación |
| POST `/predict` | Inferencia individual y alerta frente al umbral |

Ejemplo de cuerpo JSON para `/predict`:

```json
{"liquidez_corriente":0.6,"endeudamiento":0.95,"roa":-0.12,"margen_neto":-0.10}
```

Resultado esperado en este ejemplo sintético: puntaje cercano a 0.6066,
`alerta: true`. Liquidez se expresa en veces; los demás indicadores, en razones
(95 % = 0.95). El tablero permite ingresarlos en porcentajes y los convierte.
El ejemplo A devuelve aproximadamente 0.2820, sin alerta. Se ejecutaron cinco
pruebas automáticas satisfactorias en el entorno Python de desarrollo y se
verificó la integración en Docker local y AWS EC2 con datos sintéticos.

Se mantienen los filtros descriptivos, año, fecha de evaluación, activo total y
rangos automático/manual del diseño anterior. Estos campos contextualizan el
análisis y no son entradas del modelo. La mediana histórica general no depende
del rango de activos. Las cohortes etiquetadas corresponden a ejercicios
2020–2023; los datos descriptivos de 2024 no aportan una nueva evaluación
etiquetada. Los comparadores por tamaño y presencia/ausencia observada quedan
como diseño pendiente por falta de microdatos homologados; una ausencia
observada no demuestra solvencia.

### Arquitectura, acceso y reproducibilidad

```text
Navegador -> Nginx (dashboard, proxy) -> FastAPI -> Random Forest sellado
               Docker Compose en AWS EC2 (Ubuntu 24.04, AMD64)
GitHub: código; DVC: datos; MLflow: experimentos y artefacto del modelo
```

La instancia de inferencia es independiente del servidor MLflow. El despliegue
se comprobó en una EC2 t3.small con acceso por puerto 8080 restringido a IP
autorizada. La dirección pública vigente se comunica al equipo y al evaluador;
puede cambiar al reiniciar el laboratorio. La configuración local por defecto
escucha solo en loopback. El acceso de demostración usa HTTP: únicamente datos
sintéticos, sin NIT, nombres ni información confidencial. No exponer los puertos
8000 o 8050 directamente. Se requiere HTTPS, autenticación y controles adicionales
antes de un uso operativo. El servicio de inferencia no utiliza DVC ni MLflow
en tiempo de ejecución; para reproducir el entrenamiento se requieren las fuentes
y el protocolo de la segunda entrega. El almacenamiento DVC compartido sigue
pendiente. No publicar llaves privadas, credenciales, microdatos ni imágenes que
contengan el modelo sin autorización.
