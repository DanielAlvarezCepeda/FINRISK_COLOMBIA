"""Audita inventarios oficiales de procesos sin producir etiquetas supervisadas."""

import argparse
from collections import Counter, defaultdict
import csv
from datetime import date, datetime
import hashlib
import json
from pathlib import Path
import re
import unicodedata

from openpyxl import load_workbook


def clave(texto):
    texto = unicodedata.normalize("NFKD", str(texto or ""))
    return re.sub(r"[^A-Z0-9]", "", texto.encode("ascii", "ignore").decode().upper())


def nit_limpio(valor):
    if isinstance(valor, (int, float)):
        return str(int(valor)) if float(valor).is_integer() else ""
    valor = str(valor or "").strip()
    if re.fullmatch(r"[\d., ]+-\d", valor):
        valor = valor.rsplit("-", 1)[0]
    return re.sub(r"\D", "", valor)


def fecha(valor):
    if isinstance(valor, datetime):
        return valor.date()
    if isinstance(valor, date):
        return valor
    texto = str(valor or "").strip()
    try:
        return date.fromisoformat(texto[:10])
    except ValueError:
        for formato in ("%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(texto[:10], formato).date()
            except ValueError:
                pass
    return None


def fin_corte(corte):
    anio, mes = map(int, corte.split("-"))
    siguiente = date(anio + (mes == 12), 1 if mes == 12 else mes + 1, 1)
    return date.fromordinal(siguiente.toordinal() - 1)


def auditar(entrada, salida):
    cortes, por_nit = {}, defaultdict(lambda: {"cortes": [], "fechas": set(), "anios": set()})
    archivos = sorted(entrada.glob("insolvencia_????-??.xlsx"))
    if not archivos:
        raise ValueError("No hay inventarios descargados. Ejecute src/descargar_insolvencia.py y revise docs/entrega2/preparacion_datos.md.")
    for archivo in archivos:
        corte = archivo.stem.removeprefix("insolvencia_")
        libro = load_workbook(archivo, read_only=True, data_only=True)
        hojas, nits = [], set()
        for hoja in libro.worksheets:
            filas = hoja.iter_rows(values_only=True)
            cabeceras_originales = list(next(filas))
            cabeceras = [clave(x) for x in cabeceras_originales]
            if "NIT" not in cabeceras:
                hojas.append({"nombre": hoja.title, "omitida": "Sin columna NIT", "cabeceras": cabeceras_originales})
                continue
            registros = []
            for fila in filas:
                reg = dict(zip(cabeceras, fila))
                nit = nit_limpio(reg.get("NIT"))
                if not nit:
                    continue
                reg["nit_limpio"] = nit
                registros.append(reg)
            fecha_columna = "FECHAAUTOADMISION" if "FECHAAUTOADMISION" in cabeceras else None
            fechas = [fecha(x.get(fecha_columna)) for x in registros] if fecha_columna else []
            fechas_validas = [x for x in fechas if x]
            anios = Counter()
            discrepancias_anio, procesados = 0, Counter()
            for reg in registros:
                nit = reg["nit_limpio"]
                nits.add(nit)
                datos_nit = por_nit[nit]
                datos_nit["cortes"].append(corte)
                admision = fecha(reg.get(fecha_columna)) if fecha_columna else None
                if admision:
                    datos_nit["fechas"].add(admision)
                apertura = reg.get("ANODEAPERTURACELEBRACION")
                try:
                    apertura = int(apertura)
                    anios[apertura] += 1
                    datos_nit["anios"].add(apertura)
                    if admision and apertura != admision.year:
                        discrepancias_anio += 1
                except (ValueError, TypeError):
                    pass
                procesados[str(reg.get("PROCESO") or "").strip()] += 1
            hojas.append({
                "nombre": hoja.title, "filas_con_nit": len(registros),
                "nits_distintos": len({x["nit_limpio"] for x in registros}),
                "cabeceras": cabeceras_originales,
                "columna_fecha_auto_admision": fecha_columna is not None,
                "fechas_admision_validas": len(fechas_validas),
                "fecha_admision_min": min(fechas_validas).isoformat() if fechas_validas else None,
                "fecha_admision_max": max(fechas_validas).isoformat() if fechas_validas else None,
                "fechas_admision_posteriores_fin_mes_corte": sum(x > fin_corte(corte) for x in fechas_validas),
                "anio_apertura_distinto_anio_admision": discrepancias_anio,
                "anios_apertura_celebracion": dict(sorted(anios.items())),
                "procesos": dict(procesados),
                "valores_proceso_para_revision_manual": {p: n for p, n in procesados.items()
                    if not any(patron in clave(p) for patron in ("REORGANIZ", "LIQUID", "VALID", "NEGOCI"))},
            })
        libro.close()
        cortes[corte] = {"archivo": archivo.name, "bytes": archivo.stat().st_size,
                         "sha256": hashlib.sha256(archivo.read_bytes()).hexdigest(),
                         "hojas": hojas, "nits": nits}
    ultimo = max(cortes)
    ultimos_nits = cortes[ultimo]["nits"]
    comparaciones = []
    for corte, datos in cortes.items():
        comparaciones.append({"corte_anterior": corte, "corte_actual": ultimo,
                              "nits_anterior": len(datos["nits"]),
                              "nits_anterior_ausentes_actual": len(datos["nits"] - ultimos_nits),
                              "nits_actual_no_observados_anterior": len(ultimos_nits - datos["nits"])})
    reapariciones = sum(bool(v["fechas"]) and min(v["fechas"]) > fin_corte(min(v["cortes"]))
                        for v in por_nit.values())
    salida.mkdir(parents=True, exist_ok=True)
    ruta_eventos = salida / "eventos_observados_insolvencia.csv"
    with ruta_eventos.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["NIT", "primer_corte_observado", "ultimo_corte_observado",
                            "primera_fecha_auto_observada", "cantidad_fechas_auto_distintas",
                            "primer_anio_apertura_celebracion_observado", "cortes_con_presencia"])
        for nit, datos in sorted(por_nit.items()):
            escritor.writerow([nit, min(datos["cortes"]), max(datos["cortes"]),
                                min(datos["fechas"]).isoformat() if datos["fechas"] else "",
                                len(datos["fechas"]), min(datos["anios"]) if datos["anios"] else "",
                                "|".join(sorted(set(datos["cortes"])))])
    informe = {
        "fuente_indice": "https://www.supersociedades.gov.co/web/procedimientos-de-insolvencia/informes",
        "cortes": {k: {a: v for a, v in d.items() if a != "nits"} for k, d in cortes.items()},
        "nits_distintos_union_cortes": len(por_nit),
        "nits_union_ausentes_ultimo_corte": len(set(por_nit) - ultimos_nits),
        "nits_con_fecha_auto_observada": sum(bool(v["fechas"]) for v in por_nit.values()),
        "nits_con_fecha_auto_posterior_a_un_corte_de_presencia_anterior": reapariciones,
        "comparaciones_con_ultimo_corte": comparaciones,
        "archivo_eventos_observados": ruta_eventos.name,
        "interpretacion": [
            "Los cortes históricos identifican sus hojas como Procesos en Curso y contienen estados de trámite o ejecución.",
            "La ausencia de una empresa del inventario actual no demuestra que nunca ingresó en insolvencia.",
            "La primera fecha auto observada es la mínima entre las fechas disponibles, no una primera admisión histórica validada.",
            "El año de apertura o celebración puede diferir de la fecha de auto de admisión y no debe sustituirla automáticamente.",
            "Unir cortes amplía los eventos observados, pero no prueba cobertura exhaustiva de admisiones ni permite asegurar negativos históricos.",
            "El corte disponible de 2020 es septiembre. El índice consultado no ofrece base de soporte de diciembre de 2020.",
            "No se generaron etiquetas ni se entrenaron modelos."
        ],
        "habilita_etiquetas_definitivas": False,
    }
    destino = salida / "auditoria_insolvencia.json"
    destino.write_text(json.dumps(informe, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in informe.items() if k != "cortes"}, ensure_ascii=False, indent=2))


def main():
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=base, help="Carpeta de extracción para data/ y reports/.")
    parser.add_argument("--entrada", type=Path, help="Predeterminado data/raw/insolvencia en la raíz de extracción.")
    parser.add_argument("--salida", type=Path, help="Predeterminado reports/preparacion en la raíz de extracción.")
    args = parser.parse_args()
    raiz = args.raiz.expanduser().resolve()
    entrada = (args.entrada or raiz / "data/raw/insolvencia").expanduser().resolve()
    salida = (args.salida or raiz / "reports/preparacion").expanduser().resolve()
    auditar(entrada, salida)


if __name__ == "__main__":
    main()
