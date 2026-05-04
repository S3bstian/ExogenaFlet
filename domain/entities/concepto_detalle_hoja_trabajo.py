"""Entidad de dominio para el concepto completo usado por herramientas de hoja."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class ConceptoDetalleHojaTrabajo:
    """
    Snapshot completo del concepto (consulta de CONCEPTOS + FORMATO).

    Se usa para decisiones de negocio en UI (cuantias, exterior, fideicomiso),
    evitando dependencias a claves sueltas en diccionarios.
    """

    id: str
    codigo: str
    formato: str
    descripcion: str
    literal: str
    cc_mm_identidad: str
    cc_mm_nombre: str
    cc_mm_valor: str
    exterior_identidad: str
    exterior_nombre: str
    activo: str

    @classmethod
    def from_mapping(cls, m: Mapping[str, Any]) -> "ConceptoDetalleHojaTrabajo":
        """Construye la entidad desde el dict legado devuelto por infraestructura."""

        def _s(key: str) -> str:
            v = m.get(key)
            if v is None:
                return ""
            return str(v).strip()

        return cls(
            id=_s("id"),
            codigo=_s("codigo"),
            formato=_s("formato"),
            descripcion=_s("descripcion"),
            literal=_s("literal"),
            cc_mm_identidad=_s("cc_mm_identidad"),
            cc_mm_nombre=_s("cc_mm_nombre"),
            cc_mm_valor=_s("cc_mm_valor"),
            exterior_identidad=_s("exterior_identidad"),
            exterior_nombre=_s("exterior_nombre"),
            activo=_s("activo"),
        )

    def as_dict(self) -> Dict[str, str]:
        """Payload compatible con helpers legacy durante la migracion."""
        return {
            "id": self.id,
            "codigo": self.codigo,
            "formato": self.formato,
            "descripcion": self.descripcion,
            "literal": self.literal,
            "cc_mm_identidad": self.cc_mm_identidad,
            "cc_mm_nombre": self.cc_mm_nombre,
            "cc_mm_valor": self.cc_mm_valor,
            "exterior_identidad": self.exterior_identidad,
            "exterior_nombre": self.exterior_nombre,
            "activo": self.activo,
        }

    @property
    def tiene_cc_mm(self) -> bool:
        """Indica si el concepto permite la herramienta de cuantias menores."""
        return bool(self.cc_mm_identidad and self.cc_mm_nombre and self.cc_mm_valor)

    @property
    def tiene_exterior(self) -> bool:
        """Indica si el concepto permite la herramienta de NITs extranjeros."""
        return bool(self.exterior_identidad and self.exterior_nombre)
