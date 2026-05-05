import flet as ft
import flet_datatable2 as fdt  # type: ignore[import-untyped]
from ui.colors import PINK_50, PINK_200, PINK_600, PINK_800, GREY_700, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
from ui.dropdowns import DropdownCompact
from ui.progress import crear_loader_row, SIZE_SMALL
from ui.snackbars import crear_snackbar, mostrar_mensaje
from paginas.modulopasos.hoja_trabajo.trabajo_dialog import TrabajoDialog
from paginas.modulopasos.hoja_trabajo.hoja_tools_front import (
    indices_columnas_numericas,
    calcular_anchos_columnas,
    construir_esquema,
    construir_matriz_filas,
    identidad_desde_clave,
    label_columna,
    texto_celda_dato,
    fila_identidades,
    cabecera_snackbar_herramienta,
    remover_snackbar_overlay,
    concepto_tiene_cc_mm,
    concepto_tiene_exterior,
    concepto_tiene_tipo_fideicomiso,
    estado_panel_herramientas,
)
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
from utils.ui_sync import ejecutar_en_ui, loader_row_fin, loader_row_visibilidad
from domain.entities.concepto_hoja_trabajo import ConceptoHojaTrabajo

# Confirmaciones de deshacer (menú contextual de herramientas → snackbar `_snackbar_confirmar`).
_MSG_CONF_DESHACER_UNIFICAR = (
    "¿Seguro que desea deshacer las unificaciones de este concepto?\n"
    "Se devolverán las identidades origen a su estado anterior."
)
_MSG_CONF_DESHACER_AGRUPAR = (
    "¿Seguro que desea deshacer la agrupación de cuantías menores de este concepto?\n"
    "Se devolverán los registros agrupados."
)
_MSG_CONF_DESHACER_NUMERAR = (
    "¿Seguro que desea deshacer la numeración de NITs extranjeros de este concepto?\n"
    "Se devolverán las identidades al estado anterior."
)


