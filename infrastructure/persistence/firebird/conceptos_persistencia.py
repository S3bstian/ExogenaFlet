"""Consultas compartidas sobre CONCEPTOS y FORMATOS (listado paginado e ID por código+formato)."""
from typing import Any, Dict, List, Optional, Tuple

from core import session
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa


def _notificar_error(operacion: str, cause: BaseException) -> None:
    print(f"CONCEPTOS ({operacion}): {cause}")


def _codigo_empresa_sesion() -> int:
    return session.EMPRESA_ACTUAL["codigo"]


def _fila_concepto_a_dict(fila: tuple) -> Dict[str, str]:
    (
        id_concepto,
        codigo,
        formato,
        descripcion,
        literal,
        cc_mm_id,
        cc_mm_nombre,
        cc_mm_valor,
        ext_id,
        ext_nombre,
        activo,
    ) = fila
    return {
        "id": str(id_concepto).strip() if id_concepto else "",
        "codigo": codigo.strip() if codigo else "",
        "formato": formato.strip() if formato else "",
        "descripcion": descripcion.strip() if descripcion else "",
        "literal": literal.strip() if literal else "",
        "cc_mm_identidad": cc_mm_id.strip() if cc_mm_id else "",
        "cc_mm_nombre": cc_mm_nombre.strip() if cc_mm_nombre else "",
        "cc_mm_valor": str(cc_mm_valor).strip() if cc_mm_valor else "",
        "exterior_identidad": ext_id.strip() if ext_id else "",
        "exterior_nombre": ext_nombre.strip() if ext_nombre else "",
        "activo": activo.strip() if activo else "",
    }


def _sql_y_params_conteo_y_lista(
    filtro: Optional[str], offset: int, limit: int
) -> Tuple[str, List[Any], str, List[Any]]:
    base_from = """
        FROM CONCEPTOS c
        LEFT JOIN FORMATOS f ON c.IdFormato = f.Id
    """
    select_cols = """
            SELECT FIRST ? SKIP ?
                    c.Id,
                    c.Codigo,
                    f.Formato,
                    c.Descripcion,
                    c.Literal,
                    c.CC_MM_Identidad,
                    c.CC_MM_Nombre,
                    c.CC_MM_Valor,
                    c.Exterior_identidad,
                    c.Exterior_Nombre,
                    c.Activo
    """
    sql_lista = select_cols + base_from
    sql_total = "SELECT COUNT(*) " + base_from
    params_lista: List[Any] = [limit, offset]
    params_total: List[Any] = []

    if filtro:
        patron = f"%{filtro}%"
        where = """
            WHERE UPPER(c.Codigo) LIKE UPPER(?)
               OR UPPER(f.Formato) LIKE UPPER(?)
               OR UPPER(c.Descripcion) LIKE UPPER(?)
        """
        sql_lista += where
        sql_total += where
        params_lista.extend([patron, patron, patron])
        params_total.extend([patron, patron, patron])

    sql_lista += " ORDER BY c.codigo, f.formato, c.Descripcion"
    return sql_total, params_total, sql_lista, params_lista


def consultar_conceptos_paginados(
    *,
    offset: int = 0,
    limit: int = 20,
    filtro: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], int]:
    if offset < 0 or limit < 0:
        raise ValueError("offset y limit deben ser valores no negativos")

    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        sql_total, params_total, sql_lista, params_lista = _sql_y_params_conteo_y_lista(
            filtro, offset, limit
        )
        cursor.execute(sql_total, tuple(params_total))
        fila_total = cursor.fetchone()
        total = int(fila_total[0]) if fila_total and fila_total[0] is not None else 0
        cursor.execute(sql_lista, params_lista)
        filas = cursor.fetchall()
        cursor.close()
        conexion.close()
    except Exception as exc:
        _notificar_error("listado paginado", exc)
        return [], 0

    return [_fila_concepto_a_dict(fila) for fila in filas], total


def consultar_id_concepto(codigo: str, formato: str) -> Optional[int]:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT c.Id
            FROM CONCEPTOS c
            INNER JOIN FORMATOS f ON f.Id = c.IdFormato
            WHERE c.Codigo = ? AND f.Formato = ?
            """,
            (codigo, formato),
        )
        fila = cursor.fetchone()
        cursor.close()
        conexion.close()
        return int(fila[0]) if fila else None
    except Exception as exc:
        _notificar_error(f"id por código={codigo} formato={formato}", exc)
        return None
