# -*- coding: utf-8 -*-
"""FINRISK Colombia - Etapa 3: perfilamiento contable de bases colombianas.

USO (PowerShell):
    cd "C:\\Users\\User\\Desktop\\Bases de Datos trabajo M"
    py finrisk_perfilamiento_contable.py

Coloca este archivo en la MISMA carpeta que los CSV financieros grandes.
El archivo coincidencias_nit.csv puede estar junto al script o en finrisk_validacion.

Qué hace:
- Recorre los 2 estados financieros sin cargarlos completos en memoria.
- Cuenta los conceptos contables por archivo y detecta los más útiles.
- Analiza formas de la columna PERIODO y su relación con FECHA_CORTE.
- Extrae una muestra de registros para empresas que entraron a insolvencia
  con corte financiero anterior a su fecha de apertura, para validar conceptos.
- No modifica originales, no crea etiquetas y NO entrena ningún modelo.
No requiere instalaciones adicionales (solo Python estándar).
"""
from __future__ import annotations

import csv
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parent
SALIDA = BASE / 'finrisk_perfilamiento'
SALIDA.mkdir(exist_ok=True)

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31-1)

TERMINOS_CLAVE = (
    'total de activos', 'activos corrientes', 'activo corriente',
    'total de pasivos', 'pasivos corrientes', 'pasivo corriente',
    'total de patrimonio', 'patrimonio total', 'patrimonio',
    'ingresos de actividades ordinarias', 'ingresos ordinarios',
    'ganancia bruta', 'resultado bruto', 'ganancia (perdida)',
    'resultado del periodo', 'resultado del ejercicio',
    'ganancia neta', 'utilidad neta', 'perdida neta',
)


def escribir_csv(nombre, columnas, filas):
    destino = SALIDA / nombre
    with destino.open('w', encoding='utf-8-sig', newline='') as fh:
        w = csv.writer(fh, delimiter=';')
        w.writerow(columnas)
        for fila in filas:
            w.writerow(fila)
    print('  Creado:', destino)


def nit_normalizado(cadena):
    cadena = (cadena or '').strip().strip('"').strip("'")
    m = re.fullmatch(r'([\d.\s,]+)\s*-\s*(\d)', cadena)
    if m:
        cadena = m.group(1)
    return re.sub(r'\D', '', cadena)


def normalizar_texto(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'\s+', ' ', s.lower()).strip()


def extraer_anio(s):
    m = re.search(r'(?<!\d)(20\d{2}|19\d{2})(?!\d)', s or '')
    return int(m.group(1)) if m else None


def clase_periodo(raw):
    p = normalizar_texto(raw)
    anio = extraer_anio(p)
    if p in ('periodo actual', 'periodo corriente'):
        return 'ETIQUETA_ACTUAL', None
    if p in ('periodo anterior', 'periodo comparativo'):
        return 'ETIQUETA_ANTERIOR', None
    if re.fullmatch(r'(19|20)\d{2}', p):
        return 'ANIO', anio
    if re.search(r'(ene|jan|enero)[-_\s./]*0?1|0?1[-/ ]0?1', p):
        return 'FECHA_APERTURA_POSIBLE', anio
    if re.search(r'dic|dec|diciembre|12[-/ ]31|31[-/ ]12', p):
        return 'FECHA_CIERRE_POSIBLE', anio
    if anio:
        return 'OTRA_FECHA_CON_ANIO', anio
    return 'OTRO', None


def archivos_financieros():
    estados = sorted(p for p in BASE.glob('*.csv')
                     if p.name.lower().startswith('estados_financieros_')
                     and 'muestra' not in p.name.lower())
    er = [p for p in estados if 'resultado' in normalizar_texto(p.name)]
    esf = [p for p in estados if 'situacion' in normalizar_texto(p.name)]
    if len(er) != 1 or len(esf) != 1:
        raise FileNotFoundError(
            'Se esperaba 1 CSV del Estado de Resultado Integral y 1 CSV del '
            'Estado de Situación Financiera en la misma carpeta que este programa. '
            f'Archivos reconocidos: {[p.name for p in estados]}')
    return [('RESULTADOS', er[0]), ('SITUACION', esf[0])]


