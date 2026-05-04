"""Operaciones de arranque de BD por empresa."""

from application.ports.helisa_sesion_ports import HelisaSesionPort, UiLoader, UiPage


class GestionHelisaSesionUseCase:
    """Expone RW y creación de BD sin que la UI importe adaptadores Helisa."""

    def __init__(self, port: HelisaSesionPort) -> None:
        self._port = port

    def producto_tiene_rw(self, producto: str) -> bool:
        return self._port.producto_tiene_rw(producto)

    def crear_bd_particular(
        self,
        codigo: int,
        producto: str,
        loader: UiLoader,
        page: UiPage,
    ) -> None:
        self._port.crear_bd_particular(codigo, producto, loader, page)

    def ruta_directorio_exogena(self) -> str:
        return self._port.ruta_directorio_exogena()
