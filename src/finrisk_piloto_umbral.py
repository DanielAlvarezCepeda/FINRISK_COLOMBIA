"""Compara umbrales en validación sin entrenar, consultar prueba ni adoptar uno nuevo."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

if __package__:
    from .finrisk_piloto_modelos import _guardar_json, _sha_archivo, elegir_umbral_f2, evaluar_puntajes
else:
    from finrisk_piloto_modelos import _guardar_json, _sha_archivo, elegir_umbral_f2, evaluar_puntajes


def analizar_umbrales(base, manifiesto, salida, umbrales):
    base, salida = Path(base).resolve(), Path(salida).resolve()
    if salida.exists():
        raise ValueError("Use una carpeta de salida nueva para conservar los análisis anteriores.")
    registro = json.loads(Path(manifiesto).read_text(encoding="utf-8"))
    resumen = json.loads((base / "resumen_piloto.json").read_text(encoding="utf-8"))
    modelo = resumen["ganador"]
    fuente = next(r for r in registro["corridas_validacion"] if r["modelo"] == modelo)
    local = next(r for r in resumen["modelos"] if r["modelo"] == modelo)
    archivo = (base / local["archivo_predicciones"]).resolve()
    if not archivo.is_relative_to(base / "predicciones"):
        raise ValueError("Las predicciones deben estar dentro de la carpeta local de predicciones.")
    esperado = registro["verificacion_local"]["evaluaciones"][modelo + ":validacion"]["sha256_predicciones"]
    if _sha_archivo(archivo) != esperado or fuente["sha256_modelo"] != local["sha256_modelo"]:
        raise ValueError("Las predicciones o el modelo difieren del registro de MLflow.")
    protocolo = json.loads((base / "protocolo_etiqueta.json").read_text(encoding="utf-8"))
    if protocolo["sha256_dataset"] != registro["version_base_etiquetada"]:
        raise ValueError("La versión del dataset difiere del registro de MLflow.")
    pred = pd.read_csv(archivo, dtype={"nit": str}, float_precision="round_trip")
    if (not pred.anio_origen.eq(2023).all() or pred.duplicated(["nit", "anio_origen"]).any()
            or set(pred.evento) != {0, 1} or not pred.puntaje.between(0, 1).all()):
        raise ValueError("Se requieren puntajes válidos de la cohorte de validación 2023.")
    referencia = float(local["umbral"])
    recalculado, curva = elegir_umbral_f2(pred.evento, pred.puntaje)
    if abs(recalculado - referencia) > 1e-12 or referencia != fuente["umbral"]:
        raise ValueError("El umbral de referencia no coincide con el F2 o el registro original.")
    originales = evaluar_puntajes(pred.evento, pred.puntaje, referencia)
    for clave in ("n", "positivos", "alertas", "ap", "f2"):
        if not np.isclose(originales[clave], local[clave], atol=1e-12, rtol=1e-12):
            raise ValueError("No se reprodujeron las métricas originales: " + clave)
    valores = sorted(set([referencia, *umbrales]))
    if not all(np.isfinite(t) and 0 <= t <= 1 for t in valores):
        raise ValueError("Los umbrales deben ser finitos y estar entre cero y uno.")
    resultados = []
    for t in valores:
        m = evaluar_puntajes(pred.evento, pred.puntaje, t)
        matriz = m.pop("matriz_confusion")
        resultados.append({"es_referencia": t == referencia, **m, **matriz})
    salida.mkdir(parents=True)
    curva.to_csv(salida / "curva_validacion.csv.gz", index=False)
    pd.DataFrame(resultados).to_csv(salida / "comparacion_umbrales.csv", index=False)
    analisis = {
        "creado_utc": datetime.now(timezone.utc).isoformat(), "modelo": modelo,
        "fase": "validacion", "anio_origen": 2023,
        "run_id_modelo": fuente["run_id"], "model_uri": fuente["model_uri"],
        "sha256_modelo": fuente["sha256_modelo"], "sha256_predicciones": esperado,
        "sha256_dataset": protocolo["sha256_dataset"],
        "sha256_script": _sha_archivo(__file__), "umbral_referencia": referencia,
        "tracking_uri": registro["tracking_uri"], "experimento": registro["experimento"],
        "prueba_consultada": False, "modelo_reentrenado": False,
        "umbral_adoptado": False,
        "nota": "Análisis exploratorio en validación ya utilizada para seleccionar hiperparámetros. No calibra probabilidades.",
        "resultados": resultados,
    }
    _guardar_json(salida / "analisis_umbral.json", analisis)
    return analisis


def registrar_umbrales(salida):
    """Registra agregados; reutiliza corridas terminadas con la misma identidad."""
    import mlflow
    from mlflow.tracking import MlflowClient

    salida = Path(salida).resolve()
    analisis = json.loads((salida / "analisis_umbral.json").read_text(encoding="utf-8"))
    identidad = hashlib.sha256((salida / "analisis_umbral.json").read_bytes()).hexdigest()
    mlflow.set_tracking_uri(analisis["tracking_uri"])
    experimento = mlflow.set_experiment(analisis["experimento"])
    client = MlflowClient(tracking_uri=analisis["tracking_uri"])
    corridas = []
    for i, m in enumerate(analisis["resultados"]):
        clave = f"{identidad}-{i}"
        previas = client.search_runs([experimento.experiment_id],
                                    filter_string=f"tags.`finrisk.analisis_umbral` = '{clave}'")
        if len(previas) > 1:
            raise ValueError("Hay corridas duplicadas para este umbral.")
        if previas and previas[0].info.status != "FINISHED":
            raise ValueError("Revise la corrida incompleta antes de registrar nuevamente.")
        if previas:
            run_id = previas[0].info.run_id
        else:
            with mlflow.start_run(run_name=f"Ajuste umbral - {analisis['modelo']} - t={m['umbral']:.6f}",
                                  experiment_id=experimento.experiment_id,
                                  tags={"finrisk.analisis_umbral": clave, "finrisk.fase": "validacion",
                                        "finrisk.run_modelo": analisis["run_id_modelo"],
                                        "finrisk.sha256_script": analisis["sha256_script"],
                                        "finrisk.tipo": "ajuste_umbral", "finrisk.prueba_consultada": "no"}) as run:
                mlflow.log_params({"umbral": m["umbral"], "es_referencia": m["es_referencia"],
                                   "modelo": analisis["modelo"], "anio_origen": 2023,
                                   "sha256_dataset": analisis["sha256_dataset"],
                                   "sha256_modelo": analisis["sha256_modelo"],
                                   "model_uri": analisis["model_uri"]})
                mlflow.log_metrics({k: float(v) for k, v in m.items()
                                    if k not in ("umbral", "es_referencia") and v is not None})
                for nombre in ("analisis_umbral.json", "comparacion_umbrales.csv", "curva_validacion.csv.gz"):
                    mlflow.log_artifact(str(salida / nombre), artifact_path="analisis_agregado")
                run_id = run.info.run_id
        corridas.append({"umbral": m["umbral"], "run_id": run_id,
                         "url": f"{analisis['tracking_uri']}/#/experiments/{experimento.experiment_id}/runs/{run_id}"})
        _guardar_json(salida / "registro_mlflow.json", {"corridas": corridas})
    return corridas


def main():
    raiz = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, default=raiz / ".cache/finrisk/piloto_optimizado")
    parser.add_argument("--manifiesto", type=Path, default=raiz / "results/piloto_optimizado/registro_mlflow.json")
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--umbrales", type=float, nargs="+", default=[0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9])
    parser.add_argument("--registrar-mlflow", action="store_true")
    parser.add_argument("--solo-registro", action="store_true", help="Reintenta el registro de una salida existente.")
    args = parser.parse_args()
    if args.solo_registro and (not args.salida or not args.registrar_mlflow):
        parser.error("--solo-registro requiere --salida y --registrar-mlflow")
    salida = args.salida or raiz / ".cache/finrisk/umbrales" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    if not args.solo_registro:
        analisis = analizar_umbrales(args.base, args.manifiesto, salida, args.umbrales)
        print(pd.DataFrame(analisis["resultados"])[["umbral", "es_referencia", "sensibilidad", "precision_alertas", "alertas", "fp", "fn"]].to_string(index=False))
    print("Salida:", salida)
    if args.registrar_mlflow:
        print(json.dumps(registrar_umbrales(salida), indent=2))


if __name__ == "__main__":
    main()
