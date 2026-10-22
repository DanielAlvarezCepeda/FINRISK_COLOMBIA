# -*- coding: utf-8 -*-
"""
FINRISK Colombia - inspeccion inicial de fuentes de datos.

Lee SOLO las primeras 2.000 filas de archivos CSV/TXT/XLSX de la carpeta
que contiene este script. No cambia los archivos originales y no necesita
pandas. Para archivos Excel (.xlsx) requiere: py -m pip install openpyxl

Ejecucion en Windows:
    cd "C:\\Users\\User\\Desktop\\Bases de Datos trabajo M"
    py finrisk_inspeccion_inicial.py

Salidas: carpeta "muestras_finrisk", con resumen_archivos.csv y un CSV de
muestra por archivo de origen.
"""

import csv
import re
import sys
from itertools import islice
from pathlib import Path

CARPETA_ORIGEN = Path(__file__).resolve().parent
CARPETA_SALIDA = CARPETA_ORIGEN / "muestras_finrisk"
MAX_FILAS = 2000
EXTENSIONES = {".csv", ".txt", ".xlsx"}


def formato_tamano(bytes_):
    return f"{bytes_ / (1024 ** 2):,.1f} MB"


def detectar_codificacion(ruta):
    with ruta.open("rb") as archivo:
        muestra = archivo.read(65536)
    for codificacion in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            muestra.decode(codificacion)
            return codificacion
        except UnicodeDecodeError:
            pass
    return "utf-8"


def detectar_delimitador(texto):
    """Prueba delimitadores habituales y permite archivos con encabezado raro."""
    try:
        dialecto = csv.Sniffer().sniff(texto, delimiters=",;\t|")
        return dialecto.delimiter
    except csv.Error:
        primera = texto.splitlines()[0] if texto.splitlines() else ""
        return max((",", ";", "\t", "|"), key=primera.count)


def extraer_muestra_csv(ruta):
    codificacion = detectar_codificacion(ruta)
    with ruta.open("r", encoding=codificacion, errors="replace", newline="") as archivo:
        vista = archivo.read(32768)
        delimitador = detectar_delimitador(vista)
        archivo.seek(0)
        lector = csv.reader(archivo, delimiter=delimitador)
        encabezados = next(lector, [])
        filas = list(islice(lector, MAX_FILAS))

    encabezados = [str(c).strip().lstrip("\ufeff") for c in encabezados]
    if len(encabezados) == 1 and any(s in encabezados[0] for s in (",", ";")):
        aviso = "ATENCION: el encabezado quedo en una sola columna; verificar el delimitador."
    else:
        aviso = ""
    return encabezados, filas, delimitador, codificacion, aviso


def extraer_muestra_excel(ruta):
    try:
        import openpyxl
    except ImportError:
        raise RuntimeError("Para leer archivos .xlsx instala openpyxl: py -m pip install openpyxl")

    libro = openpyxl.load_workbook(ruta, read_only=True, data_only=True)
    try:
        hoja = libro.active
        datos = hoja.iter_rows(values_only=True)
        encabezados = [str(v or "").strip() for v in next(datos, ())]
        filas = [["" if v is None else str(v) for v in fila] for fila in islice(datos, MAX_FILAS)]
        return encabezados, filas, "(hoja de Excel)", "(Excel)", "Hoja: " + hoja.title
    finally:
        libro.close()


def ejemplo_columna(encabezados, filas, nombre, limite=5):
    posibles = [i for i, cab in enumerate(encabezados) if re.sub(r"\s+", "", cab).upper() == nombre.upper()]
    if not posibles:
        return "No encontrada"
    indice = posibles[0]
    valores = []
    for fila in filas:
        if len(fila) > indice:
            valor = str(fila[indice]).strip()
            if valor and valor not in valores:
                valores.append(valor)
                if len(valores) >= limite:
                    break
    return " | ".join(valores) or "Sin valores en la muestra"


def nombre_salida_seguro(ruta, usados):
    base = re.sub(r"[^a-zA-Z0-9_\-]", "_", ruta.stem)[:75]
    candidato = base + "_muestra.csv"
    numero = 2
    while candidato.lower() in usados:
        candidato = f"{base}_{numero}_muestra.csv"
        numero += 1
    usados.add(candidato.lower())
    return candidato


