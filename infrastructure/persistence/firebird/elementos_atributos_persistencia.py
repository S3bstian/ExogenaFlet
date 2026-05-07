"""
Fachada sobre elementos_persistencia con mutaciones (tipo global de elemento, guardar config atributo).
Mantiene nombres históricos para importadores legacy.
"""
import traceback
from typing import Any, Dict, List, Optional, Tuple, Union

from infrastructure.adapters.proteccion_firebird import transaccion_segura
from infrastructure.persistence.firebird.elementos_persistencia import (
    consultar_atributos,
    consultar_atributos_hoja_tercero_en_cursor,
    consultar_atributos_por_concepto,
    consultar_configuracion_atributo,
    consultar_elementos,
    consultar_formas_acumulado,
    consultar_nombres_atributos_valor_por_formato,
)


def obtener_elementos(
    concepto: Optional[Union[int, str]] = None,
    formato: Optional[int] = None,
) -> List[tuple]:
    return consultar_elementos(concepto=concepto, formato=formato)


def actualizar_tipo_global(elem_id: int, nuevo_tipo: str) -> bool:
    if nuevo_tipo not in ("T", "C", "B", "A"):
        raise ValueError(f"Tipo inválido: {nuevo_tipo}. Valores válidos: 'T', 'C', 'B', 'A'")
    try:
        with transaccion_segura() as (_conn, cursor):
            cursor.execute(
                "SELECT id FROM ATRIBUTOS WHERE idelemento = ?",
                (elem_id,),
            )
            for (id_atributo,) in cursor.fetchall():
                cursor.execute(
                    """
                    UPDATE ATRIBUTOS SET tipoacumulado = 0 WHERE id = ? AND clase = 1
                    """,
                    (id_atributo,),
                )
                cursor.execute(
                    "DELETE FROM CUENTAS_ATRIBUTOS WHERE idatributo = ?",
                    (id_atributo,),
                )
            cursor.execute(
                "UPDATE ELEMENTOS SET tipoacumuladog = ? WHERE id = ?",
                (nuevo_tipo, elem_id),
            )
        return True
    except Exception as exc:
        print(f"Error al actualizar tipo global: {exc}")
        return False


def obtener_atributos(
    elemento_id: Optional[int] = None,
    filtro: Optional[str] = None,
) -> List[tuple]:
    return consultar_atributos(elemento_id=elemento_id, filtro=filtro)


def obtener_atributos_por_concepto(concepto: Union[Dict[str, str], int, str]) -> List[tuple]:
    return consultar_atributos_por_concepto(concepto)


def obtener_nombres_atributos_valor_por_formato(formato_codigo: str) -> set:
    return consultar_nombres_atributos_valor_por_formato(formato_codigo)


def obtener_atributos_hoja_tercero(identidad_tercero: str, nombre_atributo: str, cur) -> List[tuple]:
    return consultar_atributos_hoja_tercero_en_cursor(cur, identidad_tercero, nombre_atributo)


def obtener_forma_acumulado(codigo_empresa: Optional[int] = None) -> List[tuple]:
    return consultar_formas_acumulado(codigo_empresa=codigo_empresa)


def obtener_configuracion_atributo(idatributo: int) -> Optional[Tuple[int, int, List[Dict[str, Any]]]]:
    return consultar_configuracion_atributo(idatributo)


def guardar_configuracion(
    atributo: Dict[str, Any],
    acumulado: int,
    tcuenta: int,
    cuentas: List[Dict[str, Any]],
) -> bool:
    if "Id" not in atributo:
        raise ValueError("El diccionario 'atributo' debe contener la clave 'Id'")
    atributo_id = atributo.get("Id")
    if not atributo_id:
        print("ERROR: El ID del atributo es None o vacío")
        return False

    try:
        with transaccion_segura() as (_con, cursor):
            acumulado_int = int(acumulado)
            tcuenta_int = int(tcuenta)
            try:
                cursor.execute(
                    """
                    UPDATE ATRIBUTOS
                    SET TipoAcumulado = ?, TipoContabilidad = ?
                    WHERE ID = ?
                    """,
                    (acumulado_int, tcuenta_int, atributo_id),
                )
                if cursor.rowcount == 0:
                    print(f"ERROR: No se encontró el atributo con ID {atributo_id} para actualizar")
                    return False
            except Exception as exc:
                print(f"ERROR al actualizar ATRIBUTOS: {type(exc).__name__}: {exc}")
                print(f"  - Atributo ID: {atributo_id}")
                print(f"  - TipoAcumulado: {acumulado_int}")
                print(f"  - TipoContabilidad: {tcuenta_int}")
                raise

            try:
                cursor.execute("DELETE FROM cuentas_atributos WHERE idatributo = ?", (atributo_id,))
            except Exception as exc:
                print(f"ERROR al eliminar cuentas existentes: {type(exc).__name__}: {exc}")
                print(f"  - Atributo ID: {atributo_id}")
                raise

            for indice, cuenta in enumerate(cuentas):
                if "id" not in cuenta:
                    print(f"ERROR: La cuenta en índice {indice} no tiene la clave 'id'")
                    print(f"  - Contenido de la cuenta: {cuenta}")
                    return False
                cuenta_id = cuenta["id"]
                if not cuenta_id:
                    print(f"ERROR: La cuenta en índice {indice} tiene ID None o vacío")
                    print(f"  - Contenido de la cuenta: {cuenta}")
                    return False
                try:
                    cursor.execute(
                        "INSERT INTO CUENTAS_ATRIBUTOS (idatributo, idcuenta) VALUES (?, ?)",
                        (atributo_id, cuenta_id),
                    )
                except Exception as exc:
                    print(f"ERROR al insertar cuenta en índice {indice}: {type(exc).__name__}: {exc}")
                    print(f"  - Atributo ID: {atributo_id}")
                    print(f"  - Cuenta ID: {cuenta_id}")
                    print(f"  - Contenido completo: {cuenta}")
                    raise
        return True
    except ValueError as exc:
        print(f"ERROR de validación guardando configuración: {exc}")
        return False
    except ConnectionError as exc:
        print(f"ERROR de conexión guardando configuración: {exc}")
        return False
    except Exception as exc:
        print(f"ERROR guardando configuración: {type(exc).__name__}: {exc}")
        print(f"  - Atributo ID: {atributo_id}")
        print(f"  - TipoAcumulado: {acumulado}")
        print(f"  - TipoContabilidad: {tcuenta}")
        print(f"  - Número de cuentas: {len(cuentas)}")
        traceback.print_exc()
        return False
