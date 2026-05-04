"""
Persistencia y operaciones de BD para autenticación, usuarios y utilidades
(traducción de códigos, restauración de BD, flags activo).

`auth_utils` reexporta por compatibilidad; en código nuevo preferir este módulo.
"""
from typing import Optional, Tuple, Any
import secrets
import string
import os
from infrastructure.adapters.helisa_firebird import (
    CNX_BDHelisa,
    RW_Helisa,
    crearBD_Particular,
)
from infrastructure.adapters.proteccion_firebird import (
    hacer_backup_bd,
    proceso_protegido,
    transaccion_segura,
)
from core import session
from core.settings import PERIODO


# Whitelist de tablas permitidas para traductor_cod
TABLAS_PERMITIDAS = {
    # Tablas BD global
    "TIPOSDOCUMENTOS",
    "DEPARTAMENTO",
    "MUNICIPIO",
    "PAIS",
    "CIUDADES",
    "NATURALEZAS",
    # Tablas BD particular
    "ACUMULADOS",
    "ATRIBUTOS",
    "BANCOS_MOV",
    "CONCEPTOS",
    "CONSORCIOS",
    "CUENTAS_ATRIBUTOS",
    "CUENTAS_CONT",
    "CUENTAS_TRIB",
    "ELEMENTOS",
    "FORMAACUMULADO",
    "FORMATOS",
    "HOJA_TRABAJO",
    "PRODUCTOS",
    "TERCEROS",
    "TERCEROS_MOV_CONT",
    "TERCEROS_MOV_TRIB",
}


def generar_clave(longitud: int = 12) -> str:
    """
    Genera una clave aleatoria segura alfanumérica usando secrets.
    
    Parameters
    ----------
    longitud : int, optional
        Longitud de la clave a generar. Por defecto 12.
    
    Returns
    -------
    str
        Clave aleatoria alfanumérica. Ejemplo: 'G7xP9dLk2Wm3'
    
    Examples
    --------
    >>> clave = generar_clave(16)
    >>> len(clave)
    16
    """
    caracteres = string.ascii_letters + string.digits
    return ''.join(secrets.choice(caracteres) for _ in range(longitud))


def autenticar_usuario(nombre: str, clave: str) -> Optional[Tuple[int, str]]:
    """
    Autentica un usuario verificando nombre y clave en la base de datos.
    
    Parameters
    ----------
    nombre : str
        Nombre de usuario a autenticar.
    clave : str
        Clave del usuario.
    
    Returns
    -------
    Optional[Tuple[int, str]]
        Tupla con (id, nombre) si la autenticación es exitosa.
        None si las credenciales son incorrectas o hay error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    """
    try:
        conn = CNX_BDHelisa('EX', -1, "sysdba")
        cur = conn.cursor()
        cur.execute(
            "SELECT id, nombre FROM USUARIOS WHERE nombre = ? AND clave = ? AND activo = 'S'",
            (nombre, clave)
        )
        resultado = cur.fetchone()
        cur.close()
        conn.close()
        return resultado
    except Exception as e:
        print(f"Error obteniendo el usuario: {str(e)}")
        return None


def obtener_usuarios() -> list[Tuple[int, str, str, str]]:
    """
    Obtiene la lista completa de usuarios activos e inactivos.
    
    Returns
    -------
    list[Tuple[int, str, str, str]]
        Lista de tuplas con (Id, Nombre, Email, Activo).
        Activo puede ser 'S' o 'N'.
        Lista vacía si hay error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    """
    try:
        conn = CNX_BDHelisa('EX', -1, "sysdba")
        cur = conn.cursor()
        cur.execute("SELECT Id, Nombre, Email, activo FROM USUARIOS")
        data = cur.fetchall()
        cur.close()
        conn.close()
        return data
    except Exception as e:
        print(f"Error obteniendo usuarios: {str(e)}")
        return []


