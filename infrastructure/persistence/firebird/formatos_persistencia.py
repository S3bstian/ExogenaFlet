"""
Consultas y mutaciones Firebird sobre la tabla FORMATOS.

Usado por repositorios y por la pantalla de formatos vía casos de uso.
"""
from typing import Any, Dict, List

from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from core import session


def consultar_formatos() -> List[tuple]:
    """
    Lista todos los formatos ordenados por código de formato.

    Retorna lista vacía ante error de conexión o consulta.
    """
    try:
        conn = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = conn.cursor()
        cur.execute(
            """
            SELECT
                Id, formato, descripcion, concepto, version, numenvio, fecenvio,
                fecinicial, fecfinal, valortotal, cantreg, activo
            FROM FORMATOS ORDER BY Formato
            """
        )
        resultado = cur.fetchall()
        cur.close()
        conn.close()
        return resultado
    except Exception as e:
        print(f"[ERROR] Error al obtener los formatos: {str(e)}")
        return []


def persistir_cambios_formato(campos: Dict[str, Any], formato: str) -> bool:
    """
    Persiste cabecera de formato (concepto inserción/actualización, envío, fechas).

    ``campos`` conserva el contrato legacy: valores en controles con atributo ``.value``.
    """
    try:
        with transaccion_segura() as (_conn, cur):
            concepto_valor = "01" if campos["concepto"].value == "Inserción" else "02"
            fecha_envio = f"{campos['fechaenvio'].value}T{campos['horaenvio'].value}"

            cur.execute(
                """
                UPDATE FORMATOS
                SET concepto = ?, numenvio = ?, fecenvio = ?, fecinicial = ?, fecfinal = ?
                WHERE formato = ?
                """,
                (
                    concepto_valor,
                    campos["numenvio"].value,
                    fecha_envio,
                    campos["fechainicial"].value,
                    campos["fechafinal"].value,
                    formato,
                ),
            )
        return True
    except Exception as e:
        print(f"[ERROR] Error al actualizar los valores del formato: {str(e)}")
        return False
