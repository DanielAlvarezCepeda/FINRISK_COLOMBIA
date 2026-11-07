#!/usr/bin/env python3
"""Adquisicion publica FINRISK por conceptos y periodos actuales, sin agregar importes.

Las fuentes se consultan con SoQL, dos trabajadores maximo, paginas de 50.000.
Los archivos CSV.gz conservan las 11 columnas publicas y el identificador Socrata.
El control de metadatos detecta cambios durante la descarga, pero no constituye
una instantanea historica ni prueba disponibilidad de los estados en el pasado.
"""
from __future__ import annotations
import argparse, concurrent.futures, csv, gzip, hashlib, importlib.util, io, json
import os, threading, time, urllib.error, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

CODIGO_ROOT = Path(__file__).resolve().parents[1]
CONFIGS = CODIGO_ROOT / 'configs' / 'entrega2'
ROOT = CODIGO_ROOT
REPORTS = ROOT / 'reports' / 'preparacion'
RAW = ROOT / 'data' / 'raw' / 'financieros'
MANIFEST_PATH = REPORTS / 'adquisicion_financieros.json'
FIELDS = ['codigo_instancia', 'nit', 'numero_radicado', 'id_punto_entrada',
          'punto_entrada', 'id_taxonomia', 'taxonomia', 'fecha_corte',
          'concepto', 'periodo', 'valor']
COLUMNS = [x.upper() for x in FIELDS] + ['SOCRATA_ID']
SOURCES = [('situacion', 'pfdp-zks5'), ('resultados', 'prwj-nzxa')]
LOCK = threading.RLock()
STATE = {}
SPEC = importlib.util.spec_from_file_location('consolidador_original', CODIGO_ROOT/'src'/'finrisk_etapa4_consolidar.py')
ORIGINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ORIGINAL)


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda:f.read(2**20), b''):
            h.update(part)
    return h.hexdigest()


def stable_hash(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':')).encode()).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    os.replace(temporary, path)


def save_state():
    with LOCK:
        STATE['actualizado_utc'] = now()
        write_json(MANIFEST_PATH, STATE)


def get_json(url, timeout=180):
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent':'FINRISK-academic-data-acquisition/1.0',
                                                       'Accept-Encoding':'gzip'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                if response.headers.get('Content-Encoding') == 'gzip':
                    raw = gzip.decompress(raw)
                result = json.loads(raw.decode('utf-8-sig'))
            time.sleep(0.15)
            return result
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            if isinstance(exc, urllib.error.HTTPError) and exc.code not in (429,500,502,503,504):
                raise
            if attempt == 4:
                raise
            time.sleep(min(2**attempt*2, 30))


def metadata(dataset):
    value = get_json(f'https://www.datos.gov.co/api/views/{dataset}.json')
    result = {'dataset':dataset, 'nombre':value.get('name'),
              'rowsUpdatedAt':value.get('rowsUpdatedAt'),
              'viewLastModified':value.get('viewLastModified'),
              'columns':[{'fieldName':x['fieldName'],'dataTypeName':x.get('dataTypeName')}
                         for x in value['columns']]}
    if [x['fieldName'] for x in result['columns']] != FIELDS:
        raise ValueError(f'Esquema inesperado en {dataset}')
    return result


def literal(text):
    return "'"+str(text).replace("'", "''")+"'"


def endpoint(dataset, params):
    return f'https://www.datos.gov.co/resource/{dataset}.json?'+urllib.parse.urlencode(params)


def query(dataset, **params):
    url = endpoint(dataset, {'$'+k:v for k,v in params.items()})
    value = get_json(url)
    if not isinstance(value,list):
        raise ValueError(f'Respuesta inesperada en {dataset}: {str(value)[:150]}')
    return value, url


