import flet as ft
from ui.colors import PINK_50, PINK_200, PINK_400, PINK_600, GREY_700
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO
from ui.snackbars import actualizar_mensaje_en_control
from paginas.utils.paginacion import (
    DEBOUNCE_PREFIJOS_SEC,
    build_pagination_label,
    pagination_text_value,
    normalize_digit_key,
    tecla_es_avpag,
    tecla_es_repag,
    tecla_es_solo_modificador,
)
from paginas.utils.tooltips import TooltipId, tooltip
from paginas.utils.banner_prefijo_ctrl import crear_banner_prefijo_ctrl, sync_banner_prefijo
from utils.ui_sync import ejecutar_en_ui, loader_row_fin, loader_row_visibilidad

_DEBOUNCE_BUSQUEDA_SEC = 0.35

_COLUMNAS_TABLA_TERCEROS = [
    "Seleccionar",
    "Nombre",
    "Identidad",
    "Tipo Documento",
]


class TercerosDialog:
    def __init__(
        self,
        page,
        consorcios_dialog=None,
        trabajo_dialog=None,
        modo_seleccion_unica=False,
        *,
        container,
    ):
        self.page = page
        self.consorcios_dialog = consorcios_dialog
        self.trabajo_dialog = trabajo_dialog
        self.modo_seleccion_unica = modo_seleccion_unica
        self.limit = 12
        self.offset = 0
        self.dialog_agregar = None
        self.empresa_actual = None

        self.terceros = []
        self.terceros_filtrados = []
        self.checkboxes_terceros = {}
        self.mensaje = ft.Text("", size=14, italic=True, visible=False)

        # Selección que sobrevive al cambiar de página (multiselect) o al filtrar (único usa otro campo).
        self.seleccion_global = {}
        self.tercero_seleccionado_unico = None
        self._buscar_handle = None
        self.total_terceros = 0
        self._terceros_uc = container.terceros_cartilla_uc
        self._consorcios_uc = container.consorcios_uc
        self._page_prefix_buffer = ""
        self._page_prefix_timer = None

        from ui.progress import crear_loader_row, SIZE_SMALL

        self.loading_indicator = crear_loader_row("Cargando...", size=SIZE_SMALL)
        self.loading_indicator.visible = False

        self.search_field = ft.TextField(
            label="Buscar",
            hint_text="Ej: 123456789 o Comercial S.A.",
            prefix_icon=ft.Icons.SEARCH,
            border_radius=10,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            on_change=self._buscar_tercero,
            width=333,
            height=38,
        )

        self.data_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(c)) for c in _COLUMNAS_TABLA_TERCEROS],
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

        self.radio_group_container = ft.Container(visible=False, width=0, height=0)
        self.radio_group = None
        self._btn_cancelar_catalogo = None
        self._btn_seleccionar_catalogo = None
        self._acciones_catalogo_ocupado = False

    def _titulo_seleccion_catalogo(self) -> str:
        return "Seleccione un tercero:" if self.modo_seleccion_unica else "Seleccione los terceros:"

    def _armar_barra_paginacion(self) -> ft.Row:
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
        return ft.Row(
            [self.btn_prev, self.pagination_text_footer, self.btn_next],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            margin=ft.margin.only(bottom=-20),
        )

    def _contenido_columna_catalogo(self, nav_row: ft.Row) -> ft.Column:
        self._outer_banner_alt_pagina, self._txt_banner_alt_pagina = crear_banner_prefijo_ctrl(expand=False)
        return ft.Column(
            [
                ft.Row(
                    [
                        ft.Text(self._titulo_seleccion_catalogo(), weight=ft.FontWeight.BOLD),
                        self.search_field,
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                ),
                ft.Row([self._outer_banner_alt_pagina], alignment=ft.MainAxisAlignment.CENTER),
                self.loading_indicator,
                self.radio_group_container,
                self.table_container,
                nav_row,
                self.mensaje,
            ],
            spacing=10,
            expand=True,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    def open_agregar_dialog(self):
        """
        Abre el catálogo: selección única (hoja de trabajo) o múltiple (consorcios).
        """
        self.seleccion_global = {}
        self.tercero_seleccionado_unico = None

        self.nav_row = self._armar_barra_paginacion()
        contenido = self._contenido_columna_catalogo(self.nav_row)

        accion_seleccionar = (
            self.seleccionar_tercero_unico if self.modo_seleccion_unica else self.seleccionar_consorcios
        )

        self._btn_cancelar_catalogo = ft.TextButton(
            content="Cancelar",
            on_click=lambda e: self.return_dialog(),
            style=BOTON_SECUNDARIO,
        )
        self._btn_seleccionar_catalogo = ft.Button(
            content="Seleccionar",
            on_click=accion_seleccionar,
            style=BOTON_PRINCIPAL,
        )
        self.dialog_agregar = ft.AlertDialog(
            title=ft.Text("Catálogo de terceros"),
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
        self.page.show_dialog(self.dialog_agregar)
        self.mostrar_loader("Abriendo diálogo...")
        self.cargar_terceros()

    def _banner_prefijos_sync(self) -> None:
        sync_banner_prefijo(
            self.page,
            txt=self._txt_banner_alt_pagina,
            outer=self._outer_banner_alt_pagina,
            prefix_alt=self._page_prefix_buffer,
        )

    def cargar_terceros(self):
        self._cargar_terceros_async("Cargando terceros...")

    def _cargar_terceros_async(self, mensaje_loader: str, filtro: str = ""):
        self.mostrar_loader(mensaje_loader)

        def _worker():
            try:
                if filtro:
                    terceros, total = self._terceros_uc.obtener_terceros(
                        offset=self.offset,
                        limit=self.limit,
                        filtro=filtro,
                    )
                else:
                    terceros, total = self._terceros_uc.obtener_terceros(
                        offset=self.offset,
                        limit=self.limit,
                    )
            except Exception as ex:

                def _err():
                    self.ocultar_loader()
                    actualizar_mensaje_en_control(f"Error cargando terceros: {ex}", self.mensaje)

                ejecutar_en_ui(self.page, _err)
                return

            def _ui():
                self.terceros = terceros
                self.total_terceros = total
                self.terceros_filtrados = terceros.copy()
                self.checkboxes_terceros.clear()
                self._actualizar_tabla()
                self.ocultar_loader()

            ejecutar_en_ui(self.page, _ui)

        self.page.run_thread(_worker)

    def _ir_a_pagina(self, pagina: int):
        if pagina < 1 or not self.limit:
            return
        total = self.total_terceros or 0
        if total > 0:
            total_paginas = max(1, (total + self.limit - 1) // self.limit)
            if pagina > total_paginas:
                pagina = total_paginas
        self.offset = (pagina - 1) * self.limit
        self.cargar_terceros()

    def _cancelar_timer_prefijo_pagina(self) -> None:
        if self._page_prefix_timer:
            try:
                self._page_prefix_timer.cancel()
            except Exception:
                pass
            self._page_prefix_timer = None

    def _on_keyboard_paginar(self, e: ft.KeyboardEvent):
        """
        Re Pág / Av Pág: paginar. Alt + dígitos: salto a número de página (debounce).
        """
        key = getattr(e, "key", "")
        alt = getattr(e, "alt", False)
        digit = normalize_digit_key(key)

        if alt and digit is not None:
            self._page_prefix_buffer = (self._page_prefix_buffer or "") + digit
            self._cancelar_timer_prefijo_pagina()
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

        if tecla_es_solo_modificador(key):
            return

        self._page_prefix_buffer = ""
        self._cancelar_timer_prefijo_pagina()
        self._banner_prefijos_sync()

        if tecla_es_repag(key):
            self.paginar(-1)
        elif tecla_es_avpag(key):
            self.paginar(1)

    def paginar(self, direction: int):
        nuevo_offset = self.offset + (direction * self.limit)
        if nuevo_offset < 0:
            return
        self.offset = nuevo_offset

        filtro = (self.search_field.value or "").strip()

        self._cargar_terceros_async("Paginando...", filtro=filtro)

    def _buscar_tercero(self, e: ft.ControlEvent):
        ft.context.disable_auto_update()
        if self._buscar_handle is not None:
            self._buscar_handle.cancel()
        texto = (e.control.value or "").strip()
        self.offset = 0
        loop = self.page.session.connection.loop
        self._buscar_handle = loop.call_later(
            _DEBOUNCE_BUSQUEDA_SEC, lambda: self._buscar_tercero_ejecutar(texto)
        )

    def _buscar_tercero_ejecutar(self, texto: str):
        self._cargar_terceros_async("Buscando...", filtro=texto)

    def _fila_tercero(self, checkbox: ft.Checkbox, t: dict, identidad_celda: str) -> ft.DataRow:
        return ft.DataRow(
            cells=[
                ft.DataCell(checkbox),
                ft.DataCell(ft.Text(t.get("razonsocial", ""))),
                ft.DataCell(ft.Text(identidad_celda)),
                ft.DataCell(ft.Text(t.get("tipodocumento", ""))),
            ]
        )

    def _on_change_seleccion_unica(self, id_val: str, tercero_data: dict, e: ft.ControlEvent):
        if e.control.value:
            self.tercero_seleccionado_unico = tercero_data
            for other_id, other_cb in self.checkboxes_terceros.items():
                if isinstance(other_cb, ft.Checkbox) and other_id != id_val:
                    other_cb.value = False
            self.page.update()
        elif self.tercero_seleccionado_unico and str(self.tercero_seleccionado_unico.get("identidad")) == id_val:
            self.tercero_seleccionado_unico = None

    def _armar_filas_tabla_unico(self, valor_seleccionado: str | None):
        for t in self.terceros_filtrados:
            identidad = str(t.get("identidad"))
            checked = valor_seleccionado == identidad
            cb = ft.Checkbox(
                value=checked,
                data=t,
                active_color=PINK_400,
                on_change=lambda e, iv=identidad, td=t: self._on_change_seleccion_unica(iv, td, e),
            )
            self.checkboxes_terceros[identidad] = cb
            self.data_table.rows.append(self._fila_tercero(cb, t, identidad))

    def _armar_filas_tabla_multiselect(self):
        for t in self.terceros_filtrados:
            identidad = t.get("identidad")
            checked = self.seleccion_global.get(identidad, {}).get("selected", False)
            cb = ft.Checkbox(
                value=checked,
                data=t,
                active_color=PINK_400,
                on_change=lambda e, id=identidad, data=t: self._toggle_seleccion(id, data, e.control.value),
            )
            self.checkboxes_terceros[identidad] = cb
            self.data_table.rows.append(self._fila_tercero(cb, t, str(identidad)))

    def _actualizar_paginacion_footer(self):
        self.btn_prev.visible = not self.offset <= 0
        if self.limit:
            total_paginas = (
                (self.total_terceros + self.limit - 1) // self.limit if self.total_terceros > 0 else 1
            )
        else:
            total_paginas = 1
        pagina = (self.offset // self.limit) + 1 if self.limit else 1
        has_next = pagina < total_paginas
        self.btn_next.visible = has_next
        total = self.total_terceros if self.total_terceros > 0 else None
        self.pagination_text_footer.value = pagination_text_value(pagina, total_paginas, total)

    def _actualizar_tabla(self):
        self.data_table.rows.clear()

        if not self.terceros_filtrados:
            actualizar_mensaje_en_control("No se encontraron resultados. Cargue terceros en la cartilla", self.mensaje)
        else:
            self.mensaje.visible = False

            if self.modo_seleccion_unica:
                valor = (
                    str(self.tercero_seleccionado_unico.get("identidad"))
                    if self.tercero_seleccionado_unico
                    else None
                )
                self._armar_filas_tabla_unico(valor)
            else:
                self._armar_filas_tabla_multiselect()

        self._actualizar_paginacion_footer()
        self.page.update()

    def _toggle_seleccion(self, identidad, data, value):
        self.seleccion_global[identidad] = {"selected": value, "data": data}

    def seleccionar_tercero_unico(self, e):
        if not self.tercero_seleccionado_unico:
            actualizar_mensaje_en_control("Debe seleccionar un tercero", self.mensaje)
            return

        self.mostrar_loader("Aplicando tercero...")
        loop = self.page.session.connection.loop

        def _apply():
            try:
                if self.trabajo_dialog:
                    self.trabajo_dialog._aplicar_tercero_seleccionado(self.tercero_seleccionado_unico)
                self.return_dialog()
            except Exception as ex:
                self.ocultar_loader()
                actualizar_mensaje_en_control(f"Error aplicando tercero: {ex}", self.mensaje)

        loop.call_later(0.05, _apply)

    def _identidades_en_consorcios_actuales(self) -> set:
        if not self.consorcios_dialog:
            return set()
        return {c.get("identidad") for c in (self.consorcios_dialog.consorcios_data or [])}

    def _plantilla_consorcio_desde_tercero(self, tercero: dict) -> dict:
        tipos = self.consorcios_dialog.tipos_contrato if self.consorcios_dialog else []
        return {
            "identidad": tercero.get("identidad"),
            "razonsocial": tercero.get("razonsocial", ""),
            "tipodocumento": tercero.get("tipodocumento", ""),
            "fidecomiso": 0,
            "porcentaje": 0,
            "tipo_contrato": tipos[0] if tipos else "",
        }

    def seleccionar_consorcios(self, e):
        if not self.consorcios_dialog:
            actualizar_mensaje_en_control("No hay diálogo de consorcios activo.", self.mensaje)
            return

        seleccionados = [d["data"] for d in self.seleccion_global.values() if d["selected"]]

        if not seleccionados:
            actualizar_mensaje_en_control("Debe seleccionar al menos un tercero", self.mensaje)
            return

        self.mostrar_loader("Aplicando selección...")

        def _worker():
            nuevos = []
            errores = []
            identidades_existentes = self._identidades_en_consorcios_actuales()

            for tercero in seleccionados:
                identidad = tercero.get("identidad")
                if identidad in identidades_existentes:
                    continue

                nuevo = self._plantilla_consorcio_desde_tercero(tercero)

                try:
                    new_id = self._consorcios_uc.crear_consorcio(nuevo)
                except Exception as ex:
                    errores.append(f"Error guardando consorcio {identidad}: {ex}")
                    continue

                if new_id:
                    nuevo["id"] = new_id
                    nuevos.append(nuevo)
                    identidades_existentes.add(identidad)
                else:
                    errores.append(f"No se pudo insertar {identidad}")

            def _ui():
                if nuevos:
                    self.consorcios_dialog.consorcios_data.extend(nuevos)
                if errores:
                    actualizar_mensaje_en_control("; ".join(errores), self.mensaje)
                    self.ocultar_loader()
                    return
                self.return_dialog()

            ejecutar_en_ui(self.page, _ui)

        self.page.run_thread(_worker)

    def mostrar_loader(self, mensaje="Cargando..."):
        self._set_acciones_catalogo_ocupado(True)
        loader_row_visibilidad(self.page, self.loading_indicator, True, f" {mensaje}")

    def ocultar_loader(self):
        self._set_acciones_catalogo_ocupado(False)
        loader_row_fin(self.page, self.loading_indicator)

    def _set_acciones_catalogo_ocupado(self, ocupado: bool):
        """Evita doble clic en Cancelar / Seleccionar mientras hay operación en curso."""
        self._acciones_catalogo_ocupado = ocupado
        if self._btn_cancelar_catalogo:
            self._btn_cancelar_catalogo.disabled = ocupado
        if self._btn_seleccionar_catalogo:
            self._btn_seleccionar_catalogo.disabled = ocupado

    def return_dialog(self):
        self._page_prefix_buffer = ""
        if getattr(self, "_page_prefix_timer", None):
            try:
                self._page_prefix_timer.cancel()
            except Exception:
                pass
            self._page_prefix_timer = None
        if getattr(self, "_txt_banner_alt_pagina", None):
            self._banner_prefijos_sync()

        if self.dialog_agregar:
            self.page.pop_dialog()
            self.page.on_keyboard_event = getattr(self, "_prev_keyboard", None)
            if self.modo_seleccion_unica and self.trabajo_dialog:
                if (
                    hasattr(self.trabajo_dialog, "dialog_trabajo_guardado")
                    and self.trabajo_dialog.dialog_trabajo_guardado
                ):
                    if hasattr(self.trabajo_dialog, "_set_apertura_tercero_ocupada"):
                        self.trabajo_dialog._set_apertura_tercero_ocupada(False)
                    self.page.show_dialog(self.trabajo_dialog.dialog_trabajo_guardado)
                    self.page.update()
            elif self.consorcios_dialog:
                self.consorcios_dialog.open_consorcios_dialog()
