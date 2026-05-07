"""
Persistencia y lógica de negocio XML/XSD (parseo, validación, generación).

Los XSD viven en ``resources/xsd`` (vía ``utils.paths.xsd_file_path``).
"""
from typing import Optional, Dict, Any, List, Tuple
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.persistence.firebird.hoja_trabajo_persistencia import agrupar_filas_hoja
from infrastructure.persistence.firebird.elementos_persistencia import (
    consultar_nombres_atributos_valor_por_formato,
)
from core import session
from core.settings import PERIODO
from utils.paths import xsd_file_path
import os
import xml.etree.ElementTree as ET
import re
from datetime import datetime


def _obtener_elemento_detalle_xsd_tree(root: ET.Element, ns: Dict[str, str]) -> Tuple[Optional[ET.Element], Optional[ET.Element]]:
    """
    Función privada: busca el elemento detalle en el árbol XSD.
    
    Parameters
    ----------
    root : ET.Element
        Elemento raíz del árbol XML.
    ns : Dict[str, str]
        Namespaces XML.
    
    Returns
    -------
    Tuple[Optional[ET.Element], Optional[ET.Element]]
        Tupla con (elemento, complex_type) o (None, None) si no se encuentra.
    """
    for elem in root.findall('.//xs:element[@name]', ns):
        if elem.get('name') != 'mas':
            complex_type = elem.find('.//xs:complexType', ns)
            if complex_type is not None and complex_type.findall('.//xs:attribute', ns):
                return elem, complex_type
    return None, None


def _parsear_restricciones_atributo(attr: ET.Element, ns: Dict[str, str]) -> Dict[str, Any]:
    """
    Función privada: parsea las restricciones de un atributo XSD.
    
    Parameters
    ----------
    attr : ET.Element
        Elemento atributo del XSD.
    ns : Dict[str, str]
        Namespaces XML.
    
    Returns
    -------
    Dict[str, Any]
        Diccionario con las restricciones encontradas (base, minLength, maxLength, etc.).
    """
    restricciones = {}
    simple_type = attr.find('.//xs:simpleType', ns)
    if simple_type is not None:
        restriction = simple_type.find('.//xs:restriction', ns)
        if restriction is not None:
            restricciones['base'] = restriction.get('base', '')
            for elem_restriccion in restriction:
                tag_local = (
                    elem_restriccion.tag.split("}")[1]
                    if "}" in elem_restriccion.tag
                    else elem_restriccion.tag
                )
                if tag_local in [
                    "minLength",
                    "maxLength",
                    "minInclusive",
                    "maxInclusive",
                    "pattern",
                    "totalDigits",
                ]:
                    restricciones[tag_local] = elem_restriccion.get("value") or (
                        elem_restriccion.text if elem_restriccion.text else ""
                    )
    return restricciones


def parsear_xsd(formato_codigo: str) -> Dict[str, Dict[str, Any]]:
    """
    Parsea un archivo XSD y extrae información de atributos.
    
    Parameters
    ----------
    formato_codigo : str
        Código del formato (nombre del archivo XSD sin extensión).
    
    Returns
    -------
    Dict[str, Dict[str, Any]]
        Diccionario donde cada clave es el nombre de un atributo y el valor es un
        diccionario con:
        - 'required': bool - Si el atributo es obligatorio
        - 'restrictions': Dict - Restricciones del atributo (base, minLength, etc.)
        Diccionario vacío si el archivo no existe o hay error.
    """
    try:
        ruta_xsd = xsd_file_path(formato_codigo)
        if not os.path.exists(ruta_xsd):
            return {}

        tree = ET.parse(ruta_xsd)
        ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
        elemento_elem, complex_type = _obtener_elemento_detalle_xsd_tree(tree.getroot(), ns)
        
        if not complex_type:
            return {}
        
        atributos_xsd = {}
        for attr in complex_type.findall('.//xs:attribute', ns):
            nombre = attr.get('name')
            if nombre:
                atributos_xsd[nombre] = {
                    'required': attr.get('use', 'optional') == 'required',
                    'restrictions': _parsear_restricciones_atributo(attr, ns)
                }
        
        return atributos_xsd
    except Exception as e:
        print(f"Error parseando XSD {formato_codigo}: {e}")
        return {}


