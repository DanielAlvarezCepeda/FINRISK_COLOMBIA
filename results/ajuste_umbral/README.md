# Análisis de umbrales en validación

Se reutilizan exclusivamente los puntajes de origen 2023 del bosque optimizado:
28.677 observaciones, 164 positivas. No se entrena el modelo ni se consulta
prueba. El umbral actual 0,4586231433634672 se conserva como referencia y no
se adopta automáticamente ninguna alternativa.

Se comparan 0,30, 0,40, el umbral actual, 0,50, 0,60, 0,70, 0,80 y 0,90.
Los dos últimos no generan alertas: su precisión no está definida y no se
registra como cero en MLflow. AP es constante porque el ordenamiento no cambia.

- `comparacion_umbrales.csv`: métricas y matriz de confusión por alternativa.
- `curva_validacion.csv.gz`: curva completa en los puntajes observados.
- `analisis_umbral.json`: referencias al modelo, datos, código y métricas.
- `registro_mlflow.json`: enlaces a ocho corridas de `Proyecto-MIAD`, con el
  prefijo `Ajuste umbral`. Solo se publican agregados, sin NIT ni predicciones.

Desde la raíz, con las predicciones y el manifiesto del piloto disponibles:

```bash
python src/finrisk_piloto_umbral.py --salida .cache/finrisk/umbrales/nuevo_analisis
```

Para registrar o reintentar el registro del análisis existente:

```bash
python src/finrisk_piloto_umbral.py --salida .cache/finrisk/umbrales/nuevo_analisis --solo-registro --registrar-mlflow
```

La misma salida reutiliza sus corridas terminadas; no se sobrescriben análisis.
Una nueva salida constituye un análisis distinto. La validación ya se utilizó
en la búsqueda de hiperparámetros: estos son resultados exploratorios de
selección, no una evaluación independiente ni calibración de probabilidades.
La elección posterior requiere acordar capacidad de revisión y detección deseada.
