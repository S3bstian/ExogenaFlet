"""Lecturas sobre ELEMENTOS, ATRIBUTOS, CONCEPTOS, FORMAACUMULADO y HOJA_TRABAJO (cursor externo)."""
from typing import Any, Dict, List, Optional, Tuple, Union

from core import session
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.persistence.firebird.conceptos_persistencia import consultar_id_concepto


def _notificar_error(operacion: str, cause: BaseException) -> None:
    print(f"ELEMENTOS/ATRIBUTOS ({operacion}): {cause}")


def _codigo_empresa_sesion() -> int:
    return session.EMPRESA_ACTUAL["codigo"]


def _fila_cuenta_a_dict(fila: tuple) -> Dict[str, Any]:
    return {
        "id": fila[0],
        "codigo": fila[1],
        "nombre": fila[2],
        "naturaleza": fila[3],
        "tercero": fila[4],
        "saldoinicial": fila[5],
        "debitos": fila[6],
        "creditos": fila[7],
        "saldofinal": fila[8],
        "valorabsoluto": fila[9],
        "subcuentas": fila[10],
    }


def consultar_elementos(
    concepto: Optional[Union[int, str]] = None,
    formato: Optional[int] = None,
) -> List[tuple]:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        sql = """
            SELECT e.ID, e.ETIQUETA, f.formato, e.idconcepto, e.tipoacumuladog
            FROM ELEMENTOS e
            LEFT JOIN FORMATOS f ON f.id = e.idformato
        """
        params: List[Any] = []
        condiciones: List[str] = []
        if concepto:
            condiciones.append("e.IDCONCEPTO = ?")
            params.append(concepto)
        if formato:
            condiciones.append("f.ID = ?")
            params.append(formato)
        condiciones.append("e.IDPADRE <> 0")
        if condiciones:
            sql += " WHERE " + " AND ".join(condiciones)
        cursor.execute(sql, tuple(params))
        resultado = cursor.fetchall()
        cursor.close()
        conexion.close()
        return resultado
    except Exception as exc:
        _notificar_error("consultar_elementos", exc)
        return []


def consultar_atributos(
    elemento_id: Optional[int] = None,
    filtro: Optional[str] = None,
) -> List[tuple]:
    if elemento_id is None and filtro is None:
        raise ValueError("Debe proporcionar elemento_id o filtro")
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        if elemento_id is None:
            cursor.execute(
                """
                SELECT ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO
                FROM ATRIBUTOS
                WHERE NOMBRE = ?
                """,
                (filtro,),
            )
        else:
            cursor.execute(
                """
                SELECT ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO
                FROM ATRIBUTOS
                WHERE IDELEMENTO = ?
                """,
                (elemento_id,),
            )
        resultado = cursor.fetchall()
        cursor.close()
        conexion.close()
        return resultado
    except Exception as exc:
        _notificar_error("consultar_atributos", exc)
        return []


