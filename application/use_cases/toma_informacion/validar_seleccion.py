"""Validaciones de negocio para selección de conceptos."""

from typing import List

from domain.entities.concepto_toma_informacion import ConceptoTomaInformacion


def validar_conceptos_seleccionados(conceptos: List[ConceptoTomaInformacion]) -> None:
    """Exige al menos un concepto de dominio antes de delegar la acumulación."""
    if not conceptos:
        raise ValueError("No hay conceptos seleccionados")
