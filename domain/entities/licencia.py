"""Licencia de Información Exógena: producto, cupo y empresas activadas."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List


@dataclass
class Licencia:
    """Estado completo del licenciamiento que necesita la UI para gating y conteos."""

    producto: str
    clave: str
    limite_empresas: int
    empresas_activadas: List[str] = field(default_factory=list)
    condiciones_aceptadas: bool = False

    def cupo_disponible(self) -> int:
        """Número de empresas que aún se pueden activar bajo esta licencia."""
        return max(self.limite_empresas - len(self.empresas_activadas), 0)

    def puede_activar_otra(self) -> bool:
        """True si el cupo permite activar al menos una empresa más."""
        return self.cupo_disponible() > 0

    @staticmethod
    def clave_empresa(producto: str, codigo: int) -> str:
        """Clave estable por empresa y producto para soportar NI/PH simultáneo."""
        return f"{str(producto).strip().upper()}:{int(codigo)}"

    def empresa_activada(self, producto: str, codigo: int) -> bool:
        """True si la empresa (producto+codigo) ya está vinculada a esta licencia."""
        return self.clave_empresa(producto, codigo) in set(self.empresas_activadas)
