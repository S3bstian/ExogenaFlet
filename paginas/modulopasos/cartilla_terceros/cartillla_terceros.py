import flet as ft
from ui.colors import PINK_50, PINK_200, PINK_600, PINK_800, GREY_700
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
from paginas.modulopasos.hoja_trabajo.hoja_tools_front import estado_panel_herramientas
from paginas.modulopasos.cartilla_terceros.herramientas_tercero import TerceroDialog
from paginas.utils.paginacion import (
    DEBOUNCE_PREFIJOS_SEC,
    build_pagination_label,
    pagination_text_value,
    normalize_digit_key,
    reset_page_prefix_buffer,
    reset_prefix_buffer,
    tecla_es_avpag,
    tecla_es_repag,
    tecla_es_solo_modificador,
)
from paginas.utils.tooltips import TooltipId, tooltip
from paginas.utils.banner_prefijo_ctrl import sync_banner_prefijo
from ui.snackbars import crear_snackbar, mostrar_mensaje, snackbar_invisible_para_cerrar
from utils.ui_sync import loader_row_visibilidad

class CartillaTercerosPage(ft.Column):
    def __init__(self, page: ft.Page, app=None, *, limit=20):
        super().__init__(spacing=0, alignment=ft.MainAxisAlignment.CENTER)
        self._page = page
        self._app = app  # InformacionExogenaApp: aviso Ctrl+dígitos en el appbar
        self._terceros_uc = app.container.terceros_cartilla_uc
        self.dialog_tercero = TerceroDialog(page, self)
        self.limit = limit
        self.offset = 0
        self.terceros = []
        self.terceros_filtrados = []
        self.dividir_nombres_modo = False
        self.dividir_nombres_seleccion = []
        self.snackbar_dividir = None
        self._buscar_handle = None
        self.total_terceros = 0
        # Buffers de teclado:
        # - Ctrl+prefijo (identidad): foco / selección.
        # - Alt+prefijo (número de página): salto directo de página.
        self._prefix_buffer = ""
        self._prefix_buffer_timer = None
        self._page_prefix_buffer = ""
        self._page_prefix_timer = None
        self.herramientas_abiertas = False

        from ui.progress import crear_loader_row, SIZE_SMALL
        self.loader = crear_loader_row("Cargando terceros...", size=SIZE_SMALL)
        self.loader.visible = False

        self.mensaje = ft.Text("", size=14, italic=True, visible=False, text_align=ft.TextAlign.CENTER)

        self.search_field = self._crear_search_field()
        self.table = self._crear_tabla_terceros()
        self._actualizar_columna_tabla()
        self.pagination_text_footer = build_pagination_label(1, 1)
        self.nav_row = self._crear_nav_row()
        self._crear_panel_herramientas()
        self.table_scroll = self._crear_table_scroll()
        self.content = self._crear_layout_principal()

    def view(self):
        return self.content

    def _crear_search_field(self) -> ft.TextField:
        """Construye campo de búsqueda de terceros."""
        return ft.TextField(
            label="Buscar",
            hint_text="Ej: 123456789 o Comercial S.A.",
            prefix_icon=ft.Icons.PERSON_SEARCH,
            border_radius=10,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            on_change=self._buscar_tercero,
            height=37,
            width=222,
        )

    def _crear_tabla_terceros(self) -> ft.DataTable:
        """Construye DataTable base para cartilla de terceros."""
        return ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Tipo documento")),
                ft.DataColumn(ft.Text("Razón Social")),
                ft.DataColumn(ft.Text("Identidad")),
                ft.DataColumn(ft.Text("Dirección")),
                ft.DataColumn(ft.Text("Acciones")),
            ],
            rows=[],
            heading_row_height=28,
            data_row_min_height=25,
            data_row_max_height=25,
            column_spacing=10,
            heading_row_color=PINK_50,
            divider_thickness=0.5,
        )

    def _crear_nav_row(self) -> ft.Row:
        """Construye barra inferior de paginación."""
        return ft.Row(
            [
                ft.ElevatedButton(
                    "Anterior",
                    on_click=lambda e: self.paginar(-1),
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_SHARP,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    margin=ft.margin.only(right=66),
                    tooltip=tooltip(TooltipId.PAGINA_BTN_ANTERIOR),
                ),
                self.pagination_text_footer,
                ft.ElevatedButton(
                    "Siguiente",
                    on_click=lambda e: self.paginar(1),
                    icon=ft.Icons.ARROW_FORWARD_IOS_SHARP,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    margin=ft.margin.only(left=66),
                    tooltip=tooltip(TooltipId.PAGINA_BTN_SIGUIENTE),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )

    def _items_herramientas(self) -> list[tuple[str, str, callable]]:
        """Define botones de herramientas y sus handlers."""
        return [
            ("Nuevo tercero", ft.Icons.ADD, lambda e: self.dialog_tercero.abrir(None)),
            ("Actualizar Cartilla Terceros", ft.Icons.CLOUD_SYNC_OUTLINED, lambda e: self.cargar_terceros()),
            ("Reemplazar", ft.Icons.SYNC, lambda e: self.dialog_tercero.abrir(origen="reemplazar")),
            ("Dividir nombres", ft.Icons.CONTENT_CUT, lambda e: self._activar_dividir_nombres()),
        ]

    def _crear_panel_herramientas(self) -> None:
        """Inicializa fila expandible de herramientas y botón toggle."""
        self.herramientas_row = ft.Row(
            controls=[
                ft.OutlinedButton(
                    titulo,
                    icon=icono,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    on_click=accion,
                )
                for titulo, icono, accion in self._items_herramientas()
            ],
            spacing=3,
            expand=False,
            scroll=ft.ScrollMode.AUTO,
        )
        self.herramientas_container = ft.Container(
            content=self.herramientas_row,
            width=0,
            opacity=0,
            visible=False,
            height=40,
        )
        self.boton_toggle = ft.TextButton(
            "Herramientas",
            icon=ft.Icons.KEYBOARD_DOUBLE_ARROW_LEFT,
            icon_color=PINK_600,
            style=BOTON_SECUNDARIO_SIN,
            tooltip="Desplegar herramientas",
            on_click=self.toggle_herramientas,
        )
        self.panel_herramientas = ft.Container(
            content=ft.Row(
                [self.boton_toggle, self.herramientas_container],
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )

    def _crear_table_scroll(self) -> ft.Container:
        """Crea contenedor scrollable que centra la tabla en el área disponible."""
        return ft.Container(
            content=ft.Column(
                controls=[self.table],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            expand=True,
            alignment=ft.Alignment(0, -1),
        )

    def _crear_header_principal(self) -> ft.Row:
        """Construye encabezado principal de la vista cartilla."""
        return ft.Row(
            [
                ft.Text("Cartilla de Terceros", size=18, weight=ft.FontWeight.BOLD),
                self.search_field,
                self.panel_herramientas,
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            height=45,
        )

    def _crear_layout_principal(self) -> ft.Column:
        """Arma layout principal con header, loader, tabla, navegación y mensaje."""
        return ft.Column(
            [
                self._crear_header_principal(),
                self.loader,
                ft.Column(
                    controls=[self.table_scroll, self.nav_row],
                    expand=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                self.mensaje,
            ],
            spacing=15,
            expand=True,
            margin=ft.margin.only(bottom=5),
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _texto_celda(self, valor: str, *, max_lines: int = 1) -> ft.Text:
        """ sin wrap, elipsis y tooltip con el texto completo."""
        t = (valor or "").strip().replace("\r", " ").replace("\n", " ")
        while "  " in t:
            t = t.replace("  ", " ")
        return ft.Text(
            t,
            text_align=ft.TextAlign.START,
            max_lines=max_lines,
            no_wrap=True,
            overflow=ft.TextOverflow.ELLIPSIS,
            tooltip=t,
            selectable=True,
            style=ft.TextStyle(height=0.9),
            expand=True,
        )

    def _data_cell_cartilla(self, control: ft.Control) -> ft.DataCell:
        """Contenido alineado al inicio de la celda (horizontal y vertical)."""
        return ft.DataCell(
            ft.Container(
                content=ft.Row(
                    [control],
                    expand=True,
                    alignment=ft.MainAxisAlignment.START,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=0,
                expand=True,
            )
        )

    def toggle_herramientas(self, e):
        """Abre o cierra la tira de herramientas (misma lógica que Hoja de Trabajo)."""
        self.herramientas_abiertas = not self.herramientas_abiertas
        est = estado_panel_herramientas(self.herramientas_abiertas)
        self.herramientas_container.width = est["width"]
        self.herramientas_container.opacity = est["opacity"]
        self.herramientas_container.visible = est["visible"]
        self.boton_toggle.icon = est["icon"]
        self.boton_toggle.text = est["text"]
        self.boton_toggle.tooltip = est["tooltip"]
        self.panel_herramientas.update()

    # ===================== FUNCIONES =====================

    def _filtro_busqueda_actual(self) -> str:
        """Texto de búsqueda normalizado desde el campo de filtro."""
        return (self.search_field.value or "").strip()

    def _filtro_terceros(self, texto: str = ""):
        """Construye el filtro para el caso de uso según modo dividir y texto de búsqueda."""
        texto = (texto or "").strip()
        if self.dividir_nombres_modo:
            return ["DIVIDIR", texto] if texto else ["DIVIDIR"]
        return [texto] if texto else None

    def _consultar_terceros(self, texto: str = ""):
        """Consulta terceros paginados con el filtro correspondiente al estado actual."""
        filtro = self._filtro_terceros(texto)
        if filtro is None:
            return self._terceros_uc.obtener_terceros(
                offset=self.offset,
                limit=self.limit,
            )
        return self._terceros_uc.obtener_terceros(
            offset=self.offset,
            limit=self.limit,
            filtro=filtro,
        )

    def _actualizar_estado_terceros(self, datos, total) -> None:
        """Sincroniza estado de terceros en memoria antes de renderizar tabla."""
        self.terceros = datos or []
        self.total_terceros = total or 0
        self.terceros_filtrados = self.terceros.copy()

    def cargar_terceros(self):
        self._mostrar_loader(True)
        texto = self._filtro_busqueda_actual()

        def _worker():
            try:
                datos, total = self._consultar_terceros(texto)
                if not datos:
                    self.mostrar_mensaje("No se encontraron terceros.", 8888)
                self._actualizar_estado_terceros(datos, total)
                self._actualizar_tabla()
            except Exception as e:
                self.terceros = []
                self.mostrar_mensaje(f"Error cargando terceros: {e}", 8888)
            finally:
                self._mostrar_loader(False)

        self._page.run_thread(_worker)

    def paginar(self, direction: int):
        nuevo_offset = self.offset + (direction * self.limit)
        if nuevo_offset < 0:
            return
        self.offset = nuevo_offset
        texto = self._filtro_busqueda_actual()
        self._mostrar_loader(True)
        try:
            datos, total = self._consultar_terceros(texto)
            self._actualizar_estado_terceros(datos, total)
            self._actualizar_tabla()
        except Exception as e:
            self.mostrar_mensaje(f"Error cargando página: {e}", 8888)
        finally:
            self._mostrar_loader(False)

    def _ir_a_pagina(self, pagina: int):
        """Salta a la página indicada (1-based) respetando los límites."""
        if pagina < 1 or not self.limit:
            return
        total = self.total_terceros or 0
        if total > 0:
            total_paginas = max(1, (total + self.limit - 1) // self.limit)
            if pagina > total_paginas:
                pagina = total_paginas
        self.offset = (pagina - 1) * self.limit
        self.cargar_terceros()

    def _banner_prefijos_sync(self) -> None:
        sync_banner_prefijo(
            self._page,
            app=getattr(self, "_app", None),
            prefix_ctrl=self._prefix_buffer,
            prefix_alt=self._page_prefix_buffer,
        )

    def _on_keyboard_page(self, e: ft.KeyboardEvent):
        """Repag/Avpag para paginar. Ctrl+prefijo (dígitos con pausa ≤0,8 s) para foco o toggle según modo; igual que hoja de trabajo (debounce)."""
        if getattr(self._page, "route", "") != "/home/cartilla_terceros":
            return
        key = getattr(e, "key", "")
        ctrl = getattr(e, "ctrl", False)
        alt = getattr(e, "alt", False)
        digit = normalize_digit_key(key)

        # Alt + dígitos: ir directamente a número de página.
        if alt and digit is not None:
            reset_prefix_buffer(self)
            self._page_prefix_buffer = (self._page_prefix_buffer or "") + digit
            if self._page_prefix_timer:
                self._page_prefix_timer.cancel()
            loop = self._page.session.connection.loop

            def _on_page_timeout():
                prefix = (self._page_prefix_buffer or "").strip()
                self._page_prefix_buffer = ""
                self._banner_prefijos_sync()
                if not prefix:
                    return
                try:
                    num = int(prefix)
                except ValueError:
                    return
                self._ir_a_pagina(num)

            self._page_prefix_timer = loop.call_later(DEBOUNCE_PREFIJOS_SEC, _on_page_timeout)
            self._banner_prefijos_sync()
            return

        if ctrl and digit is not None:
            reset_page_prefix_buffer(self)
            # Acumula el prefijo (ej. '2' → '23' → '235'). La acción se aplica tras una pausa
            # (debounce), igual que en hoja de trabajo y cuentas: si el foco se mueve en cada
            # dígito, el teclado deja de llegar a la página y solo “entra” el primer dígito.
            self._prefix_buffer += digit
            self._banner_prefijos_sync()
            if self._prefix_buffer_timer:
                self._prefix_buffer_timer.cancel()
            loop = self._page.session.connection.loop

            def _on_timeout():
                prefix = (self._prefix_buffer or "").strip()
                reset_prefix_buffer(self)
                self._banner_prefijos_sync()
                if not prefix:
                    return
                for identidad, control in getattr(self, "_control_por_identidad", {}).items():
                    if not str(identidad).startswith(prefix):
                        continue
                    try:
                        _ = control.page
                    except RuntimeError:
                        continue
                    if self.dividir_nombres_modo:
                        if isinstance(control, ft.Checkbox):
                            nuevo_valor = not bool(control.value)
                            control.value = nuevo_valor
                            self._toggle_dividir_nombres(identidad, nuevo_valor)
                            self._page.update()
                        break
                    if hasattr(control, "focus"):
                        async def _do_focus(ctrl=control):
                            try:
                                _ = ctrl.page
                            except RuntimeError:
                                return
                            await ctrl.focus()

                        self._page.run_task(_do_focus)
                    elif hasattr(self._page, "set_focus"):
                        self._page.set_focus(control)
                    self._page.update()
                    break

            self._prefix_buffer_timer = loop.call_later(DEBOUNCE_PREFIJOS_SEC, _on_timeout)
            return

        if tecla_es_solo_modificador(key):
            return

        # Si no es un Ctrl+digito válido, se reinicia el estado del prefijo y del buffer de página
        reset_prefix_buffer(self)
        self._page_prefix_buffer = ""
        if self._page_prefix_timer:
            try:
                self._page_prefix_timer.cancel()
            except Exception:
                pass
            self._page_prefix_timer = None
        self._banner_prefijos_sync()

        if tecla_es_repag(key):
            self.paginar(-1)
        elif tecla_es_avpag(key):
            self.paginar(1)

    def _mostrar_loader(self, visible: bool):
        loader_row_visibilidad(self._page, self.loader, visible)

    def mostrar_mensaje(self, texto, duration, tercero=None, color=None, on_dismiss=None):
        """
        Muestra un mensaje con SnackBar vía show_dialog.
        tercero: si se proporciona, muestra botón Confirmar para eliminar.
        on_dismiss: opcional, se llama al cerrar el snackbar (p. ej. para reabrir la barra de dividir).
        """
        if tercero:

            def on_confirm(_e):
                r = self._terceros_uc.eliminar_tercero(tercero)
                self.cargar_terceros()
                if r is False:
                    mostrar_mensaje(
                        self._page,
                        "No se pudo eliminar el tercero. Verifique que no esté acumulado",
                        8888,
                    )

            mostrar_mensaje(
                self._page,
                texto,
                duration,
                on_dismiss=on_dismiss,
                action_text="Confirmar",
                on_action=on_confirm,
            )
        else:
            mostrar_mensaje(self._page, texto, duration, color=color, on_dismiss=on_dismiss)

    def _buscar_tercero(self, e: ft.ControlEvent):
        ft.context.disable_auto_update()
        if self._buscar_handle is not None:
            self._buscar_handle.cancel()
        texto = (e.control.value or "").strip()
        self.offset = 0
        loop = self._page.session.connection.loop
        self._buscar_handle = loop.call_later(0.35, lambda: self._buscar_ejecutar(texto))

    def _buscar_ejecutar(self, texto: str):
        self._mostrar_loader(True)
        try:
            datos, total = self._consultar_terceros(texto)
            self._actualizar_estado_terceros(datos, total)
            self._actualizar_tabla()
        except Exception as ex:
            self._mostrar_mensaje(f"Error buscando: {ex}", True)
        finally:
            self._mostrar_loader(False)

    def _crear_accion_dividir(self, identidad, tt_ctrl_fila):
        chk = ft.Checkbox(
            value=identidad in self.dividir_nombres_seleccion,
            active_color=PINK_200,
            check_color=ft.Colors.WHITE,
            tooltip=tt_ctrl_fila,
            on_change=lambda e, idt=identidad: self._toggle_dividir_nombres(
                idt, e.control.value
            ),
        )
        return self._data_cell_cartilla(chk), chk

    def _crear_accion_edicion(self, tercero, tt_ctrl_fila):
        btn_edit = ft.IconButton(
            icon=ft.Icons.EDIT,
            tooltip=tt_ctrl_fila,
            style=BOTON_SECUNDARIO_SIN,
            icon_size=18,
            on_click=lambda e, data=tercero: self.dialog_tercero.abrir(data),
        )
        celda_accion = self._data_cell_cartilla(
            ft.Row(
                [
                    btn_edit,
                    ft.IconButton(
                        icon=ft.Icons.CLOSE,
                        tooltip="Eliminar tercero",
                        style=BOTON_SECUNDARIO_SIN,
                        icon_size=18,
                        on_click=lambda e, data=tercero: self.mostrar_mensaje(
                            f"¿Desea eliminar el tercero {data['razonsocial']}?",
                            5555,
                            data["identidad"],
                        ),
                    ),
                ],
                spacing=-10,
                alignment=ft.MainAxisAlignment.CENTER,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            )
        )
        return celda_accion, btn_edit

    def _total_paginas(self) -> int:
        """Calcula total de páginas con fallback seguro cuando no hay resultados o límite inválido."""
        if not self.limit:
            return 1
        return (
            (self.total_terceros + self.limit - 1) // self.limit
            if self.total_terceros > 0
            else 1
        )

    def _pagina_actual(self) -> int:
        """Número de página actual (1-based)."""
        return (self.offset // self.limit) + 1 if self.limit else 1

    def _actualizar_controles_paginacion(self) -> None:
        """Sincroniza botones anterior/siguiente y texto de paginación del footer."""
        self.nav_row.controls[0].visible = not self.offset <= 0
        total_paginas = self._total_paginas()
        pagina = self._pagina_actual()
        self.nav_row.controls[2].visible = pagina < total_paginas
        total = self.total_terceros if self.total_terceros > 0 else None
        self.pagination_text_footer.value = pagination_text_value(
            pagina, total_paginas, total
        )

    def _actualizar_tabla(self):
        self.table.rows.clear()
        self._control_por_identidad = {}
        for tercero in self.terceros_filtrados:
            identidad = tercero.get("identidad", "")
            razon = tercero.get("razonsocial", tercero.get("nombre", ""))
            tipo_doc = (tercero.get("tipodocumento") or "").strip()
            direccion = (tercero.get("direccion") or "").strip()
            identidad_str = str(identidad).strip()
            tt_ctrl_fila = tooltip(TooltipId.CARTILLA_CTRL_IDENTIDAD, identidad=identidad_str)

            if self.dividir_nombres_modo:
                celda_accion, control_focus = self._crear_accion_dividir(
                    identidad, tt_ctrl_fila
                )
            else:
                celda_accion, control_focus = self._crear_accion_edicion(
                    tercero, tt_ctrl_fila
                )

            self._control_por_identidad[identidad_str] = control_focus

            # Orden de celdas = columnas: Tipo doc, Razón social, Identidad, Dirección, Acciones
            fila = ft.DataRow(
                cells=[
                    self._data_cell_cartilla(self._texto_celda(tipo_doc)),
                    self._data_cell_cartilla(self._texto_celda(str(razon))),
                    self._data_cell_cartilla(self._texto_celda(str(identidad))),
                    self._data_cell_cartilla(self._texto_celda(direccion)),
                    celda_accion,
                ]
            )
            self.table.rows.append(fila)

        self._actualizar_controles_paginacion()
        self._page.update()

    def _actualizar_columna_tabla(self):
        # Última columna: Sel o Acciones (índice 4 tras Tipo documento y Dirección).
        if self.dividir_nombres_modo:
            self.table.columns[4] = ft.DataColumn(ft.Text("Sel"))
        else:
            self.table.columns[4] = ft.DataColumn(ft.Text("Acciones"))

    def _activar_dividir_nombres(self):
        self.dividir_nombres_modo = True
        self.dividir_nombres_seleccion = []
        self._actualizar_columna_tabla()
        self.cargar_terceros()
        self._mostrar_snackbar_dividir()

    def _cerrar_snackbar_dividir(self):
        """Cierra el snackbar de dividir; si no se cierra bien, abre uno invisible para que se vea como cerrado."""
        if self.snackbar_dividir is not None:
            self.snackbar_dividir.open = False
            if self.snackbar_dividir in self._page.overlay:
                self._page.overlay.remove(self.snackbar_dividir)
            self.snackbar_dividir = None
        snackbar_invisible_para_cerrar(self._page)

    def _desactivar_dividir_nombres(self):
        self.dividir_nombres_modo = False
        self.dividir_nombres_seleccion = []
        self._cerrar_snackbar_dividir()
        self._actualizar_columna_tabla()
        self.cargar_terceros()
        self._page.update()

    def _toggle_dividir_nombres(self, identidad, marcado):
        if marcado and identidad not in self.dividir_nombres_seleccion:
            self.dividir_nombres_seleccion.append(identidad)
        if not marcado and identidad in self.dividir_nombres_seleccion:
            self.dividir_nombres_seleccion.remove(identidad)

    def _mostrar_snackbar_dividir(self):
        texto = "Seleccione los terceros que desea dividir. Luego confirme el orden de los nombres."
        contenido = ft.Row(
            controls=[
                ft.Text(texto, color=PINK_800, size=14),
                ft.TextButton(
                    content="Cancelar",
                    on_click=self._on_cancelar_dividir,
                    style=BOTON_SECUNDARIO_SIN,
                    icon=ft.Icons.CLOSE,
                ),
                ft.Button(content="Seleccionar", icon=ft.Icons.CHECK, on_click=self._confirmar_dividir, style=BOTON_PRINCIPAL),
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )
        self.snackbar_dividir = crear_snackbar(contenido, duration=999999999, show_close=False)
        self._page.overlay.append(self.snackbar_dividir)
        self.snackbar_dividir.open = True
        self._page.update()

    def _on_cancelar_dividir(self, e=None):
        self._desactivar_dividir_nombres()

    def _confirmar_dividir(self, e=None):
        if not self.dividir_nombres_seleccion:
            self._cerrar_snackbar_dividir()
            self.mostrar_mensaje(
                "Seleccione al menos un tercero para dividir.",
                3000,
                on_dismiss=lambda e: self._mostrar_snackbar_dividir(),
            )
            return
        terceros_seleccionados = [
            tercero
            for tercero in self.terceros_filtrados
            if tercero.get("identidad") in self.dividir_nombres_seleccion
        ]
        self._cerrar_snackbar_dividir()
        self._page.update()
        self._desactivar_dividir_nombres()
        self.dialog_tercero.abrir(origen="dividir_nombres", terceros=terceros_seleccionados)