def archivo_coincidencias():
    posibilidades = [BASE / 'finrisk_validacion' / 'coincidencias_nit.csv',
                     BASE / 'coincidencias_nit.csv']
    for ruta in posibilidades:
        if ruta.exists():
            return ruta
    raise FileNotFoundError('No encuentro coincidencias_nit.csv. Copialo junto '
                            'al programa o dejalo en la carpeta finrisk_validacion.')


def elegir_casos():
    """3 casos por año reciente, con corte en 1-3 años anteriores (hasta 12 NIT)."""
    candidatos = defaultdict(list)
    with archivo_coincidencias().open(encoding='utf-8-sig', newline='') as fh:
        lector = csv.DictReader(fh, delimiter=';')
        for r in lector:
            if r.get('hay_corte_en_3_anios_previos') != 'SI':
                continue
            nit = nit_normalizado(r.get('NIT', ''))
            try:
                anio = int(r['anio_apertura_preliminar'])
            except (ValueError, KeyError):
                continue
            if 2023 <= anio <= 2026 and nit:
                candidatos[anio].append((nit, anio, r.get('tipos_proceso','')))
    elegidos = {}
    for anio in (2023, 2024, 2025, 2026):
        for nit, a, tipo in sorted(candidatos[anio])[:3]:
            elegidos[nit] = (a, tipo)
    if not elegidos:
        raise RuntimeError('No se encontraron casos recientes con estados previos '
                           'en el archivo de coincidencias.')
    escribir_csv('casos_seleccionados.csv',
                 ['NIT','anio_apertura_preliminar','tipo_proceso'],
                 [(nit, a, proceso) for nit,(a,proceso) in sorted(elegidos.items())])
    return elegidos


def perfilar_archivo(fuente, ruta, casos, escritor_muestras):
    catalogo = Counter()
    periodos = Counter()
    formatos = Counter()
    muestra_nit = Counter()
    anomalias = Counter()
    print(f'\nLeyendo {fuente}: {ruta.name} ({ruta.stat().st_size / 1024**3:.2f} GiB)')
    with ruta.open('r', encoding='utf-8-sig', errors='replace', newline='') as fh:
        reader = csv.reader(fh, delimiter=',', quotechar='"')
        encabezado = [h.strip().upper() for h in next(reader)]
        requeridos = ('NIT', 'FECHA_CORTE', 'CONCEPTO', 'PERIODO', 'VALOR')
        faltan = set(requeridos) - set(encabezado)
        if faltan:
            raise ValueError(f'{ruta.name}: faltan {sorted(faltan)}. Cabecera: {encabezado}')
        col = {nombre:encabezado.index(nombre) for nombre in requeridos}
        idx_max = max(col.values())
        for numero, fila in enumerate(reader, start=1):
            if len(fila) <= idx_max:
                anomalias['filas_incompletas'] += 1
                continue
            concepto = fila[col['CONCEPTO']].strip()
            periodo_raw = fila[col['PERIODO']].strip()
            anio_corte = extraer_anio(fila[col['FECHA_CORTE']])
            clase, anio_periodo = clase_periodo(periodo_raw)
            catalogo[concepto] += 1
            formatos[clase] += 1
            periodos[(anio_corte, clase, anio_periodo)] += 1
            anomalias['filas_leidas'] += 1
            nit = nit_normalizado(fila[col['NIT']])
            if nit in casos and muestra_nit[nit] < 100:
                anio_evento, tipo = casos[nit]
                # La muestra debe estar antes de la apertura; todavía es preliminar.
                if anio_corte is not None and 2015 <= anio_corte < anio_evento:
                    escritor_muestras.writerow([
                        fuente, nit, anio_evento, tipo,
                        fila[col['FECHA_CORTE']], anio_corte,
                        periodo_raw, clase, anio_periodo,
                        concepto, fila[col['VALOR']],
                    ])
                    muestra_nit[nit] += 1
            if numero % 2_000_000 == 0:
                print(f'  {numero:,} filas revisadas...', flush=True)
    return catalogo, periodos, formatos, anomalias, muestra_nit