def obtener_orden_atributos_xsd(formato_codigo: str) -> List[str]:
    """
    Obtiene el orden de los atributos según el archivo XSD.
    
    Parameters
    ----------
    formato_codigo : str
        Código del formato (nombre del archivo XSD sin extensión).
    
    Returns
    -------
    List[str]
        Lista de nombres de atributos en el orden en que aparecen en el XSD.
        Lista vacía si el archivo no existe o hay error.
    """
    try:
        ruta_xsd = xsd_file_path(formato_codigo)
        if not os.path.exists(ruta_xsd):
            return []

        tree = ET.parse(ruta_xsd)
        ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
        _, complex_type = _obtener_elemento_detalle_xsd_tree(tree.getroot(), ns)
        
        if not complex_type:
            return []
        
        return [attr.get('name') for attr in complex_type.findall('.//xs:attribute', ns) if attr.get('name')]
    except Exception as e:
        print(f"Error obteniendo orden de atributos XSD {formato_codigo}: {e}")
        return []


def _obtener_datos_identidad(formato_codigo: str) -> List[Tuple]:
    """
    Función privada: obtiene datos de la hoja de trabajo para un formato.
    Incluye ID e IDCONCEPTO para poder agrupar por registros (identidad+concepto+IDs consecutivos).

    Returns
    -------
    List[Tuple]
        (identidad, codigo_concepto, descripcion_concepto, nombre_atributo, descripcion_atributo, valor, id, id_concepto).
        Orden: identidad, id_concepto, id. Lista vacía si hay error.
    """
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
        cur.execute("""
            SELECT
                ht.IDENTIDADTERCERO,
                COALESCE(c.CODIGO, '0') AS CODIGO_CONCEPTO,
                c.DESCRIPCION AS DESCRIPCION_CONCEPTO,
                a.NOMBRE AS NOMBRE_ATRIBUTO,
                a.DESCRIPCION AS DESCRIPCION_ATRIBUTO,
                ht.VALOR,
                ht.ID,
                ht.IDCONCEPTO
            FROM HOJA_TRABAJO ht
            INNER JOIN ATRIBUTOS a ON a.ID = ht.IDATRIBUTO
            LEFT JOIN CONCEPTOS c ON c.ID = ht.IDCONCEPTO AND (ht.ID IS NOT NULL AND ht.ID != 0)
            INNER JOIN FORMATOS f ON f.ID = c.IDFORMATO
            WHERE f.FORMATO = ?
            ORDER BY ht.IDENTIDADTERCERO, ht.IDCONCEPTO, ht.ID
        """, (formato_codigo,))
        rows = cur.fetchall()
        cur.close()
        con.close()
        return rows
    except Exception as e:
        print(f"Error obteniendo datos de hoja de trabajo: {e}")
        return []

