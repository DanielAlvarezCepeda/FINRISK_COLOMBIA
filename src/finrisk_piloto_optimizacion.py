"""Búsqueda temporal acotada por AP, sin evaluar la partición de prueba.

No modifica los hiperparámetros del módulo de modelado. Los resultados de
validación son métricas de selección, no una evaluación independiente.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
import time

import pandas as pd
from sklearn.base import clone
from sklearn.model_selection import ParameterGrid

if __package__:
    from .finrisk_piloto_datos import cargar_construir
    from .finrisk_piloto_modelos import (
        FEATURES, _guardar_json, _modelos, _puntajes, _sha_archivo,
        _validar_datos, elegir_umbral_f2, evaluar_puntajes,
    )
else:
    from finrisk_piloto_datos import cargar_construir
    from finrisk_piloto_modelos import (
        FEATURES, _guardar_json, _modelos, _puntajes, _sha_archivo,
        _validar_datos, elegir_umbral_f2, evaluar_puntajes,
    )


ESPACIOS = {
    "regresion_logistica": {"modelo__C": [0.0001, 0.001, 0.003, 0.01, 0.03, 0.1, 1.0, 10.0, 100.0]},
    "bosque_aleatorio": [
        # Se conserva toda la búsqueda inicial para comparar ambas ejecuciones.
        {
            "modelo__max_depth": [4, 8, 12],
            "modelo__min_samples_leaf": [10, 20, 40],
            "modelo__max_features": ["sqrt", None],
        },
        # El mejor anterior estaba en el borde superior de profundidad.
        {
            "modelo__max_depth": [12, 16, 24, None],
            "modelo__min_samples_leaf": [20, 40, 80],
            "modelo__max_features": ["sqrt", 0.5, None],
        },
        # Sensibilidad al número de árboles alrededor del mejor anterior.
        {
            "modelo__max_depth": [12, 16],
            "modelo__min_samples_leaf": [40],
            "modelo__max_features": ["sqrt"],
            "modelo__n_estimators": [150, 600],
        },
    ],
}


def _candidatos(base, espacio):
    """Completa parámetros implícitos y elimina combinaciones repetidas."""
    grillas = espacio if isinstance(espacio, list) else [espacio]
    claves = sorted({k for grilla in grillas for k in grilla})
    originales = {k: base.get_params()[k] for k in claves}
    candidatos = []
    for parametros in ParameterGrid(espacio):
        completo = {**originales, **parametros}
        if completo not in candidatos:
            candidatos.append(completo)
    if originales not in candidatos:
        raise ValueError("La búsqueda debe incluir la configuración actual.")
    return originales, candidatos


def optimizar_piloto(raiz, salida):
    """Compara configuraciones e incluye la referencia actual por familia."""
    salida = Path(salida).expanduser().resolve()
    # Una carpeta nueva conserva tanto las búsquedas completas como las fallidas.
    salida.mkdir(parents=True, exist_ok=False)
    df, protocolo, cohortes = cargar_construir(raiz)
    datos = _validar_datos(df)
    train = datos.loc[datos.particion.eq("entrenamiento")]
    val = datos.loc[datos.particion.eq("validacion")]
    _guardar_json(salida / "protocolo_etiqueta.json", protocolo)
    cohortes.to_csv(salida / "cohortes_piloto.csv", index=False)
    metadatos = {
        "creado_utc": datetime.now(timezone.utc).isoformat(),
        "sha256_dataset": protocolo["sha256_dataset"],
        "sha256_script_modelado": _sha_archivo(Path(__file__).with_name("finrisk_piloto_modelos.py")),
        "sha256_script_optimizacion": _sha_archivo(__file__),
        "versiones": {p: version(p) for p in ("pandas", "numpy", "scikit-learn", "joblib")},
        "espacios": ESPACIOS,
        "criterio": "Mayor AP en validación; empate exacto prefiere referencia y luego orden de búsqueda.",
        "entrenamiento": [2021, 2022], "validacion": [2023],
        "prueba_evaluada": False,
        "nota": "Validación utilizada para selección de hiperparámetros; no es evaluación independiente.",
    }
    _guardar_json(salida / "busqueda.json", metadatos)
    registros, mejores = [], {}
    for nombre, espacio in ESPACIOS.items():
        base = _modelos()[nombre]
        originales, candidatos = _candidatos(base, espacio)
        for indice, parametros in enumerate(candidatos):
            modelo = clone(base).set_params(**parametros)
            inicio = time.monotonic()
            modelo.fit(train[list(FEATURES)], train.evento)
            segundos = time.monotonic() - inicio
            scores = _puntajes(modelo, val[list(FEATURES)])
            umbral, _ = elegir_umbral_f2(val.evento, scores)
            registro = {
                "modelo": nombre, "candidato": indice,
                "es_referencia": parametros == originales,
                "parametros": parametros, "segundos_ajuste": segundos,
                **evaluar_puntajes(val.evento, scores, umbral),
            }
            registros.append(registro)
            _guardar_json(salida / "resultados_validacion.json", registros)
            print(f"{nombre} {indice + 1}/{len(candidatos)} AP={registro['ap']:.8f} {parametros}", flush=True)
        familia = [r for r in registros if r["modelo"] == nombre]
        referencia = next(r for r in familia if r["es_referencia"])
        ganador = sorted(familia, key=lambda r: (-r["ap"], not r["es_referencia"], r["candidato"]))[0]
        mejores[nombre] = {
            "parametros_referencia": originales,
            "ap_referencia": referencia["ap"],
            "parametros_elegidos": ganador["parametros"],
            "ap_elegida": ganador["ap"],
            "mejora_ap": ganador["ap"] - referencia["ap"],
            "mejora_estricta": ganador["ap"] > referencia["ap"],
        }
    filas = [{**{k: v for k, v in r.items() if k not in ("parametros", "matriz_confusion")},
              **r["parametros"]} for r in registros]
    pd.DataFrame(filas).to_csv(salida / "resultados_validacion.csv", index=False)
    resumen = {**metadatos, "configuraciones_evaluadas": len(registros), "mejores": mejores}
    _guardar_json(salida / "resumen_optimizacion.json", resumen)
    return resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    salida = args.salida or args.raiz / ".cache/finrisk/optimizacion" / datetime.now(timezone.utc).strftime("busqueda_%Y%m%dT%H%M%S%fZ")
    resumen = optimizar_piloto(args.raiz, salida)
    print(pd.DataFrame(resumen["mejores"]).T.to_string())
    print("Resultados:", salida.resolve())


if __name__ == "__main__":
    main()
