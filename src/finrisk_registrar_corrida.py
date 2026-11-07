"""Registra en MLflow una evaluación de FINRISK a partir de puntajes ya calculados."""

import argparse
import csv
import hashlib
import ipaddress
import json
import math
import re
from datetime import date
from pathlib import Path

import mlflow
from mlflow.exceptions import MlflowException
from sklearn.metrics import average_precision_score, confusion_matrix

PERIODOS = ("entrenamiento", "validacion", "prueba")


def leer_puntajes(ruta):
    eventos, puntajes = [], []
    with ruta.open(encoding="utf-8-sig", newline="") as archivo:
        filas = csv.DictReader(archivo)
        if not {"evento", "puntaje"}.issubset(filas.fieldnames or ()):
            raise ValueError("El CSV requiere las columnas evento y puntaje.")
        for fila in filas:
            evento = fila.get("evento")
            if evento not in {"0", "1"}:
                raise ValueError(f"Evento inválido en la fila {filas.line_num}: use 0 o 1.")
            puntaje = float(fila.get("puntaje") or "")
            if not math.isfinite(puntaje):
                raise ValueError(f"Puntaje no finito en la fila {filas.line_num}.")
            eventos.append(int(evento))
            puntajes.append(puntaje)
    if set(eventos) != {0, 1}:
        raise ValueError("La partición requiere observaciones de ambas clases para evaluar AP.")
    return eventos, puntajes


def evaluar(eventos, puntajes, umbral):
    n = len(eventos)
    positivos = sum(eventos)
    resumen = {
        "n": n, "positivos": positivos, "negativos": n - positivos,
        "prevalencia": positivos / n,
        "ap": float(average_precision_score(eventos, puntajes)),
        "umbral": umbral,
        "sensibilidad": None, "precision_alertas": None, "alertas": None,
        "matriz_confusion": None,
    }
    if umbral is None:
        return resumen

    vn, fp, fn, vp = (
        int(valor) for valor in
        confusion_matrix(eventos, [int(p >= umbral) for p in puntajes], labels=[0, 1]).ravel()
    )
    alertas = vp + fp
    resumen.update({
        "sensibilidad": vp / positivos,
        "precision_alertas": vp / alertas if alertas else None,
        "alertas": alertas,
        "matriz_confusion": {"vp": vp, "fp": fp, "fn": fn, "vn": vn},
    })
    return resumen


def cargar_corrida(ruta):
    datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
    if not isinstance(datos, dict):
        raise ValueError("El manifiesto debe ser un objeto JSON.")
    for campo in ("modelo", "version_base_etiquetada", "commit_git",
                  "regla_etiqueta", "predicciones_csv", "artefacto_modelo"):
        if not isinstance(datos.get(campo), str) or not datos[campo].strip():
            raise ValueError(f"Complete el campo {campo}.")
    if not re.fullmatch(r"[0-9a-fA-F]{7,40}", datos["commit_git"]):
        raise ValueError("commit_git debe identificar un commit Git válido.")
    if datos.get("horizonte_meses") != 12:
        raise ValueError("Esta plantilla corresponde al horizonte propuesto de doce meses.")
    fase = datos.get("fase")
    if fase not in {"validacion", "prueba"}:
        raise ValueError("fase debe ser validacion o prueba.")

    cortes = datos["periodos"]
    limites = [
        (date.fromisoformat(cortes[p]["desde"]), date.fromisoformat(cortes[p]["hasta"]))
        for p in PERIODOS
    ]
    if any(desde > hasta for desde, hasta in limites) or any(
        anterior[1] >= siguiente[0] for anterior, siguiente in zip(limites, limites[1:])
    ):
        raise ValueError("Revise el orden de los periodos de entrenamiento, validación y prueba.")
    umbral = datos.get("umbral")
    if umbral is not None:
        if isinstance(umbral, bool) or not isinstance(umbral, (float, int)):
            raise ValueError("umbral debe ser numérico o null.")
        if not math.isfinite(umbral):
            raise ValueError("umbral debe ser finito.")
        umbral = float(umbral)
        datos["umbral"] = umbral
    if fase == "prueba" and (
        umbral is None or not re.fullmatch(r"[0-9a-f]{32}", datos.get("run_id_validacion") or "")
    ):
        raise ValueError("Para la prueba final indique el umbral y el ID de la corrida de validación.")
    if not isinstance(datos.get("hiperparametros"), dict):
        raise ValueError("hiperparametros debe ser un objeto JSON.")

    modelo = ruta.parent / datos["artefacto_modelo"]
    if modelo.suffix.lower() not in {".joblib", ".pkl", ".skops", ".onnx"} or not modelo.is_file():
        raise ValueError("Indique un archivo de modelo existente (.joblib, .pkl, .skops u .onnx).")
    eventos, puntajes = leer_puntajes(ruta.parent / datos["predicciones_csv"])
    return datos, modelo, evaluar(eventos, puntajes, umbral)