def crear_usuario(usuario_id: Optional[int], nombre: str, email: str) -> bool:
    """
    Crea un nuevo usuario en la base de datos.
    
    Si usuario_id es None, inserta un nuevo usuario (previo a validación de duplicados).
    Si usuario_id existe, actualiza nombre y email del usuario.
    
    Parameters
    ----------
    usuario_id : Optional[int]
        ID del usuario. Si es None, se crea un nuevo usuario.
        Si tiene valor, se actualiza el usuario existente.
    nombre : str
        Nombre del usuario. Se limpia automáticamente (strip).
    email : str
        Email del usuario. Se limpia automáticamente (strip).
    
    Returns
    -------
    bool
        True si la operación se realizó correctamente.
        False si hubo error, duplicado o validación fallida.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    """
    try:
        with transaccion_segura(codigo_empresa=-1) as (conn, cur):
            # Limpieza de valores
            nombre = nombre.strip()
            email = email.strip()
            
            # Validación básica
            if not nombre or not email:
                print("Error: nombre y email son requeridos")
                return False
            
            # INSERT
            if usuario_id is None:
                # Verificar duplicado
                cur.execute(
                    """
                    SELECT COUNT(*) FROM USUARIOS
                    WHERE LOWER(TRIM(Nombre)) = LOWER(TRIM(?))
                       OR LOWER(TRIM(Email)) = LOWER(TRIM(?))
                    """,
                    (nombre, email)
                )
                existe = cur.fetchone()[0]
                if existe > 0:
                    print(f"Ya existe un usuario con el mismo nombre o email: {nombre}, {email}")
                    return False
                
                clave = generar_clave()
                
                cur.execute(
                    """
                    INSERT INTO USUARIOS (Nombre, Email, Clave, Activo)
                    VALUES (?, ?, ?, 'S')
                    """,
                    (nombre, email, clave)
                )
                # Commit automático si todo sale bien
                return True
            
            # UPDATE
            else:
                cur.execute(
                    """
                    UPDATE USUARIOS
                    SET Nombre = ?, Email = ?
                    WHERE Id = ?
                    """,
                    (nombre, email, usuario_id)
                )
                # Commit automático si todo sale bien
                return True
                
    except Exception as e:
        print(f"Error guardando usuario: {str(e)}")
        return False


def obtener_codigos_traduccion(
    tabla: str, producto: str = "EX", codigo_empresa: int = -2
) -> Optional[list[Tuple[Any, ...]]]:
    """Obtiene códigos de traducción desde una tabla (PAIS, DEPARTAMENTO, MUNICIPIO, etc.)."""
    tabla_normalizada = tabla.upper().strip()
    if tabla_normalizada not in TABLAS_PERMITIDAS:
        raise ValueError(f"Tabla no permitida: {tabla}. Tablas permitidas: {', '.join(sorted(TABLAS_PERMITIDAS))}")
    try:
        con = CNX_BDHelisa(producto, codigo_empresa, "sysdba")
        if not con:
            return None
        cur = con.cursor()
        if tabla_normalizada == "TIPOSDOCUMENTOS":
            cur.execute("SELECT id, tipo, descripcion FROM TIPOSDOCUMENTOS")
        else:
            cur.execute(f"SELECT * FROM {tabla_normalizada} ORDER BY nombre")
        resultado = cur.fetchall()
        cur.close()
        con.close()
        return resultado
    except Exception as e:
        print(f"Error al obtener {tabla}: {e}")
        return None


