# Piloto optimizado

Resultados generados con `notebooks/03_Optimizacion_Modelos_FINRISK.ipynb`.
Los hiperparámetros se eligieron en validación de origen 2023; el período de
prueba 2024 ya había sido consultado en el piloto original.

Ganador: bosque aleatorio, AP de validación 0,021111. En prueba: AP 0,022821,
62 de 155 presencias detectadas (40 %), 2.504 alertas y precisión 2,48 %.
El umbral F2 sellado es 0,458623. El aumento de detección viene acompañado
de un mayor volumen de alertas; los puntajes no son probabilidades calibradas.

Los modelos y puntajes individuales permanecen en `.cache/finrisk/piloto_optimizado/`.
Esta carpeta contiene únicamente resultados agregados y trazabilidad.

## MLflow registrado

Las tres corridas de validación y la prueba del ganador quedaron registradas
con el prefijo `Piloto optimizado` en el experimento
[Proyecto-MIAD](http://54.163.35.181:8050/#/experiments/2).
Los identificadores y enlaces están en `registro_mlflow.json`.
La descarga del ganador se verificó con SHA-256 idéntico al archivo entrenado.
No se subieron filas individuales.

El commit fuente del registro es `60923892c70dfbd20bbdb17565863546f1099312`.
Los modelos y métricas se reutilizaron de caché sin reevaluar prueba.
No se ha realizado push al repositorio remoto.
