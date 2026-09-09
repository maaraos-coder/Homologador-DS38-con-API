from pathlib import Path
import os
import re
import zipfile
import unicodedata
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point

BASE_DIR = Path(__file__).resolve().parent
ZIP_PATH = str(BASE_DIR / "data" / "IPTMetropolitana.zip")
TABLA_HOMOLOGACION_PATH = str(BASE_DIR / "rules" / "homologacion_prc.csv")
TABLA_PRMS_PATH = str(BASE_DIR / "rules" / "homologacion_prms.csv")
TABLA_PUENTE_ALTO_PATH = str(BASE_DIR / "rules" / "homologacion_puente_alto.csv")
PUENTE_ALTO_SHP_PATH = str(BASE_DIR / "data" / "PRC_Puente_Alto" / "IPT_13_PRC_Puente_Alto.shp")


def normalizar(texto):
    texto = str(texto).lower()
    texto = unicodedata.normalize('NFKD', texto)
    texto = ''.join([c for c in texto if not unicodedata.combining(c)])
    texto = texto.replace('ñ', 'n')
    texto = texto.replace('_', ' ')
    texto = texto.replace('-', ' ')
    texto = ' '.join(texto.split())
    return texto.strip()

def extraer_coordenadas_google_maps(texto):
    """
    Extrae coordenadas desde texto copiado de Google Maps.
    Soporta formatos como:
    - -33.4175459, -70.5727107
    - https://www.google.com/maps/@-33.4175459,-70.5727107,17z
    - q=-33.4175459,-70.5727107
    """
    if not texto:
        return (None, None)
    texto = str(texto).strip()
    texto = texto.replace('−', '-')
    texto = texto.replace('–', '-')
    texto = texto.replace(';', ',')
    texto = texto.replace('%2C', ',')
    texto = texto.replace('%2c', ',')
    numeros = re.findall('[-+]?\\d+(?:\\.\\d+)?', texto)
    if len(numeros) < 2:
        return (None, None)
    valores = []
    for n in numeros:
        try:
            valores.append(float(n))
        except Exception:
            pass
    for i in range(len(valores) - 1):
        lat = valores[i]
        lon = valores[i + 1]
        if -56 <= lat <= -18 and -76 <= lon <= -66:
            return (lat, lon)
    for i in range(len(valores) - 1):
        lat = valores[i]
        lon = valores[i + 1]
        if -90 <= lat <= 90 and -180 <= lon <= 180:
            return (lat, lon)
    return (None, None)

def texto_atributos(fila):
    valores = []
    for col in fila.index:
        if col == 'geometry':
            continue
        try:
            valores.append(str(fila.get(col, '')))
        except Exception:
            pass
    return normalizar(' '.join(valores))

def tiene_info_normativa(fila):
    zona = str(fila.get('ZONA', '')).strip()
    nombre = str(fila.get('NOMBRE', '')).strip()
    usos = str(fila.get('UPERM', '')).strip()
    if zona and zona.lower() != 'nan':
        return True
    if nombre and nombre.lower() != 'nan':
        return True
    if usos and usos.lower() != 'nan':
        return True
    return False

def crear_gdf_vacio():
    return gpd.GeoDataFrame({'COMUNA': [], 'ZONA': [], 'NOMBRE': [], 'UPERM': [], 'UPREF': [], 'UPROH': [], 'SUELO': [], 'DECRETO': [], 'PLANO': [], 'fuente_normativa': [], 'archivo_origen': [], 'observacion_jerarquia': []}, geometry=[], crs='EPSG:4326')

def cargar_tabla_homologacion():
    tablas = []

    try:
        base = pd.read_csv(TABLA_HOMOLOGACION_PATH)
        if not base.empty:
            if "comuna" in base.columns:
                base = base[
                    base["comuna"].apply(normalizar) != normalizar("Puente Alto")
                ].copy()
            tablas.append(base)
    except Exception:
        pass

    try:
        if os.path.exists(TABLA_PUENTE_ALTO_PATH):
            puente_alto = pd.read_csv(TABLA_PUENTE_ALTO_PATH)
            if not puente_alto.empty:
                tablas.append(puente_alto)
    except Exception:
        pass

    return pd.concat(tablas, ignore_index=True) if tablas else pd.DataFrame()

def cargar_tabla_prms():
    try:
        return pd.read_csv(TABLA_PRMS_PATH)
    except Exception:
        return pd.DataFrame()

def normalizar_codigo_zona(texto):
    texto = normalizar(texto)
    texto = texto.replace('zona', '')
    texto = texto.replace(' ', '')
    texto = texto.replace('-', '')
    texto = texto.replace('_', '')
    texto = texto.replace('.', '')
    return texto

