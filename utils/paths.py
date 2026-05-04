"""
Rutas de recursos (compatible PyInstaller).
"""
import sys
import os


def resource_path(relative_path: str) -> str:
    """Obtiene ruta válida tanto en .py normal como en ejecutable PyInstaller."""
    if hasattr(sys, "_MEIPASS"):
        base_path = sys._MEIPASS
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


IMG_PATH = resource_path(os.path.join("resources", "images"))


def xsd_file_path(formato_codigo: str) -> str:
    """Ruta absoluta al XSD del formato (desarrollo o bundle PyInstaller)."""
    return resource_path(os.path.join("resources", "xsd", f"{formato_codigo}.xsd"))
