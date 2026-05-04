"""
Persistencia Firebird: cuentas tributarias/contables, subcuentas,
importación desde producto y movimientos (terceros y bancos).

Concentra SQL y transacciones; el módulo `cuentas_movimientos` solo reexporta
por compatibilidad. Preferir importar desde aquí en adaptadores nuevos.
"""
from typing import Optional, List, Dict, Any, Tuple
from infrastructure.adapters.helisa_firebird import CNX_BDHelisa, RW_Helisa
from infrastructure.adapters.proteccion_firebird import transaccion_segura
from core import session
from core.settings import PERIODO


def obtener_cuentas_producto(tipo_cuentas: int, codigo: int, producto: str) -> List[Dict[str, Any]]:
    """
    Obtiene cuentas desde una base de datos de producto externo e importa automáticamente.
    
    Parameters
    ----------
    tipo_cuentas : int
        Tipo de cuentas: 1=Tributario, 2=Contable.
    codigo : int
        Código de la empresa en el producto.
    producto : str
        Código del producto ('NI', 'PH', etc.).
    
    Returns
    -------
    List[Dict[str, Any]]
        Lista de diccionarios con las cuentas obtenidas e importadas.
        Cada diccionario contiene: 'cuenta', 'nombre', 'naturaleza', 'tercero',
        'saldoinicial', 'debitos', 'creditos', 'saldofinal', 'subcuentas'.
        Lista vacía si hay error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos del producto.
    ValueError
        Si tipo_cuentas no es 1 o 2.
    
    Notes
    -----
    Esta función automáticamente importa las cuentas obtenidas a la base de datos local.
    """
    if tipo_cuentas not in [1, 2]:
        raise ValueError("tipo_cuentas debe ser 1 (Tributario) o 2 (Contable)")
    
    cuentas = []
    con = CNX_BDHelisa(producto, codigo, "sysdba")
    cur = con.cursor()

    try:
        # ----------- TRIBUTARIO -----------
        if tipo_cuentas == 1:
            # Tabla dinámica basada en PERIODO (validada por config)
            tabla_periodo = f"COMA{PERIODO}"
            base_sql = f"""
                SELECT
                    CUENTA,
                    NOMBRE,
                    NATURALEZA,
                    MODULO_ASOCIADO,
                    INICIALHISTORICO,
                    (
                        COALESCE(DEBEHISTORICO1,0)+COALESCE(DEBEHISTORICO2,0)+COALESCE(DEBEHISTORICO3,0)+
                        COALESCE(DEBEHISTORICO4,0)+COALESCE(DEBEHISTORICO5,0)+COALESCE(DEBEHISTORICO6,0)+
                        COALESCE(DEBEHISTORICO7,0)+COALESCE(DEBEHISTORICO8,0)+COALESCE(DEBEHISTORICO9,0)+
                        COALESCE(DEBEHISTORICO10,0)+COALESCE(DEBEHISTORICO11,0)+COALESCE(DEBEHISTORICO12,0)
                    ) AS DEBITOS,
                    (
                        COALESCE(HABERHISTORICO1,0)+COALESCE(HABERHISTORICO2,0)+COALESCE(HABERHISTORICO3,0)+
                        COALESCE(HABERHISTORICO4,0)+COALESCE(HABERHISTORICO5,0)+COALESCE(HABERHISTORICO6,0)+
                        COALESCE(HABERHISTORICO7,0)+COALESCE(HABERHISTORICO8,0)+COALESCE(HABERHISTORICO9,0)+
                        COALESCE(HABERHISTORICO10,0)+COALESCE(HABERHISTORICO11,0)+COALESCE(HABERHISTORICO12,0)
                    ) AS CREDITOS,
                    SUBCUENTAS
                FROM {tabla_periodo}
                ORDER BY CUENTA
            """

        # ----------- CONTABLE -----------
        elif tipo_cuentas == 2:
            base_sql = """
                SELECT
                    m.cuenta, 
                    m.nombre, 
                    m.naturaleza, 
                    m.tercero, 
                    COALESCE(csn.csn_saldo_ini, 0) AS csn_saldo_ini,
                    SUM(debitos) AS debitos, 
                    SUM(creditos) AS creditos,
                    m.subcuentas
                FROM (
                    SELECT 
                        c.cuenta,  
                        IIF(c.naturaleza = 'D', c.valor, 0) debitos,
                        IIF(c.naturaleza = 'C', c.valor, 0) creditos
                    FROM cotr_niif c
                    WHERE c.fecha >= 53408 AND c.fecha <= 53772
                ) mv
                LEFT JOIN cuentas_niif m ON m.cuenta = mv.cuenta
                LEFT JOIN co_saldos_niif csn ON csn.csn_ano = 2025 AND csn.csn_cuenta = m.cuenta
                GROUP BY m.cuenta, m.nombre, m.naturaleza, m.tercero, csn.csn_saldo_ini, m.subcuentas
                ORDER BY m.CUENTA
            """

        cur.execute(base_sql)
        rows = cur.fetchall()

        for r in rows:
            if tipo_cuentas == 1:
                cuenta, nombre, naturaleza, tercero, inicial, deb, cred, subcuentas = r[:8]
                tercero = None
            else:
                cuenta, nombre, naturaleza, tercero, inicial, deb, cred, subcuentas = r[:8]

            if naturaleza == "D":
                saldo_final = inicial + deb + cred
            else:
                saldo_final = inicial + cred - deb

            cuentas.append({
                "cuenta": cuenta,
                "nombre": nombre,
                "naturaleza": naturaleza,
                "tercero": tercero,
                "saldoinicial": inicial,
                "debitos": deb,
                "creditos": cred,
                "saldofinal": saldo_final,
                "subcuentas": subcuentas
            })

    except Exception as e:
        print(f"Error cargando cuentas del producto: {e}")
    finally:
        cur.close()
        con.close()
    
    # Importar automáticamente
    importar_cuentas(cuentas, tipo_cuentas, codigo)
    return cuentas