def homologar_por_tabla_prc(comuna, zona_prc, nombre_zona):
    tabla = cargar_tabla_homologacion()
    if tabla.empty:
        return None
    tabla = tabla.copy()
    comuna_norm = normalizar(comuna)
    zona_norm = normalizar_codigo_zona(zona_prc)
    nombre_norm = normalizar(nombre_zona)
    tabla['comuna_norm'] = tabla['comuna'].apply(normalizar)
    tabla['zona_norm'] = tabla['zona_prc'].apply(normalizar_codigo_zona)
    tabla['nombre_norm'] = tabla['nombre_zona'].apply(normalizar)
    match = tabla[(tabla['comuna_norm'] == comuna_norm) & (tabla['zona_norm'] == zona_norm)]
    if not match.empty:
        return match.iloc[0].to_dict()
    match = tabla[(tabla['comuna_norm'] == comuna_norm) & (tabla['nombre_norm'] == nombre_norm)]
    if not match.empty:
        return match.iloc[0].to_dict()
    # No realizar respaldo por código de zona sin comuna.
    # Códigos como H1, H2, ZC, IM1, etc. pueden repetirse entre comunas
    # con significados normativos distintos. Si no existe coincidencia
    # por comuna + código o comuna + nombre, se retorna None para que
    # la homologación continúe mediante los atributos del IPT del punto.
    return None

def homologar_por_tabla_prms(zona_prms, nombre_zona):
    tabla = cargar_tabla_prms()
    if tabla.empty:
        return None
    tabla = tabla.copy()
    zona_norm = normalizar_codigo_zona(zona_prms)
    nombre_norm = normalizar(nombre_zona)
    tabla['zona_norm'] = tabla['zona_prms'].apply(normalizar_codigo_zona)
    tabla['nombre_norm'] = tabla['nombre_zona'].apply(normalizar)
    match = tabla[tabla['zona_norm'] == zona_norm]
    if not match.empty:
        return match.iloc[0].to_dict()
    match = tabla[tabla['nombre_norm'] == nombre_norm]
    if not match.empty:
        return match.iloc[0].to_dict()
    return None

def listar_shapefiles():
    with zipfile.ZipFile(ZIP_PATH, 'r') as z:
        archivos = z.namelist()
    return [a for a in archivos if a.endswith('.shp')]

def listar_shapefiles_prc():
    shps = listar_shapefiles()
    return [a for a in shps if '/PRC/' in a and 'Patrimonio' not in a and ('ZNE' not in a) and ('poligono' not in a.lower()) and ('_R.' not in a) and ('_R_' not in a)]

def buscar_capa_prms_lu():
    shps = listar_shapefiles()
    candidatos = [a for a in shps if '/PRMS/' in a and 'PRMS_LU' in a and a.endswith('.shp')]
    if candidatos:
        return candidatos[0]
    candidatos = [a for a in shps if '/PRMS/' in a and 'LU' in a and a.endswith('.shp')]
    return candidatos[0] if candidatos else None

def buscar_capa_prms_uso_suelo():
    shps = listar_shapefiles()
    candidatos = [a for a in shps if '/PRMS/' in a and 'USO_Suelo' in a and a.endswith('.shp')]
    if candidatos:
        return candidatos[0]
    candidatos = [a for a in shps if '/PRMS/' in a and 'Uso' in a and a.endswith('.shp')]
    return candidatos[0] if candidatos else None

def crear_indice_comunas():
    indice = {}
    for shp in listar_shapefiles():
        nombre_archivo = shp.split('/')[-1]
        if not shp.endswith('.shp'):
            continue
        if 'Patrimonio' in shp:
            continue
        if 'ZNE' in shp:
            continue
        if 'poligono' in shp.lower():
            continue
        if '/PRC/' not in shp and '/PRI/' not in shp and ('PNSECC' not in shp):
            continue
        comuna = nombre_archivo
        reemplazos = ['IPT_13_PRC_', 'IPT_13_PRI_', 'IPT_13_PNSECC_', '.shp']
        for r in reemplazos:
            comuna = comuna.replace(r, '')
        comuna = comuna.replace('_', ' ')
        comuna = comuna.strip()
        especiales = {'Nunoa AP': 'Ñuñoa', 'Pudahuel San Francisco': 'Pudahuel'}
        if comuna in especiales:
            comuna = especiales[comuna]
        basura = [' AP', ' Rural', ' Urbano']
        for b in basura:
            if comuna.endswith(b):
                comuna = comuna.replace(b, '').strip()
        clave = normalizar(comuna)
        if clave not in indice:
            indice[clave] = {'nombre': comuna, 'archivo': shp}
    faltantes = {'alhue': 'Alhué', 'buin': 'Buin', 'calera de tango': 'Calera de Tango', 'el monte': 'El Monte', 'lampa': 'Lampa', 'maria pinto': 'María Pinto', 'san jose de maipo': 'San José de Maipo', 'san pedro': 'San Pedro', 'tiltil': 'Tiltil'}
    for clave, nombre in faltantes.items():
        if clave not in indice:
            indice[clave] = {'nombre': nombre, 'archivo': None}

    if os.path.exists(PUENTE_ALTO_SHP_PATH):
        indice[normalizar("Puente Alto")] = {
            'nombre': 'Puente Alto',
            'archivo': '__LOCAL_PUENTE_ALTO__'
        }

    return indice

