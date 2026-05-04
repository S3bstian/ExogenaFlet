"""
Consultas Firebird de solo lectura sobre ELEMENTOS, ATRIBUTOS, CONCEPTOS y FORMAACUMULADO.

Incluye atributos por concepto, configuración con cuentas, nombres valor por formato (XML)
y lecturas sobre ``HOJA_TRABAJO`` con cursor externo. Compartidas por repositorios y
``elementos_atributos_persistencia`` (API legacy).
"""
from typing import Any, Dict, List, Optional, Tuple, Union

from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from core import session

from infrastructure.persistence.firebird.conceptos_persistencia import consultar_id_concepto


def consultar_elementos(
    concepto: Optional[Union[int, str]] = None,
    formato: Optional[int] = None,
) -> List[tuple]:
    """Lista elementos (con formato y concepto) aplicando filtros opcionales."""
    try:
        conn = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = conn.cursor()
        sql = """
            SELECT e.ID, e.ETIQUETA, f.formato, e.idconcepto, e.tipoacumuladog
            FROM ELEMENTOS e
            LEFT JOIN FORMATOS f ON f.id = e.idformato
        """
        params = []
        conditions = []

        if concepto:
            conditions.append("e.IDCONCEPTO = ?")
            params.append(concepto)

        if formato:
            conditions.append("f.ID = ?")
            params.append(formato)

        conditions.append("e.IDPADRE <> 0")

        if conditions:
            sql += " WHERE " + " AND ".join(conditions)

        cur.execute(sql, tuple(params))
        resultado = cur.fetchall()
        cur.close()
        conn.close()
        return resultado
    except Exception as e:
        print(f"Error obteniendo elementos: {e}")
        return []


def consultar_atributos(
    elemento_id: Optional[int] = None,
    filtro: Optional[str] = None,
) -> List[tuple]:
    """Lista atributos por elemento o por nombre exacto (``filtro``)."""
    if elemento_id is None and filtro is None:
        raise ValueError("Debe proporcionar elemento_id o filtro")

    try:
        conn = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = conn.cursor()

        if elemento_id is None:
            cur.execute(
                """
                SELECT ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO
                FROM ATRIBUTOS
                WHERE NOMBRE = ?
                """,
                (filtro,),
            )
        else:
            cur.execute(
                """
                SELECT ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO
                FROM ATRIBUTOS
                WHERE IDELEMENTO = ?
                """,
                (elemento_id,),
            )

        resultado = cur.fetchall()
        cur.close()
        conn.close()
        return resultado
    except Exception as e:
        print(f"Error obteniendo atributos: {e}")
        return []


