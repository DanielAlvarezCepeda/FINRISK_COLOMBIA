"""Consulta MLflow sin crear experimentos, corridas ni artefactos remotos."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import urlopen


def consultar(url, tiempo):
    try:
        with urlopen(url, timeout=tiempo) as respuesta:
            contenido = respuesta.read(1024 * 1024 + 1)
            if len(contenido) > 1024 * 1024:
                return {"ok": False, "error": "Respuesta superior a 1 MiB."}
            texto = contenido.decode("utf-8", errors="replace").strip()
            return {"ok": True, "status": respuesta.status, "contenido": texto}
    except HTTPError as error:
        return {"ok": False, "status": error.code, "error": error.reason}
    except (URLError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error)}


def comprobar(uri, experimento, tiempo):
    consultas = {
        "health": uri + "/health",
        "version": uri + "/version",
        "experimento": uri + "/api/2.0/mlflow/experiments/get-by-name?" +
        urlencode({"experiment_name": experimento}),
    }
    with ThreadPoolExecutor(max_workers=3) as pool:
        respuestas = dict(zip(consultas, pool.map(
            lambda url: consultar(url, tiempo), consultas.values()
        )))
    estado = respuestas["health"]
    if estado.get("ok") and estado.get("contenido") != "OK":
        estado.update(ok=False, error="El contenido de /health no corresponde a MLflow.")
    version = respuestas["version"]
    if version.get("ok") and not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:[A-Za-z0-9.+-]*)", version.get("contenido", "")):
        version.update(ok=False, error="La respuesta de /version no contiene una versión reconocible.")
    experimento_respuesta = respuestas["experimento"]
    if experimento_respuesta.get("ok"):
        try:
            datos = json.loads(experimento_respuesta.pop("contenido"))["experiment"]
            if not isinstance(datos, dict) or datos.get("name") != experimento:
                raise ValueError("El experimento recibido no corresponde al solicitado.")
            experimento_respuesta["datos"] = {k: datos.get(k) for k in (
                "name", "experiment_id", "lifecycle_stage", "artifact_location"
            )}
        except (KeyError, TypeError, ValueError) as error:
            experimento_respuesta.update(ok=False, error=str(error))
    ubicacion = experimento_respuesta.get("datos", {}).get("artifact_location") or ""
    esquema = urlsplit(ubicacion).scheme
    if not experimento_respuesta.get("ok"):
        nota = "Ubicación de artefactos pendiente de consultar."
    elif esquema == "mlflow-artifacts":
        nota = "El experimento declara proxy de artefactos. Falta probar escritura y recuperación."
    elif esquema in {"", "file"}:
        nota = "La ubicación parece local. Jairo debe confirmar cómo se comparten los artefactos con Windows."
    else:
        nota = "Confirmar acceso al almacenamiento de artefactos y sus credenciales con Jairo."
    return {
        "fecha_utc": datetime.now(timezone.utc).isoformat(),
        "tracking_uri": uri, "experimento_solicitado": experimento,
        "solo_lectura": True, "consultas": respuestas,
        "lectura_basica_ok": all(v.get("ok") for v in respuestas.values()),
        "nota_artefactos": nota,
        "escritura_y_recuperacion_artefactos_verificadas": False,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tracking-uri", required=True)
    parser.add_argument("--experimento", default="Proyecto-MIAD")
    parser.add_argument("--timeout", type=float, default=8)
    parser.add_argument("--salida", type=Path, default=Path("salidas/diagnostico_conexion.json"))
    args = parser.parse_args()
    uri = args.tracking_uri.rstrip("/")
    partes = urlsplit(uri)
    if partes.scheme not in {"http", "https"} or not partes.hostname:
        parser.error("Use una dirección HTTP o HTTPS válida.")
    if partes.username or partes.password or partes.query or partes.fragment:
        parser.error("Use una dirección de servidor sin credenciales, consulta ni fragmento.")
    if not 0 < args.timeout <= 30 or not args.experimento.strip():
        parser.error("El timeout debe ser mayor que cero y hasta 30 segundos. Indique el experimento.")
    resultado = comprobar(uri, args.experimento.strip(), args.timeout)
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    args.salida.write_text(json.dumps(resultado, ensure_ascii=False, indent=2) + chr(10), encoding="utf-8")
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado["lectura_basica_ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
