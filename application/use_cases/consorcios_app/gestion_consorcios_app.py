"""Orquestación de consorcios para la UI."""

from typing import Optional

from application.ports.consorcios_app_ports import (
    ConsorcioRegistro,
    ConsorciosAppPort,
    ListaConsorcios,
)


class GestionConsorciosAppUseCase:
    """Expone consorcios sin acoplar la UI a Firebird."""

    def __init__(self, port: ConsorciosAppPort) -> None:
        self._port = port

    def obtener_consorcios(self) -> ListaConsorcios:
        return self._port.obtener_consorcios()

    def verificar_consorcio_activo(self, identidad: int) -> bool:
        return self._port.verificar_consorcio_activo(identidad)

    def crear_consorcio(self, consorcio: ConsorcioRegistro) -> Optional[int]:
        return self._port.crear_consorcio(consorcio)

    def actualizar_consorcio(self, consorcio: ConsorcioRegistro) -> bool:
        return self._port.actualizar_consorcio(consorcio)

    def eliminar_consorcio(self, consorcio_id: int) -> bool:
        return self._port.eliminar_consorcio(consorcio_id)
