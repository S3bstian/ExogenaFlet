"""Concepto en el flujo Toma de información: fila CONCEPTOS + FORMATO (listado paginado)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Mapping


@dataclass(frozen=True)
class ConceptoTomaInformacion:
    """
    Modelo de dominio para un concepto seleccionable en pantalla.

    Alineado con las claves que arma el listado paginado de conceptos (``conceptos_persistencia``);
    el adaptador Firebird sigue devolviendo dicts y el caso de uso los convierte aquí.
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
    def from_mapping(cls, m: Mapping[str, Any]) -> ConceptoTomaInformacion:
        """Construye desde la fila dictada por infraestructura (mismas claves que el listado paginado)."""

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
        """
        Devuelve el mapa que esperan la acumulación en Firebird y rutas legacy.

        Conserva tipos/claves equivalentes al dict original de Firebird.
        """
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