def obtener_hoja_para_validar(
    formato_codigo: str,
    rows: Optional[List[Tuple]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Organiza datos de la hoja de trabajo para validación por registros (grupos).
    Clave por registro: id_concepto|identidad (identidades iguales se distinguen por concepto).
    """
    if rows is None:
        rows = _obtener_datos_identidad(formato_codigo)
    if not rows or len(rows[0]) < 8:
        return {}
    grupos = agrupar_filas_hoja(
        rows,
        get_id=lambda r: r[6],
        get_id_concepto=lambda r: r[7],
        get_identidad=lambda r: r[0],
    )
    resultado = {}
    for grupo in grupos:
        codigo = str(grupo["rows"][0][1])
        desc = grupo["rows"][0][2] or "Sin concepto"
        if codigo not in resultado:
            resultado[codigo] = {"descripcion": desc, "registros": {}}
        atributos = {}
        descripciones = {}
        for fila in grupo["rows"]:
            nom, desc_attr, val = fila[3], fila[4], (fila[5] or "")
            if nom != "Número de Identificación":
                atributos[nom] = val
                descripciones[nom] = str(desc_attr).strip() if desc_attr else nom
        atributos["_identidad"] = grupo["identidad"]
        atributos["_id_concepto"] = grupo["id_concepto"]
        atributos["_group_key"] = grupo["group_key"]
        atributos["_descripciones_atributos"] = descripciones
        resultado[codigo]["registros"][grupo["identidad"]] = atributos
    return resultado


def validar_valor_xsd(valor: Any, atributo_info: Dict[str, Any]) -> List[str]:
    """
    Valida un valor contra las restricciones de un atributo XSD.
    
    Parameters
    ----------
    valor : Any
        Valor a validar.
    atributo_info : Dict[str, Any]
        Información del atributo con 'required' y 'restrictions'.
    
    Returns
    -------
    List[str]
        Lista de mensajes de error. Lista vacía si el valor es válido.
    """
    errores = []
    restricciones = atributo_info.get('restrictions', {})
    
    if atributo_info.get('required') and (valor is None or str(valor).strip() == ""):
        errores.append("Campo obligatorio, no puede estar vacío")
        return errores
    
    if valor is None or str(valor).strip() == "":
        return errores
    valor_sin_espacios = str(valor).strip()
    if valor_sin_espacios == "Sin Valor":
        errores.append(
            'Sin Valor. Complete el campo en la hoja de trabajo o vuelva a acumular.'
        )
        return errores
    
    valor_str = valor_sin_espacios
    base = restricciones.get('base', '')
    
    if 'maxLength' in restricciones:
        max_len = int(restricciones['maxLength'])
        if len(valor_str) > max_len:
            errores.append(f"Longitud máxima: {max_len}, actual: {len(valor_str)}")
    
    if 'minLength' in restricciones:
        min_len = int(restricciones['minLength'])
        if len(valor_str) < min_len:
            errores.append(f"Longitud mínima: {min_len}, actual: {len(valor_str)}")
    
    if 'pattern' in restricciones:
        pattern = restricciones['pattern']
        if not re.match(pattern, valor_str):
            errores.append(f"El valor no cumple con el patrón esperado")

    if 'totalDigits' in restricciones:
        try:
            max_digits = int(restricciones['totalDigits'])
            # Contar solo dígitos, ignorando signos, separadores y espacios
            solo_digitos = re.sub(r'[^0-9]', '', valor_str)
            if len(solo_digitos) > max_digits:
                errores.append(f"Máximo {max_digits} dígitos significativos, actual: {len(solo_digitos)}")
        except (ValueError, TypeError):
            # Si la restricción viene mal formada en el XSD, no bloquea la validación
            pass
    
    if base in ['xs:int', 'xs:long', 'xs:positiveInteger']:
        try:
            num_val = int(valor_str) if '.' not in valor_str else float(valor_str)
            
            if 'minInclusive' in restricciones:
                min_val = int(restricciones['minInclusive'])
                if num_val < min_val:
                    errores.append(f"Valor mínimo: {min_val}, actual: {num_val}")
            
            if 'maxInclusive' in restricciones:
                max_val = int(restricciones['maxInclusive'])
                if num_val > max_val:
                    errores.append(f"Valor máximo: {max_val}, actual: {num_val}")
        except ValueError:
            tipo_esperado = base.replace('xs:', '') if base else 'número'
            errores.append(f"Debe ser un {tipo_esperado} válido")
    
    return errores


def validar_excepciones_especiales(
    identidad: str,
    atributos_identidad: Dict[str, Any]
) -> List[str]:
    """
    Valida excepciones especiales según reglas de negocio.
    
    Parameters
    ----------
    identidad : str
        Identidad del tercero.
    atributos_identidad : Dict[str, Any]
        Diccionario con atributos de la identidad.
    
    Returns
    -------
    List[str]
        Lista de avisos sobre campos que no se reportarán según las excepciones.
    """
    avisos = []
    identidad_num, tipo_doc_num, pais_num, identidad_limpia = _parsear_valores_excepciones(identidad, atributos_identidad)
    if tipo_doc_num == 31:
        campos_nombres = [
            clave_nombre
            for clave_nombre in ["apl1", "apl2", "nom1", "nom2"]
            if atributos_identidad.get(clave_nombre, "").strip()
        ]
        if campos_nombres:
            avisos.append(f"No se reportarán apellidos y nombres para NITs (tipo documento 31)")
    
    if tipo_doc_num in [42, 43] and identidad_limpia.startswith('444444'):
        campos_dir = [
            clave_direccion
            for clave_direccion in ["dir", "dpto", "mun"]
            if atributos_identidad.get(clave_direccion, "").strip()
        ]
        if campos_dir:
            avisos.append(f"No se reportará dirección, departamento y municipio para identidades fiscales que inician con 444444")
    
    if pais_num != 0 and pais_num != 169:
        campos_dpto = [
            clave_departamento
            for clave_departamento in ["dpto", "mun"]
            if atributos_identidad.get(clave_departamento, "").strip()
        ]
        if campos_dpto:
            avisos.append(f"No se reportará departamento y municipio para países diferentes a Colombia (169)")
    
    return avisos


def validar_formato_xsd(
    formato_codigo: str,
    atributos_xsd: Optional[Dict[str, Dict[str, Any]]] = None,
    rows: Optional[List[Tuple]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Valida todos los datos de un formato contra su esquema XSD.
    
    Parameters
    ----------
    formato_codigo : str
        Código del formato.
    atributos_xsd : Optional[Dict[str, Dict[str, Any]]], optional
        Atributos XSD pre-parseados. Si no se proporciona, se parsean.
    rows : Optional[List[Tuple]], optional
        Datos pre-obtenidos. Si no se proporciona, se obtienen desde la BD.
    
    Returns
    -------
    Dict[str, Dict[str, Any]]
        Resultados por concepto y registro. Clave de registro: identidad (por concepto).
        Estructura: {codigo_concepto: {descripcion: str, registros: {identidad: {errores, avisos, identidad, ...}}}}
    """
    if atributos_xsd is None:
        atributos_xsd = parsear_xsd(formato_codigo)
    if not atributos_xsd:
        return {}

    datos_hoja = obtener_hoja_para_validar(formato_codigo, rows=rows)
    if not datos_hoja:
        return {}
    resultado_validacion = {}
    for concepto_codigo, datos_concepto in datos_hoja.items():
        resultado_validacion[concepto_codigo] = {
            "descripcion": datos_concepto["descripcion"],
            "registros": {},
        }
        for identidad_reg, atributos_identidad in datos_concepto["registros"].items():
            identidad = atributos_identidad.get("_identidad", identidad_reg)
            errores_identidad: List[str] = []
            avisos_identidad: List[str] = []
            desc_por_nombre = atributos_identidad.get("_descripciones_atributos", {})

            for nombre_attr, valor in atributos_identidad.items():
                if nombre_attr.startswith("_"):
                    continue
                if nombre_attr in atributos_xsd:
                    attr_errores = validar_valor_xsd(valor, atributos_xsd[nombre_attr])
                    if not attr_errores:
                        continue
                    descripcion = desc_por_nombre.get(nombre_attr, nombre_attr)
                    for err in attr_errores:
                        errores_identidad.append(f"{descripcion}: {err}")
            for nombre_attr, attr_info in atributos_xsd.items():
                if attr_info.get("required") and nombre_attr not in atributos_identidad:
                    descripcion = desc_por_nombre.get(nombre_attr, nombre_attr)
                    errores_identidad.append(f"{descripcion}: Campo obligatorio faltante")
            avisos_especiales = validar_excepciones_especiales(identidad, atributos_identidad)
            avisos_identidad.extend(avisos_especiales)
            resultado_validacion[concepto_codigo]["registros"][identidad_reg] = {
                "errores": errores_identidad,
                "avisos": avisos_identidad,
                "identidad": identidad,
                "id_concepto": atributos_identidad.get("_id_concepto"),
                "group_key": atributos_identidad.get("_group_key"),
            }
    return resultado_validacion


def obtener_elemento_detalle_xsd(formato_codigo: str) -> Optional[str]:
    """
    Obtiene el nombre del elemento detalle del XSD.
    
    Parameters
    ----------
    formato_codigo : str
        Código del formato.
    
    Returns
    -------
    Optional[str]
        Nombre del elemento detalle o None si no se encuentra.
    """
    try:
        ruta_xsd = xsd_file_path(formato_codigo)
        if not os.path.exists(ruta_xsd):
            return None

        tree = ET.parse(ruta_xsd)
        ns = {'xs': 'http://www.w3.org/2001/XMLSchema'}
        elemento_elem, _ = _obtener_elemento_detalle_xsd_tree(tree.getroot(), ns)
        return elemento_elem.get('name') if elemento_elem is not None else None
    except Exception as e:
        print(f"Error obteniendo elemento detalle del XSD {formato_codigo}: {e}")
        return None


def obtener_hoja_para_generar(
    formato_codigo: str,
    rows: Optional[List[Tuple]] = None
) -> Dict[str, Dict[str, Any]]:
    """
    Organiza datos de la hoja de trabajo para generación de XML por registros (grupos).
    Clave: id_concepto|identidad. Incluye _identidad y _primer_id (para ordenar).
    """
    if rows is None:
        rows = _obtener_datos_identidad(formato_codigo)
    if not rows or len(rows[0]) < 7:
        return {}
    grupos = agrupar_filas_hoja(
        rows,
        get_id=lambda row: row[5],
        get_id_concepto=lambda row: row[6],
        get_identidad=lambda row: row[0],
    )
    resultado = {}
    for grupo in grupos:
        attrs = {}
        for fila in grupo["rows"]:
            nom, val = fila[3], (fila[4] or "")
            if nom != "Número de Identificación":
                attrs[nom] = val
        attrs["_identidad"] = grupo["identidad"]
        attrs["_primer_id"] = grupo["primer_id"]
        resultado[grupo["group_key"]] = attrs
    return resultado


def _parsear_valores_excepciones(
    identidad: str,
    atributos_identidad: Dict[str, Any]
) -> Tuple[int, int, int, str]:
    """
    Función privada: parsea valores para aplicar excepciones especiales.
    
    Parameters
    ----------
    identidad : str
        Identidad del tercero.
    atributos_identidad : Dict[str, Any]
        Diccionario con atributos de la identidad.
    
    Returns
    -------
    Tuple[int, int, int, str]
        Tupla con (identidad_num, tipo_doc_num, pais_num, identidad_limpia).
    """

    def _to_int_seguro(valor: Any) -> int:
        """
        Convierte a entero de forma tolerante:
        - Acepta strings como '31', '31.0', '31,0'
        - En caso de error o valor vacío retorna 0
        """
        if valor is None:
            return 0
        s = str(valor).strip()
        if not s:
            return 0
        try:
            # Intento directo, cubre enteros como '31'
            return int(s)
        except ValueError:
            try:
                # Intenta como float para valores tipo '31.0' o '31,0'
                s_normalizada = s.replace(",", ".")
                return int(float(s_normalizada))
            except (ValueError, TypeError):
                return 0

    identidad_limpia = str(identidad).replace(' ', '')
    identidad_num = _to_int_seguro(identidad_limpia)
    tipo_doc_num = _to_int_seguro(atributos_identidad.get('tdoc', 0))
    pais_num = _to_int_seguro(atributos_identidad.get('pais', 0))

    return identidad_num, tipo_doc_num, pais_num, identidad_limpia


def _campos_a_omitir_excepciones(
    identidad_num: int,
    tipo_doc_num: int,
    pais_num: int,
    identidad_limpia: str
) -> set:
    """
    Función privada: determina qué campos omitir según excepciones especiales.
    
    Parameters
    ----------
    identidad_num : int
        Número de identidad.
    tipo_doc_num : int
        Tipo de documento.
    pais_num : int
        Código del país.
    identidad_limpia : str
        Identidad sin espacios.
    
    Returns
    -------
    set
        Conjunto de nombres de campos a omitir.
    """
    campos_omitir = set()
    if tipo_doc_num == 31:
        campos_omitir.update(['apl1', 'apl2', 'nom1', 'nom2'])
    if tipo_doc_num in [42, 43] and identidad_limpia.startswith('444444'):
        campos_omitir.update(['dir', 'dpto', 'mun'])
    if pais_num != 0 and pais_num != 169:
        campos_omitir.update(['dpto', 'mun'])
    return campos_omitir


def _valor_xml_solo_entero(valor: Any) -> str:
    """
    Para atributos valor (clase=1): quita todo lo que va después del punto (o coma) decimal.
    En el XML solo se escribe la parte entera.
    """
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return "" if valor is None else str(valor)
    s = str(valor).strip()
    try:
        n = float(s)
    except ValueError:
        s_limpia = s.replace(".", "").replace(",", ".")
        try:
            n = float(s_limpia)
        except ValueError:
            return s
    return str(int(n))


def aplicar_excepciones_especiales_generacion(
    identidad: str,
    atributos_identidad: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Aplica excepciones especiales para generación de XML.
    
    Filtra atributos que no deben incluirse según reglas de negocio.
    
    Parameters
    ----------
    identidad : str
        Identidad del tercero.
    atributos_identidad : Dict[str, Any]
        Diccionario con atributos de la identidad.
    
    Returns
    -------
    Dict[str, Any]
        Diccionario con atributos filtrados (sin campos a omitir ni campos privados).
        Además:
        - No incluye atributos opcionales vacíos.
        - Para atributos obligatorios vacíos, normaliza:
          * Campos de texto → None
          * Campos numéricos → 0
    """
    identidad_num, tipo_doc_num, pais_num, identidad_limpia = _parsear_valores_excepciones(identidad, atributos_identidad)
    campos_omitir = _campos_a_omitir_excepciones(identidad_num, tipo_doc_num, pais_num, identidad_limpia)
    
    # Intentar obtener definición XSD del formato a partir de los metadatos si están presentes
    formato_codigo = atributos_identidad.get("_formato")
    atributos_xsd = {}
    if formato_codigo:
        try:
            atributos_xsd = parsear_xsd(str(formato_codigo))
        except Exception:
            atributos_xsd = {}
    
    atributos_filtrados: Dict[str, Any] = {}
    for k, v in atributos_identidad.items():
        # Omitir campos internos y campos definidos por excepciones
        if k.startswith("_") or k in campos_omitir:
            continue
        
        valor_str = "" if v is None else str(v).strip()
        info_xsd = atributos_xsd.get(k, {})
        es_obligatorio = bool(info_xsd.get("required"))
        restricciones = info_xsd.get("restrictions", {})
        base_tipo = restricciones.get("base", "").replace("xs:", "")
        
        # Si el campo NO es obligatorio y está vacío → no se incluye en el XML
        if not es_obligatorio and valor_str == "":
            continue
        
        # Si el campo es obligatorio y está vacío → normalizar según tipo
        if es_obligatorio and valor_str == "":
            if base_tipo in ["int", "long", "positiveInteger", "decimal"]:
                atributos_filtrados[k] = 0
            else:
                atributos_filtrados[k] = None
            continue
        
        # Caso normal: conservar valor original
        atributos_filtrados[k] = v
    
    return atributos_filtrados


def generar_xml_formato(
    formato_codigo: str,
    datos_cabecera: Dict[str, Any],
    orden_atributos: Optional[List[str]] = None,
    elemento_detalle: Optional[str] = None,
    datos_hoja: Optional[Dict[str, Dict[str, Any]]] = None
) -> List[Tuple[str, int]]:
    """
    Genera uno o más archivos XML según el formato XSD especificado.
    Si hay más de 5000 registros, divide en múltiples archivos.
    
    Parameters
    ----------
    formato_codigo : str
        Código del formato.
    datos_cabecera : Dict[str, Any]
        Datos para la cabecera del XML (periodo, concepto, version, etc.).
    orden_atributos : Optional[List[str]], optional
        Orden de atributos. Si no se proporciona, se obtiene del XSD.
    elemento_detalle : Optional[str], optional
        Nombre del elemento detalle. Si no se proporciona, se obtiene del XSD.
    datos_hoja : Optional[Dict[str, Dict[str, Any]]], optional
        Datos de la hoja de trabajo. Si no se proporciona, se obtienen desde la BD.
    
    Returns
    -------
    List[Tuple[str, int]]
        Lista de tuplas con (xml_string, cantidad_registros) para cada archivo generado.
        Lista vacía si hay error.
    """
    MAX_REGISTROS_POR_ARCHIVO = 5000
    
    try:
        # if elemento_detalle is None:
        #     elemento_detalle = obtener_elemento_detalle_xsd(formato_codigo)
        # if not elemento_detalle:
        #     return []

        # if datos_hoja is None:
        #     datos_hoja = obtener_hoja_para_generar(formato_codigo)
        # if not datos_hoja:
        #     return []

        # if orden_atributos is None:
        #     orden_atributos = obtener_orden_atributos_xsd(formato_codigo)

        # Atributos valor (clase=1): en XML se quita la cifra ,00 (últimos 3 caracteres)
        atributos_valor = consultar_nombres_atributos_valor_por_formato(formato_codigo)

        # Obtener nombre del atributo para ValorTotal desde la tabla FORMATOS
        nombre_atributo_total = None
        try:
            con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
            cur = con.cursor()
            cur.execute("SELECT valortotal FROM FORMATOS WHERE formato = ?", (formato_codigo,))
            row = cur.fetchone()
            cur.close()
            con.close()
            
            if row and row[0]:
                nombre_atributo_total = str(row[0]).strip()
        except Exception as e:
            print(f"[ERROR] Error obteniendo atributo ValorTotal: {e}")
        
        concepto_codigo = "01" if datos_cabecera.get("concepto", "01") == "Inserción" else "02"
        
        # Ordenar por _primer_id (claves = id_concepto|identidad)
        claves_ordenadas = sorted(datos_hoja.keys(), key=lambda k: datos_hoja[k].get("_primer_id", 0))
        total_registros = len(claves_ordenadas)
        
        xmls_generados = []
        for inicio in range(0, total_registros, MAX_REGISTROS_POR_ARCHIVO):
            fin = min(inicio + MAX_REGISTROS_POR_ARCHIVO, total_registros)
            lote_claves = claves_ordenadas[inicio:fin]
            lote_datos = {k: datos_hoja[k] for k in lote_claves}
            
            valor_total = 0.0
            if nombre_atributo_total:
                for k in lote_claves:
                    attrs = datos_hoja[k]
                    if nombre_atributo_total in attrs:
                        valor_str = str(attrs[nombre_atributo_total]).strip()
                        if valor_str:
                            try:
                                valor_total += float(valor_str)
                            except (ValueError, TypeError):
                                pass
            
            root = ET.Element("mas")
            root.set("xmlns:xsi", "http://www.w3.org/2001/XMLSchema-instance")
            root.set("xsi:noNamespaceSchemaLocation", f"{formato_codigo}.xsd")
            cab = ET.SubElement(root, "Cab")
            valor_total_xml = _valor_xml_solo_entero(valor_total)
            for nombre, valor in [
                ("Ano", str(PERIODO)),
                ("CodCpt", concepto_codigo),
                ("Formato", str(formato_codigo)),
                ("Version", str(datos_cabecera.get("version", ""))),
                ("NumEnvio", str(datos_cabecera.get("numenvio", ""))),
                ("FecEnvio", f"{datos_cabecera.get('fechaenvio', '')}T{datos_cabecera.get('horaenvio', '')}"),
                ("FecInicial", datos_cabecera.get("fechainicial", "")),
                ("FecFinal", datos_cabecera.get("fechafinal", "")),
                ("ValorTotal", valor_total_xml),
                ("CantReg", str(len(lote_datos)))
            ]:
                ET.SubElement(cab, nombre).text = valor
            
            for clave in lote_claves:
                attrs = datos_hoja[clave]
                identidad_real = attrs.get("_identidad", "")
                atributos_filtrados = aplicar_excepciones_especiales_generacion(identidad_real, attrs)
                elemento = ET.SubElement(root, elemento_detalle)
                
                # Generar atributos del detalle en el orden definido por el XSD
                for nombre_attr in orden_atributos:
                    if nombre_attr not in atributos_filtrados:
                        continue
                    valor_raw = atributos_filtrados.get(nombre_attr)
                    # Convertir a texto, respetando las reglas especiales para atributos de valor
                    valor_xml = "" if valor_raw is None else str(valor_raw)
                    if nombre_attr in atributos_valor:
                        valor_xml = _valor_xml_solo_entero(valor_xml)
                    elemento.set(nombre_attr, valor_xml.strip())
            
            ET.indent(root, space="  ")
            xml_str = ET.tostring(root, encoding='ISO-8859-1', xml_declaration=True).decode('ISO-8859-1')
            xmls_generados.append((xml_str, len(lote_datos)))
        
        return xmls_generados
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Error generando XML: {str(e)}")
        return []