class HojaTrabajoPage(ft.Column):
    def __init__(self, page: ft.Page, app=None):
        super().__init__(spacing=10, alignment=ft.MainAxisAlignment.CENTER)
        self._page = page
        self._app = app  # InformacionExogenaApp: aviso Ctrl+dígitos en el appbar
        c = app.container
        self._formatos_ui_uc = c.formatos_uc
        self.dialog_trabajo = TrabajoDialog(page, self)
        self._consultar_hoja_uc = c.consultar_hoja_uc
        self._mutar_hoja_uc = c.mutar_hoja_uc

        self.limit = 20
        self.offset = 0
        
        self.concepto_actual = None
        # Lista devuelta por get_hoja_trabajo(solo_conceptos=True); evita repetir la consulta al elegir ítem.
        self._conceptos_hoja_cache: list = []
        self.buscar_texto = ""
        self._buscar_handle = None

        self.rows_bd = {}
        self.matriz = []  # [encabezado] + filas de la página actual
        self._ultimo_concepto = None
        # Esquema cacheado por concepto: evita recalcular en paginación
        self._schema_atributos = []
        self._schema_encabezado = []
        self._schema_columnas_valor = set()
        self.total_identidades = 0

        self.herramientas_abiertas = False
        self.unificar_modo = False
        # Claves seleccionadas en Unificar; se mantienen al paginar (no se limpia en cargar_datos)
        self.unificar_seleccion = []
        self.snackbar_unificar = None
        self.texto_unificar = ft.Text("", color=PINK_800, size=14, weight=ft.FontWeight.BOLD)
        # Buffer para Ctrl+prefijo sobre identidad y mapa identidad -> (control, clave, es_unificar)
        self._prefix_buffer = ""
        self._prefix_buffer_timer = None
        self._control_por_identidad = {}
        # Buffer para Alt+prefijo de número de página
        self._page_prefix_buffer = ""
        self._page_prefix_timer = None

        self.dropdown_conceptos = DropdownCompact(
            label="Concepto | Formato",
            width=155,
            on_select=self._cambiar_concepto,
            tooltip=tooltip(TooltipId.HOJA_CONCEPTO),
        )
        self.search_field = ft.TextField(
            hint_text="Buscar identidad",
            prefix_icon=ft.Icons.PERSON_SEARCH,
            border_radius=10,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            height=37,
            width=188,
            on_change=self._buscar,
        )
        self.loader = crear_loader_row("Cargando hoja de trabajo...", size=SIZE_SMALL)
        self.loader.visible = False
        self.loader_herramientas = crear_loader_row("Procesando...", size=SIZE_SMALL)
        self.loader_herramientas.visible = False
        self.loader_dialogo_trabajo = crear_loader_row("Abriendo formulario...", size=SIZE_SMALL)
        self.loader_dialogo_trabajo.visible = False
        self.pagination_text_footer = build_pagination_label(1, 1)
        self.nav_row = ft.Row(
            [
                ft.ElevatedButton(
                    "Anterior",
                    on_click=lambda e: self._paginar(-1),
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_SHARP,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    visible=False,
                    margin=ft.margin.only(right=66),
                    tooltip=tooltip(TooltipId.PAGINA_BTN_ANTERIOR),
                ),
                self.pagination_text_footer,
                ft.ElevatedButton(
                    "Siguiente",
                    on_click=lambda e: self._paginar(1),
                    icon=ft.Icons.ARROW_FORWARD_IOS_SHARP,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    visible=False,
                    margin=ft.margin.only(left=66),
                    tooltip=tooltip(TooltipId.PAGINA_BTN_SIGUIENTE),
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
        )
        
        # Fila de herramientas (se reconstruye en `_actualizar_herramientas`)
        self.herramientas_row = ft.Row(
            controls=[],
            spacing=3,
            expand=False,
            scroll=ft.ScrollMode.AUTO
        )
        
        # Función para actualizar herramientas según el concepto
        self._actualizar_herramientas()
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
            on_click=self.toggle_herramientas
        )
        self.panel_herramientas = ft.Container(
            content=ft.Row(
                [
                    self.boton_toggle,
                    self.herramientas_container
                ],
                alignment=ft.MainAxisAlignment.END,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            )
        )
        # Tabla DataTable2: encabezado fijo; Acciones e Identidad fijas (fixed_left_columns=2)
        self.table = fdt.DataTable2(
            columns=[fdt.DataColumn2(label=ft.Text("..."))],
            rows=[],
            heading_row_height=40,
            data_row_height=26,
            vertical_lines=ft.border.BorderSide(0.5, GREY_700),
            column_spacing=0,
            horizontal_margin=-5,
            fixed_top_rows=1,
            fixed_left_columns=2,
            visible_vertical_scroll_bar=True,
            visible_horizontal_scroll_bar=True,
            expand=True,
            bgcolor=WHITE,
        )
        # Solo la tabla lleva borde/blanco: el slot exterior es transparente para ver el fondo si hay pocas filas.
        self.table_shell = ft.Container(
            content=self.table,
            bgcolor=WHITE,
            border=ft.border.all(0.3, PINK_200),
            border_radius=1,
        )
        self.table_container = ft.Container(
            content=ft.Column(
                [self.table_shell],
                alignment=ft.MainAxisAlignment.START,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            ),
            expand=True,
        )
        header = ft.Row(
            [
                ft.Text("Hoja de Trabajo", size=18, weight=ft.FontWeight.BOLD),
                self.dropdown_conceptos,
                self.search_field,
                self.panel_herramientas,
            ],
            alignment=ft.MainAxisAlignment.SPACE_AROUND,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
            height=45,
        )
        self.content = ft.Column(
            [
                header,
                self.loader,
                self.loader_herramientas,
                self.loader_dialogo_trabajo,
                self.table_container,
                self.nav_row
            ],
            spacing=8,
            expand=True,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def view(self):
        return self.content

    # --- Carga de datos ---
    def cargar_datos(self):
        if not self.concepto_actual:
            self.rows_bd = {}
            self.matriz = []
            self.table.columns = [ft.DataColumn(ft.Text("Seleccione un concepto"))]
            self.table.rows.clear()
            self.table.expand = True
            self.table.height = None
            self.pagination_text_footer.value = pagination_text_value(1, 1)
            self._page.update()
            return

        self._loader(True)

        def _worker():
            # Solo actualizar herramientas si cambió el concepto (no en paginación)
            concepto_cambio = (self.concepto_actual != self._ultimo_concepto)
            
            try:
                self.rows_bd, has_more, total_identidades = self._consultar_hoja_uc.obtener_filas(
                    offset=self.offset,
                    limit=self.limit,
                    concepto=self._concepto_payload(),
                    filtro=self.buscar_texto or None
                )
                self._has_more = has_more
                self.total_identidades = total_identidades
                if not self.rows_bd:
                    self.mostrar_mensaje("No se encontraron registros para la hoja.", 3000)
                self._preparar_matriz()
                self._ultimo_concepto = self.concepto_actual
            except Exception as e:
                print(f"Error cargando hoja de trabajo: {e}")
                self.rows_bd = {}
                self._has_more = False
                self.total_identidades = 0
                self._preparar_matriz()
                self._ultimo_concepto = self.concepto_actual
            #actualizar la tabla
            self._actualizar_tabla()
            self._loader(False)
            self._page.update()
            # Herramientas en segundo plano: no bloquean la primera pintada de la tabla
            if concepto_cambio:
                def _herramientas():
                    self._actualizar_herramientas()
                    self._page.update()
                self._page.run_thread(_herramientas)

        self._page.run_thread(_worker)

    def _ir_a_pagina(self, pagina: int):
        """Salta a la página indicada (1-based) respetando los límites."""
        if pagina < 1 or not self.limit:
            return
        total = getattr(self, "total_identidades", 0) or 0
        if total > 0:
            total_paginas = max(1, (total + self.limit - 1) // self.limit)
            if pagina > total_paginas:
                pagina = total_paginas
        self.offset = (pagina - 1) * self.limit
        self.cargar_datos()

    # --- Esquema y matriz ---
    def _preparar_matriz(self):
        """Actualiza esquema si cambió concepto; rellena matriz [encabezado] + filas de la página actual."""
        concepto_cambio = (self.concepto_actual != self._ultimo_concepto)
        datos = self.rows_bd

        if not datos:
            self.matriz = [["Vacío"]]
            self._schema_atributos = []
            self._schema_encabezado = []
            self._schema_columnas_valor = set()
            return

        if concepto_cambio or not self._schema_atributos:
            self._schema_atributos, self._schema_encabezado, self._schema_columnas_valor = construir_esquema(
                self._formatos_ui_uc, self._concepto_payload(), datos
            )
        self.matriz = construir_matriz_filas(datos, self._schema_encabezado, self._schema_atributos)

    # --- Tabla: celdas y contenido ---
    def _contenido_acciones(self, clave_completa: str, registro: dict, id_concepto, identidad):
        """Solo el contenido de la celda Acciones (Row), para reutilizar en paginación."""
        identidad_visual = ""
        if registro is not None and identidad is not None:
            identidad_db = identidad
            texto_identidad = str(
                registro.get("Número de Identificación", identidad_db) or ""
            )
            identidad_visual = (
                texto_identidad[:-3]
                if texto_identidad.endswith("|ex")
                else texto_identidad
            )

        tt_ctrl = tooltip(TooltipId.HOJA_CTRL_IDENTIDAD, identidad=identidad_visual)

        if self.unificar_modo:
            # En modo unificar usamos checkbox; lo registramos para Ctrl+prefijo de identidad.
            cb = ft.Checkbox(
                value=clave_completa in self.unificar_seleccion,
                active_color=PINK_200,
                tooltip=tt_ctrl,
                on_change=lambda e, k=clave_completa: self._toggle_unificar(
                    k, e.control.value
                ),
            )
            if identidad_visual:
                self._control_por_identidad[identidad_visual] = (
                    cb,
                    clave_completa,
                    True,
                )
            return ft.Row([cb], alignment=ft.MainAxisAlignment.CENTER)

        # Modo normal: botón principal de edición será el objetivo del foco por teclado.
        btn_edit = ft.IconButton(
            icon=ft.Icons.EDIT_OUTLINED,
            tooltip=tt_ctrl,
            style=BOTON_SECUNDARIO_SIN,
            icon_size=18,
            on_click=lambda e, k=clave_completa, data=registro, idc=id_concepto, idn=identidad: self._abrir_dialogo_trabajo_deferred(
                "Cargando registro...",
                id_concepto=idc,
                identidad=idn,
                datos=data,
                concepto=self._concepto_payload(),
            ),
        )
        btn_delete = ft.IconButton(
            icon=ft.Icons.DELETE,
            tooltip="Eliminar",
            style=BOTON_SECUNDARIO_SIN,
            icon_size=18,
            on_click=lambda e, idc=id_concepto, idn=identidad: self.mostrar_mensaje(
                "¿Desea eliminar la informacion?", 5555, id_concepto=idc, identidad=idn
            ),
        )

        if identidad_visual:
            self._control_por_identidad[identidad_visual] = (
                btn_edit,
                identidad,
                False,
            )

        return ft.Row(
            [btn_edit, btn_delete],
            spacing=-10,
            alignment=ft.MainAxisAlignment.CENTER,
        )

    def _contenido_celda(self, col_idx: int, fila: list | None, registro: dict | None, encabezados: list, indices_valor: set, borde_identidad) -> ft.Control:
        """Control interior de una celda de la tabla (sin DataCell).
        """
        if fila is None or registro is None:
            return ft.Text("", selectable=True)
        clave_completa = fila[1]
        # Identidad real en BD (puede incluir sufijos internos como '|ex')
        identidad_db = clave_completa.split("|", 1)[-1] if "|" in clave_completa else clave_completa
        # Texto a mostrar: usar Número de Identificación si existe, si no, la identidad; nunca mostrar sufijos internos como '|ex'
        texto_identidad = str(registro.get("Número de Identificación", identidad_db) or "")
        # Ocultar sufijo |ex (agrupaciones del sistema) al usuario
        texto_identidad_visual = texto_identidad[:-3] if texto_identidad.endswith("|ex") else texto_identidad
        id_concepto = registro.get("id_concepto")
        # Para operaciones de BD (editar/eliminar) usamos la identidad real con sufijo
        identidad = identidad_db
        if col_idx == 0:
            return self._contenido_acciones(clave_completa, registro, id_concepto, identidad)
        if col_idx == 1:
            # Identidad: texto centrado y seleccionable, con borde a la derecha.
            return ft.Container(
                content=ft.Text(
                    texto_identidad_visual,
                    text_align=ft.TextAlign.CENTER,
                    selectable=True,
                    max_lines=1,
                    no_wrap=True,
                    overflow=ft.TextOverflow.ELLIPSIS,
                    style=ft.TextStyle(height=0.9),
                ),
                alignment=ft.Alignment(0, 0),
                padding=0,
                border=borde_identidad,
            )
        valor = fila[col_idx] if col_idx < len(fila) else ""
        nombre_col = (encabezados[col_idx] or "") if col_idx < len(encabezados) else ""
        col_valor = getattr(self, "_schema_columnas_valor", set())
        texto, alineacion = texto_celda_dato(valor, nombre_col, col_idx, indices_valor, col_valor)
        # Para datos: el contenedor fuerza centrado vertical consistente en filas compactas.
        return ft.Container(
            content=ft.Text(
                texto,
                text_align=alineacion,
                selectable=True,
                max_lines=1,
                tooltip=texto,
                no_wrap=True,
                overflow=ft.TextOverflow.ELLIPSIS,
                style=ft.TextStyle(height=0.9),
            ),
            alignment=ft.Alignment(1, 0) if alineacion == ft.TextAlign.END else ft.Alignment(-1, 0),
            padding=0,
        )

    def _banner_prefijos_sync(self) -> None:
        sync_banner_prefijo(
            self._page,
            app=getattr(self, "_app", None),
            prefix_ctrl=self._prefix_buffer,
            prefix_alt=self._page_prefix_buffer,
        )

    def _on_keyboard_page(self, e: ft.KeyboardEvent):
        """
        Handler global de teclado en Hoja de Trabajo:
        - Re Pág / Av Pág: página anterior / siguiente.
        - Alt + dígitos: salto a la página indicada (tras pausa corta).
        - Ctrl + dígitos: foco o alternar Unificar en la identidad cuyo número empieza por el prefijo.
        """
        if getattr(self._page, "route", "") != "/home/hoja_trabajo":
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
            # Acumula el prefijo (ej. 9 -> 90 -> 901234...)
            self._prefix_buffer += digit
            self._banner_prefijos_sync()

            # Reinicia temporizador: al terminar de escribir, aplica el foco una sola vez.
            if self._prefix_buffer_timer:
                self._prefix_buffer_timer.cancel()
            loop = self._page.session.connection.loop

            def _on_timeout():
                prefix = (self._prefix_buffer or "").strip()
                reset_prefix_buffer(self)
                self._banner_prefijos_sync()
                if not prefix:
                    return
                for identidad, data in getattr(
                    self, "_control_por_identidad", {}
                ).items():
                    if not str(identidad).startswith(prefix):
                        continue

                    control, clave, es_unificar = data

                    # Si el control ya no está asociado a la página, lo ignoramos silenciosamente.
                    try:
                        _ = control.page  # puede lanzar RuntimeError si ya no está en la página
                    except RuntimeError:
                        continue

                    if es_unificar:
                        # Modo unificar: Ctrl+prefijo alterna el checkbox y actualiza la selección.
                        nuevo_valor = not bool(control.value)
                        control.value = nuevo_valor
                        self._toggle_unificar(clave, nuevo_valor)
                        self._page.update()
                    else:
                        # Modo normal: foco en el botón principal de edición.
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

        # No es Ctrl+digito: limpiar buffers y gestionar solo paginación.
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
            self._paginar(-1)
        elif tecla_es_avpag(key):
            self._paginar(1)

    def _filas_datos_visibles(self) -> int:
        """Filas de datos en la matriz actual (sin encabezado), acotadas al tamaño de página."""
        if not self.matriz or len(self.matriz) < 2:
            return 0
        return min(self.limit, len(self.matriz) - 1)

    def _actualizar_paginacion_footer(self) -> None:
        """Actualiza visibilidad de botones y texto de paginación."""
        self.nav_row.controls[0].visible = not self.offset <= 0
        has_more = getattr(self, "_has_more", False)
        self.nav_row.controls[2].visible = has_more

        pagina = (self.offset // self.limit) + 1 if self.limit else 1
        total = getattr(self, "total_identidades", 0) or 0
        total_paginas = (
            max(1, (total + self.limit - 1) // self.limit) if self.limit else 1
        )
        self.pagination_text_footer.value = pagination_text_value(pagina, total_paginas)
        self._page.update()

    def _reconstruir_tabla(self, encabezados: list, num_cols: int, n_filas: int) -> None:
        """Reconstruye columnas y filas desde cero (cuando cambia el esquema de la página)."""
        self._ultimos_encabezados = tuple(encabezados)
        col_valor = getattr(self, "_schema_columnas_valor", set())

        anchos = calcular_anchos_columnas(
            self._formatos_ui_uc, encabezados, col_valor, self._concepto_payload()
        )
        indices_valor = indices_columnas_numericas(encabezados, col_valor)
        numeric_indices = indices_valor

        total_ancho = float(sum(anchos)) if anchos else None
        self.table.width = total_ancho
        self.table_shell.width = (
            int(total_ancho) if total_ancho is not None else None
        )
        self.table.fixed_left_columns = 0

        self.table.columns = [
            fdt.DataColumn2(
                label=label_columna(i, h or ""),
                fixed_width=anchos[i] if i < len(anchos) else None,
                numeric=(i in numeric_indices),
                heading_row_alignment=ft.MainAxisAlignment.CENTER,
            )
            for i, h in enumerate(encabezados)
        ]

        borde_identidad = ft.border.only(
            right=ft.border.BorderSide(0.5, GREY_700)
        )
        self._indices_valor_cached = indices_valor

        filas_nuevas = []
        # Una fila por registro real: si no hay suficientes registros, no se rellenan celdas fantasma.
        for row_idx in range(n_filas):
            # matriz[0]=encabezado; fila[1]=clave id_concepto|identidad para rows_bd
            fila = (
                self.matriz[1 + row_idx] if 1 + row_idx < len(self.matriz) else None
            )
            registro = self.rows_bd.get(fila[1]) if fila else None

            celdas = [
                ft.DataCell(
                    self._contenido_celda(
                        c, fila, registro, encabezados, indices_valor, borde_identidad
                    )
                )
                for c in range(num_cols)
            ]
            filas_nuevas.append(ft.DataRow(cells=celdas))
        self.table.rows = filas_nuevas

        # Menos filas que el tamaño de página: la tabla no estira y se ajusta la altura.
        hr = self.table.heading_row_height or 40
        dr = self.table.data_row_height or 26
        sep = float(self.table.divider_thickness or 1)
        if n_filas < self.limit:
            self.table.expand = False
            sep_extra = max(0, n_filas - 1) * sep
            self.table.height = hr + n_filas * dr + sep_extra + 6
        else:
            self.table.expand = True
            self.table.height = None

    def _actualizar_tabla_paginacion(
        self, encabezados: list, num_cols: int
    ) -> None:
        """Actualiza solo el contenido de celdas (columnas permanecen iguales)."""
        indices_valor = getattr(self, "_indices_valor_cached", set())
        borde_identidad = ft.border.only(
            right=ft.border.BorderSide(0.5, GREY_700)
        )

        for row_idx in range(len(self.table.rows)):
            fila = (
                self.matriz[1 + row_idx] if 1 + row_idx < len(self.matriz) else None
            )
            registro = self.rows_bd.get(fila[1]) if fila else None

            for col_idx in range(
                min(num_cols, len(self.table.rows[row_idx].cells))
            ):
                self.table.rows[row_idx].cells[col_idx].content = self._contenido_celda(
                    col_idx, fila, registro, encabezados, indices_valor, borde_identidad
                )

    def _actualizar_tabla(self):
        """Reconstruye o actualiza la grilla según cambie el esquema o sea paginación."""
        # Reiniciar mapa identidad -> control en cada reconstrucción de tabla
        self._control_por_identidad = {}

        encabezados = self.matriz[0]
        num_cols = len(encabezados)
        n_filas = self._filas_datos_visibles()

        encabezados_key = tuple(encabezados)
        es_paginacion = (
            getattr(self, "_ultimos_encabezados", None) == encabezados_key
            and len(self.table.rows) == n_filas
        )

        if not es_paginacion:
            self._reconstruir_tabla(encabezados, num_cols, n_filas)
        else:
            self._actualizar_tabla_paginacion(encabezados, num_cols)

        self._actualizar_paginacion_footer()

    # --- Navegación: paginar, buscar, concepto ---
    def _loader(self, v: bool):
        loader_row_visibilidad(self._page, self.loader, v)

    def _abrir_dialogo_trabajo_deferred(self, mensaje: str, **kwargs):
        """
        Muestra carga antes de `TrabajoDialog.abrir`: la construcción del formulario y la carga
        de tercero en edición pueden tardar; sin defer el hilo de UI no pinta el ring.
        """
        loader_row_visibilidad(self._page, self.loader_dialogo_trabajo, True, f" {mensaje}")
        loop = self._page.session.connection.loop

        def _abrir():
            try:
                self.dialog_trabajo.abrir(**kwargs)
            finally:
                loader_row_fin(self._page, self.loader_dialogo_trabajo)

        loop.call_later(0.05, _abrir)

    def _paginar(self, direction):
        nuevo = self.offset + (direction * self.limit)
        if nuevo < 0:
            return
        self.offset = nuevo
        self.cargar_datos()
        self._page.update()

    def _cambiar_concepto(self, e):
        # Índice en _conceptos_hoja_cache (poblado en cargar_conceptos); sin repetir la consulta al elegir.
        if e.control.value is None:
            self.concepto_actual = None
        else:
            idx = int(e.control.value)
            c = self._conceptos_hoja_cache
            if not c or not (0 <= idx < len(c)):
                c = self._consultar_hoja_uc.obtener_conceptos_en_hoja()
                self._conceptos_hoja_cache = c
            self.concepto_actual = c[idx] if c and 0 <= idx < len(c) else None
        self.offset = 0
        self._ultimo_concepto = None  # Forzar actualización de herramientas al cambiar concepto
        self.cargar_datos()  # Ya actualiza herramientas si concepto cambió
    
    def _actualizar_herramientas(self):
        """Arma la fila de herramientas: un control por acción (insertar, unificar con menú, etc.)."""

        def btn(titulo: str, icono, on_click):
            return ft.OutlinedButton(
                titulo,
                icon=icono,
                icon_color=PINK_600,
                style=BOTON_SECUNDARIO,
                on_click=on_click,
            )

        def menu(titulo, icono, opciones):
            return self._context_menu_herramienta(titulo, icono, opciones)

        ctrls = [
            btn(
                "Insertar",
                ft.Icons.ADD,
                lambda e: self._abrir_dialogo_trabajo_deferred(
                    "Preparando nuevo registro...",
                    modo="nuevo",
                    concepto=self._concepto_payload(),
                )
                if self.concepto_actual is not None
                else self.mostrar_mensaje("Seleccione un concepto"),
            ),
            btn(
                "Eliminar",
                ft.Icons.DELETE_SHARP,
                lambda e: self.dialog_trabajo.abrir(modo="eliminar", concepto=self._concepto_payload())
                if self.concepto_actual is not None
                else self.mostrar_mensaje("Seleccione un concepto"),
            ),
            btn("Actualizar hoja", ft.Icons.CLOUD_SYNC_OUTLINED, lambda e: self.cargar_datos()),
            menu(
                "Unificar",
                ft.Icons.JOIN_LEFT_SHARP,
                [
                    ("Unificar identidades", lambda: self._con_concepto(self._activar_unificar)),
                    ("Deshacer unificación…", lambda: self._pregunta_deshacer(self._deshacer_unificar, _MSG_CONF_DESHACER_UNIFICAR)),
                ],
            ),
            btn("Informes", ft.Icons.IMPORT_CONTACTS_ROUNDED, lambda e: None),
        ]

        if self.concepto_actual:
            try:
                c = self._concepto_completo()
                if c:
                    if concepto_tiene_cc_mm(c):
                        ctrls.append(
                            menu(
                                "Cuantias menores",
                                ft.Icons.LOOKS_TWO_OUTLINED,
                                [
                                    ("Agrupar cuantías menores", lambda: self._con_concepto(self._activar_agrupar_cuantias_menores)),
                                    ("Deshacer agrupación…", lambda: self._pregunta_deshacer(self._deshacer_agrupar_cuantias, _MSG_CONF_DESHACER_AGRUPAR)),
                                ],
                            )
                        )
                    if concepto_tiene_exterior(c):
                        ctrls.append(
                            menu(
                                "Nits Extranjeros",
                                ft.Icons.CONTACT_EMERGENCY_OUTLINED,
                                [
                                    ("Numerar NITs", lambda: self._con_concepto(self._activar_numerar_nits)),
                                    ("Deshacer numeración…", lambda: self._pregunta_deshacer(self._deshacer_numerar_nits, _MSG_CONF_DESHACER_NUMERAR)),
                                ],
                            )
                        )
                    if concepto_tiene_tipo_fideicomiso(self._formatos_ui_uc, c):
                        ctrls.append(
                            btn(
                                "Tipo de fideicomiso",
                                ft.Icons.ACCOUNT_BALANCE,
                                lambda e: self.dialog_trabajo.abrir(
                                    modo="fideicomiso_masivo",
                                    concepto=self._concepto_payload(),
                                )
                                if self.concepto_actual is not None
                                else self.mostrar_mensaje("Seleccione un concepto"),
                            )
                        )
            except Exception as e:
                print(f"Error verificando concepto: {e}")

        self.herramientas_row.controls = ctrls
        if self.herramientas_abiertas:
            self.herramientas_container.update()

    def _con_concepto(self, fn):
        """Ejecuta `fn` solo si hay concepto seleccionado."""
        if not self._requiere_concepto():
            return
        fn()

    def _pregunta_deshacer(self, on_si, mensaje: str) -> None:
        """Abre el snackbar de confirmación de deshacer (misma lógica para todas las herramientas)."""
        if not self._requiere_concepto():
            return
        self._snackbar_confirmar(ft.Icons.UNDO_OUTLINED, mensaje, on_si)

    def _context_menu_herramienta(self, titulo_boton: str, icono, items) -> ft.ContextMenu:
        """
        OutlinedButton + menú al clic izquierdo. Solo texto en cada opción; estilo del panel
        vía `page.theme.popup_menu_theme` (main.py). Padding mínimo para acercar el hover al borde.
        """
        def _make_click(fn):
            return lambda e: fn()

        def _opcion(texto: str, fn):
            return ft.PopupMenuItem(
                content=ft.Text(
                    texto,
                    size=13,
                    color=GREY_700,
                    weight=ft.FontWeight.W_500,
                    no_wrap=True,
                ),
                on_click=_make_click(fn),
                height=36,
                padding=ft.padding.symmetric(horizontal=6, vertical=4),
                mouse_cursor=ft.MouseCursor.CLICK,
            )

        primary = [_opcion(label, fn) for label, fn in items]

        return ft.ContextMenu(
            content=ft.OutlinedButton(
                titulo_boton,
                icon=icono,
                icon_color=PINK_600,
                style=BOTON_SECUNDARIO,
            ),
            primary_trigger=ft.ContextMenuTrigger.DOWN,
            primary_items=primary,
            secondary_trigger=None,
        )

    def _concepto_completo(self):
        """Obtiene el concepto completo desde BD (con cc_mm, exterior, etc.)."""
        concepto = self._concepto_payload()
        if not isinstance(concepto, dict) or "codigo" not in concepto or "formato" not in concepto:
            return None
        codigo, formato = concepto["codigo"], concepto["formato"]
        return self._consultar_hoja_uc.obtener_concepto_completo(
            codigo=codigo,
            formato=formato,
        )

    def _concepto_payload(self):
        """
        Normaliza el concepto actual para los casos de uso y mutaciones.

        La UI puede manejar una entidad de dominio; los casos de uso esperan un dict con
        `codigo` y `formato`.
        """
        c = self.concepto_actual
        if isinstance(c, ConceptoHojaTrabajo):
            return c.as_dict()
        return c
        
    def cargar_conceptos(self):
        """Llena el dropdown en segundo plano. Llamar desde on_enter o al montar."""
        def _worker():
            try:
                conceptos = self._consultar_hoja_uc.obtener_conceptos_en_hoja()
                self._conceptos_hoja_cache = list(conceptos) if conceptos else []
                if self._conceptos_hoja_cache:
                    opciones = [
                        ft.DropdownOption(
                            key=str(i),
                            text=f"{c.codigo} | {c.formato}",
                        )
                        for i, c in enumerate(self._conceptos_hoja_cache)
                    ]
                    self.dropdown_conceptos.options = opciones
                else:
                    self.dropdown_conceptos.options = []
                self.dropdown_conceptos.value = None
            except Exception as e:
                self.mostrar_mensaje(f"Error cargando conceptos: {e}", 5555)
            self._page.update()
        self._page.run_thread(_worker)

    def _buscar(self, e):
        ft.context.disable_auto_update()
        if self._buscar_handle is not None:
            self._buscar_handle.cancel()
        texto = (e.control.value or "").strip()
        self.offset = 0
        loop = self._page.session.connection.loop
        # Debounce: ejecutar búsqueda 350 ms después del último tecleo
        self._buscar_handle = loop.call_later(0.35, lambda: self._buscar_ejecutar(texto))

    def _buscar_ejecutar(self, texto: str):
        self.buscar_texto = texto
        self.cargar_datos()

    # --- Herramientas ---
    def toggle_herramientas(self, e):
        """Abre/cierra el panel de herramientas"""
        self.herramientas_abiertas = not self.herramientas_abiertas
        est = estado_panel_herramientas(self.herramientas_abiertas)
        self.herramientas_container.width = est["width"]
        self.herramientas_container.opacity = est["opacity"]
        self.herramientas_container.visible = est["visible"]
        self.boton_toggle.icon = est["icon"]
        self.boton_toggle.text = est["text"]
        self.boton_toggle.tooltip = est["tooltip"]
        self.panel_herramientas.update()

    # --- Utilidades internas: herramientas (loader, snackbars, hilo) ---
    def _requiere_concepto(self) -> bool:
        """True si hay concepto seleccionado; si no, muestra aviso y retorna False."""
        if self.concepto_actual:
            return True
        self.mostrar_mensaje("Seleccione un concepto primero.", 3000)
        return False

    def _loader_herramientas(self, visible: bool, mensaje: str | None = None) -> None:
        """Muestra u oculta el loader de herramientas; opcionalmente cambia el texto."""
        loader_row_visibilidad(self._page, self.loader_herramientas, visible, mensaje)

    def _snackbar_herramientas_abrir(self, contenido: ft.Control, duration: int = 7000) -> ft.SnackBar:
        """Anexa un snackbar al overlay y lo abre (patrón común de menús y confirmaciones)."""
        snack = crear_snackbar(contenido, duration=duration, show_close=False)
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()
        return snack

    def _btn_cancelar_snackbar(self, on_click) -> ft.TextButton:
        return ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, style=BOTON_SECUNDARIO_SIN, on_click=on_click)

    def _snackbar_confirmar(self, icono, mensaje: str, on_si) -> None:
        """Confirmación de deshacer: Cancelar cierra el snack; Deshacer ejecuta el callback."""

        def cerrar(_e=None):
            remover_snackbar_overlay(self._page, getattr(self, "_snackbar_confirmacion", None))
            self._snackbar_confirmacion = None
            self._page.update()

        def si(_e=None):
            cerrar()
            on_si()

        botones = [
            self._btn_cancelar_snackbar(cerrar),
            ft.Button("Deshacer", icon=ft.Icons.UNDO_OUTLINED, style=BOTON_PRINCIPAL, on_click=si),
        ]
        texto = ft.Text(mensaje, color=PINK_800, size=14, expand=True)
        cabecera = cabecera_snackbar_herramienta(icono, texto, botones)
        self._snackbar_confirmacion = self._snackbar_herramientas_abrir(
            ft.Column(controls=[cabecera], spacing=8, tight=True),
            duration=999999999,
        )

    def _cerrar_snackbar_attr(self, nombre_attr: str) -> None:
        remover_snackbar_overlay(self._page, getattr(self, nombre_attr, None))
        setattr(self, nombre_attr, None)
        self._page.update()

    def _preview_identidades_snackbar(
        self,
        *,
        attr_snackbar: str,
        identidades: list,
        mensaje: str,
        icono,
        verbo_lista: str,
        prefijo_lista: str,
        texto_boton: str,
        icono_boton,
        on_confirmar,
        duration: int = 999999999,
    ) -> None:
        """Vista previa con lista copiable + Cancelar / acción principal."""
        fila = fila_identidades(
            identidades,
            verbo=verbo_lista,
            prefijo=prefijo_lista,
            page=self._page,
            on_copy=lambda: self.mostrar_mensaje("Identidades copiadas al portapapeles", 2000),
            copy_on_click=True,
        )
        accion = (
            ft.Button(texto_boton, icon=icono_boton, style=BOTON_PRINCIPAL, on_click=on_confirmar)
            if icono_boton is not None
            else ft.Button(texto_boton, style=BOTON_PRINCIPAL, on_click=on_confirmar)
        )
        botones = [
            self._btn_cancelar_snackbar(lambda _e: self._cerrar_snackbar_attr(attr_snackbar)),
            accion,
        ]
        cabecera = cabecera_snackbar_herramienta(
            icono,
            ft.Text(mensaje, color=PINK_800, size=14, expand=True),
            botones,
        )
        cols = [cabecera] + ([fila] if fila else [])
        snack = crear_snackbar(ft.Column(controls=cols, spacing=8, tight=True), duration=duration, show_close=False)
        setattr(self, attr_snackbar, snack)
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    def _hilo_herramientas(self, mensaje_loader: str, trabajo) -> None:
        """Ejecuta trabajo() en hilo; siempre oculta el loader al terminar."""
        self._loader_herramientas(True, mensaje_loader)

        def _worker():
            try:
                trabajo()
            finally:
                self._loader_herramientas(False)

        self._page.run_thread(_worker)

    # --- Mensajes ---
    def mostrar_mensaje(self, texto, duration=5555, id_concepto=None, identidad=None, color=None, on_dismiss=None):
        """
        texto: mensaje a mostrar.
        Si id_concepto e identidad se pasan, muestra botón Confirmar para eliminar ese registro.
        on_dismiss: opcional, se llama al cerrar el snackbar.
        """
        if id_concepto is not None and identidad is not None:

            def on_confirm(_e):
                self._mutar_hoja_uc.eliminar_grupo_filas_hoja(id_concepto, identidad)
                self.cargar_datos()

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

    # --- Unificar ---
    def _identidad_desde_clave(self, clave: str):
        """Obtiene la identidad (Número de Identificación) para una clave de fila."""
        cache = getattr(self, "_clave_a_identidad", None) or {}
        return identidad_desde_clave(clave, self.rows_bd, cache)

    def _obtener_identidades_origen_unificar(self) -> list:
        """Lista de identidades que se unificarán (todas las seleccionadas menos la primera)."""
        if len(self.unificar_seleccion) <= 1:
            return []
        # Selección[0]=destino; [1:]=origen a sumar
        return [
            ident for clave in self.unificar_seleccion[1:]
            if (ident := self._identidad_desde_clave(clave))
        ]

    def _activar_unificar(self):
        self.unificar_modo = True
        self.unificar_seleccion = []
        self._clave_a_identidad = {}
        self._actualizar_tabla()
        self._mostrar_snackbar_unificar()

    def _cerrar_snackbar_unificar(self):
        remover_snackbar_overlay(self._page, self.snackbar_unificar)
        self.snackbar_unificar = None
        self._snackbar_unificar_contenido = None
        self._snackbar_unificar_cabecera = None

    def _desactivar_unificar(self):
        self.unificar_modo = False
        self.unificar_seleccion = []
        self._cerrar_snackbar_unificar()
        self._actualizar_tabla()

    def _toggle_unificar(self, clave_completa: str, marcado: bool):
        """Actualiza selección de unificar según el checkbox y refresca el snackbar."""
        if marcado:
            if clave_completa not in self.unificar_seleccion:
                self.unificar_seleccion.append(clave_completa)
                if not hasattr(self, "_clave_a_identidad"):
                    self._clave_a_identidad = {}
                ident = self._identidad_desde_clave(clave_completa)
                if ident is not None:
                    self._clave_a_identidad[clave_completa] = ident
        else:
            if clave_completa in self.unificar_seleccion:
                self.unificar_seleccion.remove(clave_completa)
                if hasattr(self, "_clave_a_identidad") and clave_completa in self._clave_a_identidad:
                    del self._clave_a_identidad[clave_completa]
        if self.unificar_modo:
            self._actualizar_texto_snackbar_unificar()

    def _mostrar_snackbar_unificar(self):
        self._actualizar_texto_snackbar_unificar()
        identidades_origen = self._obtener_identidades_origen_unificar()
        detalle_row = fila_identidades(
            identidades_origen,
            verbo="unificar",
            prefijo="Identidades a unificar en la primera",
            page=self._page,
            on_copy=lambda: None,
            copy_on_click=False,
        )

        botones = [
            ft.TextButton("Cancelar", icon=ft.Icons.CLOSE, style=BOTON_SECUNDARIO_SIN, on_click=self._on_cancelar_unificar),
            ft.Button("Unificar", icon=ft.Icons.JOIN_LEFT_SHARP, style=BOTON_PRINCIPAL, on_click=self._confirmar_unificar),
        ]
        cabecera = cabecera_snackbar_herramienta(ft.Icons.INFO_OUTLINE, ft.Container(self.texto_unificar, expand=True), botones)

        contenido_controls = [cabecera]
        if detalle_row:
            contenido_controls.append(detalle_row)

        contenido = ft.Column(controls=contenido_controls, spacing=8, tight=True)
        self._snackbar_unificar_cabecera = cabecera
        self._snackbar_unificar_contenido = contenido
        self.snackbar_unificar = crear_snackbar(
            contenido,
            duration=999999999,
            show_close=False,
        )
        self._page.overlay.append(self.snackbar_unificar)
        self.snackbar_unificar.open = True
        self._page.update()

    def _on_cancelar_unificar(self, e=None):
        self._desactivar_unificar()
        
    def _actualizar_texto_snackbar_unificar(self):
        if not self.unificar_seleccion:
            self.texto_unificar.value = "Seleccione la identidad destino para la unificación."
        else:
            base_clave = self.unificar_seleccion[0]
            identidad_texto = self._identidad_desde_clave(base_clave) or "seleccionada"
            total = len(self.unificar_seleccion) - 1
            if total == 0:
                self.texto_unificar.value = f"Identidad destino: {identidad_texto}. Seleccione filas a sumar."
            else:
                self.texto_unificar.value = (
                    f"Identidad destino: {identidad_texto}\n"
                    f"Se sumarán los valores de {total} fila(s) a esta identidad."
                )

        # Actualizar fila del tooltip sin cerrar el snackbar
        contenido = getattr(self, "_snackbar_unificar_contenido", None)
        cabecera = getattr(self, "_snackbar_unificar_cabecera", None)
        if contenido is not None and cabecera is not None:
            detalle_row = fila_identidades(
                self._obtener_identidades_origen_unificar(),
                verbo="unificar",
                prefijo="Identidades a unificar en la primera",
                page=self._page,
                on_copy=lambda: None,
                copy_on_click=False,
            )
            contenido.controls = [cabecera, detalle_row] if detalle_row else [cabecera]

        if self.snackbar_unificar:
            self.snackbar_unificar.update()
        self._page.update()

    def _confirmar_unificar(self, e=None):
        if len(self.unificar_seleccion) < 2:
            self._cerrar_snackbar_unificar()
            self.mostrar_mensaje(
                "Seleccione al menos dos grupos para unificar.",
                3000,
                on_dismiss=lambda e: self._mostrar_snackbar_unificar(),
            )
            return
        self._cerrar_snackbar_unificar()

        def trabajo():
            try:
                res = self._mutar_hoja_uc.unificar_grupos_hoja_trabajo(
                    self._concepto_payload(), self.unificar_seleccion
                )
                if res is True:
                    self.mostrar_mensaje("Unificación realizada.", 3000)
                    self._desactivar_unificar()
                    self.cargar_datos()
                else:
                    self.mostrar_mensaje(str(res), 5555)
            except Exception as ex:
                self.mostrar_mensaje(f"Error unificando: {ex}", 5555)

        self._hilo_herramientas("Unificando registros...", trabajo)

    def _activar_agrupar_cuantias_menores(self):
        if not self._requiere_concepto():
            return

        def worker():
            try:
                identidades = self._mutar_hoja_uc.obtener_identidades_a_agrupar_cuantias(
                    self._concepto_payload()
                )
            except Exception as ex:

                def en_ui_err():
                    self._loader_herramientas(False)
                    self.mostrar_mensaje(f"Error preparando agrupación: {ex}", 5555)

                ejecutar_en_ui(self._page, en_ui_err)
                return

            def en_ui():
                self._loader_herramientas(False)
                if not identidades:
                    self.mostrar_mensaje("No hay registros con cuantía menor al umbral configurado.", 3000)
                    return
                n = len(identidades)
                self._preview_identidades_snackbar(
                    attr_snackbar="_snackbar_agrupar",
                    identidades=identidades,
                    mensaje=f"Se agruparán {n} identidad(es) en un único registro de cuantías menores.",
                    icono=ft.Icons.LOOKS_TWO_OUTLINED,
                    verbo_lista="agrupar",
                    prefijo_lista="Identidades a agrupar en cuantías menores",
                    texto_boton="Agrupar",
                    icono_boton=ft.Icons.LOOKS_TWO_OUTLINED,
                    on_confirmar=self._confirmar_agrupar_cuantias_menores,
                )

            ejecutar_en_ui(self._page, en_ui)

        self._loader_herramientas(True, "Preparando...")
        self._page.run_thread(worker)

    def _on_cancelar_agrupar_cuantias(self, e=None):
        self._cerrar_snackbar_attr("_snackbar_agrupar")

    def _cerrar_snackbar_agrupar_cuantias(self):
        self._cerrar_snackbar_attr("_snackbar_agrupar")

    def _confirmar_agrupar_cuantias_menores(self, e=None):
        self._cerrar_snackbar_agrupar_cuantias()

        def trabajo():
            try:
                res = self._mutar_hoja_uc.agrupar_cuantias_menores(self._concepto_payload())
                if isinstance(res, str) and res.startswith("Se agruparon"):
                    self.mostrar_mensaje(res, 3000)
                    self.cargar_datos()
                    self._actualizar_herramientas()
                else:
                    self.mostrar_mensaje(res if isinstance(res, str) else "Error agrupando cuantías menores", 5555)
            except Exception as ex:
                self.mostrar_mensaje(f"Error agrupando cuantías menores: {ex}", 5555)

        self._hilo_herramientas("Agrupando cuantías menores...", trabajo)

    def _activar_numerar_nits(self):
        if not self._requiere_concepto():
            return

        def worker():
            try:
                terceros = self._mutar_hoja_uc.obtener_terceros_a_numerar(
                    self._concepto_payload()
                )
            except Exception as ex:

                def en_ui_err():
                    self._loader_herramientas(False)
                    self.mostrar_mensaje(f"Error preparando numeración: {ex}", 5555)

                ejecutar_en_ui(self._page, en_ui_err)
                return

            def en_ui():
                self._loader_herramientas(False)
                if not terceros:
                    self.mostrar_mensaje("No se encontraron terceros con tipo de documento 42.", 3000)
                    return
                n = len(terceros)
                self._preview_identidades_snackbar(
                    attr_snackbar="_snackbar_numerar",
                    identidades=terceros,
                    mensaje=(
                        f"Se numerarán {n} identidad(es) con el patrón 44444xxxx. "
                        "El tipo de documento cambiará a 43."
                    ),
                    icono=ft.Icons.INFO_OUTLINE,
                    verbo_lista="numerar",
                    prefijo_lista="Identidades a numerar",
                    texto_boton="Continuar",
                    icono_boton=None,
                    on_confirmar=self._confirmar_numerar_nits,
                )

            ejecutar_en_ui(self._page, en_ui)

        self._loader_herramientas(True, "Preparando...")
        self._page.run_thread(worker)

    def _deshacer_agrupar_cuantias(self, e=None):
        if not self._requiere_concepto():
            return

        def trabajo():
            try:
                res = self._mutar_hoja_uc.deshacer_agrupar_cuantias(
                    self._concepto_payload()
                )
                if isinstance(res, str) and res.startswith("Se devolvieron"):
                    self.mostrar_mensaje(res, 3000)
                    self.cargar_datos()
                    self._actualizar_herramientas()
                else:
                    self.mostrar_mensaje(res if isinstance(res, str) else "Error deshaciendo", 5555)
            except Exception as ex:
                self.mostrar_mensaje(f"Error: {ex}", 5555)

        self._hilo_herramientas("Revirtiendo agrupación...", trabajo)

    def _deshacer_numerar_nits(self, e=None):
        if not self._requiere_concepto():
            return

        def trabajo():
            try:
                res = self._mutar_hoja_uc.deshacer_numerar_nits(self._concepto_payload())
                if isinstance(res, str) and res.startswith("Se devolvieron"):
                    self.mostrar_mensaje(res, 3000)
                    self.cargar_datos()
                    self._actualizar_herramientas()
                else:
                    self.mostrar_mensaje(res if isinstance(res, str) else "Error deshaciendo", 5555)
            except Exception as ex:
                self.mostrar_mensaje(f"Error: {ex}", 5555)

        self._hilo_herramientas("Revirtiendo numeración...", trabajo)

    def _deshacer_unificar(self, e=None):
        """Revertir todas las unificaciones registradas para el concepto actual."""
        if not self._requiere_concepto():
            return

        def trabajo():
            try:
                res = self._mutar_hoja_uc.deshacer_unificar(self._concepto_payload())
                if isinstance(res, str) and res.startswith("Se devolvieron"):
                    self.mostrar_mensaje(res, 3000)
                    self._desactivar_unificar()
                    self.cargar_datos()
                    self._actualizar_herramientas()
                else:
                    self.mostrar_mensaje(res if isinstance(res, str) else "Error deshaciendo unificación", 5555)
            except Exception as ex:
                self.mostrar_mensaje(f"Error deshaciendo unificación: {ex}", 5555)

        self._hilo_herramientas("Revirtiendo unificación...", trabajo)

    def _confirmar_numerar_nits(self, e=None):
        self._cerrar_snackbar_attr("_snackbar_numerar")

        def trabajo():
            try:
                res = self._mutar_hoja_uc.numerar_nits_extranjeros(
                    self._concepto_payload()
                )
                if isinstance(res, str) and res.startswith("Se numeraron"):
                    self.mostrar_mensaje(res, 3000)
                    self.cargar_datos()
                    self._actualizar_herramientas()
                else:
                    self.mostrar_mensaje(res if isinstance(res, str) else "Error numerando nits extranjeros", 5555)
            except Exception as ex:
                self.mostrar_mensaje(f"Error numerando nits extranjeros: {ex}", 5555)

        self._hilo_herramientas("Numerando NITs extranjeros...", trabajo)