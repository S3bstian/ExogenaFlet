"""Lectura y actualización de cabecera en FORMATOS."""
from typing import Any, Dict, List

from core import session
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura


def _notificar_error(operacion: str, cause: BaseException) -> None:
    print(f"FORMATOS ({operacion}): {cause}")


def _codigo_empresa_sesion() -> int:
    return session.EMPRESA_ACTUAL["codigo"]


def consultar_formatos() -> List[tuple]:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT
                Id, formato, descripcion, concepto, version, numenvio, fecenvio,
                fecinicial, fecfinal, valortotal, cantreg, activo
            FROM FORMATOS ORDER BY Formato
            """
        )
        resultado = cursor.fetchall()
        cursor.close()
        conexion.close()
        return resultado
    except Exception as exc:
        _notificar_error("listado", exc)
        return []


def persistir_cambios_formato(campos: Dict[str, Any], codigo_formato: str) -> bool:
    """campos: dict de controles Flet con .value (contrato legacy de la pantalla)."""
    try:
        with transaccion_segura() as (_conn, cursor):
            concepto_codigo = "01" if campos["concepto"].value == "Inserción" else "02"
            fecha_envio_iso = f"{campos['fechaenvio'].value}T{campos['horaenvio'].value}"
            cursor.execute(
                """
                UPDATE FORMATOS
                SET concepto = ?, numenvio = ?, fecenvio = ?, fecinicial = ?, fecfinal = ?
                WHERE formato = ?
                """,
                (
                    concepto_codigo,
                    campos["numenvio"].value,
                    fecha_envio_iso,
                    campos["fechainicial"].value,
                    campos["fechafinal"].value,
                    codigo_formato,
                ),
            )
        return True
    except Exception as exc:
        _notificar_error(f"update formato={codigo_formato}", exc)
        return False