def _reparar_texto_mojibake(valor):
    if not isinstance(valor, str):
        return valor
    if 'Ã' not in valor and 'Â' not in valor:
        return valor
    try:
        return valor.encode('latin1').decode('utf-8')
    except Exception:
        return valor


def cargar_shp(shp):
    if not shp:
        return crear_gdf_vacio()

    if shp == '__LOCAL_PUENTE_ALTO__':
        if not os.path.exists(PUENTE_ALTO_SHP_PATH):
            return crear_gdf_vacio()

        gdf = gpd.read_file(PUENTE_ALTO_SHP_PATH)

        if gdf.crs is None:
            raise ValueError('El shapefile local de Puente Alto no tiene CRS definido.')

        gdf = gdf.to_crs(epsg=4326)

        for col in ['COMUNA', 'SECTOR', 'ZONA', 'NOMBRE', 'UPREF', 'UPERM', 'UPROH']:
            if col in gdf.columns:
                gdf[col] = gdf[col].apply(_reparar_texto_mojibake)

        gdf['archivo_origen'] = PUENTE_ALTO_SHP_PATH
        gdf['fuente_normativa'] = 'PRC'
        return gdf

    ruta = f'zip://{ZIP_PATH}!{shp}'
    gdf = gpd.read_file(ruta)
    gdf = gdf.to_crs(epsg=4326)
    gdf['archivo_origen'] = shp
    return gdf

def normalizar_columnas(gdf):
    if gdf.empty:
        return crear_gdf_vacio()
    renombres = {'COM': 'COMUNA', 'NOM': 'NOMBRE', 'NOMBRE_ZON': 'NOMBRE', 'NOM_ZONA': 'NOMBRE', 'N_DOC': 'DECRETO', 'P_DO': 'PLANO', 'COD_ZONA': 'ZONA', 'ZONIF': 'ZONA', 'USO': 'UPERM', 'USO_SUELO': 'UPERM', 'DESTINO': 'UPERM', 'NOM_USO': 'NOMBRE', 'TIPO': 'NOMBRE', 'CLASE': 'NOMBRE'}
    gdf = gdf.rename(columns=renombres)
    columnas_necesarias = ['COMUNA', 'ZONA', 'NOMBRE', 'UPERM', 'UPREF', 'UPROH', 'SUELO', 'DECRETO', 'PLANO', 'fuente_normativa', 'archivo_origen', 'observacion_jerarquia']
    for col in columnas_necesarias:
        if col not in gdf.columns:
            gdf[col] = ''
    return gdf

def filtrar_por_comuna(gdf, nombre_comuna):
    if gdf.empty or 'COMUNA' not in gdf.columns:
        return crear_gdf_vacio()
    comuna_norm = normalizar(nombre_comuna)
    gdf_filtrado = gdf[gdf['COMUNA'].apply(normalizar) == comuna_norm].copy()
    if gdf_filtrado.empty:
        return crear_gdf_vacio()
    return gdf_filtrado

def detectar_comuna_por_punto(lat, lon, indice, gdf_prms_uso_total=None):
    """
    Detecta automáticamente la comuna del punto.
    Prioridad:
    1) Capa PRMS_USO_Suelo total, si tiene campo COMUNA.
    2) Revisión espacial contra los PRC/PRI disponibles en el índice.
    Devuelve la clave normalizada de la comuna o None.
    """
    try:
        punto = gpd.GeoDataFrame({'id': [1]}, geometry=[Point(lon, lat)], crs='EPSG:4326')
        if gdf_prms_uso_total is not None and (not gdf_prms_uso_total.empty):
            try:
                resultado = gpd.sjoin(punto, gdf_prms_uso_total, how='left', predicate='intersects')
                if not resultado.empty and (not pd.isna(resultado.iloc[0].get('index_right'))):
                    comuna_detectada = str(resultado.iloc[0].get('COMUNA', '')).strip()
                    clave = normalizar(comuna_detectada)
                    if clave in indice:
                        return clave
            except Exception:
                pass
        for clave, info in indice.items():
            try:
                archivo = info.get('archivo')
                if not archivo:
                    continue
                gdf = cargar_shp(archivo)
                gdf = normalizar_columnas(gdf)
                if gdf.empty:
                    continue
                resultado = gpd.sjoin(punto, gdf, how='left', predicate='intersects')
                if not resultado.empty and (not pd.isna(resultado.iloc[0].get('index_right'))):
                    return clave
            except Exception:
                continue
    except Exception:
        pass
    return None

