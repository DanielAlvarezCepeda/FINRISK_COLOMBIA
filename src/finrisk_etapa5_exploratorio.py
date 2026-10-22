#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""FINRISK COLOMBIA - ETAPA 5: auditoria y exploracion financiera.

Objetivo: calcular indicadores de calidad, estadisticas descriptivas y graficos.
NO crea etiquetas de insolvencia, NO entrena modelos y NO corrige valores en origen.

Coloque este archivo en la misma carpeta que contiene `finrisk_etapa4` y ejecute:
    py -m pip install pandas numpy matplotlib
    py finrisk_etapa5_exploratorio.py

Entradas esperadas:
    finrisk_etapa4/base_financiera_preliminar.csv
    finrisk_etapa4/discrepancias_pendientes_revision.csv  (opcional)

Salidas:
    finrisk_etapa5/resumen_analisis.txt
    finrisk_etapa5/cobertura_y_calidad_por_anio.csv
    finrisk_etapa5/estadisticos_indicadores_por_anio.csv
    finrisk_etapa5/incidencias_calidad.csv
    finrisk_etapa5/discrepancias_por_anio.csv
    finrisk_etapa5/discrepancias_por_variable.csv
    finrisk_etapa5/muestras_posibles_diferencias_unidad.csv
    finrisk_etapa5/grafico_cobertura_empresas.png
    finrisk_etapa5/grafico_calidad_por_anio.png
    finrisk_etapa5/grafico_mediana_indicadores.png