def consultar_formas_acumulado(codigo_empresa: Optional[int] = None) -> List[tuple]:
    try:
        if codigo_empresa is None:
            if not session.EMPRESA_ACTUAL:
                raise ValueError("No hay empresa seleccionada en session.EMPRESA_ACTUAL")
            codigo_empresa = session.EMPRESA_ACTUAL["codigo"]
        conexion = CNX_BDHelisa("EX", codigo_empresa, "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT Id, Nombre, Descripcion, Mostrar_cuentas, "GLOBAL"
            FROM FORMAACUMULADO
            ORDER BY "GLOBAL", Id
            """
        )
        data = cursor.fetchall()
        cursor.close()
        conexion.close()
        return data
    except Exception as exc:
        _notificar_error("consultar_formas_acumulado", exc)
        return []


def consultar_atributos_por_concepto(
    concepto: Union[Dict[str, str], int, str],
) -> List[tuple]:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
    except Exception as exc:
        _notificar_error("conectar atributos_por_concepto", exc)
        return []

    try:
        if isinstance(concepto, dict) and "codigo" in concepto and "formato" in concepto:
            id_concepto = consultar_id_concepto(concepto["codigo"], concepto["formato"])
            if id_concepto is None:
                print(f"Concepto no encontrado: {concepto['codigo']} - {concepto['formato']}")
                return []
            where_clause = "c.ID = ?"
            param = id_concepto
        elif isinstance(concepto, (int, str)) and str(concepto).isdigit():
            where_clause = "c.ID = ?"
            param = int(concepto)
        else:
            where_clause = "c.CODIGO = ?"
            param = concepto

        cursor.execute(
            f"""
            SELECT a.ID, a.NOMBRE, a.DESCRIPCION, a.CLASE, a.TIPOACUMULADO
            FROM ATRIBUTOS a
            INNER JOIN ELEMENTOS e ON e.ID = a.IDELEMENTO
            INNER JOIN CONCEPTOS c ON c.ID = e.IDCONCEPTO
            WHERE {where_clause}
            ORDER BY a.NOMBRE
            """,
            (param,),
        )
        resultado = cursor.fetchall()
        cursor.close()
        conexion.close()
        return resultado
    except Exception as exc:
        _notificar_error("atributos_por_concepto", exc)
        try:
            cursor.close()
            conexion.close()
        except Exception:
            pass
        return []


def consultar_configuracion_atributo(
    idatributo: int,
) -> Optional[Tuple[int, int, List[Dict[str, Any]]]]:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
    except Exception as exc:
        _notificar_error("conectar config_atributo", exc)
        return None

    tipo_acumulado = None
    tipo_cuenta = None
    cuentas: List[Dict[str, Any]] = []

    try:
        cursor.execute(
            """
            SELECT tipoacumulado, tipocontabilidad
            FROM ATRIBUTOS
            WHERE Id = ?
            """,
            (idatributo,),
        )
        fila_tipo = cursor.fetchone()
        if fila_tipo:
            tipo_acumulado, tipo_cuenta = fila_tipo
    except Exception as exc:
        _notificar_error(f"tipo atributo id={idatributo}", exc)
        cursor.close()
        conexion.close()
        return None

    if tipo_acumulado in [21, 50]:
        cursor.close()
        conexion.close()
        return (tipo_acumulado, tipo_cuenta, [])

    try:
        cursor.execute(
            """
            SELECT idcuenta FROM CUENTAS_ATRIBUTOS WHERE idatributo = ?
            """,
            (idatributo,),
        )
        id_cuentas = cursor.fetchall() or []
        nombre_tabla_cuentas = "Cuentas_trib" if tipo_cuenta == 1 else "Cuentas_cont"
        for (id_cuenta,) in id_cuentas:
            try:
                cursor.execute(
                    f"""
                    SELECT id, codigo, nombre, naturaleza, tercero, saldoinicial,
                           debitos, creditos, saldofinal, valorabsoluto, subcuentas
                    FROM {nombre_tabla_cuentas} WHERE ID = ?
                    """,
                    (id_cuenta,),
                )
                for fila_cuenta in cursor.fetchall() or []:
                    cuentas.append(_fila_cuenta_a_dict(fila_cuenta))
            except Exception as exc:
                _notificar_error(f"cuenta id={id_cuenta}", exc)
    except Exception as exc:
        _notificar_error("ids CUENTAS_ATRIBUTOS", exc)

    cursor.close()
    conexion.close()
    return (tipo_acumulado, tipo_cuenta, cuentas)


def consultar_nombres_atributos_valor_por_formato(formato_codigo: str) -> set:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT a.NOMBRE
            FROM ATRIBUTOS a
            INNER JOIN ELEMENTOS e ON e.ID = a.IDELEMENTO
            INNER JOIN CONCEPTOS c ON c.ID = e.IDCONCEPTO
            INNER JOIN FORMATOS f ON f.ID = c.IDFORMATO
            WHERE f.FORMATO = ? AND a.CLASE = 1
            """,
            (str(formato_codigo),),
        )
        resultado = {str(fila[0]).strip() for fila in cursor.fetchall() if fila and fila[0]}
        cursor.close()
        conexion.close()
        return resultado
    except Exception as exc:
        _notificar_error("nombres valor por formato", exc)
        return set()


def consultar_atributos_hoja_tercero_en_cursor(
    cur: Any,
    identidad_tercero: str,
    nombre_atributo: str,
) -> List[tuple]:
    """Usa el cursor del llamador; si cur es falsy abre conexión propia (legacy)."""
    cursor_activo = cur
    if not cursor_activo:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor_activo = conexion.cursor()
    try:
        cursor_activo.execute(
            """
            SELECT a.ID, a.NOMBRE, a.DESCRIPCION, a.CLASE, a.TIPOACUMULADO
            FROM HOJA_TRABAJO ht
            INNER JOIN ATRIBUTOS a ON a.ID = ht.IDATRIBUTO
            WHERE ht.IDENTIDADTERCERO = ? AND a.NOMBRE = ?
            """,
            (identidad_tercero, nombre_atributo),
        )
        return cursor_activo.fetchall()
    except Exception as exc:
        _notificar_error("atributos hoja tercero", exc)
        return []
