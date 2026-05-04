"""Adaptador Firebird: sesión Helisa y creación de BD particular."""

from application.ports.helisa_sesion_ports import UiLoader, UiPage

from infrastructure.adapters.helisa_firebird import RW_Helisa, crearBD_Particular


class FirebirdHelisaSesionRepository:
    """Encapsula RW Helisa y creación de BD particular."""

    def producto_tiene_rw(self, producto: str) -> bool:
        return RW_Helisa(producto).existe

    def crear_bd_particular(
        self,
        codigo: int,
        producto: str,
        loader: UiLoader,
        page: UiPage,
    ) -> None:
        crearBD_Particular(codigo, producto, loader, page)

    def ruta_directorio_exogena(self) -> str:
        return RW_Helisa("EX").bd
