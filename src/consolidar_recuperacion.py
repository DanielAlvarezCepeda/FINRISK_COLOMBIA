"""Reconstruye un panel financiero preliminar y separa importes en conflicto."""

import argparse
from datetime import datetime, timezone
import hashlib
import gzip
import json
from pathlib import Path
import sqlite3
import tempfile

import numpy as np
import pandas as pd

from finrisk_etapa4_consolidar import (
    VARIABLES, clasificar_concepto, normalizar_nit, periodo_actual, prioridad_reporte
)


def procesar(raiz, salida, trabajo):
    manifest_path = raiz / "reports/preparacion/adquisicion_financieros.json"
    if not manifest_path.is_file():
        raise ValueError("Falta el manifiesto de adquisición financiera completa.")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("estado") != "completo":
        raise ValueError("La descarga financiera todavía no está completa y verificada.")
    fuentes_manifest = manifest.get("fuentes", {})
    if set(fuentes_manifest) != {"situacion", "resultados"} or any(
        f.get("estado") != "completo" for f in fuentes_manifest.values()
    ):
        raise ValueError("Faltan fuentes financieras completas en el manifiesto.")
    registrados = {Path(p).as_posix(): {**info, "fuente": nombre} for nombre, f in fuentes_manifest.items() for p, info in f["archivos"].items()}
    archivos = [raiz / p for p in sorted(registrados)]
    if not archivos:
        raise ValueError("El manifiesto no registra archivos financieros.")
    salida.mkdir(parents=True, exist_ok=True)
    trabajo.mkdir(parents=True, exist_ok=True)
    fd, temporal = tempfile.mkstemp(suffix=".sqlite", prefix="consolidacion_", dir=trabajo)
    import os
    os.close(fd)
    con = sqlite3.connect(temporal)
    con.execute("CREATE TABLE registros(nit TEXT,anio INTEGER,variable TEXT,valor REAL,prioridad INTEGER,fecha TEXT,socrata_id TEXT,radicado TEXT,taxonomia TEXT,reporte TEXT,origen TEXT,fuente TEXT)")
    fuentes = []
    try:
        for archivo in archivos:
            nombre = archivo.relative_to(raiz).as_posix()
            fuente = {"situacion": "SITUACION", "resultados": "RESULTADOS"}[registrados[nombre]["fuente"]]
            with archivo.open("rb") as entrada:
                huella = hashlib.file_digest(entrada, "sha256").hexdigest()
            if huella != registrados[nombre]["sha256"]:
                raise ValueError(f"La huella no coincide para {nombre}.")
            leidas = guardadas = 0
            for df in pd.read_csv(archivo, dtype=str, keep_default_na=False, chunksize=100000):
                df.columns = df.columns.str.upper()
                necesarios = {"NIT", "FECHA_CORTE", "PERIODO", "CONCEPTO", "VALOR", "SOCRATA_ID"}
                if not necesarios.issubset(df.columns):
                    raise ValueError(f"Columnas faltantes en {nombre}: {sorted(necesarios - set(df.columns))}")
                leidas += len(df)
                df["_match"] = df.CONCEPTO.map(lambda x: clasificar_concepto(x, fuente))
                df["_anio"] = pd.to_numeric(df.FECHA_CORTE.str.slice(0, 4), errors="coerce")
                df["_valor"] = pd.to_numeric(df.VALOR.str.strip(), errors="coerce")
                df["_nit"] = df.NIT.map(normalizar_nit)
                validas = df._match.notna() & df._anio.between(2019, 2024) & np.isfinite(df._valor) & df._nit.str.len().between(6, 10)
                df = df.loc[validas].copy()
                df = df.loc[[periodo_actual(p, int(y)) for p, y in zip(df.PERIODO, df._anio)]]
                for col in ("PUNTO_ENTRADA", "NUMERO_RADICADO", "ID_TAXONOMIA"):
                    if col not in df.columns:
                        df[col] = ""
                filas = [(nit, int(anio), match[0], float(valor), prioridad_reporte(punto)*10 + match[1], fecha, sid, radicado, taxonomia, punto, nombre, fuente)
                         for nit, anio, match, valor, punto, fecha, sid, radicado, taxonomia in zip(df._nit, df._anio, df._match, df._valor, df.PUNTO_ENTRADA, df.FECHA_CORTE, df.SOCRATA_ID, df.NUMERO_RADICADO, df.ID_TAXONOMIA)]
                con.executemany("INSERT INTO registros VALUES(?,?,?,?,?,?,?,?,?,?,?,?)", filas)
                guardadas += len(filas)
                con.commit()
            with archivo.open("rb") as f:
                huella = hashlib.file_digest(f, "sha256").hexdigest()
            if leidas != registrados[nombre]["filas"]:
                raise ValueError(f"El conteo de filas no coincide para {nombre}.")
            fuentes.append({"archivo": nombre, "sha256": huella, "filas_leidas": leidas, "filas_validas": guardadas})
            print(json.dumps(fuentes[-1]), flush=True)
        con.execute("CREATE INDEX idx_clave ON registros(nit,anio,variable,prioridad)")
        con.execute("CREATE TEMP VIEW mejores AS SELECT r.* FROM registros r JOIN (SELECT nit,anio,variable,MIN(prioridad) p FROM registros GROUP BY nit,anio,variable) m ON r.nit=m.nit AND r.anio=m.anio AND r.variable=m.variable AND r.prioridad=m.p")
        with gzip.open(salida / "candidatos_prioritarios_auditoria.csv.gz", "wt", encoding="utf-8", newline="") as archivo_candidatos:
            for indice, bloque in enumerate(pd.read_sql_query("SELECT * FROM mejores ORDER BY nit,anio,variable,socrata_id", con, chunksize=100000)):
                bloque.to_csv(archivo_candidatos, index=False, header=indice == 0)
        coherencia = pd.read_sql_query("SELECT nit,anio,fuente,COUNT(DISTINCT fecha) fechas_corte,COUNT(DISTINCT taxonomia) taxonomias,COUNT(DISTINCT radicado) radicados,COUNT(DISTINCT reporte) tipos_reporte FROM mejores GROUP BY nit,anio,fuente", con)
        coherencia["requiere_revision_coherencia"] = coherencia[["fechas_corte", "taxonomias", "radicados", "tipos_reporte"]].gt(1).any(axis=1)
        coherencia.to_csv(salida / "coherencia_reportes.csv.gz", index=False)
        valores = pd.read_sql_query("SELECT nit,anio,variable,COUNT(*) candidatos,COUNT(DISTINCT valor) valores_distintos,MIN(valor) minimo,MAX(valor) maximo,MIN(fecha) fecha_corte_min,MAX(fecha) fecha_corte_max FROM mejores GROUP BY nit,anio,variable", con)
        # MIN solo recupera el importe cuando todos los candidatos coinciden.
        valores["valor_sin_conflicto"] = valores.minimo.where(valores.valores_distintos.eq(1))
        valores.to_csv(salida / "auditoria_conceptos.csv.gz", index=False)
        panel = valores.pivot(index=["nit", "anio"], columns="variable", values="valor_sin_conflicto").reset_index()
        panel.columns.name = None
        for col in VARIABLES:
            if col not in panel:
                panel[col] = np.nan
        for indicador, numerador, denominador in [("endeudamiento", "pasivo_total", "activo_total"), ("liquidez_corriente", "activo_corriente", "pasivo_corriente"), ("roa", "utilidad_neta", "activo_total"), ("margen_neto", "utilidad_neta", "ingresos")]:
            panel[indicador] = panel[numerador] / panel[denominador].where(panel[denominador].ne(0))
            panel[indicador] = panel[indicador].where(np.isfinite(panel[indicador]))
        panel["validacion_balance_relativa"] = (panel.activo_total-panel.pasivo_total-panel.patrimonio).abs() / panel.activo_total.abs().where(panel.activo_total.ne(0))
        auditoria = valores.groupby(["nit", "anio"]).agg(conceptos_en_conflicto=("valores_distintos", lambda x: int(x.gt(1).sum())), fecha_corte_min=("fecha_corte_min", "min"), fecha_corte_max=("fecha_corte_max", "max")).reset_index()
        panel = panel.merge(auditoria, on=["nit", "anio"], validate="one_to_one")
        revisar = coherencia.groupby(["nit", "anio"])["requiere_revision_coherencia"].any().reset_index()
        panel = panel.merge(revisar, on=["nit", "anio"], validate="one_to_one")
        panel["indicadores_completos"] = panel[["endeudamiento", "liquidez_corriente", "roa", "margen_neto"]].notna().all(axis=1)
        panel["fecha_disponibilidad"] = ""
        panel.to_csv(salida / "base_financiera_recuperada_sin_etiquetas.csv.gz", index=False)
        resumen = {"fecha_utc": datetime.now(timezone.utc).isoformat(), "filas_empresa_anio": len(panel), "nits": int(panel.nit.nunique()), "con_cuatro_indicadores": int(panel.indicadores_completos.sum()), "empresa_anio_con_conflicto": int(panel.conceptos_en_conflicto.gt(0).sum()), "sin_fecha_disponibilidad": len(panel), "empresa_anio_requiere_revision_coherencia": int(panel.requiere_revision_coherencia.sum()), "etiquetas_creadas": False, "modelos_entrenados": False, "politica_conflictos": "Importe ausente cuando los candidatos de mejor prioridad discrepan. Candidatos prioritarios y procedencia exportados. No se elige por orden de descarga.", "comparabilidad_entrega1": "Nueva extracción filtrada y reglas explícitas de conflictos. No es la misma versión que el puntero DVC de la entrega 1.", "fuentes": fuentes, "cobertura_anual": panel.groupby("anio").agg(filas=("nit","size"), nits=("nit","nunique"), cuatro_indicadores=("indicadores_completos","sum")).reset_index().to_dict("records")}
        (raiz / "reports/preparacion/consolidacion_financiera.json").write_text(json.dumps(resumen, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({k:v for k,v in resumen.items() if k != "fuentes"}, ensure_ascii=False), flush=True)
    finally:
        con.close()
    return temporal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--trabajo", type=Path,
                        help="SQLite temporal de auditoría. Predeterminado .cache/finrisk/consolidacion en la raíz de extracción.")
    args = parser.parse_args()
    base = args.raiz.resolve()
    trabajo = (args.trabajo or base / ".cache/finrisk/consolidacion").expanduser().resolve()
    procesar(base, base / "data/processed/recuperacion", trabajo)


if __name__ == "__main__":
    main()
