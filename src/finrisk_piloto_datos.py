"""Etiqueta el piloto de presencia observada en inventarios anuales de insolvencia.

El objetivo es presencia en el siguiente inventario de diciembre. No identifica
primeras admisiones formales ni demuestra solvencia de las empresas ausentes.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import gzip
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd


FEATURES = ("liquidez_corriente", "endeudamiento", "roa", "margen_neto")
ORIGENES = (2021, 2022, 2023, 2024)
PARTICIONES = {
    2021: "entrenamiento", 2022: "entrenamiento",
    2023: "validacion", 2024: "prueba",
}
CORTES_REQUERIDOS = (
    "2019-12", "2020-09", "2021-12", "2022-12", "2023-12", "2024-12", "2025-12",
)
COLUMNAS_DATASET = (
    "nit", "anio_origen", "anio_financiero", "anio_objetivo", "fecha_origen",
    "fecha_objetivo", "particion", "evento", *FEATURES,
    "conceptos_en_conflicto", "indicadores_faltantes",
)


def _sha256(ruta: Path) -> str:
    with ruta.open("rb") as archivo:
        return hashlib.file_digest(archivo, "sha256").hexdigest()


def _json_bytes(datos: object) -> bytes:
    return json.dumps(
        datos, sort_keys=True, ensure_ascii=False, allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")


def _booleanos(serie: pd.Series, nombre: str) -> pd.Series:
    equivalencias = {"true": True, "false": False, "1": True, "0": False}
    valores = serie.map(lambda valor: str(valor).strip().lower())
    if not valores.isin(equivalencias).all():
        raise ValueError(f"{nombre} requiere valores booleanos completos.")
    return valores.map(equivalencias).astype(bool)


def _validar_nits(serie: pd.Series, fuente: str, *, minimo: int = 1, maximo: int = 15) -> pd.Series:
    resultado = serie.astype("string").str.strip()
    if not resultado.str.fullmatch(rf"\d{{{minimo},{maximo}}}", na=False).all():
        raise ValueError(f"Hay NIT vacíos o no canónicos en {fuente}.")
    return resultado.astype(str)


def _leer_eventos(ruta: Path) -> tuple[pd.DataFrame, dict[str, set[str]]]:
    # Se leen solo presencias por corte. No se emplean fecha de auto, apertura
    # ni ningún atributo del proceso para construir los predictores.
    eventos = pd.read_csv(
        ruta, dtype=str, encoding="utf-8-sig", keep_default_na=False,
        usecols=["NIT", "cortes_con_presencia"],
    )
    eventos["NIT"] = _validar_nits(eventos["NIT"], "inventarios")
    if eventos["NIT"].duplicated().any():
        raise ValueError("El resumen de inventarios debe tener una fila por NIT.")
    por_corte: dict[str, set[str]] = defaultdict(set)
    for nit, texto in eventos.itertuples(index=False, name=None):
        cortes = texto.split("|")
        if not cortes or any(
            not re.fullmatch(r"(?:19|20)\d{2}-(?:0[1-9]|1[0-2])", c.strip())
            for c in cortes
        ):
            raise ValueError("cortes_con_presencia contiene un corte inválido o vacío.")
        if len({c.strip() for c in cortes}) != len(cortes):
            raise ValueError("Hay cortes repetidos en una misma fila de inventarios.")
        for corte in cortes:
            por_corte[corte.strip()].add(nit)
    faltantes = sorted(set(CORTES_REQUERIDOS) - set(por_corte))
    if faltantes:
        raise ValueError(
            "Faltan inventarios necesarios para distinguir presencias y ausencias: "
            + ", ".join(faltantes)
        )
    return eventos, dict(por_corte)


def _contrastar_auditoria(ruta_eventos: Path, por_corte: dict[str, set[str]]) -> dict:
    ruta = ruta_eventos.with_name("auditoria_insolvencia.json")
    if not ruta.is_file():
        return {"disponible": False, "contraste_con_auditoria": False}
    auditoria = json.loads(ruta.read_text(encoding="utf-8-sig"))
    if auditoria.get("habilita_etiquetas_definitivas") is not False:
        raise ValueError("Revise la versión y el alcance de la auditoría de inventarios.")
    cortes_auditados = auditoria.get("cortes", {})
    if not set(CORTES_REQUERIDOS).issubset(cortes_auditados):
        raise ValueError("La auditoría no contiene todos los cortes necesarios.")
    conteos = {}
    for corte in CORTES_REQUERIDOS:
        hojas = [h for h in cortes_auditados[corte].get("hojas", []) if "nits_distintos" in h]
        if len(hojas) == 1:
            esperado = int(hojas[0]["nits_distintos"])
            if esperado != len(por_corte[corte]):
                raise ValueError(f"El número de NIT en {corte} no coincide con su auditoría.")
            conteos[corte] = esperado
    return {
        "disponible": True, "contraste_con_auditoria": True,
        "sha256": _sha256(ruta), "conteos_nit_comprobados": conteos,
    }


def _leer_panel(ruta: Path) -> tuple[pd.DataFrame, dict[str, int]]:
    columnas = ["nit", "anio", *FEATURES, "requiere_revision_coherencia", "conceptos_en_conflicto"]
    panel = pd.read_csv(ruta, dtype={"nit": str}, usecols=columnas)
    panel["nit"] = _validar_nits(panel["nit"], "panel financiero", minimo=6, maximo=10)
    anio = pd.to_numeric(panel["anio"], errors="raise")
    if anio.isna().any() or not anio.eq(np.floor(anio)).all():
        raise ValueError("El año financiero debe ser entero y completo.")
    panel["anio"] = anio.astype(int)
    if panel.duplicated(["nit", "anio"]).any():
        raise ValueError("El panel financiero tiene claves NIT-año repetidas.")
    panel["requiere_revision_coherencia"] = _booleanos(
        panel["requiere_revision_coherencia"], "requiere_revision_coherencia"
    )
    conflictos = pd.to_numeric(panel["conceptos_en_conflicto"], errors="raise")
    if conflictos.isna().any() or conflictos.lt(0).any() or not conflictos.eq(np.floor(conflictos)).all():
        raise ValueError("El conteo de conceptos en conflicto debe ser entero no negativo.")
    panel["conceptos_en_conflicto"] = conflictos.astype(int)
    no_finitos = {}
    for nombre in FEATURES:
        valores = pd.to_numeric(panel[nombre], errors="raise").astype(float)
        mascara = valores.notna() & ~np.isfinite(valores)
        no_finitos[nombre] = int(mascara.sum())
        panel[nombre] = valores.mask(mascara)
    return panel, no_finitos


def cargar_construir(
    raiz_datos: str | Path,
    salida: str | Path | None = None,
    *,
    panel_path: str | Path | None = None,
    eventos_path: str | Path | None = None,
) -> tuple[pd.DataFrame, dict, pd.DataFrame]:
    """Devuelve dataset etiquetado, protocolo y auditoría anual de las cohortes.

    ``salida`` es un directorio opcional para el CSV.gz individual y los reportes
    agregados. Las rutas individuales deben permanecer fuera de Git.
    """
    raiz = Path(raiz_datos).expanduser().resolve()
    ruta_panel = Path(panel_path) if panel_path else raiz / "data/processed/recuperacion/base_financiera_recuperada_sin_etiquetas.csv.gz"
    ruta_eventos = Path(eventos_path) if eventos_path else raiz / "reports/preparacion/eventos_observados_insolvencia.csv"
    ruta_panel = ruta_panel.expanduser().resolve()
    ruta_eventos = ruta_eventos.expanduser().resolve()
    if not ruta_panel.is_file() or not ruta_eventos.is_file():
        raise FileNotFoundError(
            "Faltan el panel recuperado o el resumen de inventarios. Ejecute la preparación "
            "descrita en docs/entrega2/preparacion_datos.md."
        )
    panel, no_finitos = _leer_panel(ruta_panel)
    _, por_corte = _leer_eventos(ruta_eventos)
    contraste = _contrastar_auditoria(ruta_eventos, por_corte)
    bloques = []
    auditoria = []
    for origen in ORIGENES:
        corte_origen, corte_objetivo = f"{origen}-12", f"{origen + 1}-12"
        antecedentes = set().union(*(nits for corte, nits in por_corte.items() if corte <= corte_origen))
        objetivo = por_corte[corte_objetivo]
        cohorte = panel.loc[panel["anio"].eq(origen - 1)].copy()
        if cohorte.empty:
            raise ValueError(f"No hay datos financieros para el ejercicio {origen - 1}.")
        cohorte["evento"] = cohorte["nit"].isin(objetivo).astype("int8")
        conocida = cohorte["nit"].isin(antecedentes)
        elegible = ~conocida
        incoherente = elegible & cohorte["requiere_revision_coherencia"]
        sin_indicadores = elegible & ~incoherente & cohorte[list(FEATURES)].isna().all(axis=1)
        seleccionada = elegible & ~incoherente & ~sin_indicadores
        datos = cohorte.loc[seleccionada].copy()
        datos["indicadores_faltantes"] = datos[list(FEATURES)].isna().sum(axis=1).astype("int8")
        datos["anio_origen"] = origen
        datos["anio_financiero"] = origen - 1
        datos["anio_objetivo"] = origen + 1
        datos["fecha_origen"] = f"{origen}-12-31"
        datos["fecha_objetivo"] = f"{origen + 1}-12-31"
        datos["particion"] = PARTICIONES[origen]
        positivos = int(datos["evento"].sum())
        if len(datos) == 0 or positivos == 0 or positivos == len(datos):
            raise ValueError(f"La cohorte de origen {origen} requiere observaciones de ambas clases.")
        auditoria.append({
            "anio_origen": origen, "anio_financiero": origen - 1,
            "anio_objetivo": origen + 1, "particion": PARTICIONES[origen],
            "n_financieros": len(cohorte),
            "presencias_objetivo_sin_excluir": int(cohorte["evento"].sum()),
            "excluidos_antecedente_observado": int(conocida.sum()),
            "presencias_en_excluidos_antecedente": int(cohorte.loc[conocida, "evento"].sum()),
            "elegibles_sin_antecedentes": int(elegible.sum()),
            "presencias_elegibles_sin_antecedentes": int(cohorte.loc[elegible, "evento"].sum()),
            "excluidos_coherencia": int(incoherente.sum()),
            "presencias_excluidos_coherencia": int(cohorte.loc[incoherente, "evento"].sum()),
            "excluidos_sin_indicadores": int(sin_indicadores.sum()),
            "presencias_excluidos_sin_indicadores": int(cohorte.loc[sin_indicadores, "evento"].sum()),
            "n_modelado": len(datos), "evento_1": positivos,
            "evento_0": len(datos) - positivos,
            "prevalencia": positivos / len(datos),
            "con_indicadores_imputables": int(datos["indicadores_faltantes"].gt(0).sum()),
            "cuatro_indicadores": int(datos["indicadores_faltantes"].eq(0).sum()),
            "con_conflicto_contable": int(datos["conceptos_en_conflicto"].gt(0).sum()),
        })
        bloques.append(datos.loc[:, COLUMNAS_DATASET])
    dataset = pd.concat(bloques, ignore_index=True).sort_values(
        ["anio_origen", "nit"], kind="stable"
    ).reset_index(drop=True)
    if dataset.duplicated(["nit", "anio_origen"]).any():
        raise AssertionError("La etiqueta generó claves repetidas.")
    cohortes = pd.DataFrame(auditoria)
    canonico = dataset.to_csv(
        index=False, columns=COLUMNAS_DATASET, float_format="%.17g",
        na_rep="", lineterminator="\n",
    ).encode("utf-8")
    sha_dataset = hashlib.sha256(canonico).hexdigest()
    nucleo = {
        "version_protocolo": "piloto-presencia-inventario-v1",
        "objetivo": "aparicion_observada_en_inventario_anual",
        "regla_etiqueta": (
            "Entre reportantes financieros del ejercicio T-1 sin presencia en los cortes "
            "consultados hasta diciembre de T: 1 si el NIT aparece en diciembre de T+1; "
            "0 si no aparece en ese inventario. El cero no demuestra solvencia ni ausencia "
            "de eventos durante el intervalo. El uno no prueba primera admisión formal."
        ),
        "horizonte_meses": 12,
        "referencia_temporal": "Cortes nominales de diciembre a diciembre. Estudio retrospectivo.",
        "rezago_financiero_ejercicios": 1,
        "features": list(FEATURES),
        "identificadores_solo_para_cruce": ["nit"],
        "origenes_por_particion": {
            "entrenamiento": [2021, 2022], "validacion": [2023], "prueba": [2024],
        },
        "periodos": {
            "entrenamiento": {"desde": "2021-12-31", "hasta": "2022-12-31"},
            "validacion": {"desde": "2023-12-31", "hasta": "2023-12-31"},
            "prueba": {"desde": "2024-12-31", "hasta": "2024-12-31"},
        },
        "cortes_requeridos": list(CORTES_REQUERIDOS),
        "cortes_en_la_fuente": sorted(por_corte),
        "politica_calidad": {
            "excluir_antecedentes_observados": True,
            "excluir_requiere_revision_coherencia": True,
            "excluir_cuatro_indicadores_ausentes": True,
            "conservar_ausencias_parciales_para_imputacion_en_entrenamiento": True,
            "conservar_indicadores_negativos": True,
            "excluir_automaticamente_ingresos_o_patrimonio_negativos": False,
        },
        "fuentes": {
            "panel": {"archivo": ruta_panel.name, "sha256": _sha256(ruta_panel)},
            "eventos": {"archivo": ruta_eventos.name, "sha256": _sha256(ruta_eventos)},
        },
        "limitaciones": [
            "Presencia en un inventario de cierre y primera admisión formal son eventos diferentes.",
            "Se omiten posibles procesos que comenzaron y terminaron entre inventarios.",
            "La ausencia solo describe el registro consultado y no certifica solvencia.",
            "El rezago financiero no prueba disponibilidad histórica ni ausencia de revisiones.",
            "La separación por cohortes es retrospectiva. No acredita un backtest operativo exante.",
            "Las etiquetas pueden publicarse después de los cortes nominales. Madurez y publicación requieren verificación para uso prospectivo.",
            "La exclusión por calidad puede cambiar la población. Se conservan conteos por clase antes y después de excluir.",
        ],
        "disponibilidad_historica_verificada": False,
        "primera_admision_formal_validada": False,
        "etiqueta_exante_validada": False,
        "uso": "Prototipo académico de apoyo a revisión. No es aprobación de crédito ni diagnóstico de quiebra.",
    }
    nits = {
        nombre: set(dataset.loc[dataset["particion"].eq(nombre), "nit"])
        for nombre in ("entrenamiento", "validacion", "prueba")
    }
    protocolo = {
        **nucleo,
        "sha256_protocolo": hashlib.sha256(_json_bytes(nucleo)).hexdigest(),
        "sha256_dataset": sha_dataset,
        "version_base_etiquetada": sha_dataset,
        "filas_dataset": len(dataset),
        "nits_distintos_dataset": int(dataset["nit"].nunique()),
        "nits_por_particion": {k: len(v) for k, v in nits.items()},
        "intersecciones_nit_particiones": {
            "entrenamiento_validacion": len(nits["entrenamiento"] & nits["validacion"]),
            "entrenamiento_prueba": len(nits["entrenamiento"] & nits["prueba"]),
            "validacion_prueba": len(nits["validacion"] & nits["prueba"]),
            "las_tres": len(set.intersection(*nits.values())),
        },
        "repeticion_nit_interpretacion": (
            "La misma empresa puede figurar en varios orígenes. El piloto incluye reportantes "
            "conocidos y no mide exclusivamente generalización a empresas nunca vistas. NIT no es predictor."
        ),
        "valores_no_finitos_convertidos_en_ausentes": no_finitos,
        "contraste_auditoria_inventarios": contraste,
        "auditoria_cohortes": auditoria,
    }
    if salida is not None:
        destino = Path(salida).expanduser().resolve()
        destino.mkdir(parents=True, exist_ok=True)
        with (destino / "base_piloto_etiquetada.csv.gz").open("wb") as archivo:
            with gzip.GzipFile(filename="", mode="wb", fileobj=archivo, mtime=0) as comprimido:
                comprimido.write(canonico)
        (destino / "protocolo_etiqueta.json").write_text(
            json.dumps(protocolo, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        cohortes.to_csv(destino / "cohortes_piloto.csv", index=False, lineterminator="\n")
    return dataset, protocolo, cohortes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--salida", type=Path)
    args = parser.parse_args()
    destino = args.salida or args.raiz / "data/processed/piloto_retro"
    _, protocolo, cohortes = cargar_construir(args.raiz, destino)
    print(cohortes.to_string(index=False))
    print(json.dumps({
        "objetivo": protocolo["objetivo"],
        "sha256_dataset": protocolo["sha256_dataset"],
        "sha256_protocolo": protocolo["sha256_protocolo"],
        "filas_dataset": protocolo["filas_dataset"],
        "etiqueta_exante_validada": False,
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