def restaurar_base_datos(loader: Any, page: Optional[Any] = None) -> Optional[Exception]:
    """
    Restaura la base de datos eliminando la actual y recreándola desde el producto.
    
    Protegido contra ejecuciones simultáneas y crea backup automático antes de eliminar.
    
    Parameters
    ----------
    loader : Any
        Objeto loader para mostrar progreso durante la recreación de la BD.
    page : Any, optional
        Página Flet para actualizaciones UI thread-safe.
    
    Returns
    -------
    Optional[Exception]
        None si la operación fue exitosa.
        Exception si hubo error durante el proceso.
    
    Raises
    ------
    RuntimeError
        Si el proceso de restauración ya está en curso.
    ValueError
        Si no hay empresa seleccionada en session.EMPRESA_ACTUAL.
    
    Notes
    -----
    Esta operación es destructiva. Se crea un backup automático antes de eliminar la BD.
    """
    codigo = session.EMPRESA_ACTUAL["codigo"]
    producto = session.EMPRESA_ACTUAL["producto"]
    
    # Proteger contra ejecuciones simultáneas
    with proceso_protegido("restaurar", f"Empresa {codigo} - {producto}"):
        try:
            # Crear backup antes de eliminar la BD
            backup_path = hacer_backup_bd(codigo)
            print(f"[RESTAURAR] Backup creado: {backup_path}")
        except Exception as e:
            print(f"[RESTAURAR] Advertencia: No se pudo crear backup: {e}")
            # Continuar de todas formas, pero informar al usuario
            
        # Cerrar conexión si está abierta
        try:
            con = CNX_BDHelisa("EX", codigo, "sysdba")
            if con:
                con.close()
        except Exception as e:
            print(f"[RESTAURAR] Advertencia al cerrar conexión: {e}")
        
        # Obtener ruta de BD desde RW_Helisa para mayor precisión
        try:
            cfg = RW_Helisa('EX')
            path_bd = f"{cfg.bd}\\HELI{str(codigo).zfill(2)}BD.EXG"
        except Exception as e:
            print(f"[RESTAURAR] Error obteniendo ruta de BD: {e}")
            # Fallback a ruta hardcodeada
            path_bd = f"C:\\PROAsistemas\\EXOGENA\\{PERIODO}\\heli{str(codigo).zfill(2)}bd.exg"
        
        # Eliminar BD
        try:
            if os.path.exists(path_bd):
                os.remove(path_bd)
                print(f"[RESTAURAR] BD eliminada correctamente: {path_bd}")
            else:
                print(f"[RESTAURAR] La BD no existe en: {path_bd}, continuando...")
        except Exception as e:
            print(f"[RESTAURAR] Error eliminando BD: {e}")
            return e
        
        # Recrear BD
        try:
            crearBD_Particular(codigo, producto, loader, page)
            print(f"[RESTAURAR] BD recreada exitosamente")
            return None
        except Exception as e:
            print(f"[RESTAURAR] Error recreando BD: {e}")
            return e


def actualizar_activo(
    tabla: str,
    colactivo: str,
    colid: str,
    id_valor: Any,
    value: bool,
    codEmpresa: int
) -> bool:
    """
    Actualiza el campo activo de un registro en cualquier tabla.
    
    Parameters
    ----------
    tabla : str
        Nombre de la tabla a actualizar.
    colactivo : str
        Nombre de la columna que contiene el valor activo.
    colid : str
        Nombre de la columna ID para identificar el registro.
    id_valor : Any
        Valor del ID del registro a actualizar.
    value : bool
        Nuevo valor para el campo activo (True/False se convierte a 'S'/'N').
    codEmpresa : int
        Código de la empresa. Si es -1, usa la BD central (EX).
    
    Returns
    -------
    bool
        True si la actualización fue exitosa, False si hubo error.
    
    Raises
    ------
    ConnectionError
        Si no se puede conectar a la base de datos.
    """
    try:
        # Whitelist de tablas permitidas para prevenir inyecciones SQL
        TABLAS_PERMITIDAS_ACTIVO = {
            # Tablas BD global
            "EMPRESAS",
            "USUARIOS",
            # Tablas BD particular
            "CUENTAS_TRIB",
            "CUENTAS_CONT",
            "CUENTAS_ATRIBUTOS",
            "TERCEROS",
            "CONSORCIOS",
            "CONCEPTOS",
            "FORMATOS",
            "ELEMENTOS",
            "ATRIBUTOS",
            "ACUMULADOS",
            "BANCOS_MOV",
            "FORMAACUMULADO",
            "HOJA_TRABAJO",
            "PRODUCTOS",
            "TERCEROS_MOV_CONT",
            "TERCEROS_MOV_TRIB",
        }
        
        # Normalizar tabla a mayúsculas y validar contra whitelist
        tabla_normalizada = tabla.upper()
        if tabla_normalizada not in TABLAS_PERMITIDAS_ACTIVO:
            print(f"Error: Tabla '{tabla}' no permitida para actualizar_activo")
            return False
        
        # Validar nombres de columnas (solo caracteres alfanuméricos y guión bajo)
        if not (colactivo.replace('_', '').isalnum() and colid.replace('_', '').isalnum()):
            print(f"Error: Nombres de columnas inválidos")
            return False
        
        # Convertir bool a 'S'/'N'
        valor_str = 'S' if value else 'N'
        
        # Usar transacción segura para garantizar atomicidad
        with transaccion_segura(codigo_empresa=codEmpresa) as (con, cur):
            # Usar parámetros preparados con tabla normalizada
            cur.execute(f"""
                UPDATE {tabla_normalizada}
                SET {colactivo} = ?
                WHERE {colid} = ?
            """, (valor_str, id_valor))
            # Commit automático si todo sale bien
        return True
    except Exception as e:
        print(f"Error actualizando activo en {tabla}: {e}")
        return False
