"""Adaptador: RW Helisa + `obtener_codigos_traduccion` para catálogos maestros."""

from application.ports.catalogos_maestros_ports import ResultadoFilasTraduccion
from infrastructure.adapters.helisa_firebird import (
    RW_CrearLlaveExogena,
    RW_Helisa,
    crearBD_Global,
)
from infrastructure.persistence.firebird.auth_utils_persistencia import obtener_codigos_traduccion


class FirebirdCatalogosMaestrosRepository:
    """BD global EX y filas de tablas maestras vía legado."""

    def asegurar_bd_global(self) -> None:
        rw = RW_Helisa("EX")
        if not rw.existe:
            RW_CrearLlaveExogena(rw.servidor, rw.bd, rw.fb)
        crearBD_Global()

    def obtener_filas_traduccion(
        self,
        tabla: str,
        producto: str = "EX",
        codigo_empresa: int = -2,
    ) -> ResultadoFilasTraduccion:
        return obtener_codigos_traduccion(tabla, producto, codigo_empresa)
