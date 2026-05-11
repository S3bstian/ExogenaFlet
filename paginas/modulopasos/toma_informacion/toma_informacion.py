import threading

import flet as ft
from domain.entities.resultado_acumulacion import ResultadoAcumulacion
from ui.colors import PINK_50, PINK_200, PINK_600, PINK_800, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
from ui.progress import crear_loader_row, crear_ring, SIZE_SMALL, SIZE_LARGE
from paginas.utils.paginacion import (
    DEBOUNCE_PREFIJOS_SEC,
    build_pagination_label,
    pagination_text_value,
    normalize_digit_key,
    tecla_es_avpag,
    tecla_es_repag,
    tecla_es_solo_modificador,
)
from paginas.utils.banner_prefijo_ctrl import sync_banner_prefijo
from paginas.utils.tooltips import TooltipId, tooltip
from ui.snackbars import crear_snackbar, mostrar_mensaje
from paginas.modulopasos.hoja_trabajo.hoja_tools_front import (
    cabecera_snackbar_herramienta,
    remover_snackbar_overlay,
)
from utils.ui_sync import (
    ejecutar_en_ui,
    loader_row_fin,
    loader_row_fin_y_error,
    loader_row_trabajo,
)


class TomaInformacionPage(ft.Column):
    def __init__(self, page: ft.Page, app=None, *, limit=15):
        super().__init__()
        self._page = page
        self._app = app  # InformacionExogenaApp: banner Alt+dígitos en appbar.
        self.expand = True

        self.limit, self.offset = limit, 0
        self.conceptos = []
        self.seleccion_global = []
        self.checkboxes = {}
        self._buscar_handle = None
        self.total_conceptos = 0
        # Buffers de teclado: Ctrl+prefijo (código concepto) y Alt+prefijo (número de página)
        self._prefix_buffer = ""
        self._prefix_buffer_timer = None
        self._page_prefix_buffer = ""
        self._page_prefix_timer = None
        self._snackbar_confirm_acumular = None

        self.loader = crear_loader_row("Cargando conceptos...", size=SIZE_SMALL)
        self.loader.visible = False

        self.mensaje = ft.Text(
            "", size=14, italic=True, visible=False, text_align=ft.TextAlign.CENTER
        )
        container = app.container
        self._obtener_conceptos_uc = container.obtener_conceptos_toma_uc
        self._acumular_conceptos_uc = container.acumular_conceptos_toma_uc

        self.main_container = None

    def _loader_trabajo(self, texto: str = "Cargando conceptos...") -> None:
        loader_row_trabajo(self._page, self.loader, self.mensaje, texto)

    def _loader_fin(self) -> None:
        loader_row_fin(self._page, self.loader)

    def _loader_fin_y_error(self, texto: str) -> None:
        loader_row_fin_y_error(self._page, self.loader, self.mensaje, texto)

    # -------------------- VISTA INICIAL --------------------
    def view(self):
        self.main_container = ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            padding=ft.padding.only(left=15, right=15),
            content=self._pantalla_inicial(),
        )
        return self.main_container

    def _pantalla_inicial(self):
        def card(icon, color, titulo, texto):
            return ft.Container(
                bgcolor=color,
                border_radius=12,
                padding=15,
                content=ft.Column(
                    [
                        ft.Row(
                            [ft.Icon(icon, color="black"), ft.Text(titulo, size=18, weight=ft.FontWeight.W_600)]
                        ),
                        ft.Text(texto, size=14),
                    ],
                    spacing=10,
                ),
            )

        boton = ft.ElevatedButton(
            "Continuar",
            on_click=lambda _: self._mostrar_lista(),
            style=BOTON_PRINCIPAL,
        )

        return ft.Column(
            [
                ft.Text("Toma de Información", size=24, weight=ft.FontWeight.BOLD),
                card(
                    ft.Icons.INFO,
                    "#E3F2FD",
                    "Objetivo del proceso",
                    "Cargar en la hoja de trabajo los datos que provienen de los formatos (terceros, cuentas, etc.) "
                    "según los conceptos que elija y acumule.",
                ),
                card(
                    ft.Icons.WARNING_AMBER_ROUNDED,
                    "#FFF3E0",
                    "Advertencias importantes",
                    "Cada concepto que seleccione y acumule sustituye en la hoja todo el contenido existente "
                    "para ese concepto; el resto de conceptos en la hoja no se altera.",
                ),
                ft.Container(height=20),
                boton,
            ],
            expand=True,
            spacing=10,
        )

    # -------------------- LISTA --------------------
    def _mostrar_lista(self):
        """Construye la tabla paginada y carga conceptos (no altera la hoja de trabajo)."""
        self._page_prefix_buffer = ""
        self._banner_prefijos_sync()
        self._inicializar_componentes_lista()
        self.pagination_text_footer = build_pagination_label(1, 1)
        self.nav_row = self._crear_nav_row()
        tabla_container = self._crear_tabla_container()
        self.main_container.content = self._crear_layout_lista(tabla_container)

        self._load_conceptos()

    def _inicializar_componentes_lista(self) -> None:
        """Inicializa controles base de la pantalla de listado."""
        self.search_field = self._crear_search_field()
        self.data_table = self._crear_data_table()

    def _crear_search_field(self) -> ft.TextField:
        """Construye campo de búsqueda de conceptos para filtro incremental."""
        return ft.TextField(
            label="Buscar Concepto, Formato, Descripcion",
            hint_text="Ej: 5002 - 1001 - Honorarios",
            prefix_icon=ft.Icons.MANAGE_SEARCH_SHARP,
            border_radius=10,
            border_color=PINK_200,
            on_change=self._buscar,
            height=37,
            width=333,
        )

    def _crear_data_table(self) -> ft.DataTable:
        """Construye la tabla principal de conceptos para toma de información."""
        row_height = 35
        return ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Seleccionar", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Código Concepto", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Código Formato", weight=ft.FontWeight.BOLD)),
                ft.DataColumn(ft.Text("Descripción", weight=ft.FontWeight.BOLD)),
            ],
            rows=[],
            data_row_max_height=row_height,
            data_row_min_height=row_height,
            heading_row_height=20,
            heading_row_color=PINK_50,
            divider_thickness=0.5,
        )

    def _crear_nav_row(self) -> ft.Row:
        """Construye navegación inferior y acciones de selección/acumulación."""
        return ft.Row(
            [
                ft.OutlinedButton(
                    "Seleccionar todos",
                    on_click=self._toggle_all,
                    style=BOTON_SECUNDARIO,
                    tooltip=tooltip(TooltipId.TOMA_SELECCIONAR_TODOS),
                ),
                ft.ElevatedButton(
                    "Anterior",
                    on_click=lambda e: self._paginar(-1),
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_SHARP,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    tooltip=tooltip(TooltipId.PAGINA_BTN_ANTERIOR),
                ),
                self.pagination_text_footer,
                ft.ElevatedButton(
                    "Siguiente",
                    on_click=lambda e: self._paginar(1),
                    icon=ft.Icons.ARROW_FORWARD_IOS_SHARP,
                    icon_color=PINK_600,
                    style=BOTON_SECUNDARIO,
                    tooltip=tooltip(TooltipId.PAGINA_BTN_SIGUIENTE),
                ),
                ft.ElevatedButton(
                    "Acumular seleccionados",
                    on_click=self._on_acumular_seleccion,
                    style=BOTON_PRINCIPAL,
                    tooltip=tooltip(TooltipId.TOMA_ACUMULAR),
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

    def _crear_tabla_container(self) -> ft.Container:
        """Construye contenedor expandible de tabla con scroll vertical."""
        # Solo la tabla hace scroll; paginación y botones quedan fijos abajo.
        self.data_table_scroll = ft.Column(
            controls=[self.data_table],
            expand=True,
            scroll=ft.ScrollMode.AUTO,
        )
        return ft.Container(
            expand=True,
            alignment=ft.Alignment(0, 0),
            content=ft.Column(
                [self.data_table_scroll, self.nav_row],
                expand=True,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )

    def _crear_layout_lista(self, tabla_container: ft.Container) -> ft.Column:
        """Arma layout de la vista de listado con header, loader, tabla y mensajes."""
        return ft.Column(
            [
                ft.Row(
                    [ft.Text("Toma de Información", size=20, weight=ft.FontWeight.BOLD), self.search_field],
                    alignment=ft.MainAxisAlignment.SPACE_AROUND,
                ),
                self.loader,
                tabla_container,
                ft.Row([self.mensaje]),
            ],
            spacing=8,
        )

    # -------------------- CARGA Y RENDER --------------------
    def _load_conceptos(self, filtro=None):
        self._loader_trabajo()

        try:
            self.conceptos, self.total_conceptos = self._obtener_conceptos_uc.ejecutar(
                offset=self.offset,
                limit=self.limit,
                filtro=filtro,
            )
            self._mostrar_mensaje_sin_resultados()
            self._renderizar_tabla()
        except Exception as e:
            self.mensaje.value, self.mensaje.visible = f"Error cargando conceptos: {e}", True
        finally:
            self._loader_fin()

    def _mostrar_mensaje_sin_resultados(self) -> None:
        """Muestra aviso estándar cuando la búsqueda no retorna conceptos."""
        if self.conceptos:
            return
        self.mensaje.value, self.mensaje.visible = "No se encontraron conceptos.", True

    def _renderizar_tabla(self):
        self.data_table.rows.clear()
        self.checkboxes.clear()

        for concepto in self.conceptos:
            cid = concepto.id
            checked = any(seleccionado.id == cid for seleccionado in self.seleccion_global)
            cb = ft.Checkbox(
                value=checked,
                active_color=PINK_200,
                data=concepto,
                on_change=lambda e, id=cid, data=concepto: self._toggle(id, data, e.control.value),
            )
            self.checkboxes[cid] = cb

            if concepto.activo == "S":
                self.data_table.rows.append(
                    ft.DataRow(
                        cells=[
                            ft.DataCell(cb),
                            ft.DataCell(ft.Text(concepto.codigo)),
                            ft.DataCell(ft.Text(concepto.formato)),
                            ft.DataCell(
                                ft.Text(
                                    concepto.descripcion,
                                    style=ft.TextStyle(height=1),
                                )
                            ),
                        ]
                    )
                )
                
        self._actualizar_controles_paginacion()
        self._page.update()

    def _filtro_actual_busqueda(self):
        """Retorna filtro normalizado desde el cuadro de búsqueda."""
        return (self.search_field.value or "").strip() or None

    def _total_paginas(self) -> int:
        """Calcula total de páginas con fallback seguro cuando no hay resultados o límite inválido."""
        if not self.limit:
            return 1
        return (
            (self.total_conceptos + self.limit - 1) // self.limit
            if self.total_conceptos > 0
            else 1
        )

    def _pagina_actual(self) -> int:
        """Número de página actual (1-based)."""
        return (self.offset // self.limit) + 1 if self.limit else 1

    def _actualizar_controles_paginacion(self) -> None:
        """Sincroniza botones anterior/siguiente y texto de paginación del footer."""
        self.nav_row.controls[1].visible = not self.offset <= 0
        total_paginas = self._total_paginas()
        pagina = self._pagina_actual()
        self.nav_row.controls[3].visible = pagina < total_paginas
        total = self.total_conceptos if self.total_conceptos > 0 else None
        self.pagination_text_footer.value = pagination_text_value(
            pagina, total_paginas, total
        )

    def _ir_a_pagina(self, pagina: int):
        """Salta a la página indicada (1-based) respetando los límites."""
        if pagina < 1 or not self.limit:
            return
        total = self.total_conceptos or 0
        if total > 0:
            total_paginas = max(1, (total + self.limit - 1) // self.limit)
            if pagina > total_paginas:
                pagina = total_paginas
        self.offset = (pagina - 1) * self.limit
        self._load_conceptos(filtro=self._filtro_actual_busqueda())

    # -------------------- EVENTOS --------------------
    def _toggle(self, cid, data, value):
        if value:
            self.seleccion_global.append(data)
        else:
            self.seleccion_global = [
                seleccionado for seleccionado in self.seleccion_global if seleccionado.id != cid
            ]

    def _desmarcar_todos_visibles(self) -> None:
        """Quita selección global y desmarca checkboxes de la página visible."""
        self.seleccion_global = []
        for checkbox in self.checkboxes.values():
            checkbox.value = False
            checkbox.update()

    def _aplicar_seleccion_global(self, conceptos: list) -> None:
        """Aplica la lista seleccionada y refleja checks en la página actual."""
        self.seleccion_global = conceptos
        for checkbox in self.checkboxes.values():
            checkbox.value = True
            checkbox.update()

    def _cargar_todos_conceptos_filtrados(self, filtro):
        """Carga lote amplio de conceptos para selección masiva."""
        return list(
            self._obtener_conceptos_uc.ejecutar(
                offset=0,
                limit=5000,
                filtro=filtro,
            )[0]
        )

    def _seleccionar_todos_en_hilo(self, filtro) -> None:
        """Ejecuta la selección masiva en background y sincroniza UI al finalizar."""
        try:
            todos = self._cargar_todos_conceptos_filtrados(filtro)
        except Exception as ex:
            ejecutar_en_ui(
                self._page,
                lambda ex=ex: self._loader_fin_y_error(
                    f"Error al seleccionar todos: {ex}"
                ),
            )
            return

        def _ok():
            self._aplicar_seleccion_global(todos)
            self._loader_fin()
            if len(todos) == 5000:
                self.mostrar_mensaje("Se seleccionaron 5000 conceptos (límite).", 2500)

        ejecutar_en_ui(self._page, _ok)

    def _toggle_all(self, _event):
        new_val = not all(checkbox.value for checkbox in self.checkboxes.values())
        filtro = (self.search_field.value or "").strip() or None
        if not new_val:
            self._quitar_seleccion_masiva()
            return
        self._iniciar_seleccion_masiva(filtro)

    def _quitar_seleccion_masiva(self) -> None:
        """Desmarca selección global visible con feedback de loader."""
        self._loader_trabajo("Quitando selección...")
        self._desmarcar_todos_visibles()
        self._loader_fin()

    def _iniciar_seleccion_masiva(self, filtro) -> None:
        """Dispara selección masiva en hilo de fondo con estado ocupado."""
        self._loader_trabajo("Seleccionando todos los conceptos...")
        self._page.run_thread(lambda: self._seleccionar_todos_en_hilo(filtro))

    def _buscar(self, e):
        ft.context.disable_auto_update()
        if self._buscar_handle is not None:
            self._buscar_handle.cancel()
        texto = (e.control.value or "").strip() or None
        self.offset = 0
        loop = self._page.session.connection.loop
        self._buscar_handle = loop.call_later(0.35, lambda: self._load_conceptos(filtro=texto))

    def _on_keyboard_page(self, e: ft.KeyboardEvent):
        """Teclado global para la lista de conceptos (solo cuando está visible)."""
        if getattr(self._page, "route", "") != "/home/toma_informacion":
            return
        if not hasattr(self, "data_table"):
            return
        key = getattr(e, "key", "")
        ctrl = getattr(e, "ctrl", False)
        alt = getattr(e, "alt", False)
        digit = normalize_digit_key(key)

        # Alt + dígitos: ir directamente a número de página.
        if alt and digit is not None:
            self._page_prefix_buffer = (self._page_prefix_buffer or "") + digit
            self._banner_prefijos_sync()
            if self._page_prefix_timer:
                self._page_prefix_timer.cancel()
            loop = self._page.session.connection.loop
            prefijo_pagina = self._page_prefix_buffer

            def _on_page_timeout(prefix=prefijo_pagina):
                self._page_prefix_buffer = ""
                self._banner_prefijos_sync()
                try:
                    num = int(prefix)
                except ValueError:
                    return
                self._ir_a_pagina(num)

            self._page_prefix_timer = loop.call_later(DEBOUNCE_PREFIJOS_SEC, _on_page_timeout)
            return

        if tecla_es_solo_modificador(key):
            return

        # (En esta pantalla no usamos Ctrl+prefijo; solo Alt+prefijo y Re Pág / Av Pág)

        # Limpiar buffer de página en otras teclas.
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

    def _paginar(self, direction):
        nuevo_offset = self.offset + (direction * self.limit)
        if nuevo_offset < 0:
            return
        self.offset = nuevo_offset
        self._load_conceptos(filtro=self._filtro_actual_busqueda())

    def _banner_prefijos_sync(self) -> None:
        """Sincroniza el aviso visual del prefijo ALT usado para salto de página."""
        sync_banner_prefijo(
            self._page,
            app=getattr(self, "_app", None),
            prefix_alt=self._page_prefix_buffer,
        )
    
    def _cerrar_snackbar_confirm_acum(self) -> None:
        remover_snackbar_overlay(self._page, self._snackbar_confirm_acumular)
        self._snackbar_confirm_acumular = None
        self._page.update()

    def _mostrar_dialogo_resultado_acumulacion(
        self, resultado: ResultadoAcumulacion
    ) -> None:
        """Diálogo modal tipo informe: compacto, ordenado y con scroll solo si el contenido lo requiere."""
        if resultado.cancelado:
            titulo, encabezado = "Acumulación cancelada", "Operación detenida; no se confirmaron cambios."
        elif resultado.mensaje_error_critico:
            titulo, encabezado = "Error en acumulación", resultado.mensaje_error_critico
        else:
            titulo = "Resultado de acumulación"
            encabezado = (
                f"Conceptos: {resultado.total_conceptos_solicitados} · Registros: {resultado.total_registros}"
                + ("" if resultado.exito else "  (con errores de inserción)")
            )

        adv_items = [
            f"{advertencia.concepto_codigo} (formato {advertencia.formato}): {', '.join(advertencia.cuentas)}"
            for advertencia in resultado.advertencias_sin_datos
        ]
        # Secciones que se renderizan solo si tienen items.
        secciones: list[tuple[str, list[str]]] = [
            ("Conceptos sin elemento de acumulación", resultado.conceptos_omitidos_sin_elemento),
            ("Conceptos sin cuentas configuradas", resultado.conceptos_sin_cuentas_en_config),
            ("Cuentas sin información para acumular", adv_items),
            ("Conceptos procesados sin filas nuevas en la hoja", resultado.conceptos_sin_filas_en_hoja),
            ("Errores de inserción en hoja de trabajo", resultado.errores_insercion),
        ]

        secciones_visibles = [(t, i) for t, i in secciones if i]
        total_lineas = 2 + sum(1 + len(items) for _, items in secciones_visibles)
        alto_dialogo = min(430, max(145, 34 + total_lineas * 24))

        def linea(texto: str, *, bold: bool = False, color=None, size: int = 13) -> ft.Text:
            """Texto base del informe; mantiene una sola estética para títulos e ítems."""
            return ft.Text(
                texto,
                size=size,
                color=color,
                weight=ft.FontWeight.BOLD if bold else None,
                selectable=not bold,
            )

        bloques: list[ft.Control] = [
            ft.Container(
                padding=ft.padding.all(10),
                bgcolor=PINK_50,
                border_radius=8,
                content=ft.Column(
                    [
                        linea("Resumen", bold=True, size=14, color=PINK_800),
                        linea(
                            encabezado,
                            bold=True,
                            color=PINK_600
                            if (resultado.mensaje_error_critico or not resultado.exito)
                            else PINK_800,
                        ),
                    ],
                    spacing=3,
                    tight=True,
                ),
            )
        ]
        for titulo_sec, items in secciones_visibles:
            if not items:
                continue
            bloques.append(
                ft.Container(
                    padding=ft.padding.only(top=4),
                    content=ft.Column(
                        [linea(titulo_sec, bold=True, color=PINK_800)]
                        + [linea(f"  · {item}") for item in items],
                        spacing=3,
                        tight=True,
                    ),
                )
            )

        dlg = ft.AlertDialog(
            title=ft.Text(titulo),
            content=ft.Container(
                width=520,
                height=alto_dialogo,
                padding=ft.padding.symmetric(horizontal=8, vertical=4),
                content=ft.Column(bloques, spacing=8, tight=True, scroll=ft.ScrollMode.AUTO),
            ),
            bgcolor=WHITE,
            modal=True,
            actions=[
                ft.TextButton(
                    "Aceptar",
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=lambda _e: self._page.pop_dialog(),
                )
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(dlg)
        self._page.update()

    def _on_acumular_seleccion(self, _e):
        if not self.seleccion_global:
            self.mostrar_mensaje("No hay conceptos seleccionados", 3500)
            return
        mensaje = (
            "En la hoja se borrarán solo los conceptos que va a acumular y se volverán a generar sus filas. "
            "El resto de conceptos cargados en la hoja no cambia. ¿Desea continuar?"
        )
        self._mostrar_confirmacion_acumulacion(mensaje)

    def _aceptar_acumulacion(self, _e=None) -> None:
        """Acción de confirmación para iniciar acumulación masiva."""
        self._cerrar_snackbar_confirm_acum()
        self._ejecutar_acumulacion_con_progreso()

    def _botones_confirmacion_acumulacion(self) -> list[ft.Control]:
        """Construye botones del snackbar de confirmación de acumulación."""
        return [
            ft.TextButton(
                "Cancelar",
                icon=ft.Icons.CLOSE,
                style=BOTON_SECUNDARIO_SIN,
                on_click=lambda _e: self._cerrar_snackbar_confirm_acum(),
            ),
            ft.Button(
                "Acumular",
                icon=ft.Icons.ADD_CHART_OUTLINED,
                style=BOTON_PRINCIPAL,
                on_click=self._aceptar_acumulacion,
            ),
        ]

    def _mostrar_confirmacion_acumulacion(self, mensaje: str) -> None:
        """Muestra snackbar persistente para confirmar acumulación de seleccionados."""
        texto = ft.Text(mensaje, color=PINK_800, size=14, expand=True)
        cabecera = cabecera_snackbar_herramienta(
            ft.Icons.INFO_OUTLINE,
            texto,
            self._botones_confirmacion_acumulacion(),
        )
        snack = crear_snackbar(
            ft.Column(controls=[cabecera], spacing=8, tight=True),
            duration=999999999,
            show_close=False,
        )
        self._snackbar_confirm_acumular = snack
        self._page.overlay.append(snack)
        snack.open = True
        self._page.update()

    def _ejecutar_acumulacion_con_progreso(self) -> None:
        """Bottom sheet con progreso: vacía por concepto en hoja y acumula en hilo."""
        loader_bottom = crear_ring(indeterminado=False, size=SIZE_LARGE)
        bottom_text = ft.Text("Preparando...", size=16)
        cancel_ev = threading.Event()
        btn_cancelar = self._crear_boton_cancelar_acumulacion(cancel_ev, bottom_text)
        bottomsheet = self._crear_bottomsheet_progreso(loader_bottom, bottom_text, btn_cancelar)
        self._page.show_dialog(bottomsheet)
        self._page.update()
        self._ejecutar_hilo_acumulacion(loader_bottom, bottom_text, cancel_ev)

    def _crear_boton_cancelar_acumulacion(self, cancel_ev: threading.Event, bottom_text: ft.Text) -> ft.TextButton:
        """Construye botón cancelar con actualización de estado visual en progreso."""
        def _on_cancel(_):
            cancel_ev.set()
            btn_cancelar.disabled = True
            bottom_text.value = "Cancelando..."
            bottom_text.update()
            btn_cancelar.update()

        btn_cancelar = ft.TextButton(
            "Cancelar",
            on_click=_on_cancel,
            style=BOTON_SECUNDARIO_SIN,
        )
        return btn_cancelar

    def _crear_bottomsheet_progreso(
        self,
        loader_bottom: ft.Control,
        bottom_text: ft.Text,
        btn_cancelar: ft.TextButton,
    ) -> ft.BottomSheet:
        """Construye bottom sheet modal con progreso y acción de cancelación."""
        return ft.BottomSheet(
            ft.Container(
                padding=20,
                content=ft.Column(
                    [
                        bottom_text,
                        loader_bottom,
                        ft.Row(
                            [btn_cancelar],
                            alignment=ft.MainAxisAlignment.CENTER,
                            tight=True,
                        ),
                    ],
                    spacing=8,
                    tight=True,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
            ),
            open=True,
            dismissible=False,
            use_safe_area=True,
            size_constraints=ft.BoxConstraints(max_height=260, max_width=420),
        )

    def _ejecutar_hilo_acumulacion(self, loader_bottom, bottom_text, cancel_ev) -> None:
        """Ejecuta proceso de acumulación en hilo de fondo."""
        self._page.run_thread(
            lambda: self._acumular_en_hilo(
                loader_bottom=loader_bottom,
                bottom_text=bottom_text,
                cancel_ev=cancel_ev,
            )
        )

    def _cerrar_bottomsheet_y_mostrar_resultado(self, resultado: ResultadoAcumulacion) -> None:
        """Cierra progreso y presenta diálogo final de resultado."""
        self._page.pop_dialog()
        self._page.update()
        self._mostrar_dialogo_resultado_acumulacion(resultado)

    def _resultado_error_acumulacion(self, ex: Exception) -> ResultadoAcumulacion:
        """Construye resultado uniforme cuando falla la ejecución de acumulación."""
        return ResultadoAcumulacion(
            exito=False,
            mensaje_error_critico=str(ex),
            total_conceptos_solicitados=len(self.seleccion_global),
        )

    def _acumular_en_hilo(self, *, loader_bottom, bottom_text, cancel_ev) -> None:
        """Ejecuta acumulación en background y normaliza salida de éxito/error."""
        try:
            # Preparación (vacía por concepto) y acumulación van en una sola transacción en BD.
            resultado = self._acumular_conceptos_uc.ejecutar(
                conceptos=self.seleccion_global,
                loader=loader_bottom,
                page=self._page,
                bottom_text=bottom_text,
                cancel_event=cancel_ev,
            )
        except Exception as ex:
            resultado = self._resultado_error_acumulacion(ex)
        self._cerrar_bottomsheet_y_mostrar_resultado(resultado)
    
    def mostrar_mensaje(self, texto, duration):
        mostrar_mensaje(self._page, texto, duration)

