import asyncio
import flet as ft
from core import session
from ui.colors import PINK_50, PINK_200, BLACK, WHITE
from ui.snackbars import mostrar_mensaje
from ui.buttons import BOTON_SECUNDARIO, BOTON_LISTA, BOTON_SUBLISTA
from ui.progress import crear_ring, crear_loader_row, SIZE_MEDIUM, SIZE_LARGE, SIZE_SMALL
from paginas.empresas.consorcios import ConsorciosDialog
from paginas.empresas.infoEmpresas import InfoEmpresasDialog
from paginas.modulopasos.copias.copias import CopiasDialog
from utils.ui_sync import loader_row_fin, loader_row_visibilidad


# Tablero principal (tiles de navegación)
_CELL_HOME_TAM = 150
_GAP_HOME_NAV = 10
_COLORES_TILES_NAV = ("#66A357", "#8B7284", "#D5CA70", "#525D79", "#4F8F92", "#812C5A")


def _container_baldosa_nav(
    bgcolor: str,
    icon,
    label: str,
    w: float,
    h: float,
    left: float,
    top: float,
    on_click,
) -> ft.Container:
    """Tile focuseable (Tab); mismo layout visual que el home original."""
    return ft.Container(
        content=ft.ElevatedButton(
            content=ft.Column(
                [
                    ft.Icon(icon, size=40, color="white"),
                    ft.Text(label, size=14, weight="bold", color="white"),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            width=w,
            height=h,
            style=ft.ButtonStyle(
                bgcolor=bgcolor,
                color="white",
                elevation=0,
                padding=0,
                shape=ft.RoundedRectangleBorder(radius=0),
                overlay_color=ft.Colors.with_opacity(0.15, "white"),
            ),
            on_click=on_click,
        ),
        left=left,
        top=top,
        width=w,
        height=h,
    )


class HomePage(ft.Column):
    def __init__(self, page: ft.Page, app=None):
        super().__init__()
        self._page = page
        self._app = app
        c = app.container
        self._empresas_uc = c.empresas_uc
        self._helisa_uc = c.helisa_uc
        self._auth_uc = c.auth_uc
        self._licenciamiento_uc = c.licenciamiento_uc
        self.expand = True
        self.empresas_column = ft.Column(spacing=-5, scroll=ft.ScrollMode.AUTO, expand=True)
        self.info_dialog = InfoEmpresasDialog(self._page, c)
        self.consorcios_dialog = ConsorciosDialog(self._page, c)
        self.copias_dialog = CopiasDialog(self._page, c)
        self.empresas_NI = []
        self.empresas_PH = []
        self.productos_disponibles = []
        self.submenus = {}
        self.segmented_button = None
        self.loader_home = crear_loader_row("Cargando empresas...", size=SIZE_SMALL)
        self.loader_home.visible = False
    # ---------- Carga de empresas ----------
    def cargar_empresas(self):
        # limpiar para evitar duplicados si view() se llama varias veces
        self.productos_disponibles = []
        self.empresas_NI = []
        self.empresas_PH = []

        self.empresas_NI = self._empresas_uc.obtener_empresas("NI")
        if self.empresas_NI:
            self.productos_disponibles.append("NI")

        self.empresas_PH = self._empresas_uc.obtener_empresas("PH")
        if self.empresas_PH:
            self.productos_disponibles.append("PH")

    def _empresas_filtradas_licenciadas(self, productos: set) -> list[tuple[str, dict]]:
        """Empresas (producto, registro) con licencia activa para cada producto en `productos`."""
        licencia = self._licenciamiento_uc.obtener_licencia()
        empresas: list[tuple[str, dict]] = []
        if "NI" in productos:
            empresas.extend(
                ("NI", e)
                for e in self.empresas_NI
                if licencia and licencia.empresa_activada("NI", int(e["codigo"]))
            )
        if "PH" in productos:
            empresas.extend(
                ("PH", e)
                for e in self.empresas_PH
                if licencia and licencia.empresa_activada("PH", int(e["codigo"]))
            )
        return empresas

    def _restaurar_estilo_otros_submenus(self, submenu_abierto):
        """Cierra otros submenús y devuelve el estilo estándar a sus botones."""
        for _nombre_e, sub in list(self.submenus.items()):
            if sub != submenu_abierto:
                sub.visible = False
                parent = sub.parent
                fila_anterior = parent.controls[0]
                boton_ant = fila_anterior.controls[0]
                boton_ant.icon = None
                boton_ant.icon_color = None
                boton_ant.style = BOTON_LISTA
                parent.update()

    def _marcar_expandir_menu_por_session(self):
        """Si hay empresa en sesión, abre visualmente el submenú que coincide por nombre."""
        if not session.EMPRESA_ACTUAL:
            return
        nombre_session = session.EMPRESA_ACTUAL["nombre"]
        for ctrl in self.empresas_column.controls:
            fila = ctrl.controls[0]
            boton = fila.controls[0]
            submenu = ctrl.controls[1]
            if boton.content == nombre_session:
                submenu.visible = True
                boton.icon = ft.Icons.SUBDIRECTORY_ARROW_RIGHT_SHARP
                boton.icon_color = PINK_200
                boton.style = ft.ButtonStyle(bgcolor=PINK_50, color=BLACK)
                self._selected_button = boton
                break

    def construir_empresas_column(self, productos_seleccionados):
        productos = set(productos_seleccionados or ())
        empresas = self._empresas_filtradas_licenciadas(productos)

        self.submenus.clear()
        self.empresas_column.controls = [
            self.empresa_menu(
                emp["nombre"],
                emp["codigo"],
                emp["identidad"],
                producto,
            )
            for producto, emp in empresas
        ]
        self._marcar_expandir_menu_por_session()
        if self.empresas_column.page:
            self.empresas_column.update()

    def _construir_segmented_productos(self, seleccion_inicial: str) -> ft.SegmentedButton:
        return ft.SegmentedButton(
            allow_multiple_selection=False,
            allow_empty_selection=False,
            selected=[seleccion_inicial],
            segments=[
                ft.Segment(value="NI", label=ft.Text("Norma Internacional")),
                ft.Segment(value="PH", label=ft.Text("Propiedad Horizontal")),
            ],
            on_change=lambda e: self.construir_empresas_column(
                [next(iter(e.control.selected))] if e.control.selected else [seleccion_inicial]
            ),
            style=BOTON_SECUNDARIO,
        )

    def _aplicar_carga_empresas(self):
        """Carga empresas, arma el panel izquierdo y muestra diálogo de activación."""
        loader_row_visibilidad(self._page, self.loader_home, True)

        try:
            self.cargar_empresas()
            if len(self.productos_disponibles) >= 2:
                seleccion_inicial = self.productos_disponibles[0]
                self.segmented_button = self._construir_segmented_productos(seleccion_inicial)
                self._lado_izquierdo.controls = [self.loader_home, self.segmented_button, self.empresas_column]
                self.construir_empresas_column([seleccion_inicial])
            elif len(self.productos_disponibles) == 1:
                self.segmented_button = None
                self._lado_izquierdo.controls = [self.loader_home, self.empresas_column]
                self.construir_empresas_column(list(self.productos_disponibles))
            else:
                self.segmented_button = None
                self._lado_izquierdo.controls = [self.loader_home, self.empresas_column]
        except Exception as ex:
            self.mostrar_mensaje(f"Error cargando empresas: {ex}", 6000)
        finally:
            loader_row_fin(self._page, self.loader_home)

    def _producto_actual_para_etiquetas(self, producto: str) -> str:
        if self.segmented_button and self.segmented_button.selected:
            return next(iter(self.segmented_button.selected), producto)
        return producto

    def _construir_tablero_principal(self) -> ft.Stack:
        cell = _CELL_HOME_TAM
        gap = _GAP_HOME_NAV
        C1, C2, C3, C4, C5, C6 = _COLORES_TILES_NAV

        return ft.Stack(
            width=cell * 4 + gap * 2,
            height=cell * 3 + gap * 2,
            controls=[
                _container_baldosa_nav(
                    C1,
                    ft.Icons.DESCRIPTION,
                    "1. Formatos y conceptos",
                    cell * 2 + gap,
                    cell,
                    0,
                    0,
                    lambda e: self.navegar("/home/formatos_conceptos"),
                ),
                _container_baldosa_nav(
                    C2,
                    ft.Icons.PEOPLE,
                    "2. Cartilla de terceros",
                    cell,
                    cell,
                    cell * 2 + gap * 2,
                    0,
                    lambda e: self.navegar("/home/cartilla_terceros"),
                ),
                _container_baldosa_nav(
                    C3,
                    ft.Icons.UPLOAD_FILE,
                    "3. Toma de información",
                    cell,
                    cell + gap,
                    0,
                    cell + gap,
                    lambda e: self.navegar("/home/toma_informacion"),
                ),
                _container_baldosa_nav(
                    C4,
                    ft.Icons.WORK,
                    "4. Hoja de trabajo",
                    cell,
                    cell * 2 + gap,
                    cell + gap,
                    cell + gap,
                    lambda e: self.navegar("/home/hoja_trabajo"),
                ),
                _container_baldosa_nav(
                    C5,
                    ft.Icons.CONTENT_COPY,
                    "5. Copias",
                    cell,
                    cell,
                    2 * cell + 2 * gap,
                    cell + gap,
                    lambda e: self.navegar(self.copias_dialog.abrir),
                ),
                _container_baldosa_nav(
                    C6,
                    ft.Icons.CODE,
                    "6. Generar XML",
                    cell * 2 + gap,
                    cell,
                    cell * 2 + gap * 2,
                    2 * cell + 2 * gap,
                    lambda e: self.navegar("/home/generar_xml"),
                ),
            ],
            alignment=ft.Alignment(1, -50),
        )

    # ---------- UI principal ----------
    def view(self):
        self._lado_izquierdo = ft.Column(controls=[self.loader_home, self.empresas_column], expand=False)

        tablero = self._construir_tablero_principal()

        return ft.Container(
            expand=True,
            padding=ft.padding.only(left=6, right=6),
            content=ft.Row(
                controls=[self._lado_izquierdo, tablero],
                alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                expand=True,
            ),
        )

    def empresa_menu(self, nombre, codigo, identidad, producto):
        # Loader individual por empresa (determinado para crearBD)
        loader = ft.Row([
            crear_ring(indeterminado=False, size=SIZE_MEDIUM),
            ft.Text("Cargando...", size=11)
        ], visible=False)
        boton = ft.TextButton(
            content=nombre,
            on_click=lambda e: seleccionar_empresa(),
            style=BOTON_LISTA,
            expand=True,
        )

        fila = ft.Row(
            controls=[boton, loader],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        # --- BottomSheet restaurar ---
        def abrir_restaurar_bottomsheet():
            def cerrar_bottomsheet(_):
                self._page.pop_dialog()

            def confirmar_si(_):
                loader_bottom = crear_ring(indeterminado=False, size=SIZE_LARGE)
                bottomsheet.content.content.horizontal_alignment = ft.CrossAxisAlignment.CENTER
                bottomsheet.content.content.controls = [
                    ft.Text("Esto puede tardar...", size=17, weight="bold", color=BLACK),
                    loader_bottom,
                ]
                bottomsheet.update()
                self._page.update()
                
                def _worker():
                    try:
                        resultado = self._auth_uc.restaurar_base_datos(loader_bottom, self._page)
                        self._page.pop_dialog()
                        self._page.update()
                        if resultado is None:
                            self.mostrar_mensaje("¡Restauracion finalizada!", 2222)
                        else:
                            self.mostrar_mensaje(f"Error restaurando: {resultado}", 7000)
                    except Exception as ex:
                        self._page.pop_dialog()
                        self.mostrar_mensaje(f"Error restaurando: {ex}", 7000)
                
                self._page.run_thread(_worker)

            bottomsheet = ft.BottomSheet(
                ft.Container(
                    padding=20,
                    content=ft.Column(
                        [
                            ft.Text(
                                "Este proceso extraera nuevamente la informacion de el producto.\nPerdera los cambios hechos dentro de Exogena\n\n¿Desea continuar?",
                                size=15,
                                weight="bold",
                                color=BLACK,
                            ),
                            ft.Row(
                                [
                                    ft.TextButton(content="No", on_click=cerrar_bottomsheet, style=BOTON_SECUNDARIO),
                                    ft.Button(content="Sí", on_click=confirmar_si, bgcolor=PINK_200, color=WHITE),
                                ],
                                alignment=ft.MainAxisAlignment.END,
                            ),
                        ],
                        spacing=15,
    
                    ),
                ),
                open=True,
                dismissible=False,
                use_safe_area=True,
                size_constraints=ft.BoxConstraints(max_height=210, max_width=420)
            )
            self._page.show_dialog(bottomsheet)
            
        submenu = ft.Column(
            visible=False,
            spacing=-12,
            controls=[
                ft.TextButton(content="Información de empresa", icon=ft.Icons.INFO_OUTLINE_SHARP,
                              on_click=lambda e: self.navegar(self.info_dialog.open_dialog),
                              style=BOTON_SUBLISTA),
                ft.TextButton(content="Consorcios", icon=ft.Icons.GROUPS_3_OUTLINED,
                              on_click=lambda e: self.navegar(self.consorcios_dialog.open_consorcios_dialog),
                              style=BOTON_SUBLISTA),
                ft.TextButton(
                    content=f"Restaurar desde {self._producto_actual_para_etiquetas(producto)}",
                    icon=ft.Icons.DOWNLOAD_OUTLINED,
                    on_click=lambda e: self.navegar(abrir_restaurar_bottomsheet),
                    style=BOTON_SUBLISTA,
                )
            ],
        )
        wrapper = ft.Column(controls=[fila, submenu], spacing=-2)

        def seleccionar_empresa():
            licencia = self._licenciamiento_uc.obtener_licencia()
            if not licencia or not licencia.empresa_activada(producto, int(codigo)):
                self.mostrar_mensaje("Debe activar la empresa en Licenciamiento antes de usarla", 5000)
                return
            session.EMPRESA_ACTUAL = None
            self._restaurar_estilo_otros_submenus(submenu)

            # Abrir/cerrar el actual
            submenu.visible = not submenu.visible
            if submenu.visible:
                boton.icon = ft.Icons.SUBDIRECTORY_ARROW_RIGHT_SHARP
                boton.icon_color = PINK_200
                boton.style = ft.ButtonStyle(bgcolor=PINK_50, color=BLACK)
                loader_row_visibilidad(self._page, loader, True)
                wrapper.update()

                def _worker():
                    try:
                        self._helisa_uc.crear_bd_particular(codigo, producto, loader.controls[0], self._page)
                        session.EMPRESA_ACTUAL = {"codigo": codigo, "nombre": nombre, "producto": producto, "identidad": identidad}
                    except Exception as ex:
                        self.mostrar_mensaje(f"Error creando BD: {ex}", 5555)
                    finally:
                        loader_row_fin(self._page, loader)
                        wrapper.update()
                
                self._page.run_thread(_worker)

            else:
                boton.icon = None
                boton.icon_color = None
                boton.style = BOTON_LISTA
                session.EMPRESA_ACTUAL = None
            wrapper.update()

        self.submenus[nombre] = submenu
        return wrapper

    def mostrar_mensaje(self, texto, duration):
        mostrar_mensaje(self._page, texto, duration)
        
    def navegar(self, ruta):
        if not session.EMPRESA_ACTUAL:
            self.mostrar_mensaje("Debe seleccionar una empresa antes de continuar", 4444)
            return
        if isinstance(ruta, str):
            if self._app:
                self._app._loader_overlay_mostrar(True)
            asyncio.create_task(self._page.push_route(ruta))
        else:
            ruta()