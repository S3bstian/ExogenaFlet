"""Puertos para el flujo Generar XML (validación XSD y generación)."""

from typing import Any, Dict, List, Optional, Protocol, Tuple, TypeAlias

FormatoRow: TypeAlias = Tuple[Any, ...]
DatosIdentidadRow: TypeAlias = Tuple[Any, ...]
CabeceraFormato: TypeAlias = Dict[str, Any]
AtributoXsdMeta: TypeAlias = Dict[str, Any]
AtributosXsdMap: TypeAlias = Dict[str, AtributoXsdMeta]
RegistroHojaXml: TypeAlias = Dict[str, Any]
HojaParaXml: TypeAlias = Dict[str, RegistroHojaXml]
XmlGeneradoItem: TypeAlias = Tuple[str, int]


class GenerarXmlPort(Protocol):
    """Contrato de acceso a formatos y lógica XML/XSD del módulo."""

    def obtener_formatos(self) -> List[FormatoRow]:
        """Lista de formatos para el diálogo inicial."""

    def actualizar_formato(self, campos: CabeceraFormato, formato: str) -> bool:
        """Persiste cabecera de formato antes de generar."""

    def parsear_xsd(self, formato_codigo: str) -> AtributosXsdMap:
        """Metadatos XSD por nombre de atributo."""

    def obtener_orden_atributos_xsd(self, formato_codigo: str) -> List[str]:
        """Orden de atributos según XSD."""

    def obtener_elemento_detalle_xsd(self, formato_codigo: str) -> Optional[str]:
        """Nombre del elemento detalle en el XSD."""

    def obtener_datos_identidad(self, formato_codigo: str) -> List[DatosIdentidadRow]:
        """Filas de hoja para el formato (identidades / atributos)."""

    def validar_formato_xsd(
        self,
        formato_codigo: str,
        atributos_xsd: Optional[AtributosXsdMap] = None,
        rows: Optional[List[DatosIdentidadRow]] = None,
    ) -> AtributosXsdMap:
        """Valida datos de hoja contra el esquema."""

    def obtener_hoja_para_generar(
        self,
        formato_codigo: str,
        rows: Optional[List[DatosIdentidadRow]] = None,
    ) -> HojaParaXml:
        """Agrupa datos de hoja para serializar a XML."""

    def generar_xml_formato(
        self,
        formato_codigo: str,
        datos_cabecera: CabeceraFormato,
        orden_atributos: Optional[List[str]] = None,
        elemento_detalle: Optional[str] = None,
        datos_hoja: Optional[HojaParaXml] = None,
    ) -> List[XmlGeneradoItem]:
        """Genera contenidos XML (y conteos por archivo)."""