def importar_cuentas(cuentas: List[Dict[str, Any]], tipo_cuentas: int, codigo: int) -> None:
    """
    Importa múltiples cuentas a la base de datos local.
    
    Parameters
    ----------
    cuentas : List[Dict[str, Any]]
        Lista de diccionarios con los datos de las cuentas. Cada diccionario debe contener:
        - 'cuenta': Código de la cuenta
        - 'nombre': Nombre de la cuenta
        - 'naturaleza': Naturaleza ('D' o 'C')
        - 'tercero': ID del tercero asociado (opcional)
        - 'saldoinicial': Saldo inicial
        - 'debitos': Débitos
        - 'creditos': Créditos
        - 'saldofinal': Saldo final
        - 'valorabsoluto': Valor absoluto ('S' o 'N')
        - 'subcuentas': Número de subcuentas
    tipo_cuentas : int
        Tipo de cuentas: 1=Tributario (Cuentas_trib), 2=Contable (Cuentas_cont).
    codigo : int
        Código de la empresa donde importar las cuentas.
    
    Returns
    -------
    None
        No retorna valor. Los errores se imprimen en consola.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si tipo_cuentas no es 1 o 2.
    
    Notes
    -----
    Esta función inserta todas las cuentas en una sola transacción atómica.
    Si falla cualquier inserción, se revierte todo.
    """
    if tipo_cuentas not in [1, 2]:
        raise ValueError("tipo_cuentas debe ser 1 (Tributario) o 2 (Contable)")
    
    tabla = "Cuentas_trib" if tipo_cuentas == 1 else "Cuentas_cont"
    
    try:
        with transaccion_segura(codigo_empresa=codigo) as (con, cur):
            for cuenta in cuentas:
                cur.execute(f"""
                    INSERT INTO {tabla} 
                    (Codigo, Nombre, Naturaleza, Tercero, Saldoinicial, Debitos, Creditos, SaldoFinal, ValorAbsoluto, subcuentas)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    cuenta.get("cuenta", ""),
                    cuenta.get("nombre", ""),
                    cuenta.get("naturaleza", ""),
                    cuenta.get("tercero", ""),
                    float(cuenta.get("saldoinicial") or 0),
                    float(cuenta.get("debitos") or 0),
                    float(cuenta.get("creditos") or 0),
                    float(cuenta.get("saldofinal") or 0),
                    cuenta.get("valorabsoluto", "S"),
                    int(cuenta.get("subcuentas", 0))
                ))
            # Commit automático si todo sale bien
    except Exception as e:
        print(f"Error insertando en {tabla}: {str(e)}")
        raise e


def obtener_cuentas(
    tipo_cuentas: int,
    offset: int = 0,
    limit: int = 50,
    filtro: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Obtiene una lista paginada de cuentas desde la base de datos local.
    
    Parameters
    ----------
    tipo_cuentas : int
        Tipo de cuentas: 1=Tributario, 2=Contable.
    offset : int, optional
        Número de registros a saltar (paginación). Por defecto 0.
    limit : int, optional
        Número máximo de registros a retornar. Por defecto 50.
    filtro : str, optional
        Texto opcional para filtrar por código o nombre de cuenta (case-insensitive).
        Si se proporciona, busca coincidencias parciales.
    
    Returns
    -------
    Tuple[List[Dict[str, Any]], int]
        Primer elemento: lista de diccionarios, cada uno con las siguientes claves:
        - 'id': ID de la cuenta
        - 'codigo': Código de la cuenta
        - 'nombre': Nombre de la cuenta
        - 'naturaleza': Naturaleza ('D' o 'C')
        - 'tercero': ID del tercero asociado
        - 'saldoinicial': Saldo inicial
        - 'debitos': Débitos
        - 'creditos': Créditos
        - 'saldofinal': Saldo final
        - 'valorabsoluto': Valor absoluto ('S' o 'N')
        - 'subcuentas': Número de subcuentas
        Segundo elemento: total de registros que cumplen las condiciones actuales
        (sin paginación). Si hay error, retorna ([], 0).
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si tipo_cuentas no es 1 o 2.
        Si offset o limit son negativos.
    """
    if tipo_cuentas not in [1, 2]:
        raise ValueError("tipo_cuentas debe ser 1 (Tributario) o 2 (Contable)")
    if offset < 0 or limit < 0:
        raise ValueError("offset y limit deben ser valores no negativos")
    
    cuentas: List[Dict[str, Any]] = []
    total = 0
    con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
    cur = con.cursor()
    
    try:
        tabla = "Cuentas_trib" if tipo_cuentas == 1 else "Cuentas_cont"
        
        # Construir query de conteo total con parámetros preparados
        sql_total = f"SELECT COUNT(*) FROM {tabla}"
        params_total: List[Any] = []
        if filtro:
            filtro_param = f"%{filtro}%"
            sql_total += """
                WHERE UPPER(codigo) LIKE UPPER(?)
                   OR UPPER(nombre) LIKE UPPER(?)
            """
            params_total.extend([filtro_param, filtro_param])
        cur.execute(sql_total, tuple(params_total))
        row_total = cur.fetchone()
        total = int(row_total[0]) if row_total and row_total[0] is not None else 0

        # Construir query paginada con los mismos filtros
        sql = f"""
            SELECT FIRST ? SKIP ?
                id, codigo, nombre, naturaleza, tercero, saldoinicial, debitos, creditos, saldofinal, valorabsoluto, subcuentas
            FROM {tabla}
        """
        params: List[Any] = [limit, offset]
        
        if filtro:
            filtro_param = f"%{filtro}%"
            sql += """
                WHERE UPPER(codigo) LIKE UPPER(?)
                   OR UPPER(nombre) LIKE UPPER(?)
            """
            params.extend([filtro_param, filtro_param])
        
        sql += " ORDER BY codigo"

        cur.execute(sql, tuple(params))
        rows = cur.fetchall()

        for cuenta in rows:
            cuentas.append({
                "id": cuenta[0],
                "codigo": cuenta[1],
                "nombre": cuenta[2],
                "naturaleza": cuenta[3],
                "tercero": cuenta[4],
                "saldoinicial": cuenta[5],
                "debitos": cuenta[6],
                "creditos": cuenta[7],
                "saldofinal": cuenta[8],
                "valorabsoluto": cuenta[9],
                "subcuentas": cuenta[10]
            })
    except Exception as e:
        print(f"Error cargando cuentas: {e}")
    finally:
        cur.close()
        con.close()
    return cuentas, total


def obtener_subcuentas(tipo_cuentas: int, prefijo: str) -> List[Dict[str, Any]]:
    """
    Obtiene las subcuentas cuyo código comienza con un prefijo específico.
    
    Excluye la cuenta padre exacta (solo retorna subcuentas, no la cuenta con código igual al prefijo).
    
    Parameters
    ----------
    tipo_cuentas : int
        Tipo de cuentas: 1=Tributario, 2=Contable.
    prefijo : str
        Prefijo del código de cuenta. Retorna todas las cuentas cuyo código comienza con este prefijo,
        excepto la cuenta con código exactamente igual al prefijo.
    
    Returns
    -------
    List[Dict[str, Any]]
        Lista de diccionarios con las subcuentas encontradas.
        Cada diccionario contiene las mismas claves que obtener_cuentas().
        Lista vacía si hay error o no hay subcuentas.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
        Si tipo_cuentas no es 1 o 2.
    
    Notes
    -----
    La búsqueda es case-insensitive.
    """
    if tipo_cuentas not in [1, 2]:
        raise ValueError("tipo_cuentas debe ser 1 (Tributario) o 2 (Contable)")
    
    subcuentas = []
    con = CNX_BDHelisa("EX", session.EMPRESA_ACTUAL["codigo"], "sysdba")
    cur = con.cursor()
    
    try:
        tabla = "Cuentas_trib" if tipo_cuentas == 1 else "Cuentas_cont"
        # Usar parámetros preparados (seguro contra inyección SQL)
        sql = f"""
            SELECT id, codigo, nombre, naturaleza, tercero, saldoinicial, debitos, creditos, saldofinal, valorabsoluto, subcuentas
            FROM {tabla}
            WHERE UPPER(codigo) LIKE UPPER(?)
              AND codigo <> ?
            ORDER BY codigo
        """
        prefijo_like = f"{prefijo}%"
        cur.execute(sql, (prefijo_like, prefijo))
        rows = cur.fetchall()
        
        for r in rows:
            subcuentas.append({
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
                "subcuentas": r[10]
            })
    except Exception as e:
        print(f"Error cargando subcuentas: {e}")
    finally:
        cur.close()
        con.close()
    return subcuentas


def obtener_movimientos_terceros_producto(tipo_cuentas: int, codigo: int, producto: str) -> None:
    """
    Obtiene movimientos de terceros desde un producto externo e importa automáticamente.
    
    Parameters
    ----------
    tipo_cuentas : int
        Tipo de cuentas: 1=Tributario, 2=Contable.
    codigo : int
        Código de la empresa en el producto.
    producto : str
        Código del producto ('NI', 'PH', etc.).
    
    Returns
    -------
    None
        No retorna valor. Los errores se imprimen en consola.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos del producto.
    ValueError
        Si tipo_cuentas no es 1 o 2.
    
    Notes
    -----
    Esta función automáticamente importa los movimientos obtenidos a la base de datos local.
    """
    if tipo_cuentas not in [1, 2]:
        raise ValueError("tipo_cuentas debe ser 1 (Tributario) o 2 (Contable)")
    
    rows = []
    con = CNX_BDHelisa(producto, codigo, "sysdba")
    cur = con.cursor()
    
    try:
        if tipo_cuentas == 1:
            # Tablas dinámicas basadas en PERIODO (validadas por config)
            tabla_cotr = f"COTRXXXX"
            tabla_coma = f"COMA{PERIODO}"
            tabla_tetr = f"TETR{PERIODO}"
            
            sql = f"""
                select r.cuenta, r.identidad, sum(saldoinicial) saldoinicial, sum(debitos) debitos,  sum(creditos) creditos,
                    sum(iif (m.naturaleza = 'D', saldoinicial + debitos - creditos, saldoinicial - debitos + creditos)) saldofinal
                from(
                SELECT c.cuenta,  c.identidadtercero identidad, coalesce(t.saldoinicial, 0) saldoinicial,
                    iif (c.naturaleza = 'D', c.valor, 0) Debitos,
                    iif (c.naturaleza = 'C', c.valor, 0) Creditos
                FROM {tabla_cotr} c
                left join {tabla_tetr} t on t.identidad = c.identidadtercero and t.cuenta = c.cuenta
                WHERE c.fecha >= 53408 and c.fecha <= 53772 and c.clase_cont <> 1
                ) r
                left join {tabla_coma} m on m.cuenta = r.cuenta
                group by r.cuenta, r.identidad
            """
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            con.close()
        elif tipo_cuentas == 2:
            sql = """
                select r.cuenta, r.identidad, sum(saldoinicial) saldoinicial, sum(debitos) debitos,  sum(creditos) creditos,
                    sum(iif (m.naturaleza = 'D', saldoinicial + debitos - creditos, saldoinicial - debitos + creditos)) saldofinal
                from(
                SELECT c.cuenta,  g.identidadtercero identidad, coalesce(t.tesn_inicial2025, 0) saldoinicial,
                    iif (c.naturaleza = 'D', c.valor, 0) Debitos,
                    iif (c.naturaleza = 'C', c.valor, 0) Creditos
                FROM COTR_NIIF c
                left join cotrxxxx g on g.indice_primario = c.indice and g.fecha = c.fecha
                left join te_saldos_niif t on t.tesn_identidad = g.identidadtercero and t.tesn_cuenta = c.cuenta
                WHERE c.fecha >= 53408 and c.fecha <= 53772
                ) r
                left join cuentas_niif m on m.cuenta = r.cuenta
                group by r.cuenta, r.identidad
            """
            cur.execute(sql)
            rows = cur.fetchall()
            cur.close()
            con.close()
    except Exception as e:
        print(f"Error cargando mov Terceros del producto: {e}")
    
    importar_movimientos_terceros(rows, codigo, tipo_cuentas)


def importar_movimientos_terceros(terceros: List[tuple], codigo: int, tipo_cuentas: int) -> None:
    """
    Importa movimientos de terceros desde un producto externo.
    
    Parameters
    ----------
    terceros : List[tuple]
        Lista de tuplas con los movimientos. Cada tupla debe contener:
        (cuenta, identidad, saldoinicial, debitos, creditos, saldofinal).
    codigo : int
        Código de la empresa donde importar los movimientos.
    tipo_cuentas : int
        Tipo de cuentas: 1=Tributario (Terceros_mov_trib), 2=Contable (Terceros_mov_cont).
    
    Returns
    -------
    None
        No retorna valor. Los errores se imprimen en consola.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    ValueError
        Si tipo_cuentas no es 1 o 2.
    
    Notes
    -----
    Esta función inserta todos los movimientos en una sola transacción atómica.
    Si falla cualquier inserción, se revierte todo.
    """
    if tipo_cuentas not in [1, 2]:
        raise ValueError("tipo_cuentas debe ser 1 (Tributario) o 2 (Contable)")
    
    tabla = "Terceros_mov_trib" if tipo_cuentas == 1 else "Terceros_mov_cont"
    
    try:
        with transaccion_segura(codigo_empresa=codigo) as (con, cur):
            for t in terceros:
                cur.execute(f"""
                    INSERT INTO {tabla} (
                        Cuenta, Identidad, Saldoinicial, Debitos, Creditos, Saldofinal
                    ) VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    t[0] if t[0] else "",
                    t[1] if t[1] else "",
                    t[2] if t[2] else 0,
                    t[3] if t[3] else 0,
                    t[4] if t[4] else 0,
                    t[5] if t[5] else 0
                ))
            # Commit automático si todo sale bien
    except Exception as e:
        print(f"Error importando movimientos de terceros: {e}")
        raise e


def obtener_movimientos_bancos_producto(codigo: int, producto: str) -> None:
    """
    Obtiene movimientos de bancos desde un producto externo e importa automáticamente.
    
    Parameters
    ----------
    codigo : int
        Código de la empresa en el producto.
    producto : str
        Código del producto ('NI', 'PH', etc.).
    
    Returns
    -------
    None
        No retorna valor. Los errores se imprimen en consola.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos del producto.
    
    Notes
    -----
    Esta función automáticamente importa los movimientos de bancos obtenidos a la base de datos local.
    """
    rows = []
    rw = RW_Helisa(producto)
    
    match producto:
        case 'NI':
            extension_bd = ".HGW"
        case 'PH':
            extension_bd = ".HPH"
        case _:
            extension_bd = ".HGW"  # Default
    
    base_datos = rw.bd.replace("\\", "\\\\") + r"\\HELISABD" + extension_bd
    print(f"[BD] Base de datos: {base_datos}")
    
    con_prod = CNX_BDHelisa(producto, codigo, "sysdba")
    cur_prod = con_prod.cursor()
    
    try:
        sql_local = """
            select m.codigo_ctabancaria,
                   b.codigo_sucursal,
                   sum(m.debitos - m.creditos) as saldo
            from (
                select c.codigo_ctabancaria,
                       iif(c.naturaleza = 'D', c.valor, 0) as debitos,
                       iif(c.naturaleza = 'C', c.valor, 0) as creditos
                from cotrxxxx c
                where c.codigo_ctabancaria > 0
                  and c.fecha <= 53772
            ) m
            left join bama2025 b on b.codigo = m.codigo_ctabancaria
            group by m.codigo_ctabancaria, b.codigo_sucursal
        """
        cur_prod.execute(sql_local)
        datos_locales = cur_prod.fetchall()
    except Exception as e:
        print(f"Error cargando Bancos: {e}")
        datos_locales = []
        
    con_helisa = CNX_BDHelisa(producto, -1, "sysdba")
    cur_helisa = con_helisa.cursor()
    
    try:
        for (cta_bancaria, codigo_sucursal, saldo) in datos_locales:
            # Obtener código de banco
            cur_helisa.execute("""
                select max(b.codigo)
                from bansucur s
                left join bancos b on b.codigo = s.codigo_banco
                where s.codigo = ?
            """, (codigo_sucursal,))

            row = cur_helisa.fetchone()

            codigo_banco = row[0] if row else None

            if codigo_banco:
                # Obtener identidad/verificación/nombre
                cur_helisa.execute("""
                    select identidad, verificacion, nombre
                    from bancos
                    where codigo = ?
                """, (codigo_banco,))

                datos_banco = cur_helisa.fetchone()

                if datos_banco:
                    identidad, verificacion, nombre = datos_banco
                    rows.append([identidad, verificacion, nombre, saldo])

        cur_prod.close()
        con_prod.close()
        cur_helisa.close()
        con_helisa.close()

    except Exception as e:
        print(f"Error cargando Bancos: {e}")
    
    importar_movimientos_bancos(rows, codigo)


def importar_movimientos_bancos(bancos: List[List[Any]], codigo: int) -> None:
    """
    Importa movimientos de bancos desde un producto externo.
    
    Parameters
    ----------
    bancos : List[List[Any]]
        Lista de listas con los datos de bancos. Cada lista debe contener:
        [identidad, verificacion, nombre, saldo].
    codigo : int
        Código de la empresa donde importar los movimientos.
    
    Returns
    -------
    None
        No retorna valor. Los errores se imprimen en consola.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    
    Notes
    -----
    Esta función inserta todos los movimientos de bancos en una sola transacción atómica.
    Si falla cualquier inserción, se revierte todo.
    """
    try:
        with transaccion_segura(codigo_empresa=codigo) as (con, cur):
            for b in bancos:
                cur.execute("""
                    INSERT INTO BANCOS_MOV (
                        Identidad, Verificacion, Nombre, Saldo
                    )
                   VALUES (?, ?, ?, ?)
                """, (
                    b[0] if b[0] else "",
                    b[1] if b[1] else "",
                    b[2] if b[2] else "",
                    b[3] if b[3] else 0
                ))
            # Commit automático si todo sale bien
    except Exception as e:
        print(f"Error importando movimientos de bancos: {e}")
        raise e