def profile(name, dataset):
    meta = metadata(dataset)
    catalog_path = CONFIGS/f'catalogo_{name}.json'
    catalog = json.loads(catalog_path.read_text(encoding='utf-8-sig'))
    concepts = [x['concepto'] for x in catalog['conceptos']]
    if not concepts or any(ORIGINAL.clasificar_concepto(x, name.upper()) is None for x in concepts):
        raise ValueError('El catalogo no corresponde a las reglas originales')
    where = ("fecha_corte >= '2019-01-01T00:00:00' and fecha_corte < '2025-01-01T00:00:00'"
             + ' and concepto in ('+','.join(map(literal,concepts))+')')
    rows, url = query(dataset, select='date_extract_y(fecha_corte) as anio,periodo,count(*) as filas',
                      where=where, group='date_extract_y(fecha_corte),periodo', order='anio,periodo', limit=5000)
    if len(rows)>=5000:
        raise ValueError('Catalogo de periodos truncado')
    years = {}
    for year in range(2019,2025):
        periods = [x.get('periodo','') for x in rows if int(float(x['anio']))==year
                   and ORIGINAL.periodo_actual(x.get('periodo',''),year)]
        selected = sum(int(x['filas']) for x in rows if int(float(x['anio']))==year
                       and x.get('periodo','') in periods)
        years[str(year)] = {'periodos_actuales_literales':sorted(set(periods)), 'filas_esperadas':selected}
    result = {'consulta_utc':now(), 'metadatos_inicio':meta, 'metadatos_sha256':stable_hash(meta),
              'catalogo_sha256':sha(catalog_path),'conceptos':concepts,
              'url_catalogo_periodos':url,'catalogo_periodos':rows,'anios':years,
              'filas_actuales_esperadas':sum(x['filas_esperadas'] for x in years.values()),
              'advertencia':'No se consultan ni inventan fechas de disponibilidad historica. FECHA_CORTE no demuestra fecha de publicacion.'}
    write_json(REPORTS/f'perfiles_financieros_{name}.json', result)
    return result


def write_page(path, rows, year):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp = path.with_suffix(path.suffix+'.part')
    ids = set()
    with tmp.open('wb') as binary:
        with gzip.GzipFile(filename='',mode='wb',fileobj=binary,mtime=0,compresslevel=6) as zipped:
            with io.TextIOWrapper(zipped,encoding='utf-8',newline='') as text:
                writer = csv.writer(text)
                writer.writerow(COLUMNS)
                for row in rows:
                    ident = row.get('socrata_id','')
                    if not ident or ident in ids:
                        raise ValueError('Identificador Socrata vacio o repetido en pagina')
                    ids.add(ident)
                    if not ORIGINAL.periodo_actual(row.get('periodo',''),year):
                        raise ValueError('Se recupero un periodo no actual')
                    if not str(row.get('fecha_corte','')).startswith(str(year)):
                        raise ValueError('Se recupero un anio inesperado')
                    writer.writerow([row.get(x,'') for x in FIELDS]+[ident])
    os.replace(tmp,path)
    return {'filas':len(rows),'bytes_gzip':path.stat().st_size,'sha256':sha(path),
            'primer_socrata_id':rows[0]['socrata_id'],'ultimo_socrata_id':rows[-1]['socrata_id']}


