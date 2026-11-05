"""Auditoría opcional del CSV de etapa 4; salidas exclusivamente agregadas.

No modifica la fuente, publica NIT, crea etiquetas ni prepara entrenamiento.
El filtro descriptivo se calcula aparte y no reemplaza la base original.
"""
from __future__ import annotations
from pathlib import Path
import numpy as np
import pandas as pd
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

INDICADORES = ["endeudamiento", "liquidez_corriente", "roa", "margen_neto"]
ETIQUETAS = {"endeudamiento": "Endeudamiento", "liquidez_corriente": "Liquidez corriente", "roa": "ROA", "margen_neto": "Margen neto"}
NUMERICAS = ["anio_financiero", *INDICADORES, "activo_total", "pasivo_total", "patrimonio", "ingresos", "validacion_balance_relativa"]
OPCIONALES = ["activo_corriente", "pasivo_corriente", "utilidad_neta", "ganancia_bruta", "costo_ventas", "resultado_operacional", "costos_financieros", "roe", "capital_trabajo", "margen_bruto"]
BANDERAS = ["tiene_discrepancia", "balance_cuadra_tol_1pct", "indicadores_basicos_completos"]
TOL_BALANCE = 0.01


def _booleano(serie):
    texto = serie.astype("string").str.strip().str.casefold()
    vacio = texto.isna() | texto.eq("")
    resultado = pd.Series(pd.NA, index=serie.index, dtype="boolean")
    resultado.loc[texto.isin({"true", "1", "si", "sí", "verdadero"})] = True
    resultado.loc[texto.isin({"false", "0", "no", "falso"})] = False
    return resultado, {"verdaderos": int(resultado.eq(True).sum()), "falsos": int(resultado.eq(False).sum()), "vacios": int(vacio.sum()), "no_reconocidos": int((~vacio & resultado.isna()).sum())}


def _finito(valor):
    try:
        valor = float(valor)
        return valor if np.isfinite(valor) else np.nan
    except (ValueError, TypeError, OverflowError):
        return np.nan


def _estadisticos(datos, mascara, universo):
    filas = []
    for indicador in INDICADORES:
        serie = datos.loc[mascara, indicador].dropna()
        fila = {"universo": universo, "indicador": indicador, "unidad": "veces" if indicador == "liquidez_corriente" else "razon", "filas_universo": int(mascara.sum()), "n_finito": len(serie), "faltantes_o_invalidos": int(mascara.sum()) - len(serie)}
        nombres = ["media", "desviacion_estandar", "minimo", "p01", "p05", "p25", "mediana", "p75", "p95", "p99", "maximo"]
        valores = [serie.mean(), serie.std(), serie.min(), *serie.quantile([.01, .05, .25, .5, .75, .95, .99]).tolist(), serie.max()] if len(serie) else [np.nan] * len(nombres)
        fila.update({nombre: _finito(valor) for nombre, valor in zip(nombres, valores)})
        filas.append(fila)
    return filas


