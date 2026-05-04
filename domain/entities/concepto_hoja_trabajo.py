"""Entidad de dominio para selección de concepto en Hoja de Trabajo."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class ConceptoHojaTrabajo:
    """Representa el identificador funcional de un concepto dentro de la hoja."""

    codigo: str
    formato: str

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> "ConceptoHojaTrabajo":
        """Construye la entidad desde el payload legado `{codigo, formato}`."""
        codigo = str(m.get("codigo") or "").strip()
        formato = str(m.get("formato") or "").strip()
        return cls(codigo=codigo, formato=formato)

    def as_dict(self) -> Dict[str, str]:
        """Devuelve el payload esperado por los repositorios Firebird actuales."""
        return {"codigo": self.codigo, "formato": self.formato}
