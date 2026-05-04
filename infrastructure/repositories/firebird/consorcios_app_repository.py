"""Adaptador: consorcios."""

from typing import Optional

from application.ports.consorcios_app_ports import ConsorcioRegistro, ListaConsorcios
from infrastructure.persistence.firebird.consorcios_persistencia import (
    actualizar_consorcio,
    crear_consorcio,
    eliminar_consorcio,
    obtener_consorcios,
    verificar_consorcio_activo,
)


class FirebirdConsorciosAppRepository:
    """Delega en `infrastructure.persistence.firebird.consorcios_persistencia`."""

    def obtener_consorcios(self) -> ListaConsorcios:
        return obtener_consorcios()

    def verificar_consorcio_activo(self, identidad: int) -> bool:
        return verificar_consorcio_activo(identidad)

    def crear_consorcio(self, consorcio: ConsorcioRegistro) -> Optional[int]:
        return crear_consorcio(consorcio)

    def actualizar_consorcio(self, consorcio: ConsorcioRegistro) -> bool:
        return actualizar_consorcio(consorcio)

    def eliminar_consorcio(self, consorcio_id: int) -> bool:
        return eliminar_consorcio(consorcio_id)
