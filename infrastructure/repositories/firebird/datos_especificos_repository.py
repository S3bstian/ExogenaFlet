"""Adaptador: datos específicos vía módulo legacy."""

from typing import Any, List, Optional
from application.ports.datos_especificos_ports import ListaDatosEspecificos

from infrastructure.persistence.firebird.datos_especificos_persistencia import (
    actualizar_hijos_padre_subtipo,
    crear_dato_especifico,
    eliminar_dato_especifico,
    obtener_opciones_datos_especificos,
    obtener_opciones_datos_especificos_por_codigos,
    obtener_padres_subtipo,
    obtener_tabla_padre_para_catalogo_dependiente,
)


class FirebirdDatosEspecificosRepository:
    """Delega en `infrastructure.persistence.firebird.datos_especificos_persistencia`."""

    def obtener_opciones_datos_especificos(
        self,
        tabla: str,
        padre_tabla: Optional[str] = None,
        padre_valor: Optional[Any] = None,
    ) -> ListaDatosEspecificos:
        return obtener_opciones_datos_especificos(tabla, padre_tabla, padre_valor)

    def obtener_padres_subtipo(
        self,
        tabla: Optional[str] = None,
    ) -> ListaDatosEspecificos:
        return obtener_padres_subtipo(tabla)

    def obtener_tabla_padre_para_catalogo_dependiente(self, tabla_hija: str) -> Optional[str]:
        return obtener_tabla_padre_para_catalogo_dependiente(tabla_hija)

    def obtener_opciones_datos_especificos_por_codigos(
        self,
        codigos: List[int],
    ) -> ListaDatosEspecificos:
        return obtener_opciones_datos_especificos_por_codigos(codigos)

    def actualizar_hijos_padre_subtipo(
        self,
        tabla: str,
        codigo_padre: int,
        hijos: List[int],
    ) -> bool:
        return actualizar_hijos_padre_subtipo(tabla, codigo_padre, hijos)

    def crear_dato_especifico(
        self,
        tabla: str,
        descripcion: str,
        codigos_base: Optional[List[int]] = None,
    ) -> Optional[int]:
        return crear_dato_especifico(tabla, descripcion, codigos_base)

    def eliminar_dato_especifico(self, tabla: str, codigo: int) -> bool:
        return eliminar_dato_especifico(tabla, codigo)
