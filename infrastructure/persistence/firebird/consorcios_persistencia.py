"""
Persistencia Firebird: consorcios de la empresa actual (CRUD y verificación activo).
"""
from typing import Optional, List, Dict, Any
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from core import session


def obtener_consorcios() -> List[Dict[str, Any]]:
    """
    Obtiene todos los consorcios asociados a la empresa actual.
    
    Returns
    -------
    List[Dict[str, Any]]
        Lista de diccionarios, cada uno con las siguientes claves:
        - 'id': ID del consorcio
        - 'identidad': Identidad del consorcio
        - 'razonsocial': Razón social o nombre del consorcio
        - 'tipodocumento': Tipo de documento
        - 'fidecomiso': Número de fideicomiso
        - 'porcentaje': Porcentaje de participación
        - 'tipo_contrato': Tipo de contrato
        Lista vacía si hay error o no hay consorcios.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    """
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()
        cur.execute("""
            SELECT Id, Identidad, Nombre, TipoDocumento, NoFideicomiso, Porcentaje, TipoContrato
            FROM CONSORCIOS
            WHERE IdentidadEmpresa = ?
            ORDER BY Nombre, Id
        """, (session.EMPRESA_ACTUAL["codigo"],))
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Exception as e:
        print(f"Error leyendo Consorcios: {str(e)}")
        return []
        
    data = []
    for r in rows or []:
        data.append({
            "id": int(r[0]) if r[0] is not None else None,
            "identidad": (str(r[1]).strip() if r[1] is not None else ""),
            "razonsocial": (r[2] or "").strip(),
            "tipodocumento": (r[3] or "").strip(),
            "fidecomiso": int(r[4]) if r[4] is not None else 0,
            "porcentaje": float(r[5]) if r[5] is not None else 0.0,
            "tipo_contrato": (r[6] or "").strip(),
        })
    return data


def verificar_consorcio_activo(identidad: int) -> bool:
    """
    Verifica si la empresa actual tiene consorcios activos para una identidad específica.
    
    Parameters
    ----------
    identidad : int
        Identidad a verificar.
    
    Returns
    -------
    bool
        True si la empresa tiene consorcios activos para esa identidad.
        False si no hay consorcios activos o hay error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    """
    try:
        con = CNX_BDHelisa("EX", -1, "sysdba")
        cur = con.cursor()
        cur.execute("""
            SELECT ConsorciosActivo
            FROM EMPRESAS
            WHERE Identidad = ?
        """, (identidad,))
        row = cur.fetchone()
        cur.close()
        con.close()
        return row[0] == 'S' if row else False
    except Exception as e:
        print(f"Error verificando consorcio activo: {e}")
        return False


def crear_consorcio(consorcio: Dict[str, Any]) -> Optional[int]:
    """
    Crea un nuevo consorcio en la base de datos.
    
    Parameters
    ----------
    consorcio : Dict[str, Any]
        Diccionario con los datos del consorcio. Debe contener:
        - 'identidad': Identidad del consorcio
        - 'razonsocial': Razón social o nombre (opcional, default: "")
        - 'tipodocumento': Tipo de documento (opcional, default: "")
        - 'fidecomiso': Número de fideicomiso (opcional, default: 0)
        - 'porcentaje': Porcentaje de participación (opcional, default: 0)
        - 'tipo_contrato': Tipo de contrato (opcional, default: "")
    
    Returns
    -------
    Optional[int]
        ID del consorcio creado si se insertó correctamente.
        None si hubo error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    
    Notes
    -----
    La identidad de la empresa se toma automáticamente de session.EMPRESA_ACTUAL.
    """
    try:
        with transaccion_segura() as (con, cur):
            cur.execute("""
                INSERT INTO CONSORCIOS (Identidad, IdentidadEmpresa, Nombre, TipoDocumento, NoFideicomiso, Porcentaje, TipoContrato)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                RETURNING Id
            """, (
                int(consorcio.get("identidad")),
                session.EMPRESA_ACTUAL["codigo"],
                consorcio.get("razonsocial", ""),
                consorcio.get("tipodocumento", ""),
                int(consorcio.get("fidecomiso") or 0),
                int(round(float(consorcio.get("porcentaje") or 0))),
                consorcio.get("tipo_contrato", ""),
            ))
            row = cur.fetchone()
            new_id = int(row[0]) if row else None
            # Commit automático si todo sale bien
        return new_id
    except Exception as e:
        print(f"Error insertando Consorcio: {e}")
        return None


def actualizar_consorcio(consorcio: Dict[str, Any]) -> bool:
    """
    Actualiza un consorcio existente por su ID.
    
    Parameters
    ----------
    consorcio : Dict[str, Any]
        Diccionario con los datos del consorcio a actualizar. Debe contener:
        - 'id': ID del consorcio a actualizar (requerido)
        - 'identidad': Identidad del consorcio (opcional)
        - 'razonsocial': Razón social (opcional)
        - 'tipodocumento': Tipo de documento (opcional)
        - 'fidecomiso': Número de fideicomiso (opcional)
        - 'porcentaje': Porcentaje de participación (opcional)
        - 'tipo_contrato': Tipo de contrato (opcional)
    
    Returns
    -------
    bool
        True si se actualizó correctamente (al menos una fila afectada).
        False si hubo error, el consorcio no existe o no se proporcionó 'id'.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si el diccionario no contiene la clave 'id'.
    """
    if not consorcio or consorcio.get("id") is None:
        return False
    
    try:
        with transaccion_segura() as (con, cur):
            cur.execute("""
                UPDATE CONSORCIOS
                   SET Identidad = ?,
                       Nombre = ?,
                       TipoDocumento = ?,
                       NoFideicomiso = ?,
                       Porcentaje = ?,
                       TipoContrato = ?
                 WHERE Id = ?
            """, (
                consorcio.get("identidad", ""),
                consorcio.get("razonsocial", ""),
                consorcio.get("tipodocumento", ""),
                int(consorcio.get("fidecomiso") or 0),
                int(round(float(consorcio.get("porcentaje") or 0))),
                consorcio.get("tipo_contrato", ""),
                int(consorcio["id"]),
            ))
            ok = (cur.rowcount or 0) > 0
            # Commit automático si todo sale bien
        return ok
    except Exception as e:
        print(f"Error actualizando Consorcio {consorcio.get('id')}: {str(e)}")
        return False


def eliminar_consorcio(consorcio_id: int) -> bool:
    """
    Elimina un consorcio por su ID.
    
    Parameters
    ----------
    consorcio_id : int
        ID del consorcio a eliminar.
    
    Returns
    -------
    bool
        True si se eliminó correctamente (al menos una fila afectada).
        False si hubo error o el consorcio no existe.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    """
    try:
        with transaccion_segura() as (con, cur):
            cur.execute("DELETE FROM CONSORCIOS WHERE Id = ?", (int(consorcio_id),))
            ok = (cur.rowcount or 0) > 0
            # Commit automático si todo sale bien
        return ok
    except Exception as e:
        print(f"Error eliminando Consorcio {consorcio_id}: {str(e)}")
        return False
