"""Adaptador Firebird para la UI de formatos y conceptos."""

from typing import List, Optional, Union
from application.ports.formatos_conceptos_ui_ports import (
    AtributoUiRow,
    ConfigAtributoResultado,
    ConceptoRef,
    ConceptoUiRecord,
    ElementoUiRow,
    FormatoUiRow,
    ListaConceptosUi,
    ListaCuentasConfig,
)
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo

from infrastructure.persistence.firebird.elementos_atributos_persistencia import (
    actualizar_tipo_global,
    guardar_configuracion,
)
from infrastructure.persistence.firebird.elementos_persistencia import (
    consultar_atributos,
    consultar_atributos_por_concepto,
    consultar_configuracion_atributo,
    consultar_elementos,
    consultar_formas_acumulado,
)
from infrastructure.persistence.firebird.conceptos_persistencia import consultar_conceptos_paginados
from infrastructure.persistence.firebird.formatos_persistencia import consultar_formatos


class FirebirdFormatosConceptosUIRepository:
    """Listados vía *_persistencia; mutaciones de formato/atributo en ``elementos_atributos_persistencia``."""

    @staticmethod
    def _legacy_concepto(concepto: ConceptoRef) -> Union[dict[str, str], int, str]:
        """Convierte `ConceptoHojaTrabajo` al payload esperado por la persistencia."""
        if isinstance(concepto, ConceptoHojaTrabajo):
            return concepto.as_dict()
        return concepto

    def obtener_formatos(self) -> List[FormatoUiRow]:
        return consultar_formatos()

    def obtener_conceptos(
        self,
        offset: int = 0,
        limit: int = 20,
        filtro: Optional[str] = None,
    ) -> tuple[ListaConceptosUi, int]:
        return consultar_conceptos_paginados(offset=offset, limit=limit, filtro=filtro)

    def obtener_elementos(
        self,
        concepto: Optional[Union[int, str]] = None,
        formato: Optional[int] = None,
    ) -> List[ElementoUiRow]:
        return consultar_elementos(concepto=concepto, formato=formato)

    def obtener_atributos(
        self,
        elemento_id: Optional[int] = None,
        filtro: Optional[str] = None,
    ) -> List[AtributoUiRow]:
        return consultar_atributos(elemento_id=elemento_id, filtro=filtro)

    def actualizar_tipo_global(self, elem_id: int, nuevo_tipo: str) -> bool:
        return actualizar_tipo_global(elem_id, nuevo_tipo)

    def obtener_atributos_por_concepto(
        self,
        concepto: ConceptoRef,
    ) -> List[AtributoUiRow]:
        return consultar_atributos_por_concepto(self._legacy_concepto(concepto))

    def obtener_forma_acumulado(
        self,
        codigo_empresa: Optional[int] = None,
    ) -> List[ElementoUiRow]:
        return consultar_formas_acumulado(codigo_empresa=codigo_empresa)

    def obtener_configuracion_atributo(
        self,
        idatributo: int,
    ) -> ConfigAtributoResultado:
        return consultar_configuracion_atributo(idatributo)

    def guardar_configuracion_atributo(
        self,
        atributo: ConceptoUiRecord,
        acumulado: int,
        tcuenta: int,
        cuentas: ListaCuentasConfig,
    ) -> bool:
        return guardar_configuracion(atributo, acumulado, tcuenta, cuentas)
