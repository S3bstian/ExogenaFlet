"""Adaptador: auth y usuarios sobre BD central."""

from typing import Any, Optional

from application.ports.auth_app_ports import SesionUsuario, UsuarioDbRow
from infrastructure.persistence.firebird.auth_utils_persistencia import (
    actualizar_activo,
    autenticar_usuario,
    crear_usuario,
    obtener_usuarios,
    restaurar_base_datos,
)


class FirebirdAuthAppRepository:
    """Delega en `infrastructure.persistence.firebird.auth_utils_persistencia`."""

    def autenticar_usuario(
        self,
        nombre: str,
        clave: str,
    ) -> Optional[SesionUsuario]:
        return autenticar_usuario(nombre, clave)

    def obtener_usuarios(self) -> list[UsuarioDbRow]:
        return obtener_usuarios()

    def crear_o_actualizar_usuario(
        self,
        usuario_id: Optional[int],
        nombre: str,
        email: str,
    ) -> bool:
        return crear_usuario(usuario_id, nombre, email)

    def actualizar_activo(
        self,
        tabla: str,
        colactivo: str,
        colid: str,
        id_valor: Any,
        value: bool,
        cod_empresa: int,
    ) -> bool:
        return actualizar_activo(
            tabla, colactivo, colid, id_valor, value, cod_empresa
        )

    def restaurar_base_datos(
        self,
        loader: Any,
        page: Optional[Any] = None,
    ) -> Optional[Exception]:
        return restaurar_base_datos(loader, page)
