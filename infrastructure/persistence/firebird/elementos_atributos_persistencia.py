"""
Elementos, atributos y configuración: delegación en ``elementos_persistencia``,
mutaciones y consultas compuestas (transacciones).

``elementos_atributos`` reexporta por compatibilidad; preferir este módulo en adaptadores.
"""
from typing import Optional, List, Dict, Any, Union, Tuple
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
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
from core import session


def obtener_elementos(concepto: Optional[Union[int, str]] = None, formato: Optional[int] = None) -> List[tuple]:
    """
    Obtiene elementos filtrados por concepto y/o formato.
    
    Parameters
    ----------
    concepto : Optional[Union[int, str]], optional
        ID del concepto para filtrar. Si se proporciona, solo retorna elementos de ese concepto.
    formato : Optional[int], optional
        ID del formato para filtrar. Si se proporciona, solo retorna elementos de ese formato.
    
    Returns
    -------
    List[tuple]
        Lista de tuplas con (ID, ETIQUETA, formato, idconcepto, tipoacumuladog).
        Lista vacía si hay error o no hay resultados.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    """
    return consultar_elementos(concepto=concepto, formato=formato)


def actualizar_tipo_global(elem_id: int, nuevo_tipo: str) -> bool:
    """
    Actualiza el tipo global de acumulación de un elemento y limpia sus atributos relacionados.
    
    Actualiza el tipoacumuladog del elemento y resetea los tipoacumulado de sus atributos
    de clase 1, además de eliminar las relaciones con cuentas.
    
    Parameters
    ----------
    elem_id : int
        ID del elemento a actualizar.
    nuevo_tipo : str
        Nuevo tipo de acumulación global. Valores válidos: 'T', 'C', 'B', 'A'.
    
    Returns
    -------
    bool
        True si se actualizó correctamente.
        False si hubo error en alguna operación.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si nuevo_tipo no es uno de los valores válidos.
    
    Notes
    -----
    Esta operación es atómica: si falla cualquier paso, se revierte todo.
    """
    if nuevo_tipo not in ['T', 'C', 'B', 'A']:
        raise ValueError(f"Tipo inválido: {nuevo_tipo}. Valores válidos: 'T', 'C', 'B', 'A'")
    
    try:
        with transaccion_segura() as (conn, cur):
            # Obtener IDs de atributos del elemento
            cur.execute("""
                SELECT id
                FROM ATRIBUTOS
                WHERE idelemento = ?
            """, (elem_id,))
            rows = cur.fetchall()
            
            # Resetear tipoacumulado y eliminar cuentas de cada atributo de clase 1
            for attr_row in rows:
                attr_id = attr_row[0]
                # Resetear tipoacumulado para atributos de clase 1
                cur.execute("""
                    UPDATE ATRIBUTOS
                    SET tipoacumulado = 0
                    WHERE id = ? AND clase = 1
                """, (attr_id,))
                
                # Eliminar relaciones con cuentas
                cur.execute("""
                    DELETE FROM CUENTAS_ATRIBUTOS
                    WHERE idatributo = ?
                """, (attr_id,))
            
            # Actualizar tipo global del elemento
            cur.execute("""
                UPDATE ELEMENTOS
                SET tipoacumuladog = ?
                WHERE id = ?
            """, (nuevo_tipo, elem_id))
            
            # Commit automático si todo sale bien
        return True
    except Exception as e:
        print(f"Error al actualizar tipo global: {e}")
        return False


def obtener_atributos(elemento_id: Optional[int] = None, filtro: Optional[str] = None) -> List[tuple]:
    """
    Obtiene atributos filtrados por elemento o nombre.
    
    Parameters
    ----------
    elemento_id : Optional[int], optional
        ID del elemento. Si se proporciona, retorna todos los atributos de ese elemento.
    filtro : Optional[str], optional
        Nombre del atributo. Solo se usa si elemento_id es None.
        Si se proporciona, busca atributos por nombre exacto.
    
    Returns
    -------
    List[tuple]
        Lista de tuplas con (ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO).
        Lista vacía si hay error o no hay resultados.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si ambos elemento_id y filtro son None.
    """
    return consultar_atributos(elemento_id=elemento_id, filtro=filtro)