def detectar_limite_urbano_prms(lat, lon, gdf_prms_lu):
    if gdf_prms_lu.empty:
        return ('No evaluado', 'No se cargó PRMS_LU.')
    punto = gpd.GeoDataFrame({'id': [1]}, geometry=[Point(lon, lat)], crs='EPSG:4326')
    try:
        resultado = gpd.sjoin(punto, gdf_prms_lu, how='left', predicate='intersects')
        if not resultado.empty and (not pd.isna(resultado.iloc[0].get('index_right'))):
            fila = resultado.iloc[0]
            return ('Dentro de límite urbano PRMS', fila.get('archivo_origen', ''))
        return ('Fuera de límite urbano PRMS / área rural', 'No intersecta PRMS_LU.')
    except Exception as e:
        return ('No evaluado', str(e))

def detectar_categorias_oguc(fila):
    texto = ' '.join([str(fila.get('UPERM', '')), str(fila.get('UPREF', '')), str(fila.get('UPROH', '')), str(fila.get('SUELO', '')), str(fila.get('NOMBRE', '')), str(fila.get('ZONA', '')), texto_atributos(fila)])
    texto_norm = normalizar(texto)
    categorias = set()
    if 'zona habitacional mixto' in texto_norm or 'zona habitacional mixta' in texto_norm or 'habitacional mixto' in texto_norm or ('habitacional mixta' in texto_norm):
        return {'R', 'Eq', 'AP', 'Inf'}
    if 'residencial' in texto_norm or 'vivienda' in texto_norm or 'habitacional' in texto_norm or ('habitacionales' in texto_norm):
        categorias.add('R')
    if 'equipamiento' in texto_norm or 'comercio' in texto_norm or 'educacion' in texto_norm or ('salud' in texto_norm) or ('culto' in texto_norm) or ('cultura' in texto_norm) or ('deporte' in texto_norm) or ('seguridad' in texto_norm) or ('esparcimiento' in texto_norm) or ('cientifico' in texto_norm) or ('metropolitano' in texto_norm) or ('intercomunal' in texto_norm):
        categorias.add('Eq')
    actividad_productiva_detectada = 'actividad productiva' in texto_norm or 'actividades productivas' in texto_norm or 'productiva' in texto_norm or ('productivas' in texto_norm) or ('industrial' in texto_norm) or ('industria' in texto_norm) or ('taller' in texto_norm) or ('talleres' in texto_norm) or ('bodega' in texto_norm) or ('bodegas' in texto_norm) or ('almacenamiento' in texto_norm) or ('servicio de caracter industrial' in texto_norm) or ('servicios de caracter industrial' in texto_norm) or ('zona industrial' in texto_norm) or ('industrial exclusiva' in texto_norm)
    actividad_productiva_inofensiva = 'actividad productiva inofensiva' in texto_norm or 'actividades productivas inofensivas' in texto_norm or 'industria inofensiva' in texto_norm or ('industrial inofensiva' in texto_norm) or ('industrial inofensivo' in texto_norm) or ('taller inofensivo' in texto_norm) or ('talleres inofensivos' in texto_norm) or ('almacenamiento inofensivo' in texto_norm) or ('bodega inofensiva' in texto_norm) or ('bodegas inofensivas' in texto_norm)
    actividad_productiva_no_inofensiva = 'molesta' in texto_norm or 'molestas' in texto_norm or 'insalubre' in texto_norm or ('insalubres' in texto_norm) or ('contaminante' in texto_norm) or ('contaminantes' in texto_norm) or ('peligrosa' in texto_norm) or ('peligrosas' in texto_norm) or ('industrial exclusiva' in texto_norm) or ('industria exclusiva' in texto_norm)
    if actividad_productiva_detectada:
        if actividad_productiva_inofensiva and (not actividad_productiva_no_inofensiva):
            categorias.add('Eq')
        else:
            categorias.add('AP')
    if 'infraestructura' in texto_norm or 'transporte' in texto_norm or 'sanitaria' in texto_norm or ('energetica' in texto_norm) or ('telecomunicacion' in texto_norm) or ('telecomunicaciones' in texto_norm) or ('red vial' in texto_norm) or ('terminal' in texto_norm) or ('estacion' in texto_norm) or ('subestacion' in texto_norm) or ('planta' in texto_norm) or ('macroinfraestructura' in texto_norm):
        categorias.add('Inf')
    if 'area verde' in texto_norm or 'areas verdes' in texto_norm or 'parque' in texto_norm or ('plaza' in texto_norm) or ('recreacion' in texto_norm):
        categorias.add('AV')
    if 'espacio publico' in texto_norm or 'espacios publicos' in texto_norm or 'uso publico' in texto_norm or ('vialidad' in texto_norm) or ('bien nacional de uso publico' in texto_norm):
        categorias.add('EP')
    return categorias

