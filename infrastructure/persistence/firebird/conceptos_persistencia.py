"""
Consultas Firebird compartidas sobre CONCEPTOS + FORMATOS.

Centraliza consultas de concepto (listado paginado e ID por código+formato)
usadas por repositorios y `hoja_trabajo_persistencia`.
"""
from typing import Any, Dict, List, Optional, Tuple

from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from core import session


def consultar_conceptos_paginados(
    *,
    offset: int = 0,
    limit: int = 20,
    filtro: Optional[str] = None,
) -> Tuple[List[Dict[str, str]], int]:
    """
    Lista conceptos con formato asociado, paginada, con conteo total bajo el mismo filtro.

    Retorna ([], 0) ante error de conexión o consulta.
    """
    if offset < 0 or limit < 0:
        raise ValueError("offset y limit deben ser valores no negativos")

    total = 0
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()

        sql = """
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
            FROM CONCEPTOS c
            LEFT JOIN FORMATOS f ON c.IdFormato = f.Id
        """

        params: List[Any] = [limit, offset]

        if filtro:
            filtro_param = f"%{filtro}%"
            sql += """
                WHERE UPPER(c.Codigo) LIKE UPPER(?)
                   OR UPPER(f.Formato) LIKE UPPER(?)
                   OR UPPER(c.Descripcion) LIKE UPPER(?)
            """
            params.extend([filtro_param, filtro_param, filtro_param])

        sql += " ORDER BY c.codigo, f.formato, c.Descripcion"

        sql_total = """
            SELECT COUNT(*)
            FROM CONCEPTOS c
            LEFT JOIN FORMATOS f ON c.IdFormato = f.Id
        """
        params_total: List[Any] = []
        if filtro:
            filtro_param = f"%{filtro}%"
            sql_total += """
                WHERE UPPER(c.Codigo) LIKE UPPER(?)
                   OR UPPER(f.Formato) LIKE UPPER(?)
                   OR UPPER(c.Descripcion) LIKE UPPER(?)
            """
            params_total.extend([filtro_param, filtro_param, filtro_param])

        cur.execute(sql_total, tuple(params_total))
        row_total = cur.fetchone()
        total = int(row_total[0]) if row_total and row_total[0] is not None else 0

        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Exception as e:
        print(f"[ERROR] Error al obtener los conceptos: {str(e)}")
        return [], 0

    conceptos: List[Dict[str, str]] = []
    for r in rows:
        conceptos.append(
            {
                "id": str(r[0]).strip() if r[0] else "",
                "codigo": r[1].strip() if r[1] else "",
                "formato": r[2].strip() if r[2] else "",
                "descripcion": r[3].strip() if r[3] else "",
                "literal": r[4].strip() if r[4] else "",
                "cc_mm_identidad": r[5].strip() if r[5] else "",
                "cc_mm_nombre": r[6].strip() if r[6] else "",
                "cc_mm_valor": str(r[7]).strip() if r[7] else "",
                "exterior_identidad": r[8].strip() if r[8] else "",
                "exterior_nombre": r[9].strip() if r[9] else "",
                "activo": r[10].strip() if r[10] else "",
            }
        )
    return conceptos, total


def consultar_id_concepto(codigo: str, formato: str) -> Optional[int]:
    """
    Resuelve el ID numérico de CONCEPTOS para un par código + código de formato.

    Retorna None si no existe fila o ante error de conexión/consulta.
    """
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
        cur.execute(
            """
            SELECT c.Id
            FROM CONCEPTOS c
            INNER JOIN FORMATOS f ON f.Id = c.IdFormato
            WHERE c.Codigo = ? AND f.Formato = ?
            """,
            (codigo, formato),
        )
        row = cur.fetchone()
        cur.close()
        con.close()
        return int(row[0]) if row else None
    except Exception as e:
        print(f"[ERROR] Error obteniendo ID de concepto {codigo} - {formato}: {e}")
        return None
