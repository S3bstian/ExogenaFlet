"""Consorcios de la empresa en sesión: lectura, CRUD y bandera ConsorciosActivo en EMPRESAS."""
from typing import Any, Dict, List, Optional

from core import session
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura


def _notificar_error(operacion: str, cause: BaseException) -> None:
    print(f"Consorcios ({operacion}): {cause}")


def _codigo_empresa_sesion() -> int:
    return session.EMPRESA_ACTUAL["codigo"]


def _fila_consorcio_a_dict(
    consorcio_id,
    identidad,
    nombre,
    tipo_documento,
    numero_fideicomiso,
    porcentaje,
    tipo_contrato,
) -> Dict[str, Any]:
    return {
        "id": int(consorcio_id) if consorcio_id is not None else None,
        "identidad": str(identidad).strip() if identidad is not None else "",
        "razonsocial": (nombre or "").strip(),
        "tipodocumento": (tipo_documento or "").strip(),
        "fidecomiso": int(numero_fideicomiso) if numero_fideicomiso is not None else 0,
        "porcentaje": float(porcentaje) if porcentaje is not None else 0.0,
        "tipo_contrato": (tipo_contrato or "").strip(),
    }


def _parametros_insert(consorcio: Dict[str, Any]) -> tuple:
    empresa = _codigo_empresa_sesion()
    return (
        int(consorcio.get("identidad")),
        empresa,
        consorcio.get("razonsocial", ""),
        consorcio.get("tipodocumento", ""),
        int(consorcio.get("fidecomiso") or 0),
        int(round(float(consorcio.get("porcentaje") or 0))),
        consorcio.get("tipo_contrato", ""),
    )


def _parametros_update(consorcio: Dict[str, Any]) -> tuple:
    return (
        consorcio.get("identidad", ""),
        consorcio.get("razonsocial", ""),
        consorcio.get("tipodocumento", ""),
        int(consorcio.get("fidecomiso") or 0),
        int(round(float(consorcio.get("porcentaje") or 0))),
        consorcio.get("tipo_contrato", ""),
        int(consorcio["id"]),
    )


def obtener_consorcios() -> List[Dict[str, Any]]:
    try:
        conexion = CNX_BDHelisa("EX", _codigo_empresa_sesion(), "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            """
            SELECT Id, Identidad, Nombre, TipoDocumento, NoFideicomiso, Porcentaje, TipoContrato
            FROM CONSORCIOS
            WHERE IdentidadEmpresa = ?
            ORDER BY Nombre, Id
            """,
            (_codigo_empresa_sesion(),),
        )
        filas = cursor.fetchall()
        cursor.close()
        conexion.close()
    except Exception as exc:
        _notificar_error("lectura lista", exc)
        return []

    registros: List[Dict[str, Any]] = []
    for fila in filas or []:
        registros.append(_fila_consorcio_a_dict(*fila))
    return registros


def verificar_consorcio_activo(identidad_empresa: int) -> bool:
    """Lee EMPRESAS.ConsorciosActivo para la identidad indicada ('S' = activo)."""
    try:
        conexion = CNX_BDHelisa("EX", -1, "sysdba")
        cursor = conexion.cursor()
        cursor.execute(
            "SELECT ConsorciosActivo FROM EMPRESAS WHERE Identidad = ?",
            (identidad_empresa,),
        )
        primera = cursor.fetchone()
        cursor.close()
        conexion.close()
        return primera[0] == "S" if primera else False
    except Exception as exc:
        _notificar_error("verificar ConsorciosActivo", exc)
        return False


def crear_consorcio(consorcio: Dict[str, Any]) -> Optional[int]:
    """Inserta en CONSORCIOS usando session.EMPRESA_ACTUAL para IdentidadEmpresa."""
    try:
        with transaccion_segura() as (_con, cursor):
            cursor.execute(
                """
                INSERT INTO CONSORCIOS (Identidad, IdentidadEmpresa, Nombre, TipoDocumento, NoFideicomiso, Porcentaje, TipoContrato)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING Id
                """,
                _parametros_insert(consorcio),
            )
            fila_retorno = cursor.fetchone()
            return int(fila_retorno[0]) if fila_retorno else None
    except Exception as exc:
        _notificar_error("insert", exc)
        return None


def actualizar_consorcio(consorcio: Dict[str, Any]) -> bool:
    if not consorcio or consorcio.get("id") is None:
        return False
    try:
        with transaccion_segura() as (_con, cursor):
            cursor.execute(
                """
                UPDATE CONSORCIOS
                   SET Identidad = ?,
                       Nombre = ?,
                       TipoDocumento = ?,
                       NoFideicomiso = ?,
                       Porcentaje = ?,
                       TipoContrato = ?
                 WHERE Id = ?
                """,
                _parametros_update(consorcio),
            )
            return (cursor.rowcount or 0) > 0
    except Exception as exc:
        _notificar_error(f"update id={consorcio.get('id')}", exc)
        return False


def eliminar_consorcio(consorcio_id: int) -> bool:
    try:
        with transaccion_segura() as (_con, cursor):
            cursor.execute("DELETE FROM CONSORCIOS WHERE Id = ?", (int(consorcio_id),))
            return (cursor.rowcount or 0) > 0
    except Exception as exc:
        _notificar_error(f"delete id={consorcio_id}", exc)
        return False