def homologar_por_tabla_sma491(categorias):
    cats = set(categorias)
    if cats in [{'AV'}, {'EP'}, {'AV', 'EP'}]:
        return ('Zona I', '55 dBA', '45 dBA', 'AV/EP solos o combinados entre sí se homologan a Zona I.')
    if ('AP' in cats or 'Inf' in cats) and 'R' not in cats and ('Eq' not in cats):
        return ('Zona IV', '70 dBA', '70 dBA', 'Actividad Productiva y/o Infraestructura sin uso Residencial ni Equipamiento.')
    if 'AP' in cats or 'Inf' in cats:
        return ('Zona III', '65 dBA', '50 dBA', 'Combinación con Actividad Productiva y/o Infraestructura junto a R/Eq/AV/EP.')
    if 'Eq' in cats:
        return ('Zona II', '60 dBA', '45 dBA', 'Combinación con Equipamiento, sin Actividad Productiva ni Infraestructura.')
    if 'R' in cats:
        return ('Zona I', '55 dBA', '45 dBA', 'Uso Residencial solo o combinado únicamente con Área Verde/Espacio Público.')
    return ('No clasificada', '-', '-', 'No se detectaron categorías suficientes para homologar automáticamente.')

def _formatear_limite(valor):
    if pd.isna(valor):
        return "—"
    texto = str(valor).strip()
    if not texto or texto.lower() == "nan":
        return "—"
    try:
        numero = float(texto)
        return f"{int(numero)} dBA" if numero.is_integer() else f"{numero:g} dBA"
    except Exception:
        return texto if "dba" in texto.lower() else f"{texto} dBA"


def homologar_ds38(fila, estado_lu=None):
    if estado_lu == 'Fuera de límite urbano PRMS / área rural':
        return (
            'Zona Rural',
            'Rf + 10 dBA, con tope Zona III',
            'Rf + 10 dBA, con tope Zona III',
            'El punto se encuentra fuera del límite urbano PRMS; corresponde evaluación como Zona Rural del D.S. N°38/2011 MMA.',
            'Rural'
        )

    regla = homologar_por_tabla_prc(
        fila.get('COMUNA', ''),
        fila.get('ZONA', ''),
        fila.get('NOMBRE', '')
    )

    if regla:
        zona_csv = str(regla.get('zona_ds38', '')).strip()
        categorias_csv = str(regla.get('categorias', '')).strip()
        fundamento = str(regla.get('fundamento', '')).strip()

        if zona_csv.upper() == 'REVISAR' or categorias_csv.upper() == 'REVISAR':
            if not fundamento or fundamento.lower() == 'nan':
                fundamento = (
                    'La normativa aplicable no permite efectuar una homologación automática. '
                    'Se requiere revisión del IPT y de los antecedentes normativos específicos.'
                )
            return ('Revisión requerida', '—', '—', fundamento, 'Revisión normativa')

        return (
            zona_csv,
            _formatear_limite(regla.get('limite_dia', '')),
            _formatear_limite(regla.get('limite_noche', '')),
            fundamento,
            categorias_csv
        )

    categorias = detectar_categorias_oguc(fila)
    zona, dia, noche, criterio = homologar_por_tabla_sma491(categorias)
    categorias_texto = ' + '.join(sorted(categorias)) if categorias else 'No detectadas'
    return (zona, dia, noche, criterio, categorias_texto)

def buscar_punto_en_capa(lat, lon, gdf, tolerancia_m=50):
    punto = gpd.GeoDataFrame({'id': [1]}, geometry=[Point(lon, lat)], crs='EPSG:4326')
    if gdf.empty:
        return gpd.GeoDataFrame()
    resultado = gpd.sjoin(punto, gdf, how='left', predicate='intersects')
    if not resultado.empty:
        fila = resultado.iloc[0]
        if not pd.isna(fila.get('index_right')):
            resultado['metodo_busqueda'] = 'Dentro del polígono'
            resultado['distancia_m'] = 0
            return resultado
    if tolerancia_m == 0:
        return gpd.GeoDataFrame()
    try:
        punto_m = punto.to_crs(epsg=32719)
        gdf_m = gdf.to_crs(epsg=32719).copy()
        punto_geom = punto_m.geometry.iloc[0]
        gdf_m['distancia_m'] = gdf_m.geometry.distance(punto_geom)
        cercanos = gdf_m[gdf_m['distancia_m'] <= tolerancia_m].copy()
        if cercanos.empty:
            return gpd.GeoDataFrame()
        cercano = cercanos.sort_values('distancia_m').iloc[[0]].copy()
        distancia = round(float(cercano.iloc[0]['distancia_m']), 2)
        cercano = cercano.to_crs(epsg=4326)
        cercano['id'] = 1
        cercano['metodo_busqueda'] = 'Por tolerancia espacial'
        cercano['distancia_m'] = distancia
        return cercano
    except Exception:
        return gpd.GeoDataFrame()

def debe_revisar_prms(fila):
    archivo = str(fila.get('archivo_origen', '') or '')
    comuna = normalizar(fila.get('COMUNA', ''))

    # Un nombre/fundamento de Puente Alto puede mencionar PRMS sin que corresponda
    # reemplazar la zonificación PRC por PRMS_USO_Suelo.
    if (
        comuna == normalizar('Puente Alto')
        and 'PRC_Puente_Alto' in archivo.replace('\\\\', '/')
    ):
        return False

    texto = texto_atributos(fila)
    claves_explicitas = [
        'revisar prms', 'ver prms', 'aplica prms',
        'remitase prms', 'remítase prms', 'remitirse prms',
        'normativa prms', 'segun el prms', 'según el prms'
    ]
    return any(clave in texto for clave in claves_explicitas)

