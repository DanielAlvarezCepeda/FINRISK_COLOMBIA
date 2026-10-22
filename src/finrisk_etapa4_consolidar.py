#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FINRISK Colombia | Etapa 4: base financiera PRELIMINAR.

Uso (PowerShell):
  py -m pip install pandas
  py finrisk_etapa4_consolidar.py

Coloque este archivo junto a los CSV ORIGINALES de Estado de Situacion Financiera
 y Estado de Resultado Integral de Supersociedades.

IMPORTANTE: No genera etiquetas de insolvencia, ni una base lista para entrenar:
separacion por periodo, homologacion y discrepancias deben ser auditadas.
"""

from __future__ import annotations

import argparse
import csv
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    sys.exit("Falta pandas. Ejecute: py -m pip install pandas")


NECESARIAS = {"NIT", "FECHA_CORTE", "PERIODO", "CONCEPTO", "VALOR"}
VARIABLES = [
    "activo_total", "pasivo_total", "patrimonio", "activo_corriente",
    "pasivo_corriente", "ingresos", "ganancia_bruta", "utilidad_neta",
    "costo_ventas", "resultado_operacional", "costos_financieros",
]


def limpiar_texto(valor: object) -> str:
    if valor is None or pd.isna(valor):
        return ""
    txt = str(valor).strip().lower().replace("\ufffd", "?")
    txt = unicodedata.normalize("NFKD", txt)
    txt = "".join(c for c in txt if not unicodedata.combining(c))
    txt = re.sub(r"\s+", " ", txt)
    return txt


def normalizar_nit(valor: object) -> str:
    s = str(valor or "").strip()
    s = re.sub(r"[^0-9]", "", s)
    # Los NIT de las fuentes financieras suelen estar sin digito de verificacion.
    # No completar ceros ni eliminar el ultimo digito arbitrariamente.
    return s


def clasificar_concepto(texto: str, fuente: str):
    """Retorna (variable, prioridad). Coincidencias estrictas y auditables."""
    s = limpiar_texto(texto)
    if fuente == "SITUACION":
        exactos = {
            "total de activos": ("activo_total", 0),
            "total activos": ("activo_total", 1),
            "total pasivos": ("pasivo_total", 0),
            "total de pasivos": ("pasivo_total", 0),
            "pasivos": ("pasivo_total", 1),
            "patrimonio total": ("patrimonio", 0),
            "patrimonio": ("patrimonio", 1),
            "activos corrientes totales": ("activo_corriente", 0),
            "activos corrientes": ("activo_corriente", 1),
            "pasivos corrientes totales": ("pasivo_corriente", 0),
            "pasivos corrientes": ("pasivo_corriente", 1),
        }
        if s in exactos:
            return exactos[s]
        # Conceptos parciales: conservados solo como aproximaciones de menor prioridad.
        if s.startswith("total activos corrientes distintos de los activos no corrientes"):
            return ("activo_corriente", 3)
        if s.startswith("total pasivos corrientes distintos de los pasivos incluidos") or s.startswith("total de pasivos corrientes distintos"):
            return ("pasivo_corriente", 3)
    if fuente == "RESULTADOS":
        exactos = {
            "ingresos de actividades ordinarias": ("ingresos", 0),
            "ganancia bruta": ("ganancia_bruta", 0),
            "costo de ventas": ("costo_ventas", 0),
            "costos financieros": ("costos_financieros", 0),
        }
        if s in exactos:
            return exactos[s]
        if re.fullmatch(r"ganancia \(p.rdida\)", s):
            return ("utilidad_neta", 0)
        if re.fullmatch(r"ganancia \(p.rdida\) por actividades de operaci.n", s):
            return ("resultado_operacional", 0)
    return None


def anio_del_corte(s: object):
    m = re.match(r"^\s*((?:19|20)\d{2})", str(s or ""))
    return int(m.group(1)) if m else None


def periodo_actual(p: object, anio_corte: int) -> bool:
    """Solo ejercicios corrientes; evita duplicar comparativos y balances de apertura."""
    s = limpiar_texto(p)
    if s in {"periodo actual", "periodo corriente"}:
        return True
    if s in {"periodo anterior", "periodo previo"}:
        return False
    if re.fullmatch(r"(?:19|20)\d{2}", s):
        return int(s) == anio_corte
    # Ej.: 2017-dic-31 o 2017-12-31. Nunca 2017-ene-01.
    m = re.match(r"^((?:19|20)\d{2})-(dic|dec|12)-31$", s)
    return bool(m and int(m.group(1)) == anio_corte)


def prioridad_reporte(s: object) -> int:
    t = limpiar_texto(s)
    if "individual" in t or "separado" in t:
        return 0
    if "consolidado" in t:
        return 2
    return 1


def hallar_fuentes(carpeta: Path):
    resultado = {}
    for archivo in carpeta.glob("*.csv"):
        nombre = limpiar_texto(archivo.name)
        if "estado_de_resultado_integral" in nombre:
            resultado.setdefault("RESULTADOS", []).append(archivo)
        elif "estado_de_situacion_financiera" in nombre:
            resultado.setdefault("SITUACION", []).append(archivo)
    faltan = [k for k in ("RESULTADOS", "SITUACION") if k not in resultado]
    if faltan:
        sys.exit("No encuentro CSV originales de: " + ", ".join(faltan) +
                 ". Coloque el programa junto a los archivos financieros grandes.")
    for f, archivos in resultado.items():
        if len(archivos) != 1:
            sys.exit(f"Se encontraron {len(archivos)} archivos de {f}: {archivos}. Deje uno por fuente.")
    return {k: v[0] for k, v in resultado.items()}


def crear_bd(ruta):
    con = sqlite3.connect(ruta)
    con.execute("PRAGMA journal_mode=DELETE")
    con.execute("PRAGMA synchronous=NORMAL")
    con.execute("PRAGMA temp_store=FILE")
    con.execute("""CREATE TABLE registros (
        id INTEGER PRIMARY KEY,
        nit TEXT NOT NULL, anio INTEGER NOT NULL,
        variable TEXT NOT NULL, valor REAL NOT NULL,
        prioridad_reporte INTEGER NOT NULL, prioridad_concepto INTEGER NOT NULL,
        concepto_original TEXT, periodo_original TEXT,
        fuente TEXT, origen TEXT
    )""")
    return con


def procesar_fuente(con, ruta: Path, fuente: str, min_year: int, max_year: int, chunksize: int):
    print(f"\nLeyendo {fuente}: {ruta.name}", flush=True)
    n_leidas = n_actual = n_relevantes = n_guardadas = 0
    n_invalidos = 0
    mapa_conceptos = {}
    for pos, fragmento in enumerate(pd.read_csv(
        ruta, dtype=str, chunksize=chunksize, sep=",", encoding="utf-8-sig",
        encoding_errors="replace", on_bad_lines="warn", low_memory=False,
    ), 1):
        fragmento.columns = fragmento.columns.str.replace("\ufeff", "", regex=False).str.strip()
        if pos == 1 and not NECESARIAS.issubset(fragmento.columns):
            raise ValueError(f"Faltan columnas en {ruta.name}: {sorted(NECESARIAS - set(fragmento.columns))}. "
                             "Revise que el CSV sea delimitado por comas.")
        n_leidas += len(fragmento)
        clases_nuevas = [x for x in fragmento.CONCEPTO.dropna().unique() if x not in mapa_conceptos]
        mapa_conceptos.update({x: clasificar_concepto(x, fuente) for x in clases_nuevas})
        fragmento["_match"] = fragmento.CONCEPTO.map(mapa_conceptos)
        fragmento = fragmento.loc[fragmento._match.notna()].copy()
        n_relevantes += len(fragmento)
        if fragmento.empty:
            continue
        fragmento["_anio"] = pd.to_numeric(fragmento.FECHA_CORTE.str.extract(r"^\s*((?:19|20)\d{2})")[0], errors="coerce")
        fragmento = fragmento.loc[fragmento._anio.between(min_year, max_year)].copy()
        if fragmento.empty:
            continue
        fragmento["_actual"] = [periodo_actual(p, int(y)) for p, y in zip(fragmento.PERIODO, fragmento._anio)]
        fragmento = fragmento.loc[fragmento._actual].copy()
        n_actual += len(fragmento)
        if fragmento.empty:
            continue
        fragmento["_nit"] = fragmento.NIT.map(normalizar_nit)
        fragmento["_valor"] = pd.to_numeric(fragmento.VALOR.str.strip(), errors="coerce")
        validos = fragmento._nit.str.len().between(6, 10) & fragmento._valor.notna()
        validos &= fragmento._valor.map(lambda z: z == z and z not in (float("inf"), float("-inf")))
        n_invalidos += int((~validos).sum())
        fragmento = fragmento.loc[validos].copy()
        if fragmento.empty:
            continue
        if "PUNTO_ENTRADA" not in fragmento.columns:
            fragmento["PUNTO_ENTRADA"] = ""
        fragmento["_pr"] = fragmento.PUNTO_ENTRADA.map(prioridad_reporte)
        filas = [
            (nit, int(anio), match[0], float(valor), int(pr), int(match[1]),
             concepto, periodo, fuente, ruta.name)
            for nit, anio, match, valor, pr, concepto, periodo in zip(
                fragmento._nit, fragmento._anio, fragmento._match,
                fragmento._valor, fragmento._pr, fragmento.CONCEPTO, fragmento.PERIODO
            )
        ]
        con.executemany("""INSERT INTO registros
          (nit,anio,variable,valor,prioridad_reporte,prioridad_concepto,
           concepto_original,periodo_original,fuente,origen)
           VALUES (?,?,?,?,?,?,?,?,?,?)""", filas)
        con.commit()
        n_guardadas += len(filas)
        if pos % 10 == 0:
            print(f"  Bloques {pos}; {n_leidas:,} filas leidas; {n_guardadas:,} registros seleccionados", flush=True)
    return {"fuente": fuente, "filas_leidas": n_leidas, "conceptos_candidatos": n_relevantes,
            "filas_periodo_actual": n_actual, "filas_guardadas": n_guardadas,
            "omitidas_nit_valor": n_invalidos}


def dividir_seguro(n, d, solo_positivos=False):
    resultado = n / d.where(d > 0) if solo_positivos else n / d.where(d != 0)
    return resultado


def consolidar(con, destino: Path, min_year: int, max_year: int, estadisticas):
    print("\nConsolidando por NIT, anio e indicador ...", flush=True)
    con.execute("CREATE INDEX idx_registros_clave ON registros(nit,anio,variable)")
    sql = """
      WITH ordenadas AS (
        SELECT nit, anio, variable, valor, concepto_original, fuente,
               periodo_original, prioridad_reporte, prioridad_concepto,
               ROW_NUMBER() OVER (
                 PARTITION BY nit, anio, variable
                 ORDER BY prioridad_reporte, prioridad_concepto, id DESC
               ) AS orden,
               COUNT(*) OVER (PARTITION BY nit, anio, variable) AS num_candidatos
        FROM registros
      )
      SELECT nit,anio,variable,valor,concepto_original,fuente,
             periodo_original,prioridad_reporte,prioridad_concepto,num_candidatos
      FROM ordenadas WHERE orden=1 ORDER BY nit,anio,variable
    """
    filas = con.execute(sql).fetchall()
    cols = ["NIT", "anio_financiero", "variable", "valor", "concepto_original", "fuente",
            "periodo_original", "prioridad_reporte", "prioridad_concepto", "num_candidatos"]
    elegidos = pd.DataFrame(filas, columns=cols)
    if elegidos.empty:
        raise RuntimeError("No se encontraron conceptos validos con periodos actuales.")
    elegidos.to_csv(destino / "conceptos_seleccionados_auditoria.csv", index=False, encoding="utf-8-sig")
    print("Comprobando discrepancias en reportes repetidos ...", flush=True)
    sql_conflictos = """
      SELECT r.nit, r.anio, r.variable, COUNT(*) registros_misma_prioridad,
             COUNT(DISTINCT r.valor) importes_diferentes,
             MIN(r.valor) importe_minimo, MAX(r.valor) importe_maximo
      FROM registros r
      INNER JOIN (
        SELECT nit,anio,variable, MIN(prioridad_reporte*10+prioridad_concepto) prioridad
        FROM registros GROUP BY nit,anio,variable
      ) p ON p.nit=r.nit AND p.anio=r.anio AND p.variable=r.variable
      WHERE r.prioridad_reporte*10 + r.prioridad_concepto = p.prioridad
      GROUP BY r.nit,r.anio,r.variable
      HAVING COUNT(DISTINCT r.valor)>1
      ORDER BY r.anio DESC, r.nit
    """
    conflictos = pd.read_sql_query(sql_conflictos, con)
    conflictos.to_csv(destino / "discrepancias_pendientes_revision.csv", index=False, encoding="utf-8-sig")
    tabla = elegidos.pivot(index=["NIT", "anio_financiero"], columns="variable", values="valor").reset_index()
    tabla.columns.name = None
    for col in VARIABLES:
        if col not in tabla.columns:
            tabla[col] = float("nan")
    tabla["endeudamiento"] = dividir_seguro(tabla.pasivo_total, tabla.activo_total)
    tabla["liquidez_corriente"] = dividir_seguro(tabla.activo_corriente, tabla.pasivo_corriente)
    tabla["roa"] = dividir_seguro(tabla.utilidad_neta, tabla.activo_total)
    tabla["margen_neto"] = dividir_seguro(tabla.utilidad_neta, tabla.ingresos)
    tabla["roe"] = dividir_seguro(tabla.utilidad_neta, tabla.patrimonio)
    tabla["capital_trabajo"] = tabla.activo_corriente - tabla.pasivo_corriente
    tabla["margen_bruto"] = dividir_seguro(tabla.ganancia_bruta, tabla.ingresos)
    tabla["validacion_balance_relativa"] = (
        (tabla.activo_total - tabla.pasivo_total - tabla.patrimonio).abs()
        / tabla.activo_total.abs().where(tabla.activo_total.abs() > 0)
    )
    tabla["balance_cuadra_tol_1pct"] = tabla.validacion_balance_relativa.le(0.01)
    tabla.loc[tabla.validacion_balance_relativa.isna(), "balance_cuadra_tol_1pct"] = False
    tabla["indicadores_basicos_completos"] = tabla[["endeudamiento", "liquidez_corriente", "roa", "margen_neto"]].notna().all(axis=1)
    tabla["tiene_discrepancia"] = pd.MultiIndex.from_frame(
        tabla[["NIT", "anio_financiero"]].rename(columns={"NIT":"nit", "anio_financiero":"anio"})
    ).isin(pd.MultiIndex.from_frame(conflictos[["nit", "anio"]])) if not conflictos.empty else False
    tabla.sort_values(["NIT", "anio_financiero"]).to_csv(
        destino / "base_financiera_preliminar.csv", index=False, encoding="utf-8-sig")
    cobertura = tabla.groupby("anio_financiero", as_index=False).agg(
        empresas=("NIT", "nunique"),
        observaciones=("NIT", "size"),
        completas_basicas=("indicadores_basicos_completos", "sum"),
        balances_cuadrados=("balance_cuadra_tol_1pct", "sum"),
        con_discrepancia=("tiene_discrepancia", "sum"),
    )
    cobertura.to_csv(destino / "cobertura_por_anio.csv", index=False, encoding="utf-8-sig")
    resumen = elegidos.groupby(["fuente","variable","concepto_original"],dropna=False).size().reset_index(name="registros_seleccionados")
    resumen.to_csv(destino / "cobertura_conceptos.csv",index=False,encoding="utf-8-sig")
    with (destino / "RESUMEN_VALIDACION.txt").open("w",encoding="utf-8") as f:
        f.write("FINRISK Colombia | Etapa 4 - consolidacion preliminar\n")
        f.write("ATENCION: No usar esta base para entrenar sin revisar los conflictos y la variable objetivo.\n\n")
        for e in estadisticas:
            f.write(str(e) + "\n")
        f.write(f"\nPeriodos incluidos: {min_year}-{max_year}\n")
        f.write(f"Empresas unicas: {tabla.NIT.nunique():,}\n")
        f.write(f"Registros empresa-anio: {len(tabla):,}\n")
        f.write(f"Registros con 4 indicadores: {int(tabla.indicadores_basicos_completos.sum()):,}\n")
        f.write(f"Registros con balances cuadrados (1%): {int(tabla.balance_cuadra_tol_1pct.sum()):,}\n")
        f.write(f"Combinaciones NIT-anio con conflicto: {int(tabla.tiene_discrepancia.sum()):,}\n")
        f.write(f"Indicadores con candidatos en disputa: {len(conflictos):,}\n")
        f.write("Revisar prioridad de informes individuales/separados, taxonomias y cifras anormales.\n")
        f.write("No se ha verificado ni calculado la etiqueta de insolvencia futura.\n")
    print(f"\nLISTO. Empresas: {tabla.NIT.nunique():,}; observaciones empresa-anio: {len(tabla):,}; "
          f"4 indicadores disponibles: {int(tabla.indicadores_basicos_completos.sum()):,}")
    print(f"Archivos de salida: {destino}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--carpeta", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--desde", type=int, default=2019)
    parser.add_argument("--hasta", type=int, default=2024)
    parser.add_argument("--bloque", type=int, default=150000)
    args = parser.parse_args()
    carpeta = args.carpeta.resolve()
    archivos = hallar_fuentes(carpeta)
    salida = carpeta / "finrisk_etapa4"
    salida.mkdir(exist_ok=True)
    ruta_bd = salida / "finrisk_temporal.sqlite"
    if ruta_bd.exists():
        ruta_bd.unlink()  # la base temporal solo contiene resultados de este programa
    conexion = crear_bd(ruta_bd)
    try:
        estadisticas = [procesar_fuente(conexion, archivos[fuente], fuente,
                        args.desde, args.hasta, args.bloque) for fuente in ("SITUACION", "RESULTADOS")]
        consolidar(conexion, salida, args.desde, args.hasta, estadisticas)
    finally:
        conexion.close()
    print("Se conserva finrisk_temporal.sqlite para auditoria. Puede borrarlo tras guardar las salidas.")


if __name__ == "__main__":
    main()
