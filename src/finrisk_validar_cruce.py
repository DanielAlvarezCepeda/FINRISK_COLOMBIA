# -*- coding: utf-8 -*-
"""FINRISK Colombia - validacion inicial de cruces NIT entre archivos publicos.

Uso:
    py finrisk_validar_cruce.py

Ubique este programa en la carpeta que contiene los CSV originales.
No requiere instalar bibliotecas; procesa los archivos grandes fila a fila.
Los resultados son diagnosticos, NO etiquetas definitivas de insolvencia.
"""
from __future__ import annotations

import csv
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

CARPETA = Path(__file__).resolve().parent
SALIDA = CARPETA / 'finrisk_validacion'
SALIDA.mkdir(exist_ok=True)

try:
    csv.field_size_limit(sys.maxsize)
except OverflowError:
    csv.field_size_limit(2**31 - 1)


def estandarizar_nit(valor):
    """Quita separadores de miles y, solo si esta explicito con guion, el DV."""
    t = str(valor or '').strip().strip('"').strip("'")
    sin_dv = re.fullmatch(r'([\d\.\,\s]+)\s*-\s*(\d)', t)
    if sin_dv:
        t = sin_dv.group(1)
    return re.sub(r'\D', '', t)


def anio_valido(valor):
    m = re.search(r'(?<!\d)(19\d{2}|20\d{2})(?!\d)', str(valor or ''))
    if not m:
        return None
    anio = int(m.group(1))
    return anio if 1990 <= anio <= datetime.now().year else None


def leer_csv(ruta, separador, codificacion):
    archivo = open(ruta, 'r', encoding=codificacion, newline='', errors='replace')
    lector = csv.reader(archivo, delimiter=separador, quotechar='"')
    return archivo, lector


def exportar_csv(nombre, encabezados, filas):
    destino = SALIDA / nombre
    with destino.open('w', newline='', encoding='utf-8-sig') as f:
        escritor = csv.writer(f, delimiter=';')
        escritor.writerow(encabezados)
        escritor.writerows(filas)
    print('Creado:', destino.name)


def buscar_archivos():
    todos = list(CARPETA.glob('*.csv'))
    fin = sorted([p for p in todos if p.name.lower().startswith('estados_financieros_')
                  and '_muestra' not in p.name.lower()])
    insol = sorted([p for p in todos if 'base-soporte-insolvencia' in p.name.lower()
                    and '_muestra' not in p.name.lower()])
    octubres = [p for p in insol if 'OCTUBRE' in p.name.upper() and '2026' in p.name]
    preferida = octubres[-1] if octubres else (insol[-1] if insol else None)
    if len(fin) < 2 or preferida is None:
        raise FileNotFoundError(
            'Necesitas las 2 bases de estados financieros y al menos 1 base de insolvencia '
            'original (no las muestras), en la misma carpeta que el programa.')
    return fin, preferida, len(insol)


def cargar_insolvencia(ruta):
    """Se consideran los registros del corte mas completo, sin duplicar cortes mensuales."""
    por_nit = defaultdict(list)
    nit_longitudes = Counter()
    cont = Counter()
    with open(ruta, encoding='cp1252', newline='', errors='replace') as f:
        reader = csv.DictReader(f, delimiter=';')
        for registro in reader:
            reg = {str(k or '').strip().upper(): str(v or '').strip()
                   for k, v in registro.items()}
            nit = estandarizar_nit(reg.get('NIT', ''))
            if not nit:
                cont['sin_nit'] += 1
                continue
            nit_longitudes[len(nit)] += 1
            fecha = (reg.get('FECHA AUTO ADMISION') or reg.get('FECHA_AUTO_ADMISION') or '')
            anio_fecha = anio_valido(fecha)
            anio_campo = anio_valido(reg.get('AÑO_DE_APERTURA_CELEBRACION', ''))
            anio_apertura = anio_fecha or anio_campo
            if fecha:
                cont['con_texto_fecha_auto'] += 1
            if anio_fecha:
                cont['anio_de_auto_reconocible'] += 1
            if anio_campo:
                cont['anio_de_apertura_reconocible'] += 1
            if anio_apertura:
                cont['con_anio_apertura'] += 1
            cont['registros'] += 1
            por_nit[nit].append({
                'nombre': reg.get('NOMBRE', ''),
                'proceso': reg.get('PROCESO', ''),
                'anio_apertura': anio_apertura,
                'fecha_auto': fecha,
            })
    return por_nit, nit_longitudes, cont