def ejecutar():
    CARPETA_SALIDA.mkdir(exist_ok=True)
    rutas = sorted((p for p in CARPETA_ORIGEN.iterdir()
                    if p.is_file() and p.suffix.lower() in EXTENSIONES),
                   key=lambda p: p.name.lower())
    if not rutas:
        print("No encontre archivos CSV, TXT ni XLSX junto a este programa.")
        print("Carpeta revisada:", CARPETA_ORIGEN)
        return 1

    resumen = []
    usados = set()
    print("Carpeta:", CARPETA_ORIGEN)
    print("Archivos encontrados:", len(rutas))
    print("Leyendo como maximo", MAX_FILAS, "filas por archivo.\n")

    for i, ruta in enumerate(rutas, 1):
        print(f"[{i}/{len(rutas)}] {ruta.name} ({formato_tamano(ruta.stat().st_size)})")
        registro = {
            "archivo": ruta.name, "tamano_mb": round(ruta.stat().st_size / 1024**2, 2),
            "estado": "", "tipo": ruta.suffix.lower(), "codificacion": "",
            "delimitador": "", "columnas_n": "", "columnas": "",
            "filas_muestra": 0, "ejemplo_nit": "", "ejemplo_periodo": "",
            "ejemplo_fecha_corte": "", "ejemplo_anio_apertura": "",
            "ejemplo_proceso": "", "observaciones": "", "archivo_muestra": ""
        }
        try:
            if ruta.suffix.lower() == ".xlsx":
                encabezados, filas, delim, cod, aviso = extraer_muestra_excel(ruta)
            else:
                encabezados, filas, delim, cod, aviso = extraer_muestra_csv(ruta)
            salida = nombre_salida_seguro(ruta, usados)
            with (CARPETA_SALIDA / salida).open("w", encoding="utf-8-sig", newline="") as f:
                escritor = csv.writer(f)
                escritor.writerow(encabezados)
                escritor.writerows(filas)

            registro.update({
                "estado": "OK", "codificacion": cod, "delimitador": repr(delim),
                "columnas_n": len(encabezados), "columnas": " | ".join(encabezados),
                "filas_muestra": len(filas), "ejemplo_nit": ejemplo_columna(encabezados, filas, "NIT"),
                "ejemplo_periodo": ejemplo_columna(encabezados, filas, "PERIODO"),
                "ejemplo_fecha_corte": ejemplo_columna(encabezados, filas, "FECHA_CORTE"),
                "ejemplo_anio_apertura": ejemplo_columna(encabezados, filas, "AÑO_DE_APE"),
                "ejemplo_proceso": ejemplo_columna(encabezados, filas, "PROCESO"),
                "observaciones": aviso, "archivo_muestra": salida
            })
            print(f"  OK: {len(encabezados)} columnas, {len(filas)} filas de muestra. {aviso}")
            print("  Encabezados:", ", ".join(encabezados[:14]))
        except Exception as error:
            registro["estado"] = "ERROR"
            registro["observaciones"] = str(error)
            print("  ERROR:", error)
        resumen.append(registro)
        print()

    ruta_resumen = CARPETA_SALIDA / "resumen_archivos.csv"
    with ruta_resumen.open("w", encoding="utf-8-sig", newline="") as f:
        escritor = csv.DictWriter(f, fieldnames=list(resumen[0]))
        escritor.writeheader()
        escritor.writerows(resumen)

    correctos = sum(x["estado"] == "OK" for x in resumen)
    print(f"Finalizado: {correctos}/{len(rutas)} archivos procesados correctamente.")
    print("Resultados guardados en:", CARPETA_SALIDA)
    print("Comparte resumen_archivos.csv y las muestras de las tres bases del proyecto.")
    return 0 if correctos else 1


if __name__ == "__main__":
    try:
        sys.exit(ejecutar())
    except KeyboardInterrupt:
        print("\nInterrumpido por el usuario.")
        sys.exit(130)