def buscar_jerarquico(lat, lon, gdf_prc, gdf_prms_uso, tolerancia_m):
    resultado_prc = buscar_punto_en_capa(lat, lon, gdf_prc, tolerancia_m)
    if not resultado_prc.empty:
        fila_prc = resultado_prc.iloc[0]
        if tiene_info_normativa(fila_prc):
            if debe_revisar_prms(fila_prc):
                resultado_prms = buscar_punto_en_capa(lat, lon, gdf_prms_uso, tolerancia_m)
                if not resultado_prms.empty:
                    fila_prms = resultado_prms.iloc[0]
                    if tiene_info_normativa(fila_prms):
                        resultado_prms['fuente_normativa'] = 'PRMS_USO_Suelo'
                        resultado_prms['observacion_jerarquia'] = 'El PRC contiene referencia a revisión PRMS; por ello se utilizó la capa PRMS_USO_Suelo.'
                        return resultado_prms
                resultado_prc['fuente_normativa'] = 'PRC'
                resultado_prc['observacion_jerarquia'] = 'El PRC indica revisar PRMS, pero no se encontró información normativa válida en PRMS_USO_Suelo.'
                return resultado_prc
            resultado_prc['fuente_normativa'] = 'PRC'
            resultado_prc['observacion_jerarquia'] = 'Se utilizó la zonificación del PRC comunal.'
            return resultado_prc
    resultado_prms = buscar_punto_en_capa(lat, lon, gdf_prms_uso, tolerancia_m)
    if not resultado_prms.empty:
        fila_prms = resultado_prms.iloc[0]
        if tiene_info_normativa(fila_prms):
            resultado_prms['fuente_normativa'] = 'PRMS_USO_Suelo'
            resultado_prms['observacion_jerarquia'] = 'No se encontró PRC aplicable; se utilizó PRMS_USO_Suelo.'
            return resultado_prms
    return gpd.GeoDataFrame()

def convertir_a_utm(lat, lon):
    try:
        punto = gpd.GeoDataFrame({'id': [1]}, geometry=[Point(lon, lat)], crs='EPSG:4326')
        punto_utm = punto.to_crs(epsg=32719)
        geom = punto_utm.geometry.iloc[0]
        return (round(geom.x, 2), round(geom.y, 2))
    except Exception:
        return ('-', '-')

def obtener_usos_desde_regla_o_shape(regla_csv, fila):
    if regla_csv:
        fundamento = str(regla_csv.get('fundamento', '')).strip()
        if fundamento and fundamento.lower() != 'nan':
            return fundamento
        categorias_csv = str(regla_csv.get('categorias', '')).strip()
        nombre_csv = str(regla_csv.get('nombre_zona', '')).strip()
        return f'{nombre_csv}; categorías consideradas: {categorias_csv}'
    usos_shape = ' '.join([str(fila.get('UPREF', '')), str(fila.get('UPERM', '')), str(fila.get('UPROH', ''))]).strip()
    if not usos_shape or usos_shape.lower() == 'nan':
        usos_shape = texto_atributos(fila)
    return usos_shape

def nombre_fuente_normativa(fuente):
    if fuente == 'PRC':
        return 'Plan Regulador Comunal'
    if fuente == 'PRMS_USO_Suelo':
        return 'Plan Regulador Metropolitano de Santiago'
    if fuente == 'PRMS_LU':
        return 'Límite Urbano PRMS'
    return fuente if fuente else 'No informada'



def _normalizar_comuna_solicitada(comuna):
    if not comuna:
        return None
    indice = crear_indice_comunas()
    clave = normalizar(comuna)
    if clave in indice:
        return clave
    # Búsqueda flexible por nombre visible.
    for k, info in indice.items():
        if normalizar(info.get("nombre", "")) == clave:
            return k
    return None



def _nombre_comuna_desde_shp(shp):
    nombre_archivo = shp.split("/")[-1]
    comuna = nombre_archivo
    for r in [
        "IPT_13_PRC_",
        "IPT_13_PRI_",
        "IPT_13_PNSECC_",
        ".shp",
    ]:
        comuna = comuna.replace(r, "")
    comuna = comuna.replace("_", " ").strip()

    especiales = {
        "Nunoa AP": "Ñuñoa",
        "Pudahuel San Francisco": "Pudahuel",
    }
    comuna = especiales.get(comuna, comuna)

    for b in [" AP", " Rural", " Urbano"]:
        if comuna.endswith(b):
            comuna = comuna.replace(b, "").strip()

    return comuna


