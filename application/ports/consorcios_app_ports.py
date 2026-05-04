"""Puerto para consorcios en BD de empresa."""

from typing import Any, Dict, List, Optional, Protocol, TypeAlias

ConsorcioRegistro: TypeAlias = Dict[str, Any]
ListaConsorcios: TypeAlias = List[ConsorcioRegistro]


class ConsorciosAppPort(Protocol):
    """CRUD y verificación de consorcios."""

    def obtener_consorcios(self) -> ListaConsorcios:
        ...

    def verificar_consorcio_activo(self, identidad: int) -> bool:
        ...

    def crear_consorcio(self, consorcio: ConsorcioRegistro) -> Optional[int]:
        ...

    def actualizar_consorcio(self, consorcio: ConsorcioRegistro) -> bool:
        ...

    def eliminar_consorcio(self, consorcio_id: int) -> bool:
        ...
