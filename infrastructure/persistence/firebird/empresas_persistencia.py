"""EMPRESAS en BD global EX: poblar desde NI/PH, listado, ficha y actualización de ubicación."""
from typing import Any, Dict, List, Optional, Tuple

from core.catalogues import obtener_codigo_departamento_desde_municipio
from core.settings import PERIODO
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura


def _notificar_error(contexto: str, cause: BaseException) -> None:
    print(f"EMPRESAS ({contexto}): {cause}")


def _valor_o_none(valor) -> Optional[Any]:
    return None if valor in (None, "") else valor


def _municipio_sin_prefijo_dane(codigo_ciudad) -> Optional[Any]:
    if not codigo_ciudad or len(str(codigo_ciudad)) < 3:
        return codigo_ciudad
    return str(codigo_ciudad)[2:]


def _resolver_departamento_por_municipio(
    codigo_municipio,
    codigo_departamento_actual,
):
    if codigo_departamento_actual is not None or codigo_municipio is None:
        return codigo_departamento_actual
    cod = obtener_codigo_departamento_desde_municipio(codigo_municipio)
    return int(cod) if cod is not None else None


def _normalizar_entero_opcional(valor) -> Optional[int]:
    if valor is None:
        return None
    try:
        return int(valor)
    except (ValueError, TypeError):
        return valor


def _ficha_desde_fila_ex(row: Tuple, codigo_solicitado: int) -> Dict[str, Any]:
    identidad, nombre, direccion, municipio_raw, depto_raw, pais_raw = (
        row[0],
        row[1],
        row[2],
        row[3],
        row[4],
        row[5],
    )
    depto = _resolver_departamento_por_municipio(municipio_raw, depto_raw)
    return {
        "codigo": codigo_solicitado,
        "nombre": nombre,
        "identidad": identidad,
        "direccion": direccion or "",
        "municipio": _normalizar_entero_opcional(municipio_raw),
        "departamento": _normalizar_entero_opcional(depto),
        "pais": _normalizar_entero_opcional(pais_raw),
    }


def _poblar_un_producto(
    cur_global,
    producto: str,
    campo_codigo_empresa: str,
    año_gravable: int,
) -> None:
    try:
        print(f"[EMPRESAS] Poblando desde producto {producto}")
        con_producto = CNX_BDHelisa(producto, -1, "sysdba")
        if not con_producto:
            return
        cursor_p = con_producto.cursor()
        cursor_p.execute(
            """
            SELECT d.CODIGO, d.NOMBRE, d.IDENTIDAD, d.DIRECCION, d.CODIGO_CIUDAD,
                   c.CODIGO_DEPARTAMENTO, c.COD_PAIS
            FROM DIRECTOR d
            LEFT JOIN CIUDADES c ON c.CODIGO = d.CODIGO_CIUDAD
            WHERE ? BETWEEN d.ANOINICIO AND d.ANOACTUAL
            ORDER BY d.NOMBRE
            """,
            (año_gravable,),
        )
        for codigo, nombre, identidad, direccion, ciudad, depto, pais in cursor_p.fetchall():
            depto_resuelto = _resolver_departamento_por_municipio(ciudad, depto)
            municipio_db = _municipio_sin_prefijo_dane(ciudad)
            cur_global.execute(
                f"""
                UPDATE OR INSERT INTO EMPRESAS
                    (Identidad, Nombre, {campo_codigo_empresa}, Direccion, Municipio, Departamento, Pais)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                MATCHING (Identidad)
                """,
                (
                    identidad,
                    nombre,
                    codigo,
                    direccion,
                    _valor_o_none(municipio_db),
                    _valor_o_none(depto_resuelto),
                    _valor_o_none(pais),
                ),
            )
        cursor_p.close()
        con_producto.close()
        print(f"[EMPRESAS] Pobladas desde producto {producto}")
    except Exception as exc:
        _notificar_error(f"poblar desde {producto}", exc)


def poblar_empresas_desde_productos() -> None:
    """Sincroniza DIRECTOR (NI/PH) hacia EMPRESAS en EX; se usa al construir la BD global."""
    año = int(PERIODO)
    try:
        with transaccion_segura(codigo_empresa=-1) as (_conn, cur_global):
            for prod, columna in (("NI", "CodigoEmpresaNI"), ("PH", "CodigoEmpresaPH")):
                _poblar_un_producto(cur_global, prod, columna, año)
    except Exception as exc:
        _notificar_error("poblar en BD global", exc)


