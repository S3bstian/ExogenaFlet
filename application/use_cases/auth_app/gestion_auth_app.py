"""Casos de uso de login y administración de usuarios."""

from typing import Any, Optional

from application.ports.auth_app_ports import AuthAppPort, SesionUsuario, UsuarioDbRow


class GestionAuthAppUseCase:
    """Expone auth sin acoplar la UI a la capa de persistencia legacy."""

    def __init__(self, port: AuthAppPort) -> None:
        self._port = port

    def autenticar_usuario(
        self,
        nombre: str,
        clave: str,
    ) -> Optional[SesionUsuario]:
        return self._port.autenticar_usuario(nombre, clave)

    def obtener_usuarios(self) -> list[UsuarioDbRow]:
        return self._port.obtener_usuarios()

    def crear_o_actualizar_usuario(
        self,
        usuario_id: Optional[int],
        nombre: str,
        email: str,
    ) -> bool:
        return self._port.crear_o_actualizar_usuario(usuario_id, nombre, email)

    def actualizar_activo(
        self,
        tabla: str,
        colactivo: str,
        colid: str,
        id_valor: Any,
        value: bool,
        cod_empresa: int,
    ) -> bool:
        return self._port.actualizar_activo(
            tabla, colactivo, colid, id_valor, value, cod_empresa
        )

    def restaurar_base_datos(
        self,
        loader: Any,
        page: Optional[Any] = None,
    ) -> Optional[Exception]:
        return self._port.restaurar_base_datos(loader, page)
