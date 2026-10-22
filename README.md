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