def _archivos_normativos_comuna(comuna_clave):
    # Para Puente Alto se usa exclusivamente el shapefile local actualizado.
    if comuna_clave == normalizar("Puente Alto") and os.path.exists(PUENTE_ALTO_SHP_PATH):
        return ["__LOCAL_PUENTE_ALTO__"]

    archivos = []
    for shp in listar_shapefiles():
        if (
            "/PRC/" not in shp
            and "/PRI/" not in shp
            and "PNSECC" not in shp
        ):
            continue
        if "Patrimonio" in shp or "ZNE" in shp or "poligono" in shp.lower():
            continue

        if normalizar(_nombre_comuna_desde_shp(shp)) == comuna_clave:
            archivos.append(shp)

    def prioridad(shp):
        n = shp.upper()
        if "_PRC_" in n:
            return (0, n)
        if "_PRI_" in n:
            return (1, n)
        if "PNSECC" in n:
            return (2, n)
        return (3, n)

    return sorted(archivos, key=prioridad)


def _cargar_capas_normativas_comuna(comuna_clave):
    archivos = _archivos_normativos_comuna(comuna_clave)
    capas = []

    for shp in archivos:
        try:
            g = normalizar_columnas(cargar_shp(shp))
            if not g.empty:
                g["fuente_normativa"] = "PRC"
                capas.append(g)
        except Exception:
            continue

    if not capas:
        return crear_gdf_vacio(), archivos

    combinado = gpd.GeoDataFrame(
        pd.concat(capas, ignore_index=True),
        geometry="geometry",
        crs="EPSG:4326",
    )
    return combinado, archivos


def _cargar_capas_para_comuna(comuna_clave):
    indice = crear_indice_comunas()
    if comuna_clave not in indice:
        raise ValueError(f"Comuna no disponible en el homologador: {comuna_clave}")

    comuna_info = indice[comuna_clave]

    # Cargar todas las capas normativas comunales.
    gdf_prc, archivos_comuna = _cargar_capas_normativas_comuna(comuna_clave)

    capa_prms_lu = buscar_capa_prms_lu()
    capa_prms_uso = buscar_capa_prms_uso_suelo()

    gdf_prms_lu_total = normalizar_columnas(
        cargar_shp(capa_prms_lu) if capa_prms_lu else crear_gdf_vacio()
    )
    gdf_prms_uso_total = normalizar_columnas(
        cargar_shp(capa_prms_uso) if capa_prms_uso else crear_gdf_vacio()
    )

    # PRMS de usos de suelo: filtrar por comuna si el atributo lo permite.
    gdf_prms_uso = filtrar_por_comuna(
        gdf_prms_uso_total, comuna_info["nombre"]
    )
    if gdf_prms_uso.empty:
        gdf_prms_uso = gdf_prms_uso_total.copy()

    # IMPORTANTE: el límite urbano PRMS se consulta contra la capa completa.
    # No se recorta por el bbox de un PRC/PNSECC, porque eso puede clasificar
    # erróneamente como rural un punto urbano situado fuera de un seccional.
    gdf_prms_lu = gdf_prms_lu_total.copy()

    gdf_prms_lu = normalizar_columnas(gdf_prms_lu)
    gdf_prms_lu["fuente_normativa"] = "PRMS_LU"

    gdf_prms_uso = normalizar_columnas(gdf_prms_uso)
    gdf_prms_uso["fuente_normativa"] = "PRMS_USO_Suelo"

    comuna_info = dict(comuna_info)
    comuna_info["archivos_normativos"] = archivos_comuna

    return comuna_info, gdf_prc, gdf_prms_uso, gdf_prms_lu, gdf_prms_uso_total


def utm19s_a_latlon(este, norte):
    punto = gpd.GeoDataFrame(
        {"id": [1]},
        geometry=[Point(float(este), float(norte))],
        crs="EPSG:32719"
    ).to_crs(epsg=4326)
    geom = punto.geometry.iloc[0]
    return float(geom.y), float(geom.x)


