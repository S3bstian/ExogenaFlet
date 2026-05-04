"""Puerto para validación online de licencia y persistencia local de activación."""

from typing import Optional, Protocol

from domain.entities.licencia import Licencia


class LicenciamientoPort(Protocol):
    """Contrato del licenciamiento: condiciones, clave de activación y empresas."""

    def obtener_licencia(self) -> Optional[Licencia]:
        """Lee licencia previamente activada desde almacenamiento local."""

    def condiciones_aceptadas(self) -> bool:
        """True si ya se aceptaron condiciones (puede faltar aún la clave de activación)."""

    def aceptar_condiciones(self) -> None:
        """Marca persistentemente las condiciones de uso como aceptadas."""

    def activar_licencia(self, clave: str) -> Optional[Licencia]:
        """Valida la clave online y, si es válida, persiste y retorna la licencia."""

    def activar_empresa(self, producto: str, codigo_empresa: int) -> bool:
        """Registra activación irreversible de una empresa contra la licencia actual."""