def obtener_atributos_por_concepto(concepto: Union[Dict[str, str], int, str]) -> List[tuple]:
    """
    Obtiene los atributos asociados a un concepto.
    
    Parameters
    ----------
    concepto : Union[Dict[str, str], int, str]
        Puede ser:
        - Dict con 'codigo' y 'formato': {"codigo": "...", "formato": "..."}
        - ID de concepto (int o str numérico)
        - Código de concepto (str) - para compatibilidad, puede fallar si hay duplicados
    
    Returns
    -------
    List[tuple]
        Lista de tuplas con (ID, NOMBRE, DESCRIPCION, CLASE, TIPOACUMULADO).
        Lista vacía si hay error, concepto no encontrado o no hay atributos.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    """
    return consultar_atributos_por_concepto(concepto)


def obtener_nombres_atributos_valor_por_formato(formato_codigo: str) -> set:
    """
    Obtiene los NOMBRE de atributos con CLASE=1 (valor/monto) para un formato.
    Sirve para saber qué atributos formatear sin decimales en XML (quitar ,00).
    """
    return consultar_nombres_atributos_valor_por_formato(formato_codigo)


def obtener_atributos_hoja_tercero(identidad_tercero: str, nombre_atributo: str, cur) -> List[tuple]:
    """
    Obtiene atributos de hoja de trabajo para un tercero y nombre de atributo.
    Usado dentro de transacciones; recibe cursor abierto. No cierra la conexión ni el cursor.
    """
    return consultar_atributos_hoja_tercero_en_cursor(
        cur, identidad_tercero, nombre_atributo
    )


def obtener_forma_acumulado(codigo_empresa: Optional[int] = None) -> List[tuple]:
    """
    Obtiene todas las formas de acumulado disponibles.
    
    Parameters
    ----------
    codigo_empresa : Optional[int], optional
        Código de empresa. Si es None, usa session.EMPRESA_ACTUAL["codigo"].
        -2 = Base de datos XX, -1 = Base de datos Global, 0..99 = Base de datos de la empresa.
    
    Returns
    -------
    List[tuple]
        Lista de tuplas con (Id, Nombre, Descripcion, Mostrar_cuentas, Global).
        Lista vacía si hay error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL y codigo_empresa es None.
    """
    return consultar_formas_acumulado(codigo_empresa=codigo_empresa)


def obtener_configuracion_atributo(idatributo: int) -> Optional[Tuple[int, int, List[Dict[str, Any]]]]:
    """
    Obtiene la configuración completa de un atributo incluyendo sus cuentas asociadas.
    
    Parameters
    ----------
    idatributo : int
        ID del atributo del cual obtener la configuración.
    
    Returns
    -------
    Optional[Tuple[int, int, List[Dict[str, Any]]]]
        Tupla con:
        - tipoacumulado: ID del tipo de acumulado
        - tipocontabilidad: Tipo de contabilidad (1=Tributario, 2=Contable)
        - cuentas: Lista de diccionarios con información de cuentas asociadas
        None si hay error o el atributo no existe.
    
    Cada diccionario de cuenta contiene:
        - 'id': ID de la cuenta
        - 'codigo': Código de la cuenta
        - 'nombre': Nombre de la cuenta
        - 'naturaleza': Naturaleza de la cuenta
        - 'tercero': ID del tercero asociado
        - 'saldoinicial': Saldo inicial
        - 'debitos': Débitos
        - 'creditos': Créditos
        - 'saldofinal': Saldo final
        - 'valorabsoluto': Valor absoluto ('S' o 'N')
        - 'subcuentas': Subcuentas
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    
    Notes
    -----
    Si tipoacumulado es 21 o 50, retorna lista de cuentas vacía (no necesita cuentas).
    """
    return consultar_configuracion_atributo(idatributo)


