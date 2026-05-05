"""
Punto de entrada Flet de Información Exógena.

Por qué existe: arranca la ventana, compone navegación y delega negocio en
`AppContainer` (casos de uso), sin acoplar la UI a Firebird.

Qué hace: define `InformacionExogenaApp` (appbar, login, transición de rutas) y `main`,
que configura `ft.Page` y el flujo de arranque (licenciamiento, catálogos, ruta inicial).

Cómo se usa: ejecutar este módulo (`python main.py`) o `ft.run(main)` desde otro script.
"""

import asyncio
import time
from typing import Any

import flet as ft
from paginas.cambioContra import CambioContraDialog
from paginas.herramientas.herramientas import HerramientasDialog

from core import session
from composition.app_container import AppContainer
from core.settings import PERIODO
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SUBLISTA
from ui.colors import FONDO_PAGINA, PINK_50, PINK_200, PINK_600, WHITE
from ui.fields import creador_campo_texto
from ui.progress import SIZE_SMALL, crear_loader_row
from ui.theme import tema_aplicacion
from routing import (
    get_appbar_content,
    parent_route_for_back,
    resolve_route,
    update_topbar,
)
from utils.paths import IMG_PATH
from paginas.licenciamiento.primera_ejecucion import (
    ejecutar_si_corresponde,
)
from paginas.utils.banner_prefijo_ctrl import crear_banner_prefijo_ctrl, sync_banner_prefijo


def _configurar_pagina_principal(page: ft.Page) -> None:
    """Aplica configuración visual y de ventana de la aplicación."""
    page.title = "Información Exógena"
    page.window.icon = f"{IMG_PATH}/icono.ico"
    page.window.width = 1024
    page.window.height = 768
    page.window.min_width = 1024
    page.window.min_height = 768
    page.window.maximized = False
    page.theme = tema_aplicacion()
    page.theme_mode = ft.ThemeMode.LIGHT
    page.theme.page_transitions.windows = "cupertino"
    page.bgcolor = FONDO_PAGINA


def _mostrar_mensaje_arranque(page: ft.Page, mensaje: ft.Text, texto: str) -> None:
    """Actualiza el mensaje temporal mostrado durante la inicialización."""
    mensaje.value = texto
    mensaje.visible = True
    page.update()