NOTA: Las reglas de 'filas_validas_descriptivo' son filtros provisionales,
no la definicion de poblacion elegible para entrenar un modelo de insolvencia.
"""

from pathlib import Path
import argparse
import sys
import pandas as pd
import numpy as np

# La importacion se deja igual que en el comando de comprobacion que funciono
# en Windows. No forzamos el backend 'Agg': no es necesario para guardar PNG
# en este equipo. Si falla una dependencia, mostramos el error real.
try:
    import matplotlib.pyplot as plt
except ImportError as exc:
    import traceback
    traceback.print_exc()
    sys.exit(f'Error concreto al importar matplotlib.pyplot: {exc}')

INDICADORES = ['endeudamiento', 'liquidez_corriente', 'roa', 'margen_neto']
RELEVANTES = INDICADORES + [
    'activo_total','pasivo_total','patrimonio','activo_corriente',
    'pasivo_corriente','ingresos','utilidad_neta','validacion_balance_relativa'
]


def booleano(serie):
    return serie.astype(str).str.strip().str.lower().isin(['true','1','si','sí','verdadero'])


def entero(serie):
    return pd.to_numeric(serie, errors='coerce').astype('Int64')


def porcentaje(parte, total):
    return round(float(parte) / float(total) * 100, 2) if total else 0.0


def revisar(df):
    faltantes = {'NIT', 'anio_financiero', *INDICADORES} - set(df.columns)
    if faltantes:
        raise ValueError(f'La base no incluye columnas necesarias: {sorted(faltantes)}')
    df = df.copy()
    df['NIT'] = df['NIT'].astype('string').str.strip()
    df['anio_financiero'] = entero(df['anio_financiero'])
    df = df[df['anio_financiero'].notna()].copy()
    for col in RELEVANTES:
        if col not in df.columns:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors='coerce')
        df.loc[~np.isfinite(df[col]), col] = np.nan

    df['balance_ok'] = (df['validacion_balance_relativa'] <= .01) & df['validacion_balance_relativa'].notna()
    if 'balance_cuadra_tol_1pct' in df:
        df['balance_ok'] = df['balance_ok'] & booleano(df['balance_cuadra_tol_1pct'])
    df['conflicto'] = booleano(df['tiene_discrepancia']) if 'tiene_discrepancia' in df else False
    df['cuatro_indicadores'] = df[INDICADORES].notna().all(axis=1)
    df['activos_positivos'] = df['activo_total'] > 0
    df['ingresos_positivos'] = df['ingresos'] > 0
    df['fila_valida_descriptivo'] = (
        df['cuatro_indicadores'] & df['balance_ok'] & ~df['conflicto']
        & df['activos_positivos'] & df['ingresos_positivos']
    )
    return df


def preparar_calidad(df):
    salida = df.groupby('anio_financiero', dropna=False).agg(
        empresas=('NIT','nunique'),
        observaciones=('NIT','size'),
        cuatro_indicadores=('cuatro_indicadores','sum'),
        balances_cuadrados=('balance_ok','sum'),
        con_discrepancia=('conflicto','sum'),
        activos_positivos=('activos_positivos','sum'),
        ingresos_positivos=('ingresos_positivos','sum'),
        filas_validas_descriptivo=('fila_valida_descriptivo','sum'),
    ).reset_index()
    for nombre in ['cuatro_indicadores','balances_cuadrados', 'con_discrepancia', 'filas_validas_descriptivo']:
        salida['pct_'+nombre] = (salida[nombre]/salida['observaciones']*100).round(2)
    return salida


def preparar_estadisticos(df):
    d = df[df['fila_valida_descriptivo']]
    registros = []
    for anio, grupo in d.groupby('anio_financiero'):
        for variable in INDICADORES:
            s = grupo[variable].dropna()
            if not len(s):
                continue
            registros.append({
                'anio_financiero': int(anio), 'indicador':variable, 'n':len(s),
                'media':float(s.mean()), 'mediana':float(s.median()),
                'p05':float(s.quantile(.05)), 'p25':float(s.quantile(.25)),
                'p75':float(s.quantile(.75)), 'p95':float(s.quantile(.95)),
                'minimo':float(s.min()), 'maximo':float(s.max()),
            })
    return pd.DataFrame(registros)


def preparar_incidencias(df):
    tests = [
        ('sin_cuatro_indicadores', ~df['cuatro_indicadores']),
        ('balance_no_cuadra_o_sin_dato', ~df['balance_ok']),
        ('con_candidatos_en_conflicto', df['conflicto']),
        ('activo_total_no_positivo_o_faltante', ~df['activos_positivos']),
        ('ingresos_no_positivos_o_faltantes', ~df['ingresos_positivos']),
        ('patrimonio_negativo', df['patrimonio'] < 0),
        ('liquidez_corriente_mayor_a_10', df['liquidez_corriente'] > 10),
        ('endeudamiento_mayor_a_1', df['endeudamiento'] > 1),
    ]
    return pd.DataFrame([
        {'tipo_incidencia':nombre, 'registros':int(cond.fillna(False).sum()),
         'porcentaje': porcentaje(cond.fillna(False).sum(),len(df))}
        for nombre, cond in tests
    ])


def preparar_discrepancias(path, out):
    if not path.exists():
        return {'n':None, 'pares':None, 'empresas':None, 'casi_mil':None}
    d = pd.read_csv(path, encoding='utf-8-sig', dtype={'nit':'string'})
    for col in ['anio','importe_minimo','importe_maximo']:
        d[col] = pd.to_numeric(d[col], errors='coerce')
    por_anio = d.groupby('anio',as_index=False).agg(
        discrepancias_indicador=('nit','size'), empresas=('nit','nunique')
    )
    por_variable = d.groupby('variable',as_index=False).agg(
        discrepancias_indicador=('nit','size'), empresas=('nit','nunique')
    ).sort_values('discrepancias_indicador', ascending=False)
    por_anio.to_csv(out/'discrepancias_por_anio.csv',index=False,encoding='utf-8-sig')
    por_variable.to_csv(out/'discrepancias_por_variable.csv',index=False,encoding='utf-8-sig')
    d['ratio_max_min'] = np.where(
        (d['importe_minimo'] > 0) & (d['importe_maximo'] > 0),
        d['importe_maximo']/d['importe_minimo'], np.nan
    )
    sospechas = d[d['ratio_max_min'].between(990,1010)].copy()
    sospechas.to_csv(out/'muestras_posibles_diferencias_unidad.csv', index=False, encoding='utf-8-sig')
    return {
        'n':len(d), 'pares':len(d[['nit','anio']].drop_duplicates()),
        'empresas':d.nit.nunique(), 'casi_mil':len(sospechas),
    }


def graficos(calidad, estad, out):
    x = calidad['anio_financiero'].astype(int).astype(str).tolist()
    fig,ax = plt.subplots(figsize=(9,4.7))
    ax.bar(x,calidad['empresas'])
    ax.set(title='FINRISK Colombia - Cobertura empresarial 2019-2024',
           xlabel='Año financiero', ylabel='Empresas con registro')
    ax.grid(axis='y',alpha=.2)
    fig.tight_layout(); fig.savefig(out/'grafico_cobertura_empresas.png',dpi=180); plt.close(fig)

    fig,ax = plt.subplots(figsize=(9,4.7))
    ax.plot(x,calidad['pct_cuatro_indicadores'], marker='o', label='Con 4 indicadores')
    ax.plot(x,calidad['pct_balances_cuadrados'], marker='s', label='Balance cuadra al 1%')
    ax.plot(x,calidad['pct_filas_validas_descriptivo'], marker='^', label='Filtro descriptivo estricto')
    ax.set(title='FINRISK Colombia - Cobertura y control de calidad',xlabel='Año financiero',ylabel='% de registros')
    ax.set_ylim(0,101);ax.legend();ax.grid(alpha=.2)
    fig.tight_layout();fig.savefig(out/'grafico_calidad_por_anio.png',dpi=180);plt.close(fig)

    if not estad.empty:
        fig,ax = plt.subplots(figsize=(9,4.7))
        for var in ['endeudamiento','roa','margen_neto']:
            tabla = estad[estad['indicador']==var].sort_values('anio_financiero')
            if len(tabla):
                ax.plot(tabla['anio_financiero'], tabla['mediana'], marker='o', label=var)
        ax.set(title='FINRISK Colombia - Medianas financieras (muestra filtrada)',
               xlabel='Año financiero',ylabel='Razón')
        ax.legend(); ax.grid(alpha=.2)
        fig.tight_layout();fig.savefig(out/'grafico_mediana_indicadores.png',dpi=180);plt.close(fig)


def principal(carpeta):
    origen=carpeta/'finrisk_etapa4'
    path=origen/'base_financiera_preliminar.csv'
    if not path.exists():
        sys.exit(f'No se encuentra {path}. Ejecute primero la etapa 4 en esta carpeta.')
    salida=carpeta/'finrisk_etapa5'
    salida.mkdir(exist_ok=True)
    df=pd.read_csv(path,encoding='utf-8-sig',dtype={'NIT':'string'},low_memory=False)
    df=revisar(df)
    calidad=preparar_calidad(df)
    estad=preparar_estadisticos(df)
    incidencias=preparar_incidencias(df)
    discrepancias=preparar_discrepancias(origen/'discrepancias_pendientes_revision.csv',salida)

    calidad.to_csv(salida/'cobertura_y_calidad_por_anio.csv',index=False,encoding='utf-8-sig')
    estad.to_csv(salida/'estadisticos_indicadores_por_anio.csv',index=False,encoding='utf-8-sig')
    incidencias.to_csv(salida/'incidencias_calidad.csv',index=False,encoding='utf-8-sig')
    graficos(calidad,estad,salida)
    texto = f'''FINRISK Colombia - Etapa 5 | Auditoria y analisis descriptivo
\nArchivo: {path.name}
Filas empresa-anio: {len(df):,}
Empresas distintas: {df.NIT.nunique():,}
Rango de anios: {df.anio_financiero.min()} a {df.anio_financiero.max()}
Con cuatro indicadores: {int(df.cuatro_indicadores.sum()):,} ({porcentaje(df.cuatro_indicadores.sum(),len(df))}%)
Balances al 1%: {int(df.balance_ok.sum()):,} ({porcentaje(df.balance_ok.sum(),len(df))}%)
Con discrepancia: {int(df.conflicto.sum()):,} ({porcentaje(df.conflicto.sum(),len(df))}%)
Filas aptas para ANALISIS DESCRIPTIVO ESTRICTO: {int(df.fila_valida_descriptivo.sum()):,} ({porcentaje(df.fila_valida_descriptivo.sum(),len(df))}%)
Discrepancias en indicadores: {discrepancias['n']}
NIT-anio con alguna discrepancia: {discrepancias['pares']}
Observaciones con cociente min/max proximo a 1:1000 (SENAL PARA AUDITAR, NO CORREGIR AUTOMATICAMENTE): {discrepancias['casi_mil']}

ADVERTENCIAS:
- No hay variable objetivo ni etiqueta historica de insolvencia en este procesamiento.
- La base no permite afirmar que una empresa estuvo libre de insolvencia.
- Las diferencias de escala cercanas a 1:1000 requieren contrastar el punto de entrada,
  radicado, concepto y unidad de reporte ANTES de modificar importes.
- El filtro descriptivo puede excluir observaciones de empresas en crisis;
  NO utilizarlo directamente como filtro para entrenar ni inferir poblaciones.
- Los graficos describen periodos/reportes, NO la probabilidad de insolvencia.
- Mantenga por separado los datos originales, el procesamiento y los productos de visualizacion.
'''
    (salida/'resumen_analisis.txt').write_text(texto,encoding='utf-8')
    print('\n'+texto)
    print('Resultados disponibles en:',salida)
    print('COMPARTIR: resumen_analisis.txt, cobertura_y_calidad_por_anio.csv,')
    print(' estadisticos_indicadores_por_anio.csv, incidencias_calidad.csv.')

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--carpeta',type=Path,default=Path(__file__).resolve().parent)
    args=parser.parse_args()
    principal(args.carpeta.resolve())