def examinar_financiero(ruta, nits_insol):
    """Streaming; guarda las fechas de corte SOLO para NIT encontrados en insolvencia."""
    nit_unicos = set()
    nits_relacionados = defaultdict(set)
    conteo_anios = Counter()
    conteo_periodo = Counter()
    conteo = Counter()
    with open(ruta, encoding='utf-8-sig', newline='', errors='replace') as f:
        lector = csv.reader(f, delimiter=',', quotechar='"')
        cabecera = next(lector)
        cabecera = [h.strip().upper().lstrip('\ufeff') for h in cabecera]
        requeridos = {'NIT', 'FECHA_CORTE', 'PERIODO'}
        faltantes = requeridos - set(cabecera)
        if faltantes:
            raise ValueError(f'En {ruta.name} faltan las columnas: {faltantes}. '
                             f'Columnas detectadas: {cabecera[:15]}')
        i_nit, i_fecha, i_periodo = (cabecera.index(k) for k in ('NIT', 'FECHA_CORTE', 'PERIODO'))
        mayor = max(i_nit, i_fecha, i_periodo)
        for n, fila in enumerate(lector, 1):
            if len(fila) <= mayor:
                conteo['filas_incompletas'] += 1
                continue
            nit = estandarizar_nit(fila[i_nit])
            if not nit:
                conteo['filas_sin_nit'] += 1
                continue
            nit_unicos.add(nit)
            ano = anio_valido(fila[i_fecha])
            if ano:
                conteo_anios[ano] += 1
            valor_periodo = fila[i_periodo].strip()
            if valor_periodo:
                conteo_periodo[valor_periodo] += 1
            if nit in nits_insol:
                conteo['filas_coincidentes'] += 1
                if ano:
                    nits_relacionados[nit].add(ano)
            conteo['filas_validas'] += 1
            if n % 1_000_000 == 0:
                print(f'  {ruta.name[:46]}: {n:,} filas examinadas...', flush=True)
    return nit_unicos, nits_relacionados, conteo, conteo_anios, conteo_periodo