class InformacionExogenaApp:
    def __init__(self, page: ft.Page):
        """Inicializa página, contenedor de casos de uso y handlers de navegación."""
        self.page = page
        self.container = AppContainer()
        self._auth_uc = self.container.auth_uc
        self.periodo = PERIODO
        self.cambio_contra_dialog = CambioContraDialog(self.page)
        self.herramientas_dialog = HerramientasDialog(self.page, self.container)
        self._registrar_eventos_pagina()
        self._crear_controles_base()
        self._crear_appbar_base()

    def _registrar_eventos_pagina(self) -> None:
        """Conecta callbacks de navegación de Flet con la app."""
        self.page.on_route_change = self.route_change
        self.page.on_view_pop = self.view_pop

    def _crear_controles_base(self) -> None:
        """Construye controles reutilizables en todas las rutas."""
        self.login_button = ft.TextButton(content="Iniciar Sesión", on_click=self.login, icon=ft.Icons.SUPERVISED_USER_CIRCLE_OUTLINED, style=BOTON_PRINCIPAL, visible=False)
        self.logo_helisa = ft.Image(
            src=IMG_PATH + "/helisa.png",
            width=600,
            height=310,
            fit=ft.BoxFit.CONTAIN,
        )
        self.backbutton = ft.OutlinedButton("Atras", icon=ft.Icons.ARROW_BACK_IOS_NEW_SHARP, icon_color=PINK_600, style=BOTON_SECUNDARIO,
                                            visible=False, on_click=self.view_pop)
        self.loader_overlay = crear_loader_row("Cargando...", size=SIZE_SMALL)
        # Mismo control en cada reconstrucción del appbar (Ctrl+dígitos en hoja / cartilla).
        self._outer_banner_prefijo_appbar, self._txt_banner_prefijo_appbar = crear_banner_prefijo_ctrl(expand=False)

    def _crear_appbar_base(self) -> None:
        """Construye el appbar inicial antes de reconfigurarlo por ruta."""
        self.appbar = ft.Container(
            padding=ft.padding.symmetric(horizontal=12, vertical=6),
            content=ft.Column([
                ft.Row(controls=[
                        self.logo_helisa,
                        ft.Container(expand=True),
                        self.backbutton,
                        self.login_button
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER),
            height=666,
            bgcolor=PINK_50,
            # Permite que el logo de /home (Stack en routing) se pinte fuera del alto fijo del appbar.
            clip_behavior=ft.ClipBehavior.NONE,
        )

    @staticmethod
    def _set_control_error(control: ft.Control, message: str | None) -> None:
        """Compatibilidad entre versiones de Flet para mostrar error en campos."""
        if hasattr(control, "error"):
            control.error = message
        if hasattr(control, "error_text"):
            control.error_text = message
        if hasattr(control, "update"):
            control.update()

    @staticmethod
    def _credenciales_vacias(usuario: ft.TextField, password: ft.TextField) -> bool:
        """Valida campos obligatorios y marca errores de forma consistente."""
        usuario_vacio = usuario.value.strip() == ""
        password_vacio = password.value.strip() == ""
        if not (usuario_vacio or password_vacio):
            return False

        InformacionExogenaApp._set_control_error(usuario, "Complete el campo" if usuario_vacio else None)
        InformacionExogenaApp._set_control_error(password, "Complete el campo" if password_vacio else None)
        return True

    def _autenticar_credenciales(self, usuario: ft.TextField, password: ft.TextField):
        """Autentica usuario y devuelve la tupla de sesión o `None`."""
        return self._auth_uc.autenticar_usuario(
            usuario.value.strip(),
            password.value.strip(),
        )

    def _mostrar_error_credenciales(self, usuario: ft.TextField, password: ft.TextField) -> None:
        """Informa credenciales inválidas en ambos campos para feedback inmediato."""
        self._set_control_error(usuario, "Verifique sus credenciales")
        self._set_control_error(password, "Verifique sus credenciales")

    def _crear_controles_login(self) -> tuple[ft.TextField, ft.TextField, ft.TextButton]:
        """Construye controles del diálogo de autenticación."""
        usuario = creador_campo_texto("Ingrese su usuario", ["focus"])
        password = creador_campo_texto("Ingrese su contraseña", ["contraseña"])
        olvido = ft.TextButton(
            content="¿Olvidó su contraseña?",
            style=BOTON_SUBLISTA,
            icon=ft.Icons.LIVE_HELP_SHARP,
            on_click=lambda _evento: self.cambio_contra_dialog.open_dialog(),
        )
        return usuario, password, olvido

    def _procesar_login(self, usuario: ft.TextField, password: ft.TextField) -> None:
        """Valida y autentica credenciales; navega a `/home` en caso exitoso."""
        if self._credenciales_vacias(usuario, password):
            self.page.update()
            return

        val_usuario = self._autenticar_credenciales(usuario, password)
        if not val_usuario:
            self._mostrar_error_credenciales(usuario, password)
            self.page.update()
            return

        session.USUARIO_ACTUAL = {"id": val_usuario[0], "nombre": val_usuario[1], "email": ""}
        self.page.pop_dialog()  # Flet 0.80: reemplaza dialog.open = False
        self.page.update()
        asyncio.create_task(self.page.push_route("/home"))

    def _crear_dialogo_login(
        self,
        usuario: ft.TextField,
        password: ft.TextField,
        olvido: ft.TextButton,
    ) -> ft.AlertDialog:
        """Arma y retorna el AlertDialog de autenticación."""
        content_col = ft.Column([usuario, password, olvido], tight=True, spacing=12)
        return ft.AlertDialog(
            title=ft.Text("Ingrese sus credenciales.", text_align=ft.TextAlign.CENTER),
            content=ft.Container(content=content_col, width=320, bgcolor=WHITE),
            actions=[
                ft.Button(
                    content="Entrar",
                    on_click=lambda _evento: self._procesar_login(usuario, password),
                    style=BOTON_PRINCIPAL,
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            scrollable=False,
        )

    def login(self, e: ft.ControlEvent) -> None:
        """Muestra el diálogo de login y redirige a `/home` al autenticarse."""
        usuario, password, olvido = self._crear_controles_login()
        dialog = self._crear_dialogo_login(usuario, password, olvido)
        self.page.show_dialog(dialog)  # Flet 0.80: reemplaza page.open()
        self.page.update()

    def _loader_overlay_mostrar(self, mostrar: bool):
        """Loader en overlay (top-right). Add/remove explícito: visible solo durante transiciones."""
        if mostrar:
            if not getattr(self, "_loader_ctn", None) or self._loader_ctn not in self.page.overlay:
                self._loader_ctn = ft.Container(
                    content=self.loader_overlay,
                    top=18,
                    right=155,
                    alignment=ft.Alignment(255, 0),
                )
                self.page.overlay.append(self._loader_ctn)
        else:
            ctn = getattr(self, "_loader_ctn", None)
            if ctn and ctn in self.page.overlay:
                self.page.overlay.remove(ctn)
        self.page.update()

    def _actualizar_appbar_para_ruta(self, route_handler: Any) -> None:
        """Actualiza appbar según metadatos de la ruta activa."""
        height, appbar_content = get_appbar_content(route_handler.appbar, self)
        self.appbar.height = height
        self.appbar.content = appbar_content
        self.page.update()

    @staticmethod
    def _padding_para_ruta(route: str | None) -> ft.Padding:
        """Define padding especial para hoja de trabajo y cero para el resto."""
        return ft.Padding.all(3) if route == "/home/hoja_trabajo" else ft.Padding.all(0)

    @staticmethod
    def _ejecutar_on_enter_seguro(handler: Any, page: ft.Page, view_instance: Any) -> None:
        """Ejecuta `on_enter` cuando existe, aislando errores de la vista."""
        if not handler.on_enter:
            return
        try:
            handler.on_enter(page, view_instance)
        except Exception as ex:
            print("Error en on_enter:", ex)

    def route_change(self, e: ft.RouteChangeEvent) -> None:
        """Redirige entre vistas usando el registro de rutas con loader transitorio."""
        sync_banner_prefijo(self.page, app=self)
        troute = ft.TemplateRoute(self.page.route)
        update_topbar(troute, self)
        res = resolve_route(troute)
        route: str | None = None
        es_transicion = bool(res) and not troute.match("/")
        if res:
            route, h = res
            if es_transicion:
                self._loader_overlay_mostrar(True)
            self._actualizar_appbar_para_ruta(h)

        self.page.run_task(self._build_and_navigate, troute, res, es_transicion, route)

    def _crear_vista(self, route: str | None, content: ft.Control) -> ft.View:
        """Construye la `ft.View` con appbar y contenido principal."""
        return ft.View(
            route=route,
            controls=[self.appbar, content],
            bgcolor=FONDO_PAGINA,
            padding=self._padding_para_ruta(route),
        )

    async def _build_and_navigate(
        self,
        troute: ft.TemplateRoute,
        res: Any,
        es_transicion: bool,
        route: str | None,
    ) -> None:
        """Construye la vista activa para la ruta y ejecuta `on_enter` cuando aplique."""
        try:
            await asyncio.sleep(0)
            if troute.match("/") and self.page.views:
                self.page.clean()

            # Una vista por ruta: evita acumular ft.View y controles al navegar (patrón Flet).
            self.page.views.clear()

            if not res:
                asyncio.create_task(self.page.push_route("/"))
                return

            _, handler = res
            content, view_instance = handler.build_view(self.page, self)
            self.page.views.append(self._crear_vista(route, content))
            self.page.update()
            self._ejecutar_on_enter_seguro(handler, self.page, view_instance)
        except Exception as ex:
            print(ex)
        finally:
            if res and es_transicion:
                self._loader_overlay_mostrar(False)
            self.page.update()

    def view_pop(self, e: ft.ViewPopEvent | None):
        """Atrás: subrutas /home/... vuelven a /home (sin depender de la pila de vistas)."""
        destino = parent_route_for_back(self.page.route)
        if destino is None:
            return
        self._loader_overlay_mostrar(True)
        asyncio.create_task(self.page.push_route(destino))

def main(page: ft.Page):
    """Configura la ventana principal y dispara el flujo inicial de la app."""
    _configurar_pagina_principal(page)

    msg = ft.Text("", color=ft.Colors.GREY_600, visible=False)
    page.add(msg)
    page.update()  # Aplica full_screen y demás propiedades de ventana
    app = InformacionExogenaApp(page)

    def _continuar_arranque() -> None:
        """Tras condiciones + activación (si aplica): valida catálogos y pinta la ruta inicial."""
        _mostrar_mensaje_arranque(page, msg, "🔄 Validando bases de datos...")
        time.sleep(0.5)

        result = app.container.cargar_catalogos_uc.ejecutar()
        _mostrar_mensaje_arranque(page, msg, result)
        time.sleep(0.8 if result.startswith("✅") else 300)

        msg.visible = False
        page.update()
        page.route = "/"
        app.route_change(None)

    ejecutar_si_corresponde(page, app, _continuar_arranque)

if __name__ == "__main__":
    ft.run(main)  # Flet 0.80: run(main) reemplaza a app(target=main)