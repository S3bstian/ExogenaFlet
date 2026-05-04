"""Entidades del dominio."""

from domain.entities.concepto_toma_informacion import ConceptoTomaInformacion
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo
from domain.entities.concepto_detalle_hoja_trabajo import ConceptoDetalleHojaTrabajo
from domain.entities.resultado_acumulacion import (
    AdvertenciaAcumulacionSinDatos,
    ResultadoAcumulacion,
)

__all__ = [
    "ConceptoTomaInformacion",
    "ConceptoHojaTrabajo",
    "ConceptoDetalleHojaTrabajo",
    "AdvertenciaAcumulacionSinDatos",
    "ResultadoAcumulacion",
]