def guardar_configuracion(
    atributo: Dict[str, Any],
    acumulado: int,
    tcuenta: int,
    cuentas: List[Dict[str, Any]]
) -> bool:
    """
    Guarda la configuración completa de un atributo.
    
    Actualiza el tipoacumulado y tipocontabilidad del atributo, elimina todas las
    cuentas actuales asociadas e inserta las nuevas cuentas seleccionadas.
    Todas las operaciones se ejecutan en una sola transacción atómica.
    
    Parameters
    ----------
    atributo : Dict[str, Any]
        Diccionario con información del atributo. Debe contener la clave 'Id'.
    acumulado : int
        ID del tipo de acumulado a asignar.
    tcuenta : int
        Tipo de contabilidad (1=Tributario, 2=Contable).
    cuentas : List[Dict[str, Any]]
        Lista de diccionarios con las cuentas a asociar. Cada diccionario debe
        contener la clave 'id' con el ID de la cuenta.
    
    Returns
    -------
    bool
        True si se guardó correctamente.
        False si hubo error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si atributo no contiene la clave 'Id'.
    
    Notes
    -----
    Esta función es atómica: si falla cualquier operación, se revierte todo.
    """
    if "Id" not in atributo:
        raise ValueError("El diccionario 'atributo' debe contener la clave 'Id'")
    
    atributo_id = atributo.get("Id")
    if not atributo_id:
        print("ERROR: El ID del atributo es None o vacío")
        return False
    
    try:
        with transaccion_segura() as (con, cur):
            # Validar datos antes de ejecutar
            acumulado_int = int(acumulado)
            tcuenta_int = int(tcuenta)
            
            # Actualizar configuración general
            try:
                cur.execute("""
                    UPDATE ATRIBUTOS
                    SET TipoAcumulado = ?,
                        TipoContabilidad = ?
                    WHERE ID = ?
                """, (acumulado_int, tcuenta_int, atributo_id))
                
                if cur.rowcount == 0:
                    print(f"ERROR: No se encontró el atributo con ID {atributo_id} para actualizar")
                    return False
            except Exception as e:
                print(f"ERROR al actualizar ATRIBUTOS: {type(e).__name__}: {e}")
                print(f"  - Atributo ID: {atributo_id}")
                print(f"  - TipoAcumulado: {acumulado_int}")
                print(f"  - TipoContabilidad: {tcuenta_int}")
                raise
            
            # Eliminar todas las cuentas actuales del atributo
            try:
                cur.execute("""
                    DELETE FROM cuentas_atributos WHERE idatributo = ?
                """, (atributo_id,))
            except Exception as e:
                print(f"ERROR al eliminar cuentas existentes: {type(e).__name__}: {e}")
                print(f"  - Atributo ID: {atributo_id}")
                raise
            
            # Insertar las nuevas cuentas seleccionadas
            for idx, c in enumerate(cuentas):
                if "id" not in c:
                    print(f"ERROR: La cuenta en índice {idx} no tiene la clave 'id'")
                    print(f"  - Contenido de la cuenta: {c}")
                    return False
                
                cuenta_id = c["id"]
                if not cuenta_id:
                    print(f"ERROR: La cuenta en índice {idx} tiene ID None o vacío")
                    print(f"  - Contenido de la cuenta: {c}")
                    return False
                
                try:
                    cur.execute("""
                        INSERT INTO CUENTAS_ATRIBUTOS (idatributo, idcuenta)
                        VALUES (?, ?)
                    """, (atributo_id, cuenta_id))
                except Exception as e:
                    print(f"ERROR al insertar cuenta en índice {idx}: {type(e).__name__}: {e}")
                    print(f"  - Atributo ID: {atributo_id}")
                    print(f"  - Cuenta ID: {cuenta_id}")
                    print(f"  - Contenido completo: {c}")
                    raise
            
            # Commit automático si todo sale bien
        return True
    except ValueError as e:
        print(f"ERROR de validación guardando configuración: {e}")
        return False
    except ConnectionError as e:
        print(f"ERROR de conexión guardando configuración: {e}")
        return False
    except Exception as e:
        print(f"ERROR guardando configuración: {type(e).__name__}: {e}")
        print(f"  - Atributo ID: {atributo_id}")
        print(f"  - TipoAcumulado: {acumulado}")
        print(f"  - TipoContabilidad: {tcuenta}")
        print(f"  - Número de cuentas: {len(cuentas)}")
        import traceback
        traceback.print_exc()
        return False