def download_source(name, dataset, page_size, only_profile):
    prof = profile(name,dataset)
    print(json.dumps({'fuente':name,'fase':'perfil','filas_actuales':prof['filas_actuales_esperadas']},ensure_ascii=True),flush=True)
    with LOCK:
        source = STATE['fuentes'].setdefault(name,{})
        fingerprint = {'metadatos_sha256':prof['metadatos_sha256'],'catalogo_sha256':prof['catalogo_sha256'],
                       'page_size':page_size,'columns':COLUMNS}
        if source.get('huella') and source['huella'] != fingerprint:
            raise ValueError(f'Fuente {name} cambio o configuracion distinta, use --raiz con una carpeta de extracción nueva')
        source.update({'dataset':dataset,'huella':fingerprint,'metadatos_inicio':prof['metadatos_inicio'],
                       'filas_esperadas':prof['filas_actuales_esperadas'],'estado':'perfilado' if only_profile else 'descargando'})
        source.setdefault('archivos',{})
        save_state()
    if only_profile:
        return
    for year_text, info in prof['anios'].items():
        year = int(year_text)
        expected = info['filas_esperadas']
        if not expected:
            continue
        clause = (f"fecha_corte >= '{year}-01-01T00:00:00' and fecha_corte < '{year+1}-01-01T00:00:00'"
                  +' and concepto in ('+','.join(map(literal,prof['conceptos']))+')'
                  +' and periodo in ('+','.join(map(literal,info['periodos_actuales_literales']))+')')
        # Offset paginado sobre :id estable. Se comprueba que la fuente no cambie.
        for offset in range(0,expected,page_size):
            page = offset//page_size
            rel = Path('data/raw/financieros')/name/f'{year}_{page:03d}.csv.gz'
            file = ROOT/rel
            key = rel.as_posix()
            with LOCK:
                previous = source['archivos'].get(key)
            page_expected = min(page_size,expected-offset)
            if previous and file.exists() and previous['filas']==page_expected and sha(file)==previous['sha256']:
                continue
            rows,url = query(dataset,select=','.join(FIELDS)+',:id as socrata_id',where=clause,
                             order=':id',limit=page_size,offset=offset)
            if len(rows)!=page_expected:
                raise ValueError(f'{name} {year} offset{offset}: esperadas{page_expected}, recibidas{len(rows)}')
            entry = write_page(file,rows,year)
            entry.update({'url':url,'anio':year,'offset':offset,'limit':page_size,'descargado_utc':now()})
            with LOCK:
                source['archivos'][key]=entry
                source['filas_descargadas']=sum(x['filas'] for x in source['archivos'].values())
                source['bytes_gzip']=sum(x['bytes_gzip'] for x in source['archivos'].values())
                save_state()
                total = sum(s.get('bytes_gzip',0) for s in STATE['fuentes'].values())
            print(json.dumps({'fuente':name,'anio':year,'pagina':page,'filas_acumuladas':source['filas_descargadas'],
                              'MB_gzip_total':round(total/1e6,2)},ensure_ascii=True),flush=True)
            if total>500_000_000:
                raise ValueError('Alcanzado limite de 500MB comprimidos. Reanudar tras revisar volumen.')
    final_meta = metadata(dataset)
    if stable_hash(final_meta)!=prof['metadatos_sha256']:
        with LOCK:
            source['estado']='invalidar_fuente_cambio_durante_descarga'
            source['metadatos_fin']=final_meta
            save_state()
        raise ValueError('La fuente cambio durante la adquisicion, no usar esta descarga')
    if source.get('filas_descargadas') != source['filas_esperadas']:
        raise ValueError('Conteo total no coincide')
    with LOCK:
        source.update({'estado':'completo','metadatos_fin':final_meta,'finalizado_utc':now()})
        save_state()
    print(json.dumps({'fuente':name,'estado':'completo','filas':source['filas_descargadas']},ensure_ascii=True),flush=True)


def main():
    global ROOT, REPORTS, RAW, MANIFEST_PATH
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raiz', type=Path, default=CODIGO_ROOT,
                        help='Carpeta de extracción para data/ y reports/. Los catálogos se leen del repositorio.')
    parser.add_argument('--perfil',action='store_true')
    parser.add_argument('--pagina',type=int,default=50000)
    args=parser.parse_args()
    if not 1<=args.pagina<=50000:
        parser.error('pagina debe estar entre1 y50000')
    ROOT = args.raiz.expanduser().resolve()
    REPORTS = ROOT / 'reports' / 'preparacion'
    RAW = ROOT / 'data' / 'raw' / 'financieros'
    MANIFEST_PATH = REPORTS / 'adquisicion_financieros.json'
    STATE.clear()
    REPORTS.mkdir(parents=True,exist_ok=True)
    RAW.mkdir(parents=True,exist_ok=True)
    if MANIFEST_PATH.exists():
        STATE.update(json.loads(MANIFEST_PATH.read_text(encoding='utf-8')))
    else:
        STATE.update({'creado_utc':now(),'fuentes':{},'estado':'iniciado',
                      'columnas_csv':COLUMNS,'periodo':[2019,2024],
                      'transformacion':'Seleccion de filas originales. Sin SUM/MAX de valores financieros. Encabezados mayusculas y SOCRATA_ID agregado.',
                      'limite':'Metadatos estables durante adquisicion no equivalen a instantanea historica ni validacion de etiqueta.'})
    STATE['script_sha256']=sha(Path(__file__))
    save_state()
    errors=[]
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        futures={pool.submit(download_source,n,d,args.pagina,args.perfil):n for n,d in SOURCES}
        for future in concurrent.futures.as_completed(futures):
            try:future.result()
            except Exception as exc:
                name=futures[future]
                with LOCK:
                    STATE['fuentes'].setdefault(name,{})['error']=repr(exc)
                    save_state()
                errors.append((name,repr(exc)))
                print(json.dumps({'fuente':name,'error':repr(exc)}),flush=True)
    STATE['estado']='error' if errors else ('perfilado' if args.perfil else 'completo')
    STATE['finalizado_utc']=now()
    save_state()
    if errors:
        raise SystemExit(1)

if __name__=='__main__':
    main()
