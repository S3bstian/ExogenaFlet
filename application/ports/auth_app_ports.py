"""Puerto para autenticación y gestión de usuarios globales (BD EX)."""

from typing import Any, Optional, Protocol, Tuple, TypeAlias

SesionUsuario: TypeAlias = Tuple[int, str]
UsuarioDbRow: TypeAlias = Tuple[int, str, str, str]


class AuthAppPort(Protocol):
    """Login, usuarios y banderas activo en tablas permitidas."""

    def autenticar_usuario(
        self,
        nombre: str,
        clave: str,
    ) -> Optional[SesionUsuario]:
        ...

    def obtener_usuarios(self) -> list[UsuarioDbRow]:
        ...

    def crear_o_actualizar_usuario(
        self,
        usuario_id: Optional[int],
        nombre: str,
        email: str,
    ) -> bool:
        ...

    def actualizar_activo(
        self,
        tabla: str,
        colactivo: str,
        colid: str,
        id_valor: Any,
        value: bool,
        cod_empresa: int,
    ) -> bool:
        ...

    def restaurar_base_datos(
        self,
        loader: Any,
        page: Optional[Any] = None,
    ) -> Optional[Exception]:
        """Sincroniza BD particular desde producto; puede retornar excepción."""
