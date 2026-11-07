"""Descarga cortes públicos de insolvencia conservando bytes y procedencia."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from urllib.request import Request, urlopen

FUENTES = {
    "2019-12": "https://www.supersociedades.gov.co/documents/58444/6516407/BASE_SOPORTE_INSOLVENCIA_DIC_2019.xlsx/4b4c0c48-4f23-3cc6-35df-df2b329679fb?version=1.0&t=1694034011022",
    "2020-09": "https://www.supersociedades.gov.co/documents/58444/6516168/BASE_SOPORTE_INSOLVENCIA_SEP_2020.xlsx/ffeb2f14-5607-73c6-8591-ef2ee9f1fc94?version=1.0&t=1694033963280",
    "2021-12": "https://www.supersociedades.gov.co/documents/58444/6516010/Base-datos-insolvencia-diciembre-2021.xlsx/ffbd0733-6430-c60e-d454-6a47367b6ecd?version=1.0&t=1694028376290",
    "2022-12": "https://www.supersociedades.gov.co/documents/58444/6515849/BASE-SOPORTE-INSOLVENCIA-2022-CORTE-DICIEMBRE.xlsx/193a9c81-3986-ed94-af98-cdc8ac6c68a9?version=1.0&t=1694026647657",
    "2023-12": "https://www.supersociedades.gov.co/documents/58444/6515839/BASE-SOPORTE-INSOLVENCIA-2023-CORTE-DICIEMBRE.xlsx/4e32b9f3-5c45-b1a8-8606-a431fb3f21a3?version=1.1&t=1724249141759",
    "2026-10": "https://www.supersociedades.gov.co/documents/58444/9506465/Base-Soporte-Insolvencia-2026-CORTE-OCTUBRE.xlsx/3505ebea-c49e-c42f-00ea-48b443a1bc39?t=1791380389241&version=1.0",
    "2025-12": "https://www.supersociedades.gov.co/documents/58444/8332056/Base-Soporte-Insolvencia-2025-CORTE-DICIEMBRE.xlsx/b3b136e2-234a-d640-c79e-5ab0af1fd4c9?t=1767619414849&version=1.0",
    "2024-12": "https://www.supersociedades.gov.co/documents/58444/7803983/Base-Soporte-Insolvencia-2024-CORTE-DICIEMBRE.xlsx/a5476d0a-46fe-c53f-ea36-417c206c1838?t=1735911388000&version=1.1",
}


def descargar(item, destino):
    corte, url = item
    registro = {"corte": corte, "url": url, "fecha_descarga_utc": datetime.now(timezone.utc).isoformat()}
    try:
        solicitud = Request(url, headers={"User-Agent": "FINRISK-academic-source-audit/1.0"})
        with urlopen(solicitud, timeout=60) as respuesta:
            contenido = respuesta.read()
            registro["url_final"] = respuesta.url
            registro["content_type"] = respuesta.headers.get("Content-Type")
        if not contenido.startswith(b"PK"):
            raise ValueError("La respuesta no corresponde a un archivo XLSX.")
        archivo = destino / f"insolvencia_{corte}.xlsx"
        huella = hashlib.sha256(contenido).hexdigest()
        if archivo.exists():
            anterior = hashlib.sha256(archivo.read_bytes()).hexdigest()
            if anterior != huella:
                raise ValueError("La fuente cambió y se conserva el XLSX existente. Use --raiz con otra carpeta para una nueva extracción.")
            registro["archivo_reutilizado"] = True
        else:
            archivo.write_bytes(contenido)
            registro["archivo_reutilizado"] = False
        registro.update(archivo=archivo.name, bytes=len(contenido), sha256=hashlib.sha256(contenido).hexdigest(), ok=True)
    except Exception as error:
        registro.update(ok=False, error=str(error))
    return registro


def main():
    base = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raiz", type=Path, default=base, help="Carpeta de extracción para data/ y reports/.")
    parser.add_argument("--destino", type=Path, help="Directorio de originales. Predeterminado data/raw/insolvencia en la raíz de extracción.")
    parser.add_argument("--reporte", type=Path, help="Manifiesto. Predeterminado reports/preparacion/adquisicion_insolvencia.json.")
    parser.add_argument("--fuentes-json", type=Path, help="Objeto JSON corte: URL para agregar otros cortes oficiales.")
    args = parser.parse_args()
    raiz = args.raiz.expanduser().resolve()
    args.destino = (args.destino or raiz / "data/raw/insolvencia").expanduser().resolve()
    args.reporte = (args.reporte or raiz / "reports/preparacion/adquisicion_insolvencia.json").expanduser().resolve()
    args.destino.mkdir(parents=True, exist_ok=True)
    args.reporte.parent.mkdir(parents=True, exist_ok=True)
    fuentes = dict(FUENTES)
    if args.fuentes_json:
        fuentes.update(json.loads(args.fuentes_json.read_text(encoding="utf-8-sig")))
    with ThreadPoolExecutor(max_workers=3) as pool:
        resultados = list(pool.map(lambda item: descargar(item, args.destino), fuentes.items()))
    args.reporte.write_text(json.dumps(resultados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(resultados, ensure_ascii=False, indent=2))
    return 0 if all(x["ok"] for x in resultados) else 2


if __name__ == "__main__":
    raise SystemExit(main())
