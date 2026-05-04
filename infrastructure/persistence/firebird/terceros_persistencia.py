"""
Acceso a datos de la tabla TERCEROS (lectura, alta, actualización, borrado)
e importación masiva desde tablas de producto (TEMA{PERIODO}).

Las rutas de aplicación deben preferir puertos/repositorios; este módulo
concentra SQL y transacciones Firebird en un solo lugar.
"""
from typing import Optional, List, Dict, Any, Union, Tuple
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from infrastructure.persistence.firebird.elementos_persistencia import (
    consultar_atributos_hoja_tercero_en_cursor,
)
from core import session
from core.settings import PERIODO
from core.catalogues import TIPOSDOC


def obtener_terceros(
    offset: int = 0,
    limit: int = 10,
    filtro: Optional[Union[str, List[str]]] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Obtiene una lista paginada de terceros con filtrado opcional.

    Parameters
    ----------
    offset : int, optional
        Número de registros a saltar (paginación). Por defecto 0.
    limit : int, optional
        Número máximo de registros a retornar. Por defecto 10.
    filtro : Optional[Union[str, List[str]]], optional
        Filtro de búsqueda. Puede ser:
        - str: Texto para buscar en identidad o razón social (case-insensitive)
        - List con ["DIVIDIR", texto]: Filtro especial para dividir nombres,
          solo retorna personas jurídicas (naturaleza=0) excluyendo tipo documento 31,
          con búsqueda opcional por texto
        None: Sin filtro, retorna todos los terceros

    Returns
    -------
    Tuple[List[Dict[str, Any]], int]
        Primer elemento: lista de diccionarios, cada uno con las siguientes claves:
        - 'id': ID del tercero
        - 'tipodocumento': Nombre del tipo de documento
        - 'identidad': Número de identificación
        - 'naturaleza': Naturaleza (0=Jurídica, 1=Natural)
        - 'digitoverificacion': Dígito de verificación
        - 'razonsocial': Razón social o nombre completo
        - 'primerapellido': Primer apellido
        - 'segundoapellido': Segundo apellido
        - 'primernombre': Primer nombre
        - 'segundonombre': Segundo nombre
        - 'direccion': Dirección
        - 'departamento': Código del departamento
        - 'municipio': Código del municipio
        - 'pais': Código del país
        Segundo elemento: total de terceros que cumplen las condiciones actuales
        (sin paginación). Si hay error, retorna ([], 0).

    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si offset o limit son negativos.

    Notes
    -----
    La búsqueda con filtro es case-insensitive y busca coincidencias parciales.
    """
    if offset < 0 or limit < 0:
        raise ValueError("offset y limit deben ser valores no negativos")

    total = 0
    try:
        con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
        cur = con.cursor()

        # Construir query base y de conteo con parámetros preparados
        if filtro:
            if isinstance(filtro, list) and len(filtro) > 0 and filtro[0] == "DIVIDIR":
                # Modo DIVIDIR: solo personas jurídicas, excluyendo tipo 31
                base_where = "WHERE naturaleza = 0 AND tipodocumento != 31"
                params_total: List[Any] = []

                if len(filtro) > 1:
                    # Normalizar y recortar el texto de filtro para evitar problemas
                    # de truncamiento en columnas con longitud fija (ej. identidad).
                    _texto = str(filtro[1]).strip()
                    filtro_razon = f"%{_texto}%"
                    filtro_ident = f"%{_texto}%"
                    base_where += " AND (UPPER(razonsocial) LIKE UPPER(?) OR UPPER(identidad) LIKE UPPER(?))"
                    params_total.extend([filtro_razon, filtro_ident])

                sql_total = f"SELECT COUNT(*) FROM TERCEROS {base_where}"
                cur.execute(sql_total, tuple(params_total))
                row_total = cur.fetchone()
                total = int(row_total[0]) if row_total and row_total[0] is not None else 0

                sql = f"""
                    SELECT FIRST ? SKIP ? *
                    FROM TERCEROS
                    {base_where}
                    ORDER BY razonsocial
                """
                params: List[Any] = [limit, offset] + params_total
            else:
                # Filtro normal: buscar en identidad o razón social
                _base = filtro[0] if isinstance(filtro, list) else filtro
                # Importante: eliminar espacios en blanco alrededor para que el patrón
                # no exceda la longitud máxima de columnas como IDENTIDAD (ej. CHAR(20)).
                _texto = str(_base).strip()
                filtro_razon = f"%{_texto}%"
                filtro_ident = f"%{_texto}%"
                sql_total = """
                    SELECT COUNT(*)
                    FROM TERCEROS
                    WHERE UPPER(razonsocial) LIKE UPPER(?)
                       OR UPPER(identidad) LIKE UPPER(?)
                """
                params_total = [filtro_razon, filtro_ident]
                cur.execute(sql_total, tuple(params_total))
                row_total = cur.fetchone()
                total = int(row_total[0]) if row_total and row_total[0] is not None else 0

                sql = """
                    SELECT FIRST ? SKIP ? *
                    FROM TERCEROS
                    WHERE UPPER(razonsocial) LIKE UPPER(?)
                       OR UPPER(identidad) LIKE UPPER(?)
                    ORDER BY razonsocial
                """
                params = [limit, offset, filtro_razon, filtro_ident]
        else:
            sql_total = "SELECT COUNT(*) FROM TERCEROS"
            cur.execute(sql_total)
            row_total = cur.fetchone()
            total = int(row_total[0]) if row_total and row_total[0] is not None else 0

            sql = "SELECT FIRST ? SKIP ? * FROM TERCEROS ORDER BY razonsocial"
            params = [limit, offset]

        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        con.close()

    except Exception as e:
        print(f"Error obteniendo terceros: {e}")
        return [], 0

    # Cache codigo -> nombre desde TIPOSDOC para evitar N llamadas
    _cache_tipodoc = {}
    for cod, datos in TIPOSDOC.items():
        nom = datos[1] if datos and len(datos) >= 2 else None
        if nom is not None:
            _cache_tipodoc[cod] = nom
            _cache_tipodoc[str(cod)] = nom

    terceros: List[Dict[str, Any]] = []
    for r in rows:
        cod = r[1]
        tipodoc_texto = (_cache_tipodoc.get(cod) or _cache_tipodoc.get(str(cod)) or str(cod).strip()) if cod is not None else ""

        terceros.append({
            "id": str(r[0]).strip(),
            "tipodocumento": tipodoc_texto,
            "identidad": r[2],
            "naturaleza": r[3],
            "digitoverificacion": r[4],
            "razonsocial": r[5],
            "primerapellido": r[6],
            "segundoapellido": r[7],
            "primernombre": r[8],
            "segundonombre": r[9],
            "direccion": r[10],
            "departamento": r[11],
            "municipio": r[12],
            "pais": r[13],
        })
    return terceros, total


def obtener_terceros_producto(codigo: int, producto: str) -> int:
    """
    Obtiene los terceros desde una base de datos de producto externo
    **y los inserta de forma masiva e inmediata** en la tabla `TERCEROS`
    de la base de datos EX correspondiente a la empresa.

    Esta función está optimizada para velocidad:
    - Solo hace **un SELECT** en la BD del producto.
    - Luego realiza un **INSERT masivo en una única transacción** usando
      `importar_terceros_producto`, evitando validaciones registro a registro.

    Parameters
    ----------
    codigo : int
        Código de la empresa en el producto.
    producto : str
        Código del producto ('NI', 'PH', 'EX', etc.).

    Returns
    -------
    int
        Número de terceros leídos (y enviados a insertar). Si hay error,
        retorna 0.

    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos del producto.
    """
    try:
        con = CNX_BDHelisa(producto, codigo, "sysdba")
        cur = con.cursor()
        table = f"TEMA{PERIODO}"
        cur.execute(f"""
            select decode(ma.clase,
                            'C', '13', 'A', '31', 'X', '22', 'T', '12',
                            'R', '11', 'E', '21', 'P', '41', 'F', '42',
                            'D', '42', 'I', '50', 'S', '48', 'B', '47',
                            'U', '91', 'H', '43'
                    ) as tipo_documento, ma.identidad, ma.nombre razon_social,
                    xx.apellido1, xx.apellido2, xx.nombre1, xx.nombre2, ma.direccion,
                    cx.codigo_dian municipio, cx.codigo_departamento, px.codigo pais, ma.verificacion,
                    ma.naturaleza
            from {table} ma
            left join temaxxxx xx on ma.identidad = xx.identidad
            left join ciudxxxx cx on ma.ciudad = cx.codigo
            left join paisxxxx px on cx.cod_pais = px.codigo
        """)
        rows = cur.fetchall()
        cur.close()
        con.close()
    except Exception as e:
        print(f"[ERROR] Error obteniendo terceros del producto: {e}")
        return 0

    # Si no hay filas, no hay nada que insertar
    if not rows:
        return 0

    # Inserción inmediata usando el motor optimizado de crear_tercero
    # en modo "desde_producto" (inserción masiva en una sola transacción).
    resultado = crear_tercero(rows, codigo, desde_producto=True)

    # Si algo falló, crear_tercero ya habrá registrado el error.
    return resultado if isinstance(resultado, int) else 0


def crear_tercero(
    tercero: Any,
    codigo: int,
    *,
    desde_producto: bool = False
) -> Union[str, bool, int]:
    """
    Crea terceros en la base de datos.

    Modo normal (por unidad, desde la UI):
    - Recibe un diccionario con los datos del tercero.
    - Valida que no exista otro tercero con la misma identidad y tipo de documento.
    - Inserta un solo registro en TERCEROS.

    Modo optimizado (desde producto):
    - Se invoca con `desde_producto=True` y `tercero` como:
        - una tupla de datos, o
        - una lista/iterable de tuplas tal como las devuelve el SELECT sobre TEMA{PERIODO}.
    - Inserta todos los registros en una sola transacción, sin validar duplicados
      uno por uno.

    Parameters
    ----------
    tercero : Any
        - Modo normal: Dict[str, Any] con las claves:
          'identidad', 'tipodocumento', 'naturaleza', 'razonsocial',
          'primerapellido', 'segundoapellido', 'primernombre', 'segundonombre',
          'direccion', 'departamento', 'municipio', 'pais'.
        - Modo producto: tupla o iterable de tuplas con la forma:
          (tipo_documento, identidad, razon_social, apellido1, apellido2,
           nombre1, nombre2, direccion, municipio, codigo_departamento,
           pais, verificacion, naturaleza).
    desde_producto : bool, optional
        - False (por defecto): crea un solo tercero desde la UI.
        - True: inserta terceros en bloque desde datos de producto.

    Returns
    -------
    Union[str, bool, int]
        - Modo normal:
            "Tercero creado correctamente." si se creó exitosamente.
            "Error: ya existe un tercero con esa identidad y tipo de documento." si hay duplicado.
            False si hubo error.
        - Modo producto:
            Número de registros insertados (int). 0 si hubo error.

    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    """
    # MODO OPTIMIZADO: importación masiva desde producto
    if desde_producto:
        # Normalizar a lista de tuplas
        # Si es una sola tupla, la envolvemos en lista; si es lista/tupla de tuplas, la usamos tal cual.
        if len(tercero) == 0:
            return 0
        if isinstance(tercero[0], (list, tuple)):
            filas = list(tercero)
        else:
            filas = [tercero]

        try:
            with transaccion_segura(codigo) as (con, cur):
                for t in filas:
                    # Esperamos la misma estructura del SELECT en obtener_terceros_producto:
                    # (tipo_documento, identidad, razon_social, apellido1, apellido2,
                    #  nombre1, nombre2, direccion, municipio, codigo_departamento,
                    #  pais, verificacion, naturaleza)
                    cur.execute("""
                        INSERT INTO TERCEROS (
                            TipoDocumento, Identidad, naturaleza, DigitoVerificacion,
                            RazonSocial, PrimerApellido, SegundoApellido,
                            PrimerNombre, SegundoNombre, Direccion,
                            Municipio, Departamento, Pais
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        int(t[0]) if t[0] else 0,
                        t[1],
                        int(t[12]),
                        t[11] if t[11] else "",
                        t[2].strip() if t[2] else "",
                        t[3],
                        t[4],
                        t[5],
                        t[6],
                        t[7],
                        int(t[8]) if t[8] else 0,
                        int(t[9]) if t[9] else 0,
                        int(t[10]) if t[10] else 0
                    ))
                # Commit automático al salir del contexto
            return len(filas)
        except Exception as e:
            print(f"Error al importar terceros desde producto: {e}")
            return 0

    # MODO NORMAL: creación individual desde la UI
    if not isinstance(tercero, dict):
        raise ValueError("En modo normal, 'tercero' debe ser un diccionario.")

    try:
        with transaccion_segura() as (con, cur):
            # Validación de duplicado
            cur.execute("""
                SELECT COUNT(*) FROM TERCEROS
                WHERE IDENTIDAD = ? AND TIPODOCUMENTO = ?
            """, (
                tercero.get("identidad"),
                tercero.get("tipodocumento"),
            ))
            if cur.fetchone()[0] > 0:
                return "Error: ya existe un tercero con esa identidad y tipo de documento."

            # Insertar nuevo registro
            cur.execute("""
                INSERT INTO TERCEROS (
                    IDENTIDAD, TIPODOCUMENTO, NATURALEZA, RAZONSOCIAL,
                    PRIMERAPELLIDO, SEGUNDOAPELLIDO,
                    PRIMERNOMBRE, SEGUNDONOMBRE,
                    DIRECCION, DEPARTAMENTO, MUNICIPIO, PAIS
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                tercero.get("identidad"),
                tercero.get("tipodocumento"),
                tercero.get("naturaleza"),
                tercero.get("razonsocial"),
                tercero.get("primerapellido"),
                tercero.get("segundoapellido"),
                tercero.get("primernombre"),
                tercero.get("segundonombre"),
                tercero.get("direccion"),
                tercero.get("departamento"),
                tercero.get("municipio"),
                tercero.get("pais"),
            ))
            # Commit automático si todo sale bien
        return "Tercero creado correctamente."
    except Exception as e:
        print(f"Error al insertar tercero: {e}")
        return False


def actualizar_tercero(tercero: Dict[str, Any]) -> Union[str, bool]:
    """
    Actualiza un tercero existente y sus registros relacionados en HOJA_TRABAJO.

    Actualiza los datos del tercero en la tabla Terceros y también actualiza
    los valores correspondientes en HOJA_TRABAJO si existen.

    Parameters
    ----------
    tercero : Dict[str, Any]
        Diccionario con los datos del tercero a actualizar. Debe contener:
        - 'id': ID del tercero a actualizar
        - 'identidad': Identidad del tercero
        - Todos los demás campos opcionales (tipodocumento, razonsocial, etc.)

    Returns
    -------
    Union[str, bool]
        "Tercero actualizado correctamente." si se actualizó exitosamente.
        "Error: ya existe otro tercero con esa identidad y tipo de documento." si hay duplicado.
        False si hubo error.

    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si el diccionario no contiene la clave 'id'.

    Notes
    -----
    Esta función actualiza tanto la tabla Terceros como HOJA_TRABAJO en una sola transacción.
    """
    if "id" not in tercero:
        raise ValueError("El diccionario 'tercero' debe contener la clave 'id'")

    try:
        with transaccion_segura() as (con, cur):
            # Mapeo de campos del tercero a nombres de atributos
            mapeo_campos = {
                "tipodocumento": "tdoc",
                "digitoverificacion": "dv",
                "razonsocial": "raz",
                "primerapellido": "ap1",
                "segundoapellido": "ap2",
                "primernombre": "nom1",
                "segundonombre": "nom2",
                "direccion": "dir",
                "departamento": "coddepto",
                "municipio": "mun",
                "pais": "pais"
            }

            # Validar duplicado
            cur.execute("""
                SELECT COUNT(*)
                FROM TERCEROS
                WHERE IDENTIDAD = ?
                    AND TIPODOCUMENTO = ?
                    AND ID <> ?
            """, (
                tercero.get("identidad"),
                tercero.get("tipodocumento"),
                tercero.get("id"),
            ))
            count = cur.fetchone()[0]
            if count > 0:
                return "Error: ya existe otro tercero con esa identidad y tipo de documento."

            # Actualizar tabla Terceros
            cur.execute("""
                UPDATE TERCEROS
                SET
                    TIPODOCUMENTO = ?,
                    NATURALEZA = ?,
                    RAZONSOCIAL = ?,
                    PRIMERAPELLIDO = ?,
                    SEGUNDOAPELLIDO = ?,
                    PRIMERNOMBRE = ?,
                    SEGUNDONOMBRE = ?,
                    DIRECCION = ?,
                    DEPARTAMENTO = ?,
                    MUNICIPIO = ?,
                    PAIS = ?
                WHERE ID = ?
            """, (
                tercero.get("tipodocumento"),
                tercero.get("naturaleza"),
                tercero.get("razonsocial"),
                tercero.get("primerapellido"),
                tercero.get("segundoapellido"),
                tercero.get("primernombre"),
                tercero.get("segundonombre"),
                tercero.get("direccion"),
                tercero.get("departamento"),
                tercero.get("municipio"),
                tercero.get("pais"),
                tercero.get("id"),
            ))

            # Actualizar HOJA_TRABAJO
            identidad = tercero.get("identidad")
            for k, v in tercero.items():
                if k not in ["id", "identidad", "naturaleza"]:
                    # Obtener solo los atributos que existen en la hoja de trabajo para este tercero
                    nombre_attr = mapeo_campos.get(k)
                    if nombre_attr:
                        atrs = consultar_atributos_hoja_tercero_en_cursor(
                            cur, identidad, nombre_attr
                        )
                        for atr in atrs:
                            cur.execute("""
                                UPDATE HOJA_TRABAJO
                                SET VALOR = ?
                                WHERE IDENTIDADTERCERO = ? AND IDATRIBUTO = ?
                            """, (v, identidad, atr[0]))

            # Commit automático si todo sale bien
        return "Tercero actualizado correctamente."
    except Exception as e:
        print(f"Error al actualizar tercero: {e}")
        return False


def eliminar_tercero(identidad: str) -> Union[bool, Exception]:
    """
    Elimina un tercero solo si no tiene movimientos acumulados en HOJA_TRABAJO.

    Parameters
    ----------
    identidad : str
        Identidad del tercero a eliminar.

    Returns
    -------
    Union[bool, Exception]
        True si se eliminó correctamente.
        False si el tercero tiene registros en HOJA_TRABAJO y no se puede eliminar.
        Exception si hubo error durante el proceso.

    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.

    Notes
    -----
    Esta función verifica que el tercero no tenga registros en HOJA_TRABAJO antes de eliminar.
    Si tiene registros, retorna False sin eliminar.
    """
    try:
        with transaccion_segura() as (con, cur):
            # Verificar si el tercero tiene registros en HOJA_TRABAJO
            cur.execute("""
                SELECT COUNT(*)
                FROM HOJA_TRABAJO
                WHERE IDENTIDADTERCERO = ?
            """, (identidad,))
            tiene_registros = cur.fetchone()[0] > 0
            if tiene_registros:
                return False

            # Eliminar el tercero
            cur.execute("""
                DELETE FROM TERCEROS
                WHERE IDENTIDAD = ?
            """, (identidad,))
            # Commit automático si todo sale bien
        return True
    except Exception as e:
        print(f"Error eliminando el tercero: {e}")
        return e
