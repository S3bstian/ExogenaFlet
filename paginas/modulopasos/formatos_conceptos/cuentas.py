import flet as ft
from ui.colors import PINK_50, PINK_200, PINK_400, PINK_600, GREY_700
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO
from ui.snackbars import actualizar_mensaje_en_control
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
from paginas.utils.banner_prefijo_ctrl import crear_banner_prefijo_ctrl, sync_banner_prefijo
from utils.ui_sync import ejecutar_en_ui, loader_row_fin, loader_row_visibilidad


class CuentasDialog:
    def __init__(self, page, atributos_dialog, *, container):
        self.page = page
        self.atributos_dialog = atributos_dialog

        # paginación
        self.limit = 12
        self.offset = 0

        # persistencia
        self.cuentas = []
        self.cuentas_filtradas = []
        self.checkboxes_cuentas = {}
        self.seleccion_global = {}
        self.concepto = None
        self._buscar_handle = None
        self.total_cuentas = 0
        # Buffers de teclado: Ctrl+prefijo (cuenta) y Alt+prefijo (número de página)
        self._prefix_buffer = ""
        self._prefix_buffer_timer = None
        self._page_prefix_buffer = ""
        self._page_prefix_timer = None

        self.mensaje = ft.Text("", size=14, italic=True, visible=False)
        self.dialog = None
        self.tipo_cuentas = None
        self._btn_cancelar_catalogo = None
        self._btn_seleccionar_catalogo = None

        from ui.progress import crear_loader_row, SIZE_SMALL
        self.loading_indicator = crear_loader_row("Cargando...", size=SIZE_SMALL)
        self.loading_indicator.visible = False
        self._cuentas_uc = container.cuentas_uc

    def _filtro_actual(self) -> str:
        return (self.search_field.value or "").strip() if getattr(self, "search_field", None) else ""

    def _consultar_cuentas(self, filtro: str):
        if filtro:
            return self._cuentas_uc.obtener_cuentas(
                self.tipo_cuentas,
                offset=self.offset,
                limit=self.limit,
                filtro=filtro,
            )
        return self._cuentas_uc.obtener_cuentas(
            self.tipo_cuentas,
            offset=self.offset,
            limit=self.limit,
        )

    def _aplicar_resultado_cuentas(self, cuentas, total) -> None:
        self.cuentas = cuentas
        self.total_cuentas = total
        self.cuentas_filtradas = self.cuentas.copy()
        self._actualizar_tabla()

    def _ejecutar_carga_cuentas(self, *, mensaje_loader: str, filtro: str, mensaje_error: str) -> None:
        self.mostrar_loader(mensaje_loader)

        def _worker():
            try:
                cuentas, total = self._consultar_cuentas(filtro)
            except Exception as ex:
                def _err():
                    self.ocultar_loader()
                    actualizar_mensaje_en_control(f"{mensaje_error}: {ex}", self.mensaje)

                ejecutar_en_ui(self.page, _err)
                return

            def _ui():
                self._aplicar_resultado_cuentas(cuentas, total)
                self.ocultar_loader()

            ejecutar_en_ui(self.page, _ui)

        self.page.run_thread(_worker)

    def _total_paginas(self) -> int:
        if not self.limit:
            return 1
        return (self.total_cuentas + self.limit - 1) // self.limit if self.total_cuentas > 0 else 1

    def _pagina_actual(self) -> int:
        return (self.offset // self.limit) + 1 if self.limit else 1

    # ===================== ABRIR =====================
    def open_cuentas(self, tipo_cuentas, concepto, tglobal):
        self.concepto = concepto
        self.tglobal = tglobal
        self.tipo_cuentas = tipo_cuentas
        self.offset = 0
        
        self.seleccion_global = {
            cuenta["codigo"]: {"selected": True, "data": cuenta}
            for cuenta in self.atributos_dialog.cuentas_seleccionadas
        }

        self.search_field = ft.TextField(
            label="Buscar cuenta o nombre",
            hint_text="Ej: 110505 o Bancolombia",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=10,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            width=255,
            height=38,
            on_change=self._buscar_cuenta,
        )

        self.data_table = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Seleccionar")),
                ft.DataColumn(ft.Text("Cuenta")),
                ft.DataColumn(ft.Text("Nombre")),
                ft.DataColumn(ft.Text("Naturaleza")),
            ],
            rows=[],
            column_spacing=10,
            data_row_max_height=35,
            heading_row_height=30,
            heading_row_color=PINK_50,
            divider_thickness=0.5,
        )

        self.table_container = ft.Column(
            controls=[self.data_table],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )

        # botones de paginación
        self.pagination_text_footer = build_pagination_label(1, 1)
        self.btn_prev = ft.ElevatedButton(
            "Anterior",
            on_click=lambda e: self.paginar(-1),
            icon=ft.Icons.ARROW_BACK_IOS_NEW_SHARP,
            icon_color=PINK_600,
            style=BOTON_SECUNDARIO,
            tooltip=tooltip(TooltipId.PAGINA_BTN_ANTERIOR),
        )
        self.btn_next = ft.ElevatedButton(
            "Siguiente",
            on_click=lambda e: self.paginar(1),
            icon=ft.Icons.ARROW_FORWARD_IOS_SHARP,
            icon_color=PINK_600,
            style=BOTON_SECUNDARIO,
            tooltip=tooltip(TooltipId.PAGINA_BTN_SIGUIENTE),
        )
        self.nav_row = ft.Row(
            [self.btn_prev, self.pagination_text_footer, self.btn_next],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            margin=ft.margin.only(bottom=-20)
        )
        self._outer_banner_prefijo_ctrl, self._txt_banner_prefijo_ctrl = crear_banner_prefijo_ctrl(expand=False)
        contenido = ft.Column(
            [
                ft.Row(
                    [
                        ft.Text("Seleccione las cuentas:", weight=ft.FontWeight.BOLD),
                        self.search_field,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                ),
                ft.Row(
                    [self._outer_banner_prefijo_ctrl],
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                self.loading_indicator,
                self.table_container,
                self.nav_row,
                self.mensaje,
            ],
            spacing=10,
            expand=True,
        )

        self._btn_cancelar_catalogo = ft.TextButton(
            content="Cancelar",
            on_click=lambda e: self.return_dialog(),
            style=BOTON_SECUNDARIO,
        )
        self._btn_seleccionar_catalogo = ft.Button(
            content="Seleccionar",
            on_click=self.seleccionar_cuentas,
            style=BOTON_PRINCIPAL,
        )
        self.dialog = ft.AlertDialog(
            title=ft.Text("Catálogo de cuentas"),
            content=contenido,
            bgcolor=ft.Colors.WHITE,
            modal=True,
            actions=[
                self._btn_cancelar_catalogo,
                self._btn_seleccionar_catalogo,
            ],
            on_dismiss=lambda e: setattr(self.page, "on_keyboard_event", getattr(self, "_prev_keyboard", None)),
        )

        self._prev_keyboard = getattr(self.page, "on_keyboard_event", None)
        self.page.on_keyboard_event = self._on_keyboard_paginar
        self.page.show_dialog(self.dialog)
        self.page.update()
        self.cargar_cuentas()

    # ===================== CARGA =====================
    def cargar_cuentas(self):
        self._ejecutar_carga_cuentas(
            mensaje_loader="Cargando cuentas...",
            filtro=self._filtro_actual(),
            mensaje_error="Error cargando cuentas",
        )

    def _banner_prefijos_sync(self) -> None:
        sync_banner_prefijo(
            self.page,
            txt=self._txt_banner_prefijo_ctrl,
            outer=self._outer_banner_prefijo_ctrl,
            prefix_ctrl=self._prefix_buffer,
            prefix_alt=self._page_prefix_buffer,
        )

    def _ir_a_pagina(self, pagina: int):
        """Salta a la página indicada (1-based) respetando los límites dentro del diálogo."""
        if pagina < 1 or not self.limit:
            return
        total = self.total_cuentas or 0
        if total > 0:
            total_paginas = max(1, (total + self.limit - 1) // self.limit)
            if pagina > total_paginas:
                pagina = total_paginas
        self.offset = (pagina - 1) * self.limit
        self.cargar_cuentas()

    def _on_keyboard_paginar(self, e: ft.KeyboardEvent):
        """
        Manejo de teclado dentro del diálogo de cuentas.
        - Re Pág / Av Pág: paginar.
        - Ctrl + secuencia de dígitos: seleccionar/deseleccionar cuenta cuyo código empieza por el prefijo.
        - Alt + secuencia de dígitos: ir directamente a la página indicada.
        """
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
            loop = self.page.session.connection.loop

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
            # Acumula prefijo de cuenta (ej. 1 -> 11 -> 1105)
            self._prefix_buffer += digit
            self._banner_prefijos_sync()
            # Reinicia temporizador: solo cuando termina de escribir aplicamos el cambio.
            if self._prefix_buffer_timer:
                self._prefix_buffer_timer.cancel()
            loop = self.page.session.connection.loop

            def _on_timeout():
                prefix = (self._prefix_buffer or "").strip()
                reset_prefix_buffer(self)
                self._banner_prefijos_sync()
                if not prefix:
                    return
                for codigo, cb in self.checkboxes_cuentas.items():
                    if str(codigo).startswith(prefix) and isinstance(cb, ft.Checkbox):
                        nuevo_valor = not bool(cb.value)
                        cb.value = nuevo_valor
                        self._toggle_seleccion(codigo, cb.data, nuevo_valor)
                        self.page.update()
                        break

            self._prefix_buffer_timer = loop.call_later(DEBOUNCE_PREFIJOS_SEC, _on_timeout)
            return

        if tecla_es_solo_modificador(key):
            return

        # No es Ctrl+digito ni Alt+digito: limpiar buffers y gestionar solo paginación.
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

    # ===================== PAGINACIÓN =====================
    def paginar(self, direction: int):
        nuevo_offset = self.offset + (direction * self.limit)
        if nuevo_offset < 0:
            return
        self.offset = nuevo_offset
        self._ejecutar_carga_cuentas(
            mensaje_loader="Paginando...",
            filtro=self._filtro_actual(),
            mensaje_error="Error paginando cuentas",
        )

    # ===================== BUSQUEDA =====================
    def _buscar_cuenta(self, e: ft.ControlEvent):
        ft.context.disable_auto_update()
        if self._buscar_handle is not None:
            self._buscar_handle.cancel()
        texto = (e.control.value or "").strip()
        self.offset = 0
        loop = self.page.session.connection.loop
        self._buscar_handle = loop.call_later(0.35, lambda: self._buscar_cuenta_ejecutar(texto))

    def _buscar_cuenta_ejecutar(self, texto: str):
        self._ejecutar_carga_cuentas(
            mensaje_loader="Buscando...",
            filtro=(texto or "").strip(),
            mensaje_error="Error buscando cuentas",
        )

    # ===================== TABLA =====================
    def _actualizar_tabla(self):
        self.data_table.rows.clear()
        self.checkboxes_cuentas = {}

        if not self.cuentas_filtradas:
            actualizar_mensaje_en_control("No se encontraron cuentas", self.mensaje)
        else:
            self.mensaje.visible = False
            for cuenta in self.cuentas_filtradas:
                codigo_cuenta = cuenta.get("codigo")
                checked = self.seleccion_global.get(codigo_cuenta, {}).get("selected", False)

                cb = ft.Checkbox(
                    value=checked,
                    data=cuenta,
                    width=25,
                    active_color=PINK_400,
                    tooltip=tooltip(TooltipId.CUENTAS_CTRL_CODIGO, codigo=str(codigo_cuenta)),
                    on_change=lambda e, id=codigo_cuenta, data=cuenta: self._toggle_seleccion(
                        id, data, e.control.value
                    ),
                )
                self.checkboxes_cuentas[codigo_cuenta] = cb

                fila = ft.DataRow(
                    cells=[
                        ft.DataCell(cb),
                        ft.DataCell(ft.Text(codigo_cuenta)),
                        ft.DataCell(ft.Text(cuenta.get("nombre", ""))),
                        ft.DataCell(ft.Text(cuenta.get("naturaleza", ""))),
                    ]
                )
                self.data_table.rows.append(fila)

        self.btn_prev.visible = not self.offset <= 0
        total_paginas = self._total_paginas()
        pagina = self._pagina_actual()
        self.btn_next.visible = pagina < total_paginas
        total = self.total_cuentas if self.total_cuentas > 0 else None
        self.pagination_text_footer.value = pagination_text_value(pagina, total_paginas, total)
        self.page.update()

    def _toggle_seleccion(self, cuenta_prefijo, data, value: bool):
        """
        Cuando se marca/desmarca una cuenta, pedimos al caso de uso sus subcuentas
        y aplicamos la misma selección a todas ellas (incluso las que no están cargadas en la página).
        """
        self.mostrar_loader("Aplicando selección y cargando subcuentas...")

        def _worker():
            try:
                subcuentas = self._cuentas_uc.obtener_subcuentas(
                    self.tipo_cuentas, cuenta_prefijo
                )
            except Exception as exc:
                print(
                    f"Error al obtener/subir selección de subcuentas para {cuenta_prefijo}: {exc}"
                )

                def _err():
                    self.ocultar_loader()
                    self.page.update()

                ejecutar_en_ui(self.page, _err)
                return

            cuentas_a_procesar = [data] + subcuentas

            def _ui():
                for cuenta in cuentas_a_procesar:
                    codigo = cuenta["codigo"]
                    self.seleccion_global[codigo] = {"selected": value, "data": cuenta}

                    cb = self.checkboxes_cuentas.get(codigo)
                    if cb:
                        cb.value = value
                        cb.update()

                self.ocultar_loader()
                self.page.update()

            ejecutar_en_ui(self.page, _ui)

        self.page.run_thread(_worker)

    # ===================== SELECCIONAR =====================
    def seleccionar_cuentas(self, _event):
        seleccionados = [
            seleccion["data"]
            for seleccion in self.seleccion_global.values()
            if seleccion["selected"] and seleccion["data"]["subcuentas"] == 0
        ]
        if not seleccionados:
            actualizar_mensaje_en_control("Debe seleccionar al menos una cuenta", self.mensaje)
            return

        self.atributos_dialog.recibir_cuentas(seleccionados)
        self.return_dialog()

    # ===================== UTILIDADES =====================
    def mostrar_loader(self, mensaje="Cargando..."):
        self._set_acciones_catalogo_ocupado(True)
        loader_row_visibilidad(self.page, self.loading_indicator, True, f" {mensaje}")

    def ocultar_loader(self):
        self._set_acciones_catalogo_ocupado(False)
        loader_row_fin(self.page, self.loading_indicator)

    def _set_acciones_catalogo_ocupado(self, ocupado: bool):
        """Bloquea acciones del diálogo mientras el catálogo está ejecutando una operación."""
        if self._btn_cancelar_catalogo:
            self._btn_cancelar_catalogo.disabled = ocupado
        if self._btn_seleccionar_catalogo:
            self._btn_seleccionar_catalogo.disabled = ocupado

    def return_dialog(self):
        self.seleccion_global = {}
        self.page.pop_dialog()
        args = getattr(self.atributos_dialog, "_last_opciones_args", None)
        self.atributos_dialog.open_opciones_dialog(*args, self.concepto, self.tglobal)
