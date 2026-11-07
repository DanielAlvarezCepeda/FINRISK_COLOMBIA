"""Registra el piloto retrospectivo y sus pipelines, sin entrenar ni enviar filas individuales."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import re

import joblib
import mlflow
import mlflow.sklearn
from mlflow.models import infer_signature
from mlflow.tracking import MlflowClient
import pandas as pd

if __package__:
    from .finrisk_piloto_modelos import CONFIGURACION, ORDEN_MODELOS, elegir_umbral_f2, evaluar_puntajes
else:
    from finrisk_piloto_modelos import CONFIGURACION, ORDEN_MODELOS, elegir_umbral_f2, evaluar_puntajes

FEATURES = ["liquidez_corriente", "endeudamiento", "roa", "margen_neto"]


def _sha(path):
    with Path(path).open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def _sha_json(objeto):
    """La misma representación canónica utilizada al sellar el entrenamiento."""
    contenido = json.dumps(objeto, ensure_ascii=False, sort_keys=True, allow_nan=False,
                           separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(contenido).hexdigest()


def _guardar(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + chr(10), encoding="utf-8")


def _metricas(registro, prefijo):
    valores = {
        f"{prefijo}_{k}": float(v) for k, v in registro.items()
        if isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
        and k not in {"umbral", "segundos_ajuste"}
    }
    valores.update({f"{prefijo}_{k}": v for k, v in registro["matriz_confusion"].items()})
    return valores


def _comparar_metricas(esperadas, recalculadas, nombre):
    for clave, valor in recalculadas.items():
        if clave not in esperadas:
            raise ValueError(f"Falta {clave} en las métricas de {nombre}.")
        guardado = esperadas[clave]
        if isinstance(valor, float):
            coincide = (isinstance(guardado, (int, float)) and not isinstance(guardado, bool)
                        and math.isfinite(guardado)
                        and math.isclose(guardado, valor, rel_tol=1e-12, abs_tol=1e-12))
        else:
            coincide = guardado == valor
        if not coincide:
            raise ValueError(f"Las métricas de {nombre} no coinciden con el CSV: {clave}.")


def preflight_piloto(resumen_path, commit_git):
    """Audita los archivos locales sin abrir MLflow, entrenar ni predecir otra prueba.

    Recalcula las métricas de los puntajes ya sellados. Las filas individuales
    permanecen locales; el informe de verificación contiene solo huellas y conteos.
    """
    if not re.fullmatch(r"[0-9a-f]{40}", commit_git):
        raise ValueError("Indique el SHA completo del commit que contiene el código del piloto.")
    resumen_path = Path(resumen_path).expanduser().resolve()
    base = resumen_path.parent
    resumen = json.loads(resumen_path.read_text(encoding="utf-8"))
    protocolo = json.loads((base / "protocolo_etiqueta.json").read_text(encoding="utf-8"))
    sello = json.loads((base / resumen["seleccion_sellada"]).read_text(encoding="utf-8"))
    firma = resumen["firma"]
    if _sha_json(sello) != resumen["sha256_seleccion"]:
        raise ValueError("La selección sellada no coincide con su huella canónica.")
    if sello["firma"] != firma or json.loads((base / "firma_ejecucion.json").read_text(encoding="utf-8")) != firma:
        raise ValueError("Las firmas del resumen, la ejecución y el sello difieren.")
    if _sha_json(protocolo) != firma["sha256_protocolo_etiqueta"]:
        raise ValueError("El protocolo completo difiere del que produjo los modelos.")
    configuracion = json.loads((base / "configuracion_modelado.json").read_text(encoding="utf-8"))
    if _sha_json(configuracion) != firma["sha256_configuracion"] or _sha_json(CONFIGURACION) != firma["sha256_configuracion"]:
        raise ValueError("La configuración difiere de la utilizada al entrenar.")
    if _sha(Path(__file__).with_name("finrisk_piloto_modelos.py")) != firma["sha256_script_modelado"]:
        raise ValueError("El código de entrenamiento difiere del que produjo los modelos.")
    for paquete, utilizada in firma["versiones"].items():
        if version(paquete) != utilizada:
            raise ValueError("Cambió una dependencia del entrenamiento: " + paquete)
    if (resumen["objetivo"] != "presencia_inventario_anual" or resumen["validacion_exante"] is not False
            or resumen["puntaje_calibrado"] is not False or resumen["alcance"] != "piloto_retrospectivo"):
        raise ValueError("El registro solo corresponde al piloto retrospectivo acordado.")
    if (protocolo["features"] != FEATURES or protocolo["horizonte_meses"] != 12
            or protocolo["rezago_financiero_ejercicios"] != 1
            or protocolo["origenes_por_particion"] != {"entrenamiento": [2021, 2022], "validacion": [2023], "prueba": [2024]}):
        raise ValueError("Los predictores o las cohortes no corresponden al piloto acordado.")
    modelos = resumen["modelos"]
    if len(modelos) != 3 or {r["modelo"] for r in modelos} != set(ORDEN_MODELOS):
        raise ValueError("Se requieren los tres candidatos distintos de validación.")
    ganador = next(r for r in modelos if r["modelo"] == resumen["ganador"])
    orden = {nombre: indice for indice, nombre in enumerate(ORDEN_MODELOS)}
    elegido = sorted(modelos, key=lambda r: (-r["ap"], orden[r["modelo"]]))[0]
    prueba = resumen["prueba"]
    if elegido["modelo"] != ganador["modelo"] or sello["prueba_consultada_para_seleccion"] is not False:
        raise ValueError("La selección no corresponde a la AP de validación sellada.")
    for clave in ("modelo", "umbral", "sha256_modelo"):
        if ganador[clave] != sello[clave] or prueba[clave] != sello[clave]:
            raise ValueError("El ganador, la prueba y el sello difieren: " + clave)
    if (resumen["umbral"] != sello["umbral"] or sello["ap_validacion"] != ganador["ap"]
            or prueba["sha256_seleccion"] != resumen["sha256_seleccion"]
            or prueba["numero_evaluaciones_prueba"] != 1 or prueba["modelo_reajustado_antes_prueba"] is not False
            or prueba["archivo_modelo"] != ganador["archivo_modelo"]
            or datetime.fromisoformat(sello["sellado_utc"]) > datetime.fromisoformat(prueba["evaluado_utc"])):
        raise ValueError("La prueba no conserva la selección y el modelo sellados.")
    huellas = {}
    claves_validacion = None
    for registro in [*modelos, prueba]:
        nombre, fase = registro["modelo"], registro["fase"]
        esperada = "prueba" if registro is prueba else "validacion"
        if fase != esperada:
            raise ValueError("Una evaluación tiene una fase incorrecta.")
        if _sha(base / registro["archivo_modelo"]) != registro["sha256_modelo"]:
            raise ValueError("Cambió el archivo del modelo " + nombre)
        if fase == "validacion" and _sha_json(registro["hiperparametros"]) != _sha_json(CONFIGURACION[nombre]):
            raise ValueError("Los hiperparámetros no corresponden a " + nombre)
        pred_path = base / registro["archivo_predicciones"]
        # El lector predeterminado puede redondear un puntaje constante bajo su umbral.
        pred = pd.read_csv(pred_path, dtype={"nit": str}, float_precision="round_trip")
        requeridas = {"nit", "anio_origen", "evento", "puntaje"}
        if not requeridas.issubset(pred.columns) or pred.empty or pred.duplicated(["nit", "anio_origen"]).any():
            raise ValueError("Las predicciones necesitan claves únicas y columnas completas: " + nombre)
        if (pred[list(requeridas)].isna().any().any() or not pred.nit.str.fullmatch(r"[0-9]{6,10}").all()
                or not pred.anio_origen.eq(2023 if fase == "validacion" else 2024).all()
                or set(pred.evento) != {0, 1} or not pred.puntaje.between(0, 1).all()):
            raise ValueError("Hay valores o cohortes inválidos en las predicciones: " + nombre)
        umbral = registro["umbral"]
        if isinstance(umbral, bool) or not isinstance(umbral, (int, float)) or not math.isfinite(umbral) or not 0 <= umbral <= 1:
            raise ValueError("El umbral no es válido: " + nombre)
        recalculadas = evaluar_puntajes(pred.evento, pred.puntaje, umbral)
        _comparar_metricas(registro, recalculadas, nombre + ":" + fase)
        if resumen["particiones"][fase] != {"n": recalculadas["n"], "positivos": recalculadas["positivos"]}:
            raise ValueError("Los conteos de la partición no coinciden con las predicciones.")
        if fase == "validacion":
            umbral_recalculado, _ = elegir_umbral_f2(pred.evento, pred.puntaje)
            if umbral != umbral_recalculado:
                raise ValueError("El umbral no corresponde al máximo F2 de validación: " + nombre)
            claves = pred[["nit", "anio_origen", "evento"]].sort_values(["nit", "anio_origen"]).reset_index(drop=True)
            if claves_validacion is not None and not claves.equals(claves_validacion):
                raise ValueError("Los candidatos no comparten las mismas filas y etiquetas de validación.")
            claves_validacion = claves
        huellas[nombre + ":" + fase] = {"sha256_predicciones": _sha(pred_path), "n": len(pred)}
    verificacion = {
        "preflight_local_superado": True, "sha256_seleccion": resumen["sha256_seleccion"],
        "sha256_protocolo_completo": firma["sha256_protocolo_etiqueta"],
        "metricas_recalculadas_desde_puntajes": True, "nuevas_predicciones_prueba": False,
        "evaluaciones": huellas, "filas_individuales_subidas": False,
    }
    return {"base": base, "resumen": resumen, "protocolo": protocolo, "sello": sello, "verificacion": verificacion}


def _validar_corrida_remota(corrida, experimento_id, parametros, tags, completa):
    """Evita reutilizar por accidente una corrida ajena o modificada."""
    if str(corrida.info.experiment_id) != str(experimento_id):
        raise ValueError("La corrida previa pertenece a otro experimento.")
    if getattr(corrida.info, "lifecycle_stage", "active") != "active":
        raise ValueError("La corrida previa fue eliminada.")
    if completa and corrida.info.status != "FINISHED":
        raise ValueError("Una corrida previa completada cambió de estado.")
    for clave, valor in parametros.items():
        remoto = corrida.data.params.get(clave)
        if (completa or remoto is not None) and remoto != str(valor):
            raise ValueError("La corrida previa difiere en el parámetro " + clave)
    for clave, valor in tags.items():
        remoto = corrida.data.tags.get(clave)
        if (completa or remoto is not None) and remoto != str(valor):
            raise ValueError("La corrida previa difiere en la etiqueta " + clave)


def registrar_piloto(resumen_path, commit_git, tracking_uri="http://54.163.35.181:8050",
                     experimento="Proyecto-MIAD", salida=None, autor=None):
    """Tres validaciones y una prueba del ganador; reutiliza las corridas ya completadas."""
    auditoria = preflight_piloto(resumen_path, commit_git)
    base, resumen, protocolo = auditoria["base"], auditoria["resumen"], auditoria["protocolo"]

    destino = Path(salida).resolve() if salida else base.parents[2] / "results/piloto_retrospectivo/registro_mlflow.json"
    estado_path = base / "estado_mlflow.json"
    identificacion = hashlib.sha256(json.dumps(
        {"firma": resumen["firma"], "commit": commit_git, "tracking_uri": tracking_uri,
         "experimento": experimento, "sha256_preflight": _sha_json(auditoria["verificacion"])},
        sort_keys=True).encode()).hexdigest()
    estado = json.loads(estado_path.read_text(encoding="utf-8")) if estado_path.exists() else {
        "identificacion": identificacion, "corridas": {}
    }
    if estado["identificacion"] != identificacion:
        raise ValueError("Existe otro registro MLflow en esta carpeta. Use una ejecución separada.")
    mlflow.set_tracking_uri(tracking_uri)
    exp = mlflow.set_experiment(experimento)
    client = MlflowClient(tracking_uri=tracking_uri)
    tags_base = {
        "finrisk.tipo": "piloto_retrospectivo", "finrisk.alcance": "piloto_retrospectivo",
        "finrisk.objetivo": "presencia_inventario_anual", "finrisk.validacion_exante": "no",
        "finrisk.puntaje_calibrado": "no", "ec2_public_ipv4": "54.163.35.181",
        "mlflow.source.git.commit": commit_git, "mlflow.source.name": "src/finrisk_piloto_modelos.py",
        "mlflow.source.type": "LOCAL",
    }
    if autor:
        tags_base["mlflow.user"] = autor
    requisitos = [f"{p}=={version(p)}" for p in ("mlflow", "scikit-learn", "numpy", "pandas", "cloudpickle")]
    ejemplo = pd.DataFrame([dict(zip(FEATURES, [1.0, 0.5, 0.02, 0.05]))])

    def ejecutar(registro, fase, validacion_id=None):
        clave = fase + ":" + registro["modelo"]
        previo = estado["corridas"].get(clave)
        parametros = {
            "modelo": registro["modelo"], "commit_git": commit_git,
            "version_base_etiquetada": protocolo["sha256_dataset"],
            "sha256_modelo": registro["sha256_modelo"], "sha256_seleccion": resumen["sha256_seleccion"],
            "sha256_protocolo": protocolo["sha256_protocolo"],
            "horizonte_nominal_meses": 12, "umbral": registro["umbral"],
            "anio_financiero_rezago": 1, "objetivo": "presencia_inventario_anual",
        }
        tags = {**tags_base, "finrisk.fase": fase}
        if validacion_id:
            val = client.get_run(validacion_id)
            _validar_corrida_remota(val, exp.experiment_id, parametros,
                                    {**tags_base, "finrisk.fase": "validacion"}, True)
            tags["finrisk.run_validacion"] = validacion_id
            parametros["modelo_uri_validacion"] = estado["corridas"]["validacion:" + registro["modelo"]]["model_uri"]
        if previo:
            existente = client.get_run(previo["run_id"])
            _validar_corrida_remota(existente, exp.experiment_id, parametros, tags, previo.get("completo", False))
            if previo.get("completo"):
                if (previo.get("modelo") != registro["modelo"] or previo.get("fase") != fase
                        or previo.get("sha256_modelo") != registro["sha256_modelo"]
                        or previo.get("umbral") != registro["umbral"] or not previo.get("model_uri")):
                    raise ValueError("El estado local no coincide con la corrida completada.")
                for k, valor in _metricas(registro, "val" if fase == "validacion" else "test").items():
                    if k not in existente.data.metrics or not math.isclose(existente.data.metrics[k], valor, rel_tol=1e-12, abs_tol=1e-12):
                        raise ValueError("Una métrica remota completada difiere: " + k)
                if validacion_id and previo["model_uri"] != parametros["modelo_uri_validacion"]:
                    raise ValueError("La prueba previa referencia otro pipeline.")
                return previo
        with mlflow.start_run(
            run_id=previo["run_id"] if previo else None, experiment_id=exp.experiment_id,
            run_name=f"Piloto inventario - {registro['modelo']} - {fase}", tags=tags
        ) as run:
            estado["corridas"][clave] = {**(previo or {}), "run_id": run.info.run_id, "completo": False}
            _guardar(estado_path, estado)
            mlflow.log_params(parametros)
            mlflow.log_metrics(_metricas(registro, "val" if fase == "validacion" else "test"))
            mlflow.log_dict(protocolo, "protocolo_etiqueta.json")
            mlflow.log_dict(auditoria["sello"], "seleccion_sellada.json")
            mlflow.log_dict(auditoria["verificacion"], "verificacion_local.json")
            mlflow.log_dict(registro, "resumen_evaluacion.json")
            model_uri = None
            if fase == "validacion":
                mlflow.log_dict(registro["hiperparametros"], "configuracion_modelo.json")
                mlflow.log_artifact(str(base / registro["archivo_modelo"]), artifact_path="modelo_joblib")
                pipeline = joblib.load(base / registro["archivo_modelo"])
                model_info = mlflow.sklearn.log_model(
                    pipeline, name="pipeline_" + registro["modelo"],
                    serialization_format="cloudpickle",
                    signature=infer_signature(ejemplo, pipeline.predict_proba(ejemplo)),
                    input_example=ejemplo, pyfunc_predict_fn="predict_proba", pip_requirements=requisitos,
                    metadata={"objetivo": "presencia_inventario_anual", "puntaje_calibrado": False,
                              "ejemplo_entrada_sintetico": True, "clases": [0, 1],
                              "columna_evento_1": 1},
                )
                model_uri = model_info.model_uri
            else:
                model_uri = estado["corridas"]["validacion:" + registro["modelo"]]["model_uri"]
                mlflow.log_param("modelo_uri_validacion", model_uri)
            informacion = {
                "run_id": run.info.run_id, "modelo": registro["modelo"], "fase": fase,
                "model_uri": model_uri, "sha256_modelo": registro["sha256_modelo"],
                "umbral": registro["umbral"],
                "url": tracking_uri.rstrip("/") + "/#/experiments/" + exp.experiment_id + "/runs/" + run.info.run_id,
            }
        if client.get_run(informacion["run_id"]).info.status != "FINISHED":
            raise ValueError("La corrida no terminó correctamente.")
        estado["corridas"][clave] = {**informacion, "completo": True}
        _guardar(estado_path, estado)
        return estado["corridas"][clave]

    validaciones = [ejecutar(r, "validacion") for r in resumen["modelos"]]
    validacion_ganador = next(x for x in validaciones if x["modelo"] == resumen["ganador"])
    prueba = ejecutar(resumen["prueba"], "prueba", validacion_ganador["run_id"])
    ganador = next(r for r in resumen["modelos"] if r["modelo"] == resumen["ganador"])
    descargas = base / "descarga_verificada"
    descargas.mkdir(exist_ok=True)
    descargado = Path(client.download_artifacts(
        validacion_ganador["run_id"], "modelo_joblib/" + Path(ganador["archivo_modelo"]).name, str(descargas)
    ))
    sha_recuperado = _sha(descargado)
    if sha_recuperado != ganador["sha256_modelo"]:
        raise ValueError("El pipeline recuperado difiere del archivo entrenado.")
    resultado = {
        "creado_utc": datetime.now(timezone.utc).isoformat(), "tracking_uri": tracking_uri,
        "experimento": experimento, "experiment_id": exp.experiment_id, "commit_fuente": commit_git,
        "objetivo": "presencia_inventario_anual", "alcance": "piloto_retrospectivo",
        "validacion_exante": False, "puntaje_calibrado": False,
        "version_base_etiquetada": protocolo["sha256_dataset"],
        "corridas_validacion": validaciones, "corrida_prueba": prueba,
        "pipeline_recuperado_sha256": sha_recuperado, "pipeline_recuperado_identico": True,
        "verificacion_local": auditoria["verificacion"],
        "filas_individuales_subidas": False,
    }
    _guardar(destino, resultado)
    return resultado


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--resumen", type=Path, default=Path(".cache/finrisk/piloto_retrospectivo/resumen_piloto.json"))
    parser.add_argument("--commit", required=True)
    parser.add_argument("--tracking-uri", default="http://54.163.35.181:8050")
    parser.add_argument("--experimento", default="Proyecto-MIAD")
    parser.add_argument("--salida", type=Path, default=Path("results/piloto_retrospectivo/registro_mlflow.json"))
    parser.add_argument("--autor")
    parser.add_argument("--solo-preflight", action="store_true", help="Audita el caché local sin conectarse a MLflow.")
    args = parser.parse_args()
    if args.solo_preflight:
        resultado = preflight_piloto(args.resumen, args.commit)["verificacion"]
    else:
        resultado = registrar_piloto(args.resumen, args.commit, args.tracking_uri, args.experimento, args.salida, args.autor)
    print(json.dumps(resultado, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
