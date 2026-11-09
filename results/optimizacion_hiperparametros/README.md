# Optimización de hiperparámetros del piloto

Resultados de la búsqueda del 7 de noviembre de 2026: 9 configuraciones de
regresión logística y 54 de bosque aleatorio. Se reutilizaron los pipelines de
`src/finrisk_piloto_modelos.py`, conservando imputación, transformaciones, pesos
de clase y semilla. Cada configuración se ajustó con los orígenes 2021–2022
(54.845 observaciones, 262 positivas) y se comparó por precisión promedio (AP)
en origen 2023 (28.677 observaciones, 164 positivas).

| Modelo | AP de referencia | Mejor AP | Parámetros seleccionados |
| --- | ---: | ---: | --- |
| Regresión logística | 0,012903 | 0,013148 | `C=0.0001` |
| Bosque aleatorio | 0,017315 | 0,021111 | `max_depth=16`, `min_samples_leaf=20`, `max_features="sqrt"`, `n_estimators=300` |

La mejora relativa del bosque respecto a su referencia es aproximadamente
21,9 %. Las configuraciones originales se evaluaron sobre los mismos datos
locales que los candidatos. La huella del dataset local difiere de la del
piloto histórico, aunque coinciden los conteos por partición; esta comparación
utiliza exclusivamente la nueva extracción.

## Archivos

- `resultados_validacion.csv`: las 63 configuraciones, sus hiperparámetros,
  tiempos de ajuste y métricas de validación. `es_referencia` identifica la
  configuración original de cada familia. Los candidatos se numeran desde cero
  dentro de cada familia. Una celda vacía en un hiperparámetro puede indicar
  `None` o que no aplica a esa familia; consultar los espacios del JSON.
- `mejores_hiperparametros.json`: parámetros originales y elegidos, métricas AP,
  espacios de búsqueda, versiones y huellas de los datos, los scripts y el CSV.
  Las claves `modelo__...` pueden pasarse al `set_params()` de los pipelines.

Los hiperparámetros no explorados mantienen los valores del módulo de modelado
identificado por su huella. No se incluyen datos individuales ni modelos
entrenados en esta carpeta.

## Reproducir

Con las fuentes locales preparadas y el entorno del proyecto activado, ejecutar
desde la raíz:

```bash
python src/finrisk_piloto_optimizacion.py
```

El comando crea una carpeta nueva en `.cache/finrisk/optimizacion/`. No reemplaza
esta evidencia compartida. Las huellas de los scripts permiten comprobar si el
código utilizado sigue siendo el de esta búsqueda; los tiempos pueden variar.

## Interpretación y uso

La validación se utilizó para elegir hiperparámetros: sus métricas son resultados
de selección, no una evaluación independiente. Esta búsqueda amplía una búsqueda
previa de 23 configuraciones sobre la misma validación; las 23 están incluidas
en las 63 aquí presentadas. No se evaluó la partición de prueba en ninguna de
estas búsquedas. El umbral de cada candidato se calculó con F2 en validación,
pero el criterio de selección de hiperparámetros fue AP.

`finrisk_piloto_modelos.py` permanece sin cambios. Este JSON no se carga
automáticamente desde ese módulo. Para adoptar los parámetros posteriormente,
actualizar únicamente los valores correspondientes en `_modelos()` y en
`CONFIGURACION`, manteniendo la coherencia entre implementación y registro.