def analizar_microdatos(path, output_dir):
    """Retorna tablas, graficos, archivos_tablas, resumen y advertencias.

    Requiere NUMERICAS más NIT y tiene_discrepancia. Las banderas
    balance_cuadra_tol_1pct e indicadores_basicos_completos son opcionales.
    Todos los DataFrames retornados son agregados. No retorna filas ni NIT.
    """
    origen = Path(path).expanduser().resolve()
    if not origen.is_file():
        raise FileNotFoundError("No se encontró el CSV de microdatos configurado.")
    destino = Path(output_dir).expanduser().resolve()
    if destino == origen or destino.suffix.lower() == ".csv":
        raise ValueError("output_dir debe ser una carpeta distinta del CSV de entrada.")
    nombres_salida = [
        "microdatos_" + nombre + ".csv" for nombre in
        ["auditoria", "calidad_numerica", "banderas_booleanas", "calidad_por_anio",
         "estadisticos_indicadores", "spearman_pares", "vista_histogramas"]
    ]
    if any((destino / nombre).resolve() == origen for nombre in nombres_salida):
        raise ValueError("El destino sobrescribiría el CSV de origen; use otra carpeta.")
    try:
        original = pd.read_csv(origen, dtype="string", encoding="utf-8-sig", keep_default_na=False, on_bad_lines="error", low_memory=False)
    except (pd.errors.ParserError, pd.errors.EmptyDataError, UnicodeError) as exc:
        raise ValueError("No fue posible leer el CSV: verifique UTF-8, separador coma y filas completas.") from exc
    original.columns = original.columns.str.replace("\ufeff", "", regex=False).str.strip()
    if original.columns.duplicated().any():
        raise ValueError("Hay encabezados duplicados después de quitar espacios. Revise el esquema.")
    faltan = sorted({"NIT", "tiene_discrepancia", *NUMERICAS} - set(original.columns))
    if faltan:
        raise ValueError("Faltan columnas de la base de etapa 4: " + ", ".join(faltan))
    if original.empty:
        raise ValueError("El CSV incluye encabezados, pero no observaciones para explorar.")
    datos = original.copy(deep=True)
    total = len(datos)
    calidad = []
    for columna in NUMERICAS + [c for c in OPCIONALES if c in datos]:
        texto = original[columna].astype("string").str.strip()
        vacio = texto.isna() | texto.eq("")
        convertido = pd.to_numeric(texto.mask(vacio), errors="coerce").astype(float)
        no_finito = pd.Series(np.isinf(convertido), index=datos.index) | texto.str.casefold().isin({"nan", "+nan", "-nan"})
        coercion = ~vacio & convertido.isna() & ~no_finito
        datos[columna] = convertido.where(np.isfinite(convertido), np.nan)
        calidad.append({"columna": columna, "filas": total, "vacios_origen": int(vacio.sum()), "coerciones_a_nulo": int(coercion.sum()), "no_finitos": int(no_finito.sum()), "n_finitos": int(datos[columna].notna().sum()), "nulos_tras_auditoria": int(datos[columna].isna().sum())})

    # Estas claves son internas: nunca se incluyen en tablas o figuras retornadas.
    nit = original.NIT.astype("string").str.strip()
    nit_valido = nit.str.fullmatch(r"[0-9]{6,10}", na=False)
    anio = datos.anio_financiero
    anio_valido = anio.notna() & anio.between(1900, 2100) & anio.mod(1).eq(0)
    clave_valida = nit_valido & anio_valido
    claves = pd.DataFrame({"clave_interna": nit, "anio_interno": anio})
    duplicada = pd.Series(False, index=datos.index)
    duplicada.loc[clave_valida] = claves.loc[clave_valida].duplicated(keep=False)
    banderas, tabla_banderas = {}, []
    for columna in BANDERAS:
        if columna in original:
            banderas[columna], conteo = _booleano(original[columna])
            tabla_banderas.append({"bandera": columna, "disponible": True, **conteo})
        else:
            tabla_banderas.append({"bandera": columna, "disponible": False, "verdaderos": 0, "falsos": 0, "vacios": total, "no_reconocidos": 0})
    cuatro = datos[INDICADORES].notna().all(axis=1)
    error = datos.validacion_balance_relativa
    with np.errstate(divide="ignore", invalid="ignore", over="ignore"):
        recalculado = (datos.activo_total - datos.pasivo_total - datos.patrimonio).abs() / datos.activo_total.abs().where(datos.activo_total.ne(0))
    recalculado = recalculado.where(np.isfinite(recalculado), np.nan)
    error_valido = error.notna() & error.ge(0)
    calculable = recalculado.notna()
    balance_recalculado = calculable & recalculado.le(TOL_BALANCE)
    coherente = pd.Series(np.isclose(error, recalculado, atol=1e-9, rtol=1e-6, equal_nan=False), index=datos.index) & error_valido & calculable
    balance = balance_recalculado & error_valido & error.le(TOL_BALANCE) & coherente
    if "balance_cuadra_tol_1pct" in banderas:
        balance &= banderas["balance_cuadra_tol_1pct"].eq(True).fillna(False)
    conflicto = banderas["tiene_discrepancia"]
    activos_ok, ingresos_ok = datos.activo_total.gt(0), datos.ingresos.gt(0)
    filtro = (clave_valida & ~duplicada & cuatro & balance & conflicto.eq(False).fillna(False) & activos_ok & ingresos_ok).fillna(False)

    metricas = [
        ("filas_leidas", total), ("nit_vacio", int(nit.eq("").sum())), ("nit_formato_no_valido", int((~nit_valido).sum())),
        ("anio_no_valido", int((~anio_valido).sum())), ("filas_con_clave_valida", int(clave_valida.sum())),
        ("empresas_nit_validos_distintos", int(nit[nit_valido].nunique())),
        ("claves_nit_anio_distintas_validas", int(claves.loc[clave_valida].drop_duplicates().shape[0])),
        ("claves_nit_anio_duplicadas", int(claves.loc[duplicada].drop_duplicates().shape[0])),
        ("filas_en_claves_duplicadas", int(duplicada.sum())),
        ("filas_extra_por_clave_duplicada", int(claves.loc[clave_valida].duplicated(keep="first").sum())),
        ("filas_exactas_repetidas_extra", int(original.duplicated(keep="first").sum())),
        ("cuatro_indicadores_finitos", int(cuatro.sum())), ("balance_no_calculable", int((~calculable).sum())),
        ("error_balance_reportado_negativo", int(error.lt(0).sum())), ("error_balance_reportado_nulo_o_invalido", int(error.isna().sum())),
        ("errores_balance_no_coinciden", int((error_valido & calculable & ~coherente).sum())),
        ("balance_recalculado_ok_1pct", int(balance_recalculado.sum())), ("balance_validado_1pct", int(balance.sum())),
        ("conflicto_confirmado", int(conflicto.eq(True).sum())), ("estado_conflicto_desconocido", int(conflicto.isna().sum())),
        ("activos_positivos", int(activos_ok.sum())), ("ingresos_positivos", int(ingresos_ok.sum())),
        ("filas_filtro_descriptivo_auditado", int(filtro.sum())), ("filas_fuera_filtro_descriptivo", int((~filtro).sum())),
    ]
    for columna, derivada in [("balance_cuadra_tol_1pct", balance_recalculado), ("indicadores_basicos_completos", cuatro)]:
        if columna in banderas:
            conocida = banderas[columna].notna()
            if columna == "balance_cuadra_tol_1pct":
                conocida &= calculable
            metricas.append(("inconsistencia_" + columna, int((conocida & banderas[columna].ne(derivada).fillna(False)).sum())))
    anual = pd.DataFrame({"anio_financiero": anio, "filas": 1, "nit_valido": nit_valido, "clave_duplicada": duplicada, "cuatro_indicadores": cuatro, "balance_validado": balance, "conflicto_confirmado": conflicto.eq(True).fillna(False), "conflicto_desconocido": conflicto.isna(), "filtro_descriptivo": filtro}).loc[anio_valido].groupby("anio_financiero", as_index=False).sum()
    if not anual.empty:
        empresas = pd.DataFrame({"anio_financiero": anio, "clave_interna": nit}).loc[clave_valida].groupby("anio_financiero").clave_interna.nunique()
        anual["anio_financiero"] = anual.anio_financiero.astype(int)
        anual["empresas_nit_validos"] = anual.anio_financiero.map(empresas).fillna(0).astype(int)
        anual["pct_filtro_descriptivo"] = anual.filtro_descriptivo / anual.filas * 100
    estadisticos = pd.DataFrame(_estadisticos(datos, pd.Series(True, index=datos.index), "todas_las_filas") + _estadisticos(datos, filtro, "filtro_descriptivo_auditado"))

    # Se ranquea DESPUÉS de seleccionar cada pareja completa, sin usar scipy.
    correlaciones = []
    matriz = pd.DataFrame(np.nan, index=INDICADORES, columns=INDICADORES)
    numeros_pares = pd.DataFrame(0, index=INDICADORES, columns=INDICADORES)
    par_evaluable = False
    for i, izquierda in enumerate(INDICADORES):
        for derecha in INDICADORES[i:]:
            pares = datos.loc[filtro, list(dict.fromkeys([izquierda, derecha]))].dropna()
            n, coeficiente = len(pares), np.nan
            if n >= 3 and pares[izquierda].nunique() >= 2 and pares[derecha].nunique() >= 2:
                coeficiente = 1.0 if izquierda == derecha else pares.rank(method="average").corr(method="pearson").iloc[0, 1]
                par_evaluable |= izquierda != derecha
            matriz.loc[izquierda, derecha] = matriz.loc[derecha, izquierda] = coeficiente
            numeros_pares.loc[izquierda, derecha] = numeros_pares.loc[derecha, izquierda] = n
            if izquierda != derecha:
                correlaciones.append({"indicador_1": izquierda, "indicador_2": derecha, "universo": "filtro_descriptivo_auditado", "n_pares": n, "spearman": _finito(coeficiente), "estado": "Calculable" if np.isfinite(coeficiente) else "Menos de 3 pares o variable constante"})

    destino.mkdir(parents=True, exist_ok=True)
    graficos, recortes = {}, []
    figura = Figure(figsize=(12, 8), constrained_layout=True)
    FigureCanvasAgg(figura)
    for eje, indicador in zip(figura.subplots(2, 2).ravel(), INDICADORES):
        serie = datos[indicador].dropna()
        bajo, alto = serie.quantile([.01, .99]).tolist() if len(serie) else (np.nan, np.nan)
        vista = serie[serie.between(bajo, alto)]
        omitidos = int((serie < bajo).sum() + (serie > alto).sum()) if len(serie) else 0
        factor = 1 if indicador == "liquidez_corriente" else 100
        with np.errstate(over="ignore"):
            valores = vista.to_numpy(dtype=float) * factor
        valores = valores[np.isfinite(valores)]
        if len(valores):
            eje.hist(valores, bins=min(40, max(5, int(np.sqrt(len(valores))))), color="#25678A", edgecolor="white")
        else:
            eje.text(.5, .5, "Sin valores representables en la vista", ha="center", va="center", transform=eje.transAxes)
        eje.set_title(f"{ETIQUETAS[indicador]} | n finito = {len(serie):,}\nVista p01–p99; extremos fuera de vista = {omitidos:,}", fontsize=10)
        eje.set_xlabel("veces" if factor == 1 else "%")
        eje.set_ylabel("Observaciones empresa-año")
        eje.grid(axis="y", alpha=.2)
        recortes.append({"indicador": indicador, "universo": "todas_las_filas_finitas", "n_finito": len(serie), "p01_original": bajo, "p99_original": alto, "n_dentro_p01_p99": len(vista), "extremos_fuera_de_vista": omitidos, "no_representables_al_cambiar_unidad": len(vista) - len(valores), "unidad_estadisticos": "veces" if factor == 1 else "razon"})
    figura.suptitle("FINRISK | Distribuciones de las razones originales\nSe limita la vista; no se recortan ni se winsorizan los datos de análisis.", fontsize=13)
    ruta = destino / "microdatos_histogramas_p01_p99.png"
    figura.savefig(ruta, dpi=150)
    graficos["histogramas"] = str(ruta)
    if par_evaluable:
        figura_corr = Figure(figsize=(9, 7), constrained_layout=True)
        FigureCanvasAgg(figura_corr)
        eje = figura_corr.subplots()
        valores = matriz.to_numpy(dtype=float)
        mapa = eje.imshow(np.ma.masked_invalid(valores), vmin=-1, vmax=1, cmap="RdBu_r")
        eje.set_xticks(range(4), [ETIQUETAS[c] for c in INDICADORES], rotation=25, ha="right")
        eje.set_yticks(range(4), [ETIQUETAS[c] for c in INDICADORES])
        for i in range(4):
            for j in range(4):
                texto = f"{valores[i, j]:.2f}\nn = {numeros_pares.iloc[i, j]:,}" if np.isfinite(valores[i, j]) else f"No calculable\nn = {numeros_pares.iloc[i, j]:,}"
                eje.text(j, i, texto, ha="center", va="center", fontsize=9, color="white" if np.isfinite(valores[i, j]) and abs(valores[i, j]) > .65 else "black")
        eje.set_title("Spearman | Filtro descriptivo auditado\nSe requieren ≥3 pares y variación en ambas variables")
        figura_corr.colorbar(mapa, ax=eje, label="Correlación de rangos")
        ruta = destino / "microdatos_correlacion_spearman.png"
        figura_corr.savefig(ruta, dpi=150)
        graficos["correlacion_spearman"] = str(ruta)
    tablas = {"auditoria": pd.DataFrame(metricas, columns=["metrica", "conteo"]), "calidad_numerica": pd.DataFrame(calidad), "banderas_booleanas": pd.DataFrame(tabla_banderas), "calidad_por_anio": anual, "estadisticos_indicadores": estadisticos, "spearman_pares": pd.DataFrame(correlaciones), "vista_histogramas": pd.DataFrame(recortes)}
    archivos = {}
    for nombre, tabla in tablas.items():
        ruta = destino / f"microdatos_{nombre}.csv"
        tabla.to_csv(ruta, index=False, encoding="utf-8-sig")
        archivos[nombre] = str(ruta)
    advertencias = [
        "Auditoría descriptiva opcional. No se creó ni validó una etiqueta de insolvencia.",
        "La fuente se conserva intacta; las coerciones se registran sin corregir importes originales.",
        "El filtro descriptivo exige clave válida única, cuatro razones finitas, balance coherente al 1 %, ausencia de conflicto confirmada, activos e ingresos positivos. No define población de entrenamiento.",
        "Los controles se solapan: no sumar conteos como exclusiones independientes.",
        "Las medias y correlaciones no establecen causalidad. Duplicados y cobertura variable requieren auditoría de radicados, unidades y selección.",
        "No se exportan NIT, nombres, filas individuales ni un conjunto de entrenamiento.",
        "Tablas en razones originales; histogramas de endeudamiento, ROA y margen en %, liquidez en veces.",
    ]
    if not par_evaluable:
        anterior = destino / "microdatos_correlacion_spearman.png"
        if anterior.is_file():
            anterior.unlink()  # Solo un producto generado reservado por este módulo.
        advertencias.append("Sin matriz gráfica de Spearman: faltan ≥3 pares con variación en ambas variables del filtro descriptivo.")
    return {"tablas": tablas, "graficos": graficos, "archivos_tablas": archivos, "resumen": {"filas_leidas": total, "filas_filtro_descriptivo_auditado": int(filtro.sum()), "pct_filtro_descriptivo_auditado": round(float(filtro.mean()) * 100, 2)}, "advertencias": advertencias}