def main():
    print('FINRISK | validacion preliminar de viabilidad (sin pandas)')
    print('Carpeta de trabajo:', CARPETA)
    finanzas, archivo_ins, numero_cortes = buscar_archivos()
    print('Corte de insolvencia seleccionado:', archivo_ins.name)
    insol, longitudes, c_insol = cargar_insolvencia(archivo_ins)
    print('NIT distintos en corte:', f'{len(insol):,}')
    print('Advertencia: otros cortes mensuales son fotografias repetidas del universo de procesos.')
    info_fin = {}
    for ruta in finanzas:
        print('\nLeyendo:', ruta.name, '(', round(ruta.stat().st_size / 1024**3, 2), 'GiB )')
        result = examinar_financiero(ruta, set(insol))
        info_fin[ruta.name] = result
        print('  NIT unicos:', f'{len(result[0]):,}')
        print('  NIT que coinciden con insolvencia:', f'{len(result[1]):,}')

    sets = [r[0] for r in info_fin.values()]
    comun_finanzas = set.intersection(*sets)
    cruce_completo = comun_finanzas & set(insol)
    print('\nNIT presentes en ambos estados financieros:', f'{len(comun_finanzas):,}')
    print('NIT presentes en ambos estados e insolvencia:', f'{len(cruce_completo):,}')

    filas_coincidencias = []
    por_fecha = Counter()
    con_fin_antes = 0
    con_fin_3_anos = 0
    sin_anio_evento = 0
    for nit in sorted(cruce_completo):
        eventos = insol[nit]
        anios_ins = [e['anio_apertura'] for e in eventos if e['anio_apertura']]
        anio_evento = min(anios_ins) if anios_ins else None
        # Solo rango para diagnostico. Las filas comparativas requieren depuracion posterior.
        anios_fin = set()
        for _, datos in info_fin.items():
            anios_fin.update(datos[1].get(nit, set()))
        anterior = bool(anio_evento and any(y < anio_evento for y in anios_fin))
        anterior_3 = bool(anio_evento and any(anio_evento - 3 <= y < anio_evento for y in anios_fin))
        if anterior:
            con_fin_antes += 1
        if anterior_3:
            con_fin_3_anos += 1
        if not anio_evento:
            sin_anio_evento += 1
        if anio_evento:
            por_fecha[anio_evento] += 1
        filas_coincidencias.append([
            nit, eventos[0]['nombre'], len(eventos),
            ' | '.join(sorted(set(e['proceso'] for e in eventos))),
            anio_evento or '', min(anios_fin) if anios_fin else '',
            max(anios_fin) if anios_fin else '',
            ' | '.join(map(str, sorted(anios_fin))),
            'SI' if anterior else 'NO', 'SI' if anterior_3 else 'NO',
            ' | '.join(sorted(set(e['fecha_auto'] for e in eventos if e['fecha_auto'])))[:160]
        ])

    resumen = [
        ('Archivos financieros analizados', len(finanzas)),
        ('Archivos mensuales insolvencia en carpeta (NO acumulados)', numero_cortes),
        ('Archivo insolvencia usado', archivo_ins.name),
        ('Registros en insolvencia corte seleccionado', c_insol['registros']),
        ('NIT unicos en insolvencia corte', len(insol)),
        ('Registros con fecha auto admision textual', c_insol['con_texto_fecha_auto']),
        ('Registros con ano auto admision identificable', c_insol['anio_de_auto_reconocible']),
        ('Registros con ano apertura/celebracion identificable', c_insol['anio_de_apertura_reconocible']),
        ('NIT unicos en ambos archivos financieros', len(comun_finanzas)),
        ('NIT insolvencia presentes en ambos estados financieros', len(cruce_completo)),
        ('Cruces con algun estado financiero de FECHA_CORTE previa al ano apertura (preliminar)', con_fin_antes),
        ('Cruces con FECHA_CORTE 1-3 anos antes del ano apertura (preliminar)', con_fin_3_anos),
        ('Cruces sin ano de apertura identificable', sin_anio_evento),
    ]
    for nombre, (_, _, cont, _, _) in info_fin.items():
        resumen += [(nombre + ' - filas validas', cont['filas_validas']),
                    (nombre + ' - filas incompletas', cont['filas_incompletas']),
                    (nombre + ' - NIT unicos', len(info_fin[nombre][0])),
                    (nombre + ' - NIT coincidentes insolvencia', len(info_fin[nombre][1]))]
    exportar_csv('resumen_cruce.csv', ['indicador', 'valor'], resumen)
    exportar_csv('coincidencias_nit.csv', [
        'NIT', 'nombre_insolvencia', 'registros_de_proceso_en_corte',
        'tipos_proceso', 'anio_apertura_preliminar', 'primer_anio_corte_financiero',
        'ultimo_anio_corte_financiero', 'anios_corte_financiero',
        'hay_corte_previo', 'hay_corte_en_3_anios_previos', 'fecha_auto_admision_raw',
    ], filas_coincidencias)
    exportar_csv('longitudes_nit_insolvencia.csv', ['cantidad_digitos_nit', 'numero_registros'], sorted(longitudes.items()))
    filas_anios = []
    for nombre, (_, _, _, por_anio, _) in info_fin.items():
        filas_anios.extend((nombre, y, c) for y, c in sorted(por_anio.items()))
    exportar_csv('registros_por_anio_corte.csv', ['archivo', 'anio_fecha_corte', 'numero_filas'], filas_anios)
    periodo_filas = []
    for nombre, (_, _, _, _, por_periodo) in info_fin.items():
        periodo_filas.extend((nombre, v, c) for v, c in por_periodo.most_common(60))
    exportar_csv('principales_formatos_periodo.csv', ['archivo', 'valor_periodo', 'numero_filas'], periodo_filas)
    exportar_csv('anio_apertura_nits_cruzados.csv', ['anio_apertura_preliminar', 'numero_nits'], sorted(por_fecha.items()))
    (SALIDA / 'LEEME.txt').write_text(
        'FINRISK: Resultados preliminares de integracion por NIT.\n'
        'ATENCION: NO son etiquetas definitivas ni un dataset listo para entrenar.\n'
        'A) FECHA_CORTE es la fecha del reporte; la columna PERIODO puede referirse a un ejercicio anterior.\n'
        'B) Anio de apertura/celebracion no equivale necesariamente a fecha del auto de admision.\n'
        'C) Los 9 cortes mensuales no son 9 grupos independientes de nuevas insolvencias.\n'
        'D) La coincidencia entre bases no valida si los registros corresponden a sociedades comparables.\n'
        'E) Se deben depurar reportes duplicados, taxonomias NIIF y periodos comparativos.\n'
        'F) El cero (no insolvente) solo se puede definir con un seguimiento y cobertura validos.\n'
        'Comparte resumen_cruce.csv, registros_por_anio_corte.csv y los primeros registros de\n'
        'coincidencias_nit.csv para decidir si conviene modelar insolvencia o deterioro financiero.\n',
        encoding='utf-8'
    )
    print('\nLISTO. Resultados en:', SALIDA)
    print('Comparte: resumen_cruce.csv, registros_por_anio_corte.csv y coincidencias_nit.csv')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('\nERROR:', exc)
        input('Presiona Enter para cerrar...')
        raise
