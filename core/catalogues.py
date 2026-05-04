"""Catálogos en memoria (PAISES, DEPARTAMENTOS, MUNICIPIOS, TIPOSDOC) y utilidades de conversión."""
from typing import Optional, List, Tuple, Any

PAISES = {}
DEPARTAMENTOS = {}
MUNICIPIOS = {}
TIPOSDOC = {}

# Fallback mínimo (Colombia) cuando la BD no tiene datos
_FALLBACK_PAISES = {169: "COLOMBIA", "169": "COLOMBIA"}
_FALLBACK_DEPARTAMENTOS = {
    11: ["BOGOTÁ D.C.", 169], 25: ["CUNDINAMARCA", 169], 5: ["ANTIOQUIA", 169],
    8: ["ATLÁNTICO", 169], 17: ["CALDAS", 169], 18: ["CAUCA", 169], 46: ["CAQUETÁ", 169],
}
_FALLBACK_MUNICIPIOS = {
    1: [11001, "BOGOTÁ D.C.", 11], 2: [25001, "AGUA DE DIOS", 25], 3: [5001, "MEDELLÍN", 5],
}


def _parse_paises(raw: Optional[List[Tuple[Any, ...]]]) -> dict:
    """Parsea PAIS/PAISES: soporta (id, codigo, nombre) o (codigo, nombre)."""
    if not raw:
        return {}
    out = {}
    for row in raw:
        if len(row) >= 3:
            out[str(row[1])] = row[2]
        elif len(row) >= 2:
            out[str(row[0])] = row[1]
    return out if out else {}


def _parse_departamentos(raw: Optional[List[Tuple[Any, ...]]]) -> dict:
    """Parsea DEPARTAMENTO: soporta (id, codigo, nombre, padre) o (codigo, nombre, padre)."""
    if not raw:
        return {}
    out = {}
    for row in raw:
        if len(row) >= 4:
            cod, nombre, padre = row[1], row[2], row[3]
        elif len(row) >= 3:
            cod, nombre, padre = row[0], row[1], row[2]
        else:
            continue
        try:
            k = int(cod) if cod is not None else cod
        except (ValueError, TypeError):
            k = cod
        try:
            padre_int = int(padre) if padre is not None else 0
        except (ValueError, TypeError):
            padre_int = 0
        out[k] = [nombre, padre_int]
    return out if out else {}


def _parse_municipios(raw: Optional[List[Tuple[Any, ...]]]) -> dict:
    """Parsea MUNICIPIO/CIUDADES: soporta (id, codigo, nombre, padre) o (codigo, nombre, padre)."""
    if not raw:
        return {}
    out = {}
    for i, row in enumerate(raw):
        if len(row) >= 4:
            cod, nombre, padre = row[1], row[2], row[3]
        elif len(row) >= 3:
            cod, nombre, padre = row[0], row[1], row[2]
        else:
            continue
        key = i + 1
        out[key] = [int(cod) if str(cod).isdigit() else cod, nombre, int(padre) if padre is not None else 0]
    return out if out else {}


def obtener_codigo_tipodoc(valor) -> Optional[str]:
    """Convierte texto/nombre/código de tipo de documento a código numérico."""
    if not valor:
        return None
    valor_str = str(valor).strip().upper()
    if valor_str.isdigit() and int(valor_str) in TIPOSDOC:
        return str(valor_str)
    for cod, datos in TIPOSDOC.items():
        if len(datos) >= 2:
            tipo, desc = datos[0], datos[1]
            if str(tipo).upper() == valor_str or str(desc).upper() == valor_str or str(cod) == valor_str:
                return str(cod)
    return None


def obtener_nombre_tipodoc(codigo) -> Optional[str]:
    """Convierte código de tipo de documento a descripción."""
    if not codigo:
        return None
    datos = TIPOSDOC.get(int(codigo)) if str(codigo).isdigit() else None
    datos = datos if datos else TIPOSDOC.get(str(codigo))
    return datos[1] if datos and len(datos) >= 2 else None


def obtener_codigo_pais(valor) -> Optional[str]:
    """Convierte nombre de país a código."""
    if not valor:
        return None
    valor_str = str(valor).strip().upper()
    if valor_str.isdigit() and int(valor_str) in PAISES:
        return str(valor_str)
    for cod, nombre in PAISES.items():
        if str(nombre).upper() == valor_str or str(cod) == valor_str:
            return str(cod)
    return None


def obtener_nombre_pais(codigo) -> Optional[str]:
    """Convierte código de país a nombre."""
    if not codigo:
        return None
    r = PAISES.get(int(codigo)) if str(codigo).isdigit() else None
    return r if r else PAISES.get(str(codigo))


def obtener_codigo_departamento(valor, pais_codigo=None) -> Optional[str]:
    """Convierte nombre de departamento a código."""
    if not valor:
        return None
    valor_str = str(valor).strip().upper()
    if valor_str.isdigit():
        cod = int(valor_str)
        if cod in DEPARTAMENTOS and (pais_codigo is None or DEPARTAMENTOS[cod][1] == int(pais_codigo)):
            return str(valor_str)
    for cod, datos in DEPARTAMENTOS.items():
        if len(datos) >= 2:
            nombre, padre = datos[0], datos[1]
            if (str(nombre).upper() == valor_str or str(cod) == valor_str) and (
                pais_codigo is None or padre == int(pais_codigo)
            ):
                return str(cod)
    return None


def obtener_nombre_departamento(codigo) -> Optional[str]:
    """Convierte código de departamento a nombre."""
    if not codigo:
        return None
    datos = DEPARTAMENTOS.get(int(codigo)) if str(codigo).isdigit() else None
    datos = datos if datos else DEPARTAMENTOS.get(str(codigo))
    return datos[0] if datos and len(datos) >= 1 else None


def obtener_codigo_departamento_desde_municipio(codigo_municipio) -> Optional[str]:
    """Deriva el código de departamento de los 2 primeros dígitos del municipio."""
    if codigo_municipio is None:
        return None
    s = str(codigo_municipio).strip()
    if len(s) < 2:
        return None
    try:
        return str(int(s[:2]))
    except ValueError:
        return None


def obtener_codigo_municipio(valor, depto_codigo=None) -> Optional[str]:
    """Convierte nombre de municipio a código."""
    if not valor:
        return None
    valor_str = str(valor).strip().upper()
    for datos in MUNICIPIOS.values():
        cod, nombre, padre = datos[0], datos[1], datos[2]
        if (
            str(cod) == valor_str
            or (valor_str.isdigit() and int(cod) == int(valor_str))
            or str(nombre).upper() == valor_str
        ):
            if depto_codigo is None or padre == int(depto_codigo):
                return str(cod)
    return None


def obtener_nombre_municipio(codigo, depto_codigo=None) -> Optional[str]:
    """Convierte código de municipio a nombre. Si depto_codigo se indica, filtra por departamento."""
    if not codigo:
        return None
    cod_busca = int(codigo)
    dep_busca = int(depto_codigo) if depto_codigo is not None else None
    for datos in MUNICIPIOS.values():
        cod, nombre, padre = datos[0], datos[1], datos[2]
        try:
            if int(cod) != cod_busca:
                continue
            if dep_busca is not None and int(padre) != dep_busca:
                continue
            return nombre
        except (ValueError, TypeError):
            continue
    return None