def consultar_formas_acumulado(codigo_empresa: Optional[int] = None) -> List[tuple]:
    """
    Lee FORMAACUMULADO desde la BD indicada por ``codigo_empresa`` (o empresa en sesión).

    ``codigo_empresa``: None usa ``session.EMPRESA_ACTUAL``; -2/-1/0..99 según convención Helisa.
    """
    try:
        if codigo_empresa is None:
            if not session.EMPRESA_ACTUAL:
                raise ValueError("No hay empresa seleccionada en session.EMPRESA_ACTUAL")
            codigo_empresa = session.EMPRESA_ACTUAL["codigo"]
        conn = CNX_BDHelisa("EX", codigo_empresa, "sysdba")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT Id, Nombre, Descripcion, Mostrar_cuentas, "GLOBAL"
            FROM FORMAACUMULADO
            ORDER BY "GLOBAL", Id
            """
        )
        data = cur.fetchall()
        cur.close()
        conn.close()
        return data
    except Exception as e:
        print(f"Error obteniendo FormaAcumulado: {e}")
        return []


def consultar_atributos_por_concepto(
    concepto: Union[Dict[str, str], int, str],
) -> List[tuple]:
    """Atributos ligados a un concepto (dict código+formato, ID numérico o código legacy)."""
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
    except Exception as e:
        print(f"Error conectando con bd: {e}")
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

        cur.execute(
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

        resultado = cur.fetchall()
        cur.close()
        con.close()
        return resultado
    except Exception as e:
        print(f"Error obteniendo atributos del concepto: {e}")
        try:
            cur.close()
            con.close()
        except Exception:
            pass
        return []

def consultar_configuracion_atributo(
    idatributo: int,
) -> Optional[Tuple[int, int, List[Dict[str, Any]]]]:
    """Tipo de acumulado, contabilidad y cuentas asociadas a un atributo (lectura)."""
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
    except Exception as e:
        print(f"Error conectando con bd: {e}")
        return None

    tipo_acumulado = None
    tipo_cuenta = None
    cuentas: List[Dict[str, Any]] = []

    try:
        cur.execute(
            """
            SELECT tipoacumulado, tipocontabilidad
            FROM ATRIBUTOS
            WHERE Id = ?
            """,
            (idatributo,),
        )
        row = cur.fetchone()
        if row:
            tipo_acumulado, tipo_cuenta = row
    except Exception as e:
        print(f"Error obteniendo el tipoacumulado de atributo: {e}")
        cur.close()
        con.close()
        return None

    if tipo_acumulado in [21, 50]:
        cur.close()
        con.close()
        return (tipo_acumulado, tipo_cuenta, [])

    try:
        cur.execute(
            """
            SELECT idcuenta FROM CUENTAS_ATRIBUTOS WHERE idatributo = ?
            """,
            (idatributo,),
        )
        idcuentas = cur.fetchall() or []

        for c in idcuentas:
            try:
                tabla = "Cuentas_trib" if tipo_cuenta == 1 else "Cuentas_cont"
                cur.execute(
                    f"""
                    SELECT id, codigo, nombre, naturaleza, tercero, saldoinicial,
                           debitos, creditos, saldofinal, valorabsoluto, subcuentas
                    FROM {tabla} WHERE ID = ?
                    """,
                    (c[0],),
                )

                rows = cur.fetchall() or []
                for r in rows:
                    cuentas.append(
                        {
                            "id": r[0],
                            "codigo": r[1],
                            "nombre": r[2],
                            "naturaleza": r[3],
                            "tercero": r[4],
                            "saldoinicial": r[5],
                            "debitos": r[6],
                            "creditos": r[7],
                            "saldofinal": r[8],
                            "valorabsoluto": r[9],
                            "subcuentas": r[10],
                        }
                    )
            except Exception as e:
                print(f"Error obteniendo cuentas de la configuración de atributo: {e}")
    except Exception as e:
        print(f"Error obteniendo id de las cuentas de la relacion al atributo: {e}")

    cur.close()
    con.close()
    return (tipo_acumulado, tipo_cuenta, cuentas)

def consultar_nombres_atributos_valor_por_formato(formato_codigo: str) -> set:
    """
    Nombres de atributos con CLASE=1 (valor/monto) para un código de formato.

    Usado en generación XML para formatear montos sin decimales ficticios.
    """
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
        cur.execute(
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
        resultado = {str(r[0]).strip() for r in cur.fetchall() if r and r[0]}
        cur.close()
        con.close()
        return resultado
    except Exception as e:
        print(f"Error obteniendo atributos valor por formato: {e}")
        return set()


def consultar_atributos_hoja_tercero_en_cursor(
    cur: Any,
    identidad_tercero: str,
    nombre_atributo: str,
) -> List[tuple]:
    """
    Atributos de hoja para una identidad y nombre de atributo, usando el cursor del llamador.

    No abre conexión ni hace commit; pensado para uso dentro de ``transaccion_segura``.
    """
    if not cur:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
    try:
        cur.execute(
            """
            SELECT a.ID, a.NOMBRE, a.DESCRIPCION, a.CLASE, a.TIPOACUMULADO
            FROM HOJA_TRABAJO ht
            INNER JOIN ATRIBUTOS a ON a.ID = ht.IDATRIBUTO
            WHERE ht.IDENTIDADTERCERO = ? AND a.NOMBRE = ?
            """,
            (identidad_tercero, nombre_atributo),
        )
        return cur.fetchall()
    except Exception as e:
        print(f"Error obteniendo atributos de hoja para tercero: {e}")
        return []
