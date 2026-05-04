"""Resultado de la acumulación masiva en hoja de trabajo (toma de información)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class AdvertenciaAcumulacionSinDatos:
    """Cuentas ligadas al concepto para las que no hubo filas de origen (movimientos / maestro)."""

    concepto_codigo: str
    formato: str
    cuentas: List[str]


@dataclass
class ResultadoAcumulacion:
    """Estado final mínimo y accionable que la UI necesita para informar al usuario."""

    cancelado: bool = False
    exito: bool = False
    total_inserts: int = 0
    total_conceptos_solicitados: int = 0
    conceptos_omitidos_sin_elemento: List[str] = field(default_factory=list)
    conceptos_sin_cuentas_en_config: List[str] = field(default_factory=list)
    conceptos_sin_filas_en_hoja: List[str] = field(default_factory=list)
    advertencias_sin_datos: List[AdvertenciaAcumulacionSinDatos] = field(default_factory=list)
    errores_insercion: List[str] = field(default_factory=list)
    mensaje_error_critico: Optional[str] = None
