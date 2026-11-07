"""Modelos del piloto retrospectivo de presencia en inventarios anuales.

La clasificación corresponde a la presencia observada en el siguiente inventario.
No valida primeras admisiones, solvencia ni disponibilidad histórica de reportes.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, confusion_matrix, precision_recall_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler


FEATURES = ("liquidez_corriente", "endeudamiento", "roa", "margen_neto")
PARTICIONES = {2021: "entrenamiento", 2022: "entrenamiento", 2023: "validacion", 2024: "prueba"}
ORDEN_MODELOS = ("referencia_prevalencia", "regresion_logistica", "bosque_aleatorio")
CONFIGURACION = {
    "semilla": 42,
    "features": list(FEATURES),
    "particiones_por_anio_origen": PARTICIONES,
    "referencia_prevalencia": {"strategy": "prior"},
    "regresion_logistica": {
        "imputacion": "mediana de entrenamiento con indicadores de faltantes",
        "keep_empty_features": True,
        "transformacion": "arcsinh, seguida de StandardScaler ajustado con entrenamiento",
        "C": 1.0, "class_weight": "balanced", "max_iter": 2000, "random_state": 42,
    },
    "bosque_aleatorio": {
        "imputacion": "mediana de entrenamiento con indicadores de faltantes",
        "keep_empty_features": True,
        "n_estimators": 300, "max_depth": 8, "min_samples_leaf": 20,
        "class_weight": "balanced_subsample", "n_jobs": 2, "random_state": 42,
    },
    "criterio_modelo": "Mayor AP en validación. Empates exactos por orden de menor complejidad predefinido.",
    "criterio_umbral": "Máximo F2 en validación. Empates con tolerancia absoluta 1e-12 por menor umbral.",
    "nota_umbral": "Criterio técnico que pondera sensibilidad. No representa costos ni capacidad de revisión de un banco.",
    "alcance": "piloto_retrospectivo",
    "objetivo": "presencia_inventario_anual",
    "validacion_exante": False,
    "puntaje_calibrado": False,
}


def _ahora():
    return datetime.now(timezone.utc).isoformat()


def _sha_archivo(path):
    with Path(path).open("rb") as entrada:
        return hashlib.file_digest(entrada, "sha256").hexdigest()


def _json_bytes(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")


def _guardar_json(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2, allow_nan=False) + chr(10), encoding="utf-8")


def _validar_datos(df):
    requeridas = {"nit", "anio_origen", "particion", "evento", *FEATURES}
    if not requeridas.issubset(df.columns):
        raise ValueError("Faltan columnas del piloto: " + ", ".join(sorted(requeridas - set(df.columns))))
    datos = df.copy()
    if datos.empty or datos.duplicated(["nit", "anio_origen"]).any():
        raise ValueError("El piloto requiere claves empresa-año únicas y filas no vacías.")
    if datos.nit.isna().any() or not datos.nit.astype(str).str.fullmatch(r"[0-9]{6,10}").all():
        raise ValueError("Revise los NIT normalizados. Se usan para auditoría y nunca como predictores.")
    if not datos.anio_origen.isin(PARTICIONES).all():
        raise ValueError("Se requieren las cohortes de origen de 2021 a 2024.")
    if not datos.particion.eq(datos.anio_origen.map(PARTICIONES)).all():
        raise ValueError("La partición no corresponde al año de origen acordado.")
    if not datos.evento.isin([0, 1]).all():
        raise ValueError("La etiqueta observada debe ser binaria.")
    datos["evento"] = datos.evento.astype(int)
    for feature in FEATURES:
        datos[feature] = pd.to_numeric(datos[feature], errors="raise").astype(float)
    if np.isinf(datos[list(FEATURES)].to_numpy()).any():
        raise ValueError("Los indicadores admiten faltantes, pero no infinitos.")
    if datos[list(FEATURES)].isna().all(axis=1).any():
        raise ValueError("El módulo de datos debe separar filas sin ninguno de los cuatro indicadores.")
    for particion in ("entrenamiento", "validacion", "prueba"):
        if not datos.particion.eq(particion).any():
            raise ValueError("Partición vacía: " + particion)
    for particion in ("entrenamiento", "validacion"):
        if set(datos.loc[datos.particion.eq(particion), "evento"]) != {0, 1}:
            raise ValueError("Entrenamiento y validación necesitan ambas clases.")
    return datos.sort_values(["anio_origen", "nit"], kind="stable").reset_index(drop=True)


def _modelos():
    imputer = lambda: SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
    return {
        "referencia_prevalencia": Pipeline([
            ("imputacion", imputer()),
            ("modelo", DummyClassifier(strategy="prior")),
        ]),
        "regresion_logistica": Pipeline([
            ("imputacion", imputer()),
            ("arcsinh", FunctionTransformer(np.arcsinh, feature_names_out="one-to-one")),
            ("escala", StandardScaler()),
            ("modelo", LogisticRegression(C=1.0, class_weight="balanced", max_iter=2000, random_state=42)),
        ]),
        "bosque_aleatorio": Pipeline([
            ("imputacion", imputer()),
            ("modelo", RandomForestClassifier(
                n_estimators=300, max_depth=8, min_samples_leaf=20,
                class_weight="balanced_subsample", n_jobs=2, random_state=42,
            )),
        ]),
    }


def _puntajes(modelo, x):
    clases = list(modelo.classes_)
    if 1 not in clases:
        raise ValueError("El modelo no contiene la clase observada 1.")
    puntajes = np.asarray(modelo.predict_proba(x)[:, clases.index(1)], dtype=float)
    if not np.isfinite(puntajes).all():
        raise ValueError("El modelo generó un puntaje no finito.")
    return puntajes


def elegir_umbral_f2(eventos, puntajes):
    """Umbral de validación con todos los empates de puntaje tratados en bloque."""
    precision, sensibilidad, umbrales = precision_recall_curve(eventos, puntajes, drop_intermediate=False)
    validos = np.isfinite(umbrales)
    umbrales = umbrales[validos]
    p, r = precision[:-1][validos], sensibilidad[:-1][validos]
    f2 = np.divide(5 * p * r, 4 * p + r, out=np.zeros_like(p), where=(4 * p + r) > 0)
    if not len(umbrales):
        raise ValueError("No hay umbral finito de validación.")
    mejores = np.flatnonzero(np.isclose(f2, f2.max(), rtol=0, atol=1e-12))
    indice = int(mejores[0])
    curva = pd.DataFrame({"umbral": umbrales, "precision_alertas": p, "sensibilidad": r, "f2": f2})
    return float(umbrales[indice]), curva


def evaluar_puntajes(eventos, puntajes, umbral):
    eventos = np.asarray(eventos, dtype=int)
    puntajes = np.asarray(puntajes, dtype=float)
    if set(eventos) != {0, 1}:
        raise ValueError("La evaluación de AP requiere ambas clases observadas.")
    vn, fp, fn, vp = (int(x) for x in confusion_matrix(eventos, puntajes >= umbral, labels=[0, 1]).ravel())
    n, positivos, alertas = len(eventos), int(eventos.sum()), vp + fp
    precision = vp / alertas if alertas else None
    sensibilidad = vp / positivos
    prevalencia = positivos / n
    return {
        "n": n, "positivos": positivos, "negativos": n - positivos, "prevalencia": prevalencia,
        "ap": float(average_precision_score(eventos, puntajes)), "umbral": float(umbral),
        "sensibilidad": sensibilidad, "precision_alertas": precision,
        "f1": 2 * vp / (2 * vp + fp + fn) if (2 * vp + fp + fn) else 0.0,
        "f2": 5 * vp / (5 * vp + fp + 4 * fn) if (5 * vp + fp + 4 * fn) else 0.0,
        "alertas": alertas, "fraccion_alertas": alertas / n,
        "lift_precision": precision / prevalencia if precision is not None else None,
        "matriz_confusion": {"vp": vp, "fp": fp, "fn": fn, "vn": vn},
    }


def _predicciones(df, puntajes, archivo):
    columnas = [c for c in ("nit", "anio_origen", "anio_financiero", "anio_objetivo", "evento") if c in df]
    tabla = df[columnas].copy()
    tabla["puntaje"] = puntajes
    tabla.to_csv(archivo, index=False)


def entrenar_piloto(df, protocolo, salida):
    """Ajusta candidatos con entrenamiento y abre la prueba solo tras sellar selección.

    Una ejecución completa se reutiliza por huella. Las predicciones individuales
    y los pesos permanecen como archivos locales, separados de los agregados.
    """
    datos = _validar_datos(df)
    salida = Path(salida).expanduser().resolve()
    salida.mkdir(parents=True, exist_ok=True)
    versiones = {p: version(p) for p in ("pandas", "numpy", "scikit-learn", "joblib")}
    columnas_huella = ["nit", "anio_origen", "particion", "evento", *FEATURES]
    dataset_bytes = datos[columnas_huella].to_csv(index=False, float_format="%.17g", na_rep="NA", lineterminator=chr(10)).encode("utf-8")
    firma = {
        "sha256_datos_modelado": hashlib.sha256(dataset_bytes).hexdigest(),
        "sha256_protocolo_etiqueta": hashlib.sha256(_json_bytes(protocolo)).hexdigest(),
        "sha256_configuracion": hashlib.sha256(_json_bytes(CONFIGURACION)).hexdigest(),
        "sha256_script_modelado": _sha_archivo(__file__),
        "versiones": versiones,
    }
    resumen_path = salida / "resumen_piloto.json"
    if resumen_path.exists():
        previo = json.loads(resumen_path.read_text(encoding="utf-8"))
        if previo.get("firma") != firma:
            raise ValueError("Hay resultados de otra versión. Conserve esta ejecución y use una carpeta nueva.")
        for registro in previo["modelos"]:
            if _sha_archivo(salida / registro["archivo_modelo"]) != registro["sha256_modelo"]:
                raise ValueError("El archivo de un modelo cambió después de su evaluación.")
        sello = json.loads((salida / "seleccion_sellada.json").read_text(encoding="utf-8"))
        if hashlib.sha256(_json_bytes(sello)).hexdigest() != previo["sha256_seleccion"]:
            raise ValueError("La selección sellada cambió.")
        previo["resultado_en_cache"] = True
        return previo
    if (salida / "firma_ejecucion.json").exists():
        raise ValueError("La carpeta contiene una ejecución incompleta. Revísela y use una carpeta nueva.")
    _guardar_json(salida / "firma_ejecucion.json", firma)
    _guardar_json(salida / "configuracion_modelado.json", CONFIGURACION)
    _guardar_json(salida / "protocolo_etiqueta.json", protocolo)
    for carpeta in ("modelos", "predicciones", "agregados"):
        (salida / carpeta).mkdir(exist_ok=True)

    train = datos.loc[datos.particion.eq("entrenamiento")]
    val = datos.loc[datos.particion.eq("validacion")]
    x_train, y_train = train[list(FEATURES)], train.evento
    x_val, y_val = val[list(FEATURES)], val.evento
    registros, ajustados, curvas = [], {}, []
    for nombre, modelo in _modelos().items():
        inicio = time.monotonic()
        modelo.fit(x_train, y_train)
        segundos = time.monotonic() - inicio
        if list(modelo.feature_names_in_) != list(FEATURES):
            raise ValueError("Los predictores del pipeline no coinciden con los cuatro indicadores.")
        scores = _puntajes(modelo, x_val)
        umbral, curva = elegir_umbral_f2(y_val, scores)
        metricas = evaluar_puntajes(y_val, scores, umbral)
        if nombre == "referencia_prevalencia" and not np.isclose(metricas["ap"], metricas["prevalencia"], atol=1e-12, rtol=0):
            raise AssertionError("La AP de la referencia constante debe coincidir con la prevalencia de validación.")
        archivo_modelo = "modelos/" + nombre + ".joblib"
        joblib.dump(modelo, salida / archivo_modelo, compress=3)
        archivo_pred = "predicciones/" + nombre + "_validacion.csv"
        _predicciones(val, scores, salida / archivo_pred)
        registro = {"modelo": nombre, "fase": "validacion", **metricas,
                    "segundos_ajuste": round(segundos, 6), "archivo_modelo": archivo_modelo,
                    "sha256_modelo": _sha_archivo(salida / archivo_modelo),
                    "archivo_predicciones": archivo_pred, "hiperparametros": CONFIGURACION[nombre]}
        registros.append(registro)
        curva.insert(0, "modelo", nombre)
        curvas.append(curva)
        ajustados[nombre] = modelo
    orden = {nombre: i for i, nombre in enumerate(ORDEN_MODELOS)}
    elegido = sorted(registros, key=lambda x: (-x["ap"], orden[x["modelo"]]))[0]
    _guardar_json(salida / "agregados/metricas_validacion.json", registros)
    columnas_metricas = ["modelo", "n", "positivos", "prevalencia", "ap", "umbral", "sensibilidad", "precision_alertas", "f1", "f2", "alertas", "fraccion_alertas", "lift_precision"]
    pd.DataFrame(registros)[columnas_metricas].to_csv(salida / "agregados/metricas_validacion.csv", index=False)
    pd.concat(curvas, ignore_index=True).to_csv(salida / "agregados/curvas_precision_sensibilidad_validacion.csv.gz", index=False)
    sello = {
        "sellado_utc": _ahora(), "modelo": elegido["modelo"], "umbral": elegido["umbral"],
        "sha256_modelo": elegido["sha256_modelo"], "ap_validacion": elegido["ap"],
        "criterio_modelo": CONFIGURACION["criterio_modelo"], "criterio_umbral": CONFIGURACION["criterio_umbral"],
        "nota_umbral": CONFIGURACION["nota_umbral"], "firma": firma,
        "prueba_consultada_para_seleccion": False,
    }
    _guardar_json(salida / "seleccion_sellada.json", sello)
    sello_sha = hashlib.sha256(_json_bytes(sello)).hexdigest()

    # A partir de aquí se predice y evalúa únicamente el ganador sobre prueba.
    test = datos.loc[datos.particion.eq("prueba")]
    pipeline = ajustados[elegido["modelo"]]
    assert _sha_archivo(salida / elegido["archivo_modelo"]) == sello["sha256_modelo"]
    scores_test = _puntajes(pipeline, test[list(FEATURES)])
    resultado_test = {
        "modelo": elegido["modelo"], "fase": "prueba", **evaluar_puntajes(test.evento, scores_test, sello["umbral"]),
        "sha256_seleccion": sello_sha, "sha256_modelo": sello["sha256_modelo"],
        "archivo_modelo": elegido["archivo_modelo"], "archivo_predicciones": "predicciones/ganador_prueba.csv",
        "evaluado_utc": _ahora(), "numero_evaluaciones_prueba": 1, "modelo_reajustado_antes_prueba": False,
    }
    _predicciones(test, scores_test, salida / resultado_test["archivo_predicciones"])
    _guardar_json(salida / "agregados/resultado_prueba.json", resultado_test)
    matriz = resultado_test["matriz_confusion"]
    pd.DataFrame([[matriz["vn"], matriz["fp"]], [matriz["fn"], matriz["vp"]]],
                 index=["observado_0", "observado_1"], columns=["alerta_0", "alerta_1"]).to_csv(salida / "agregados/matriz_confusion_prueba.csv")
    resumen = {
        "creado_utc": _ahora(), "alcance": CONFIGURACION["alcance"], "objetivo": CONFIGURACION["objetivo"],
        "validacion_exante": False, "puntaje_calibrado": False,
        "interpretacion": "El uno es presencia en el siguiente inventario anual. El cero es ausencia en ese inventario. No son primeras admisiones verificadas ni diagnósticos de solvencia.",
        "limitaciones": [
            "La disponibilidad histórica de reportes y de etiquetas no está verificada.",
            "La separación cronológica es un benchmark retrospectivo, no una simulación operativa libre de información posterior.",
            "Los inventarios pueden omitir procesos ocurridos y cerrados entre cortes.",
            "El umbral F2 es técnico y requiere revisar costos y volumen de alertas antes de un uso operativo.",
        ],
        "firma": firma, "particiones": {p: {"n": int((datos.particion == p).sum()), "positivos": int(datos.loc[datos.particion.eq(p), "evento"].sum())} for p in ("entrenamiento", "validacion", "prueba")},
        "modelos": registros, "ganador": elegido["modelo"], "umbral": sello["umbral"],
        "seleccion_sellada": "seleccion_sellada.json", "sha256_seleccion": sello_sha,
        "prueba": resultado_test, "resultado_en_cache": False,
    }
    _guardar_json(resumen_path, resumen)
    return resumen


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--salida", type=Path)
    parser.add_argument("--panel", type=Path)
    parser.add_argument("--eventos", type=Path)
    args = parser.parse_args()
    if __package__:
        from .finrisk_piloto_datos import cargar_construir
    else:
        from finrisk_piloto_datos import cargar_construir
    raiz = args.raiz.expanduser().resolve()
    datos, protocolo, _ = cargar_construir(raiz, panel_path=args.panel, eventos_path=args.eventos)
    salida = args.salida or raiz / ".cache/finrisk/piloto/modelado"
    resumen = entrenar_piloto(datos, protocolo, salida)
    print(json.dumps({"ganador": resumen["ganador"], "umbral": resumen["umbral"], "prueba": resumen["prueba"], "resultado_en_cache": resumen["resultado_en_cache"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
