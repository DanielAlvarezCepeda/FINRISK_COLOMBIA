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

## MLflow pendiente

Se intentó conectar con `http://54.163.35.181:8050/`, pero la conexión agotó
el tiempo de espera antes de crear corridas. No se dispone de manifiesto remoto.
Cuando el servidor esté disponible, activar `FINRISK_REGISTRAR_MLFLOW=1` en el
entorno del kernel y ejecutar el notebook. El código debe estar incluido en
el commit local; las salidas del notebook pueden cambiar sin alterar su código.
El prefijo de las nuevas corridas será `Piloto optimizado`.

La ejecución completa en caché se reutiliza sin volver a evaluar prueba.
No se ha realizado push al repositorio remoto.
