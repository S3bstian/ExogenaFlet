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
import flet as ft
from paginas.herramientas.herramientas import HerramientasDialog
from paginas.cambioContra import CambioContraDialog

from core import session
from core.settings import PERIODO
from composition.app_container import AppContainer
from ui.colors import FONDO_PAGINA, WHITE, PINK_50, PINK_200, PINK_800, PINK_600, GREY_700
from ui.theme import tema_aplicacion
from ui.progress import crear_loader_row, SIZE_SMALL
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SUBLISTA
from ui.fields import creador_campo_texto
from utils.paths import IMG_PATH
from routing import (
    get_appbar_content,
    update_topbar,
    parent_route_for_back,
    resolve_route,
)
from paginas.utils.banner_prefijo_ctrl import crear_banner_prefijo_ctrl, sync_banner_prefijo
from paginas.licenciamiento.primera_ejecucion import (
    ejecutar_si_corresponde,
)


# Clase app
class MagneticosApp:
    def __init__(self, page):
        """Define `page`, el contenedor de casos de uso (`AppContainer`) y la navegación (`route_change`, `view_pop`)."""
        self.page = page
        self.container = AppContainer()
        self._auth_uc = self.container.auth_uc
        self.periodo = PERIODO
        self.cambio_contra_dialog = CambioContraDialog(self.page)
        self.herramientas_dialog = HerramientasDialog(self.page, self.container)
        self.page.on_route_change = self.route_change
        self.page.on_view_pop = self.view_pop

        """Definicion de objetos de interfaz o controles flet
        login_button = boton de iniciar sesion
        
        logo_helisa = imagen del logo corporativo
        
        msg = mensaje de alerta en la parte inferior
        
        appbar = barra horizontal que al iniciar el programa es la ventana principal pero 
            al interior del mismo se convierte en la barra de navegacion
            
        root = contiene lo que se muestra en pantalla
        """
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

        self.msg = ft.Container(
            content=ft.Text("", color=ft.Colors.GREY_600, visible=False),
            bgcolor=FONDO_PAGINA,
            alignment=ft.Alignment(0, -1),
        )
        
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

    def login(self, e):
        #crea los controles de campo de texto 
        usuario = creador_campo_texto("Ingrese su usuario", ["focus"])
        password = creador_campo_texto("Ingrese su contraseña", ["contraseña"])
        olvido = ft.TextButton(content="¿Olvidó su contraseña?", style=BOTON_SUBLISTA, icon=ft.Icons.LIVE_HELP_SHARP, on_click=lambda e: self.cambio_contra_dialog.open_dialog())

        def close(_):  # Cierra el diálogo y valida credenciales antes de navegar a /home.
            # Flet 0.80: TextField usa .error (no .error_text) para el mensaje y borde rojo
            def set_error(c, msg):
                if hasattr(c, "error"):
                    c.error = msg
                if hasattr(c, "error_text"):
                    c.error_text = msg
                if hasattr(c, "update"):
                    c.update()
            # Campos vacíos
            if usuario.value.strip() == "" or password.value.strip() == "":
                set_error(usuario, "Complete el campo" if not usuario.value.strip() else None)
                set_error(password, "Complete el campo" if not password.value.strip() else None)
                self.page.update()
                return
            val_usuario = self._auth_uc.autenticar_usuario(
                usuario.value.strip(), password.value.strip()
            )
            if not val_usuario:
                set_error(usuario, "Verifique sus credenciales")
                set_error(password, "Verifique sus credenciales")
                self.page.update()
                return
            
            session.USUARIO_ACTUAL = {"id": val_usuario[0], "nombre": val_usuario[1], "email": ""}
            self.page.pop_dialog()  # Flet 0.80: reemplaza dialog.open = False
            self.page.update()
            asyncio.create_task(self.page.push_route("/home"))

        content_col = ft.Column([usuario, password, olvido], tight=True, spacing=12)
        dialog = ft.AlertDialog(
            title=ft.Text("Ingrese sus credenciales.", text_align=ft.TextAlign.CENTER),
            content=ft.Container(content=content_col, width=320, bgcolor=WHITE),
            actions=[ft.Button(content="Entrar", on_click=close, style=BOTON_PRINCIPAL)],
            actions_alignment=ft.MainAxisAlignment.END,
            bgcolor=WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            scrollable=False,
        )
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

    def route_change(self, e):
        """Redirige entre vistas usando el registro de rutas. Loader en overlay solo durante transición."""
        sync_banner_prefijo(self.page, app=self)
        troute = ft.TemplateRoute(self.page.route)
        update_topbar(troute, self)
        res = resolve_route(troute)
        es_transicion = bool(res) and not troute.match("/")
        if res:
            route, h = res
            if es_transicion:
                self._loader_overlay_mostrar(True)
            height, appbar_content = get_appbar_content(h.appbar, self)
            self.appbar.height = height
            self.appbar.content = appbar_content
            self.page.update()

        async def _build_and_navigate():
            try:
                await asyncio.sleep(0)
                if troute.match("/"):
                    if self.page.views:
                        self.page.clean()
                # Una vista por ruta: evita acumular ft.View y controles al navegar (patrón Flet).
                self.page.views.clear()

                if not res:
                    asyncio.create_task(self.page.push_route("/"))
                    return

                content, view_instance = h.build_view(self.page, self)
                padding = ft.Padding.all(3) if route == "/home/hoja_trabajo" else ft.Padding.all(0)
                self.page.views.append(
                    ft.View(
                        route=route,
                        controls=[self.appbar, content],
                        bgcolor=FONDO_PAGINA,
                        padding=padding,
                    )
                )
                self.page.update()
                if h.on_enter:
                    try:
                        h.on_enter(self.page, view_instance)
                    except Exception as ex:
                        print("Error en on_enter:", ex)
            except Exception as ex:
                print(ex)
            finally:
                if res and es_transicion:
                    self._loader_overlay_mostrar(False)
                self.page.update()

        self.page.run_task(_build_and_navigate)

    def view_pop(self, e):
        """Atrás: subrutas /home/... vuelven a /home (sin depender de la pila de vistas)."""
        destino = parent_route_for_back(self.page.route)
        if destino is None:
            return
        self._loader_overlay_mostrar(True)
        asyncio.create_task(self.page.push_route(destino))

def main(page: ft.Page):
    """Iniciador main, se define la page, se construye la app y se pasa la page a la app"""
    # Configuración de la página
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

    msg = ft.Text("", color=ft.Colors.GREY_600, visible=False)
    page.add(msg)
    page.update()  # Aplica full_screen y demás propiedades de ventana
    app = MagneticosApp(page)

    def _continuar_arranque() -> None:
        """Tras condiciones + activación (si aplica): valida catálogos y pinta la ruta inicial."""
        msg.value = "🔄 Validando bases de datos..."
        msg.visible = True
        page.update()
        time.sleep(0.5)

        result = app.container.cargar_catalogos_uc.ejecutar()
        msg.value = result
        msg.visible = True
        page.update()
        time.sleep(0.8 if result.startswith("✅") else 300)

        msg.visible = False
        page.update()
        page.route = "/"
        app.route_change(None)

    ejecutar_si_corresponde(page, app, _continuar_arranque)

if __name__ == '__main__':
    ft.run(main)  # Flet 0.80: run(main) reemplaza a app(target=main) 