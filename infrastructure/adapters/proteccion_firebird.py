"""
Transacciones atómicas, exclusión de procesos concurrentes y backup de archivos .EXG.

Implementación canónica de transacciones y respaldos Firebird.
"""
import os
import shutil
import threading
from contextlib import contextmanager
from datetime import datetime

from core import session

from infrastructure.adapters.helisa_firebird import CNX_BDHelisa, RW_Helisa

_procesos_activos: dict = {}
_lock_procesos = threading.Lock()


@contextmanager
def transaccion_segura(codigo_empresa=None):
    """
    Context manager atómico (commit al salir bien, rollback ante error, cierre de cursor/conexión).
    """
    con = None
    cur = None

    try:
        if codigo_empresa is None:
            if not session.EMPRESA_ACTUAL:
                raise ValueError("No hay empresa seleccionada y no se proporcionó codigo_empresa")
            codigo_empresa = session.EMPRESA_ACTUAL["codigo"]

        con = CNX_BDHelisa("EX", codigo_empresa, "sysdba")
        if con is None:
            raise ConnectionError(f"No se pudo conectar a la BD de la empresa {codigo_empresa}")

        cur = con.cursor()
        yield (con, cur)
        con.commit()

    except Exception as exc:
        if con:
            try:
                con.rollback()
            except Exception as rollback_error:
                print(f"Error al hacer rollback: {rollback_error}")
        raise

    finally:
        if cur:
            try:
                cur.close()
            except Exception:
                pass
        if con:
            try:
                con.close()
            except Exception:
                pass


@contextmanager
def proceso_protegido(proceso_id: str, detalles: str = ""):
    """Evita dos ejecuciones simultáneas del mismo proceso lógico (identificador único)."""
    with _lock_procesos:
        if proceso_id in _procesos_activos:
            proceso_info = _procesos_activos[proceso_id]
            raise RuntimeError(
                f"⚠️ El proceso '{proceso_id}' ya está en curso. "
                f"Iniciado: {proceso_info.get('inicio', 'N/A')}. "
                f"Detalles: {proceso_info.get('detalles', 'N/A')}. "
                f"Espere a que termine antes de intentar nuevamente."
            )

        _procesos_activos[proceso_id] = {
            "inicio": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "detalles": detalles,
        }
        print(f"[PROCESO_PROTEGIDO] Iniciado: '{proceso_id}' - {detalles}")

    try:
        yield

    finally:
        with _lock_procesos:
            if proceso_id in _procesos_activos:
                del _procesos_activos[proceso_id]
                print(f"[PROCESO_PROTEGIDO] Finalizado: '{proceso_id}'")


def hacer_backup_bd(codigo_empresa: int, ruta_destino: str = None) -> str:
    """Copia física del archivo de BD de la empresa bajo la ruta configurada en RW_Helisa('EX')."""
    try:
        cfg = RW_Helisa("EX")
        origen = f"{cfg.bd}\\HELI{str(codigo_empresa).zfill(2)}BD.EXG"

        if not os.path.exists(origen):
            raise FileNotFoundError(f"No se encontró la BD en: {origen}")

        backup_dir = f"{cfg.bd}\\backups"
        os.makedirs(backup_dir, exist_ok=True)

        if ruta_destino is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            ruta_destino = f"{backup_dir}\\HELI{str(codigo_empresa).zfill(2)}BD_backup_{timestamp}.EXG"

        shutil.copy2(origen, ruta_destino)
        print(f"[BACKUP] Backup creado: {ruta_destino}")

        return ruta_destino

    except Exception as exc:
        print(f"[ERROR] No se pudo crear backup: {exc}")
        raise


__all__ = [
    "hacer_backup_bd",
    "proceso_protegido",
    "transaccion_segura",
]