def registrar(datos, modelo, metricas, etiquetas, destino, experimento="FINRISK - Entrega 2"):
    fase = datos["fase"]
    etiquetas.update({"finrisk.tipo": "evaluacion", "finrisk.fase": fase})
    vinculados = ("modelo", "commit_git", "version_base_etiquetada", "horizonte_meses")
    parametros = {k: datos[k] for k in vinculados}
    protocolo = {k: datos[k] for k in ("periodos", "regla_etiqueta", "hiperparametros")}
    protocolo_bytes = json.dumps(protocolo, sort_keys=True).encode("utf-8")
    parametros["sha256_protocolo"] = hashlib.sha256(protocolo_bytes).hexdigest()
    with modelo.open("rb") as archivo:
        parametros["sha256_modelo"] = hashlib.file_digest(archivo, "sha256").hexdigest()
    if datos.get("umbral") is not None:
        parametros["umbral"] = datos["umbral"]
    if fase == "prueba":
        seleccionado = mlflow.get_experiment_by_name(experimento)
        anterior = mlflow.get_run(datos["run_id_validacion"])
        if seleccionado is None or anterior.info.experiment_id != seleccionado.experiment_id:
            raise ValueError("La validación debe pertenecer al experimento seleccionado.")
        if anterior.data.tags.get("finrisk.tipo") != "evaluacion":
            raise ValueError("El run de origen debe corresponder a una evaluación de FINRISK.")
        if anterior.info.status != "FINISHED" or anterior.data.tags.get("finrisk.fase") != "validacion":
            raise ValueError("El run de origen debe ser una evaluación de validación finalizada.")
        if any(anterior.data.params.get(k) != str(v) for k, v in parametros.items()):
            raise ValueError("El modelo, los datos, el commit, el umbral o el protocolo difieren de la validación.")
        etiquetas["finrisk.run_validacion"] = datos["run_id_validacion"]

    destino.mkdir(parents=True, exist_ok=True)
    mlflow.set_experiment(experimento)
    with mlflow.start_run(run_name=f"{datos['modelo']} - {fase}", tags=etiquetas) as run:
        mlflow.log_params(parametros)
        prefijo = "val" if fase == "validacion" else "test"
        indicadores = {k: v for k, v in metricas.items()
                       if k not in {"umbral", "matriz_confusion"} and v is not None}
        indicadores.update(metricas["matriz_confusion"] or {})
        mlflow.log_metrics({f"{prefijo}_{k}": v for k, v in indicadores.items()})
        mlflow.log_dict(protocolo, "protocolo.json")
        mlflow.log_artifact(str(modelo), artifact_path="modelo")
        resumen = {
            "run_id": run.info.run_id, "experimento": experimento,
            "experiment_id": run.info.experiment_id,
            "modelo": datos["modelo"], "fase": fase,
            "periodo": datos["periodos"][fase], "version_base_etiquetada": datos["version_base_etiquetada"],
            "commit_git": datos["commit_git"], **metricas,
        }
        mlflow.log_dict(resumen, "resumen.json")

    salida = destino / f"resumen_{resumen['run_id']}.json"
    salida.write_text(json.dumps(resumen, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    return salida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--experimento", help="Nombre del experimento del equipo, por ejemplo Proyecto-MIAD.")
    parser.add_argument("--ip-ec2", type=ipaddress.IPv4Address)
    parser.add_argument("--salidas", type=Path, default=Path("salidas"))
    modo = parser.add_mutually_exclusive_group(required=True)
    modo.add_argument("--humo", action="store_true", help="Comprueba el registro técnico.")
    modo.add_argument("--manifiesto", type=Path)
    args = parser.parse_args()
    if args.experimento is not None:
        args.experimento = args.experimento.strip()
        if not args.experimento:
            parser.error("Indique un nombre de experimento no vacío.")

    etiquetas = {"ec2_public_ipv4": str(args.ip_ec2)} if args.ip_ec2 else {}
    try:
        mlflow.set_tracking_uri(args.tracking_uri)
        if args.humo:
            mlflow.set_experiment(args.experimento or "FINRISK - verificación técnica")
            with mlflow.start_run(run_name="Prueba de conexión y artefactos",
                                  tags={**etiquetas, "finrisk.tipo": "prueba_tecnica"}) as run:
                texto = "Verificación técnica de registro y lectura de artefactos."
                mlflow.log_text(texto, "verificacion.txt")
                if mlflow.artifacts.load_text(f"runs:/{run.info.run_id}/verificacion.txt") != texto:
                    raise ValueError("El artefacto recuperado difiere del registrado.")
                print(f"Prueba técnica registrada. Run ID {run.info.run_id}")
        else:
            datos, modelo, metricas = cargar_corrida(args.manifiesto)
            salida = registrar(datos, modelo, metricas, etiquetas, args.salidas,
                               args.experimento or "FINRISK - Entrega 2")
            print(f"Resumen para el informe y el tablero en {salida}")
    except (KeyError, OSError, TypeError, ValueError, MlflowException) as error:
        parser.exit(2, f"Revise la corrida. {error}{chr(10)}")


if __name__ == "__main__":
    main()