def main():
    print('FINRISK COLOMBIA | Perfilamiento contable | Etapa 3')
    print('Ruta de trabajo:', BASE)
    casos = elegir_casos()
    print(f'Casos seleccionados para revisar: {len(casos)} NIT.')
    resultados = {}
    archivo_muestras = SALIDA / 'muestra_conceptos_por_empresa.csv'
    with archivo_muestras.open('w', encoding='utf-8-sig', newline='') as fh:
        muestras = csv.writer(fh, delimiter=';')
        muestras.writerow(['fuente','NIT','anio_apertura_preliminar','tipo_proceso',
                           'fecha_corte_raw','anio_corte','periodo_raw',
                           'clasificacion_periodo','anio_periodo','concepto','valor_raw'])
        for fuente, ruta in archivos_financieros():
            resultados[fuente] = perfilar_archivo(fuente, ruta, casos, muestras)
    print('\nExportando resultados...')
    catalogo = []
    seleccion = []
    periodos = []
    formatos = []
    auditoria = []
    for fuente, (conceptos, cuentas_periodos, tipos, estado, muestras) in resultados.items():
        for concepto, cantidad in conceptos.most_common():
            texto = normalizar_texto(concepto)
            es_candidato = any(t in texto for t in TERMINOS_CLAVE)
            fila = (fuente, concepto, cantidad, 'SI' if es_candidato else 'NO')
            catalogo.append(fila)
            if es_candidato:
                seleccion.append(fila)
        for (anio_corte, categoria, anio_periodo), cantidad in sorted(
                cuentas_periodos.items(), key=lambda x:(x[0][0] or 0,x[0][1],x[0][2] or 0)):
            periodos.append((fuente, anio_corte or '', categoria, anio_periodo or '', cantidad))
        formatos.extend((fuente, tipo, numero) for tipo, numero in tipos.most_common())
        auditoria.extend((fuente, nombre, cantidad) for nombre,cantidad in sorted(estado.items()))
        auditoria.extend((fuente, 'filas_muestra_'+nit, count) for nit,count in muestras.items())
    escribir_csv('catalogo_conceptos.csv',
                 ['fuente','concepto_raw','numero_filas','posible_indicador'], catalogo)
    escribir_csv('conceptos_clave.csv',
                 ['fuente','concepto_raw','numero_filas','posible_indicador'], seleccion)
    escribir_csv('distribucion_periodos.csv',
                 ['fuente','anio_fecha_corte','tipo_periodo','anio_valor_periodo','numero_filas'],periodos)
    escribir_csv('tipos_periodo.csv',
                 ['fuente','tipo_periodo','numero_filas'], formatos)
    escribir_csv('auditoria_perfilamiento.csv',
                 ['fuente','indicador','valor'], auditoria)
    (SALIDA / 'LEEME.txt').write_text(
        'FINRISK etapa 3: revision de conceptos y fechas contables.\n'
        'IMPORTANTE: Los resultados NO son indicadores finales ni etiquetas de insolvencia.\n'
        'Revisar concepto contable, escala/unidades, taxonomias y periodos.\n'
        'FECHA_CORTE identifica el reporte; PERIODO identifica el importe y puede ser comparativo.\n'
        'Por tanto NO sumar registros ni calcular ratios todavia.\n'
        'Comparte con ChatGPT los archivos: conceptos_clave.csv, tipos_periodo.csv,\n'
        'distribucion_periodos.csv y muestra_conceptos_por_empresa.csv.\n',
        encoding='utf-8'
    )
    print('\nFINALIZADO. La carpeta esta en:', SALIDA)
    print('Comparte: conceptos_clave.csv, tipos_periodo.csv, distribucion_periodos.csv')
    print('y muestra_conceptos_por_empresa.csv')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nERROR:', type(exc).__name__, str(exc))
        input('Presiona Enter para cerrar...')
        raise