def _empresas_desde_ex(producto: str) -> List[Dict[str, Any]]:
    conexion = CNX_BDHelisa("EX", -1, "sysdba")
    if conexion is None:
        raise ConnectionError("No se pudo conectar a la BD global (EX)")
    cursor = conexion.cursor()
    if producto == "NI":
        cursor.execute(
            """
            SELECT CodigoEmpresaNI, Nombre, Identidad
            FROM EMPRESAS
            WHERE CodigoEmpresaNI IS NOT NULL
            ORDER BY Nombre
            """
        )
    else:
        cursor.execute(
            """
            SELECT CodigoEmpresaPH, Nombre, Identidad
            FROM EMPRESAS
            WHERE CodigoEmpresaPH IS NOT NULL
            ORDER BY Nombre
            """
        )
    resultado = [{"codigo": c, "nombre": n, "identidad": i} for c, n, i in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return resultado


def _empresas_desde_director_producto(producto: str) -> List[Dict[str, Any]]:
    conexion = CNX_BDHelisa(producto, -1, "sysdba")
    if conexion is None:
        raise ConnectionError(f"No se pudo conectar a BD de producto {producto}")
    cursor = conexion.cursor()
    cursor.execute(
        """
        SELECT d.CODIGO, d.NOMBRE, d.IDENTIDAD
        FROM DIRECTOR d
        WHERE ? BETWEEN d.ANOINICIO AND d.ANOACTUAL
        ORDER BY d.NOMBRE
        """,
        (int(PERIODO),),
    )
    lista = [{"codigo": c, "nombre": n, "identidad": i} for c, n, i in cursor.fetchall()]
    cursor.close()
    conexion.close()
    return lista


def obtener_empresas(producto: str) -> List[Dict[str, Any]]:
    if producto not in ("NI", "PH"):
        return []
    try:
        return _empresas_desde_ex(producto)
    except Exception as exc_primero:
        _notificar_error(f"listado desde EX producto={producto}", exc_primero)
        try:
            return _empresas_desde_director_producto(producto)
        except Exception as exc_fallback:
            _notificar_error(f"listado desde DIRECTOR producto={producto}", exc_fallback)
            return []


def obtener_info_empresa(producto: str, codigo_empresa: int) -> Optional[Dict[str, Any]]:
    try:
        conexion = CNX_BDHelisa("EX", -1, "sysdba")
        cursor = conexion.cursor()
        if producto == "NI":
            cursor.execute(
                """
                SELECT Identidad, Nombre, Direccion, Municipio, Departamento, Pais
                FROM EMPRESAS WHERE CodigoEmpresaNI = ?
                """,
                (codigo_empresa,),
            )
        else:
            cursor.execute(
                """
                SELECT Identidad, Nombre, Direccion, Municipio, Departamento, Pais
                FROM EMPRESAS WHERE CodigoEmpresaPH = ?
                """,
                (codigo_empresa,),
            )
        fila = cursor.fetchone()
        cursor.close()
        conexion.close()
        if fila:
            return _ficha_desde_fila_ex(fila, codigo_empresa)
    except Exception as exc:
        _notificar_error(f"ficha EX producto={producto} codigo={codigo_empresa}", exc)
    return None


def _codigos_ubicacion_para_update(
    codigo_ciudad: Optional[str],
    codigo_departamento: Optional[str],
    codigo_pais: Optional[str],
) -> Tuple[Optional[int], Optional[int], Optional[int]]:
    def a_int(valor) -> Optional[int]:
        if valor is None or (isinstance(valor, str) and not valor.strip()):
            return None
        try:
            return int(valor)
        except (ValueError, TypeError):
            return None

    return a_int(codigo_ciudad), a_int(codigo_departamento), a_int(codigo_pais)


def actualizar_info_empresa(
    identidad: str,
    direccion: Optional[str],
    codigo_ciudad: Optional[str],
    codigo_departamento: Optional[str],
    codigo_pais: Optional[str],
) -> bool:
    cod_ciu, cod_depto, cod_pais = _codigos_ubicacion_para_update(
        codigo_ciudad, codigo_departamento, codigo_pais
    )
    argumentos = (direccion or None, cod_ciu, cod_depto, cod_pais, identidad)
    try:
        with transaccion_segura(codigo_empresa=-1) as (_conn, cursor):
            cursor.execute(
                """
                UPDATE EMPRESAS SET Direccion = ?, Municipio = ?, Departamento = ?, Pais = ?
                WHERE Identidad = ?
                """,
                argumentos,
            )
            return getattr(cursor, "rowcount", -999) > 0
    except Exception as exc:
        _notificar_error("actualizar ficha", exc)
        return False