def homologar_coordenada(lat=None, lon=None, este=None, norte=None, comuna=None, tolerancia_m=50):
    if (lat is None or lon is None) and (este is None or norte is None):
        raise ValueError("Debes indicar lat/lon o este/norte UTM WGS84 Huso 19S.")

    if lat is None or lon is None:
        lat, lon = utm19s_a_latlon(este, norte)

    lat = float(lat)
    lon = float(lon)
    tolerancia_m = int(tolerancia_m)

    indice = crear_indice_comunas()

    # Cargamos PRMS total una vez para detectar comuna cuando no se especifica.
    capa_prms_uso = buscar_capa_prms_uso_suelo()
    gdf_prms_uso_total = normalizar_columnas(
        cargar_shp(capa_prms_uso) if capa_prms_uso else crear_gdf_vacio()
    )

    comuna_clave = _normalizar_comuna_solicitada(comuna)
    if comuna and not comuna_clave:
        raise ValueError(f"No se reconoce la comuna indicada: {comuna}")

    if not comuna_clave:
        comuna_clave = detectar_comuna_por_punto(
            lat, lon, indice, gdf_prms_uso_total=gdf_prms_uso_total
        )

    if not comuna_clave:
        raise ValueError("No fue posible detectar automáticamente la comuna del punto.")

    comuna_info, gdf_prc, gdf_prms_uso, gdf_prms_lu, _ = _cargar_capas_para_comuna(comuna_clave)

    estado_lu, detalle_lu = detectar_limite_urbano_prms(lat, lon, gdf_prms_lu)

    resultado = buscar_jerarquico(
        lat, lon, gdf_prc, gdf_prms_uso, tolerancia_m
    )

    utm_e, utm_n = convertir_a_utm(lat, lon)

    if resultado.empty:
        if estado_lu == "Fuera de límite urbano PRMS / área rural":
            return {
                "ok": True,
                "comuna": comuna_info["nombre"],
                "lat": lat,
                "lon": lon,
                "utm_este": utm_e,
                "utm_norte": utm_n,
                "clasificacion_territorial": estado_lu,
                "zona_ds38": "Zona Rural",
                "limite_dia": "Rf + 10 dBA, con tope Zona III",
                "limite_noche": "Rf + 10 dBA, con tope Zona III",
                "fuente_normativa": "Límite Urbano PRMS",
                "zona_ipt": "",
                "nombre_zona_ipt": "",
                "categorias": "Rural",
                "fundamento": (
                    "El punto se encuentra fuera del límite urbano PRMS; corresponde "
                    "evaluación como Zona Rural del D.S. N°38/2011 MMA."
                ),
                "metodo_busqueda": "",
                "distancia_m": None,
                "observacion_jerarquia": "",
                "advertencia": (
                    "Resultado preliminar. Debe verificarse con IPT vigente, cartografía oficial, "
                    "Ordenanza correspondiente y Res. Ex. SMA N°491/2016."
                ),
            }

        return {
            "ok": False,
            "comuna": comuna_info["nombre"],
            "lat": lat,
            "lon": lon,
            "utm_este": utm_e,
            "utm_norte": utm_n,
            "clasificacion_territorial": estado_lu,
            "detalle_limite_urbano": detalle_lu,
            "mensaje": "No se encontró información territorial para el punto.",
        }

    fila = resultado.iloc[0]

    zona_ds38, limite_dia, limite_noche, criterio, categorias = homologar_ds38(
        fila, estado_lu
    )

    regla_csv = homologar_por_tabla_prc(
        fila.get("COMUNA", ""),
        fila.get("ZONA", ""),
        fila.get("NOMBRE", "")
    )
    if regla_csv is None:
        regla_csv = homologar_por_tabla_prms(
            fila.get("ZONA", ""),
            fila.get("NOMBRE", "")
        )

    if regla_csv:
        zona_csv = str(regla_csv.get("zona_ds38", "")).strip()
        categorias_csv = str(regla_csv.get("categorias", "")).strip()

        if zona_csv.upper() == "REVISAR" or categorias_csv.upper() == "REVISAR":
            zona_ds38 = "Revisión requerida"
            limite_dia = "—"
            limite_noche = "—"
            criterio = regla_csv.get("fundamento", criterio)
            categorias = "Revisión normativa"
        else:
            zona_ds38 = regla_csv.get("zona_ds38", zona_ds38)
            limite_dia = _formatear_limite(regla_csv.get("limite_dia", limite_dia))
            limite_noche = _formatear_limite(regla_csv.get("limite_noche", limite_noche))
            criterio = regla_csv.get("fundamento", criterio)
            categorias = regla_csv.get("categorias", categorias)

    fuente = str(fila.get("fuente_normativa", "") or "")
    metodo = str(fila.get("metodo_busqueda", "") or "")
    distancia = fila.get("distancia_m", None)
    try:
        if pd.isna(distancia):
            distancia = None
        elif distancia is not None:
            distancia = float(distancia)
    except Exception:
        distancia = None

    return {
        "ok": True,
        "comuna": str(fila.get("COMUNA", "") or comuna_info["nombre"]),
        "lat": lat,
        "lon": lon,
        "utm_este": utm_e,
        "utm_norte": utm_n,
        "clasificacion_territorial": estado_lu,
        "detalle_limite_urbano": detalle_lu,
        "fuente_normativa": nombre_fuente_normativa(fuente),
        "fuente_normativa_codigo": fuente,
        "zona_ipt": str(fila.get("ZONA", "") or ""),
        "nombre_zona_ipt": str(fila.get("NOMBRE", "") or ""),
        "usos_suelo_fundamento": obtener_usos_desde_regla_o_shape(regla_csv, fila),
        "zona_ds38": str(zona_ds38),
        "limite_dia": str(limite_dia),
        "limite_noche": str(limite_noche),
        "categorias": str(categorias),
        "fundamento": str(criterio),
        "metodo_busqueda": metodo,
        "distancia_m": distancia,
        "observacion_jerarquia": str(fila.get("observacion_jerarquia", "") or ""),
        "advertencia": (
            "Resultado preliminar. Debe verificarse con IPT vigente, cartografía oficial, "
            "Ordenanza correspondiente y Res. Ex. SMA N°491/2016."
        ),
    }
