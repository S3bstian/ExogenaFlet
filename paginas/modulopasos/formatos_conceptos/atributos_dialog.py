import flet as ft
from core import session
from paginas.modulopasos.formatos_conceptos.cuentas import CuentasDialog
from ui.dropdowns import DropdownCompact
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from ui.colors import PINK_200, GREY_700
from ui.snackbars import actualizar_mensaje_en_control, mostrar_mensaje_overlay
from utils.ui_sync import ejecutar_en_ui, loader_row_fin, loader_row_trabajo


_GLOBAL_GRUPO_VALIDO = frozenset({"T", "C", "B", "A"})


class AtributosDialog:
    def __init__(self, page, formatos_dialog, container):
        self.page = page
        self.formatos_dialog = formatos_dialog
        self._formatos_uc = formatos_dialog.formatos_uc
        self._datos_uc = container.datos_especificos_uc
        self._auth_uc = container.auth_uc
        self.cuentas = CuentasDialog(self.page, self, container=container)

        self._config_cache = None
        self._last_opciones_args = None
        self._tglobal_catalogo = "T"

        self.mensaje = ft.Text("", size=14, italic=True, visible=False)
        self.tipo_acumulado = None
        self.tipo_cuenta = None
        self.cuentas_container = None
        self.opciones_dialog = None
        self.cuentas_seleccionadas = []
        self.concepto = None
        self._btn_buscar_cuentas = None

    @staticmethod
    def _clase_atributo_numerica(atributo: dict) -> int | None:
        raw = atributo.get("Clase", atributo.get("clase"))
        try:
            return int(raw) if raw is not None and str(raw).strip() != "" else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _normalizar_tglobal(tglobal) -> str:
        t = (tglobal or "").strip().upper()
        return t if t in _GLOBAL_GRUPO_VALIDO else "T"

    def _opciones_tipo_acumulado(self, todos_acumulados, tglobal: str) -> list[ft.DropdownOption]:
        opciones: list[ft.DropdownOption] = []
        for opt in todos_acumulados:
            tipo_id = opt[0]
            global_opt = str(opt[4]).strip().upper() if len(opt) > 4 and opt[4] else ""
            if global_opt not in _GLOBAL_GRUPO_VALIDO or global_opt != tglobal:
                continue
            nombre_visible = opt[1] if len(opt) > 1 else str(tipo_id)
            descripcion_tooltip = opt[2] if len(opt) > 2 else ""
            opciones.append(
                ft.DropdownOption(
                    key=str(tipo_id),
                    text=nombre_visible,
                    content=ft.Text(
                        nombre_visible,
                        tooltip=ft.Tooltip(message=descripcion_tooltip or ""),
                    ),
                )
            )
        return opciones

    @staticmethod
    def _ajustar_valor_acumulado_por_defecto(
        tipo_acumulado: str, opciones_filtradas: list[ft.DropdownOption]
    ) -> str:
        if tipo_acumulado == "0" and opciones_filtradas:
            return str(getattr(opciones_filtradas[0], "key", opciones_filtradas[0].text))
        return tipo_acumulado

    def _persistir_cache_actual(self) -> None:
        """Sincroniza `_config_cache` con controles y cuentas en memoria."""
        self._config_cache = (
            self.tipo_acumulado.value,
            self.tipo_cuenta.value,
            [dict(cuenta) for cuenta in self.cuentas_seleccionadas],
        )

    def _abrir_catalogo_cuentas(self, e):
        if self.tipo_cuenta.value == "0":
            actualizar_mensaje_en_control("Debe seleccionar un tipo de cuenta antes de continuar", self.mensaje)
            return

        self._persistir_cache_actual()
        self.mensaje.visible = False
        if self._btn_buscar_cuentas:
            self._btn_buscar_cuentas.disabled = True
        self.page.update()
        loop = self.page.session.connection.loop

        def _abrir():
            self.page.pop_dialog()
            self.cuentas.open_cuentas(int(self.tipo_cuenta.value), self.concepto, self._tglobal_catalogo)

        loop.call_later(0.05, _abrir)

    # ----------------- configuración por atributo -----------------
    def open_opciones_dialog(self, formato, atributo, concepto, tglobal):
        self.concepto = concepto
        self._tglobal_catalogo = self._normalizar_tglobal(tglobal)

        if self._clase_atributo_numerica(atributo) == 2:
            return self._open_dialog_datos_especificos(atributo)

        self._last_opciones_args = [formato, atributo]
        self.mensaje.visible = False
        self.mensaje.value = ""

        atributo_id = atributo.get("Id")

        _ldr = getattr(self.formatos_dialog, "loader_estructura_inline", None)
        _slot = getattr(self.formatos_dialog, "_loader_estructura_slot", None)
        if _slot is not None:
            _slot.visible = True
        if _ldr is not None:
            loader_row_trabajo(self.page, _ldr, None, "Cargando configuración...")

        def _worker():
            try:
                if not self._config_cache:
                    configatributo = self._formatos_uc.obtener_configuracion_atributo(atributo_id)
                    tipo_acumulado = str(configatributo[0] or 0)
                    tipo_cuenta = str(configatributo[1] or 0)
                    cuentas_a_mostrar = [dict(cuenta) for cuenta in configatributo[2]]
                    self._config_cache = (tipo_acumulado, tipo_cuenta, cuentas_a_mostrar)
                todos_acumulados = self._formatos_uc.obtener_forma_acumulado()
            except Exception as ex:
                def _err():
                    if _ldr is not None:
                        loader_row_fin(self.page, _ldr)
                    if _slot is not None:
                        _slot.visible = False
                    mostrar_mensaje_overlay(self.page, f"Error cargando configuración: {ex}", 5000)

                ejecutar_en_ui(self.page, _err)
                return

            def _ui():
                if _ldr is not None:
                    loader_row_fin(self.page, _ldr)
                if _slot is not None:
                    _slot.visible = False
                self._montar_opciones_dialog_ui(atributo, todos_acumulados)

            ejecutar_en_ui(self.page, _ui)

        self.page.run_thread(_worker)

    def _montar_opciones_dialog_ui(self, atributo, todos_acumulados):
        tipo_acumulado, tipo_cuenta, cuentas_a_mostrar = self._config_cache
        tglobal = self._tglobal_catalogo

        opciones_filtradas = self._opciones_tipo_acumulado(todos_acumulados, tglobal)
        tipo_acumulado = self._ajustar_valor_acumulado_por_defecto(tipo_acumulado, opciones_filtradas)

        self.tipo_acumulado = DropdownCompact(
            options=opciones_filtradas,
            width=250,
            value=tipo_acumulado,
            on_select=self.actualizar_visibilidad,
        )
        self.tipo_cuenta = DropdownCompact(
            options=[
                ft.DropdownOption(key="1", text="Tributario"),
                ft.DropdownOption(key="2", text="Contable"),
            ],
            width=250,
            value=tipo_cuenta,
        )

        self.cuentas_seleccionadas = [dict(cuenta) for cuenta in cuentas_a_mostrar]
        self.cuentas_container = ft.Column(spacing=-11)

        self._btn_buscar_cuentas = ft.IconButton(
            icon=ft.Icons.SEARCH,
            style=BOTON_SECUNDARIO_SIN,
            tooltip="Buscar cuentas",
            on_click=self._abrir_catalogo_cuentas,
        )

        self.fila_tipo_cuenta = ft.Row(
            [
                ft.Text("Tipo de contabilidad:", width=150),
                self.tipo_cuenta,
                self._btn_buscar_cuentas,
            ],
            visible=False,
            spacing=10,
        )

        self.fila_cuentas_titulo = ft.Row(
            [
                ft.Text("Cuentas seleccionadas:", weight="bold"),
                ft.Text("Valor absoluto", weight="bold", size=12, expand=True, text_align="end"),
                ft.Text("Quitar", weight="bold", size=12, expand=False, text_align="end"),
            ],
        )

        contenido = ft.Column(
            [
                ft.Row(
                    [ft.Text("Tipo de Acumulado:", width=150), self.tipo_acumulado],
                    spacing=10,
                ),
                self.fila_tipo_cuenta,
                self.fila_cuentas_titulo,
                self.cuentas_container,
            ],
            spacing=12,
            scroll=ft.ScrollMode.AUTO,
        )

        self.opciones_dialog = ft.AlertDialog(
            title=ft.Text(f"Configuración del valor: {atributo.get('Nombre','')}"),
            content=ft.Container(
                content=contenido,
            ),
            bgcolor=ft.Colors.WHITE,
            modal=True,
            elevation=10,
            shape=ft.RoundedRectangleBorder(radius=10),
            actions=[
                self.mensaje,
                ft.TextButton(
                    content="Cancelar",
                    on_click=lambda e: self.return_dialog(self.opciones_dialog, None),
                    style=BOTON_SECUNDARIO_SIN,
                ),
                ft.Button(
                    content="Guardar",
                    on_click=lambda e: self.guardar_configuracion(atributo),
                    style=BOTON_PRINCIPAL,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.opciones_dialog)
        self.actualizar_visibilidad()
        self.mostrar_cuentas_seleccionadas()

    def _open_dialog_datos_especificos(self, atributo: dict):
        """
        Abre el diálogo de configuración para atributos CLASE=2.
        Permite agregar y eliminar opciones en DATOSESPECIFICOS.
        """
        self._config_cache = None
        self.cuentas_seleccionadas = []

        nombre_attr = (atributo.get("Nombre") or "").strip()
        desc_attr = (atributo.get("Descripcion") or "").strip()
        tabla_key = nombre_attr or desc_attr
        opciones_tabla = self._datos_uc.obtener_opciones_datos_especificos(tabla_key)
        # Algunos catálogos guardan TABLA con la descripción del atributo.
        if not opciones_tabla and desc_attr and desc_attr != tabla_key:
            tabla_key = desc_attr
            opciones_tabla = self._datos_uc.obtener_opciones_datos_especificos(tabla_key)
        # Subtipo se define por metadato en DATOSESPECIFICOS.TIPO = 2 (no por nombre del atributo).
        es_subtipo = any(int((opt.get("tipo") or 0)) == 2 for opt in opciones_tabla)
        padres_map = {}
        if es_subtipo:
            padres = self._datos_uc.obtener_padres_subtipo(None)
            padres_map = {str(padre.get("codigo")): padre for padre in padres}

        opciones = [] if es_subtipo else opciones_tabla

        self.mensaje.visible = False
        self.mensaje.value = ""

        input_desc = ft.TextField(
            label="Descripción",
            hint_text="Texto de la opción a agregar",
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
        )
        selector_tabla = DropdownCompact(
            label="Padre",
            options=[
                ft.DropdownOption(
                    key=k,
                    text=f"{v.get('codigo')} - {v.get('descripcion') or v.get('codigo')}",
                )
                for k, v in padres_map.items()
            ],
            value=None,
            width=350,
            on_select=lambda e: _refresh(),
        )
        selector_tabla_wrap = ft.Container(content=selector_tabla, visible=es_subtipo)

        lista_container = ft.Column(spacing=8, tight=True, controls=[], scroll=ft.ScrollMode.AUTO)
        lista_scroll = ft.Container(content=lista_container, height=180)

        def render_lista():
            lista_container.controls = []
            if not opciones:
                lista_container.controls.append(
                    ft.Text("No hay opciones registradas.", italic=True, size=12, color=GREY_700)
                )
                return
            for opt in opciones:
                codigo = opt.get("codigo")
                descripcion = (opt.get("descripcion") or "").strip()
                tipo = opt.get("tipo") or 0

                eliminar_btn = ft.IconButton(
                    icon=ft.Icons.DELETE,
                    icon_color=ft.Colors.RED_300,
                    style=BOTON_SECUNDARIO_SIN,
                    tooltip="Eliminar (solo si TIPO<=0)",
                    disabled=not (int(tipo) <= 0),
                    on_click=lambda e, c=codigo: _on_delete(c),
                )

                lista_container.controls.append(
                    ft.Row(
                        [
                            ft.Text(f"{codigo}: {descripcion}" if descripcion else str(codigo), expand=True),
                            eliminar_btn,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        spacing=8,
                    )
                )

        def _refresh():
            nonlocal opciones, opciones_tabla
            if es_subtipo:
                if not selector_tabla.value:
                    opciones = []
                else:
                    padre_info = padres_map.get(selector_tabla.value or "", {})
                    hijos_codigos = padre_info.get("hijos") or []
                    opciones = self._datos_uc.obtener_opciones_datos_especificos_por_codigos(hijos_codigos)
            else:
                opciones_tabla = self._datos_uc.obtener_opciones_datos_especificos(tabla_key)
                opciones = opciones_tabla
            render_lista()
            if self.opciones_dialog:
                self.opciones_dialog.update()
            self.page.update()

        def _on_add(e=None):
            desc = (input_desc.value or "").strip()
            if not desc:
                actualizar_mensaje_en_control("Debe ingresar una descripción.", self.mensaje)
                return
            tabla_objetivo = tabla_key
            if not tabla_objetivo:
                actualizar_mensaje_en_control("Debe seleccionar un padre antes de agregar.", self.mensaje)
                return
            padre_codigo = int(selector_tabla.value) if es_subtipo and selector_tabla.value else None
            if es_subtipo and padre_codigo is None:
                actualizar_mensaje_en_control("Debe seleccionar un padre antes de agregar.", self.mensaje)
                return
            codigos_base = padres_map.get(selector_tabla.value or "", {}).get("hijos") or [] if es_subtipo else []

            nuevo_codigo = self._datos_uc.crear_dato_especifico(
                tabla_objetivo, desc, codigos_base=codigos_base
            )
            if nuevo_codigo is None:
                actualizar_mensaje_en_control(
                    "No fue posible agregar la opción. Revisa consola.",
                    self.mensaje,
                )
                return
            if es_subtipo and selector_tabla.value in padres_map:
                padres_map[selector_tabla.value]["hijos"] = [
                    *(padres_map[selector_tabla.value].get("hijos") or []),
                    nuevo_codigo,
                ]
                tabla_padre = (padres_map[selector_tabla.value].get("tabla") or "").strip()
                self._datos_uc.actualizar_hijos_padre_subtipo(
                    tabla_padre,
                    padre_codigo,
                    padres_map[selector_tabla.value]["hijos"],
                )

            input_desc.value = ""
            actualizar_mensaje_en_control("Opción agregada correctamente.", self.mensaje, ft.Colors.GREEN_300)
            _refresh()

        def _on_delete(codigo: int):
            tabla_objetivo = tabla_key
            if not tabla_objetivo:
                actualizar_mensaje_en_control("Debe seleccionar un padre antes de eliminar.", self.mensaje)
                return
            ok = self._datos_uc.eliminar_dato_especifico(tabla_objetivo, codigo)
            if not ok:
                actualizar_mensaje_en_control(
                    "No se eliminó: solo se puede eliminar si TIPO<=0.",
                    self.mensaje,
                )
                return
            if es_subtipo and selector_tabla.value in padres_map:
                hijos_actuales = padres_map[selector_tabla.value].get("hijos") or []
                padres_map[selector_tabla.value]["hijos"] = [
                    hijo for hijo in hijos_actuales if int(hijo) != int(codigo)
                ]
                padre_codigo = int(selector_tabla.value)
                tabla_padre = (padres_map[selector_tabla.value].get("tabla") or "").strip()
                self._datos_uc.actualizar_hijos_padre_subtipo(
                    tabla_padre,
                    padre_codigo,
                    padres_map[selector_tabla.value]["hijos"],
                )
            actualizar_mensaje_en_control("Opción eliminada correctamente.", self.mensaje, ft.Colors.GREEN_300)
            _refresh()

        render_lista()

        contenido = ft.Column(
            [
                ft.Text("Opciones registradas:", size=13, color=GREY_700),
                selector_tabla_wrap,
                lista_scroll,
                ft.Divider(height=12, color=PINK_200),
                ft.Text("Agregar nueva opción:", size=13, color=GREY_700),
                input_desc,
            ],
            spacing=8,
            tight=True,
        )

        self.opciones_dialog = ft.AlertDialog(
            title=ft.Text(f"Configurar atributo: {atributo.get('Nombre','')}"),
            content=ft.Container(content=contenido),
            bgcolor=ft.Colors.WHITE,
            modal=True,
            elevation=10,
            shape=ft.RoundedRectangleBorder(radius=10),
            actions=[
                self.mensaje,
                ft.TextButton(
                    content="Cancelar",
                    on_click=lambda e: self.return_dialog(self.opciones_dialog, None),
                    style=BOTON_SECUNDARIO_SIN,
                ),
                ft.Button(
                    content="Agregar",
                    on_click=_on_add,
                    style=BOTON_PRINCIPAL,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.opciones_dialog)
        self.page.update()

    # ----------------- VISIBILIDAD -----------------
    def actualizar_visibilidad(self, e=None):
        visibles = self.tipo_acumulado.value not in ['0', '21', '50', '51']
        for control in [
            self.tipo_cuenta,
            self.fila_tipo_cuenta,
            self.fila_cuentas_titulo,
            self.cuentas_container,
        ]:
            if control:
                control.visible = visibles
        self.opciones_dialog.update()

    # ----------------- CUENTAS -----------------
    def recibir_cuentas(self, cuentas):
        # La selección del catálogo reemplaza completamente la selección previa.
        self.cuentas_seleccionadas = [dict(cuenta) for cuenta in cuentas]
        self._persistir_cache_actual()
        self.mostrar_cuentas_seleccionadas()

    def mostrar_cuentas_seleccionadas(self):
        self.cuentas_container.controls.clear()
        if not self.cuentas_seleccionadas:
            self.tipo_cuenta.disabled = False
            self.cuentas_container.controls.append(
                ft.Text("No hay cuentas seleccionadas...", italic=True, size=12)
            )
        else:
            self.tipo_cuenta.disabled = True
            for cuenta in self.cuentas_seleccionadas:
                sw = ft.Switch(
                    value=(cuenta["valorabsoluto"] == "S"),
                    active_track_color=PINK_200,
                    on_change=lambda e, cuenta_actual=cuenta: self.toggle_valorabsoluto(
                        cuenta_actual, e.control.value
                    ),
                    scale=0.66,
                    
                )
                eliminar_btn = ft.IconButton(
                    icon=ft.Icons.CLOSE,
                    icon_color=ft.Colors.RED,
                    style=BOTON_SECUNDARIO_SIN,
                    tooltip="Quitar cuenta",
                    on_click=lambda e, cuenta_actual=cuenta: self.quitar_cuenta(cuenta_actual),
                )
                fila = ft.Row(
                    [ft.Text(f"{cuenta.get('nombre')} - {cuenta.get('codigo')}", expand=True, size=14), sw, eliminar_btn],
                    alignment="spaceBetween",
                    spacing=8,
                )
                self.cuentas_container.controls.append(fila)
        if self.opciones_dialog:
            self.opciones_dialog.update()
        self.page.update()

    def quitar_cuenta(self, cuenta):
        self.cuentas_seleccionadas = [
            cuenta_actual
            for cuenta_actual in self.cuentas_seleccionadas
            if cuenta_actual != cuenta
        ]
        self._persistir_cache_actual()
        self.mostrar_cuentas_seleccionadas()

    def toggle_valorabsoluto(self, cuenta, estado):
        cuenta["valorabsoluto"] = "N" if not estado else "S"
        self._persistir_cache_actual()
        tabla = "Cuentas_trib" if str(self.tipo_cuenta.value) == "1" else "Cuentas_cont"
        self._auth_uc.actualizar_activo(
            tabla, "valorabsoluto", "id", cuenta["id"], estado, session.EMPRESA_ACTUAL["codigo"]
        )

    def guardar_configuracion(self, atributo):
        result = self._formatos_uc.guardar_configuracion_atributo(
            atributo,
            self.tipo_acumulado.value,
            self.tipo_cuenta.value,
            self.cuentas_seleccionadas,
        )
        if result:
            self._persistir_cache_actual()
            actualizar_mensaje_en_control("Configuración guardada correctamente", self.mensaje, ft.Colors.GREEN_400)
        else:
            actualizar_mensaje_en_control("Ocurrieron errores al guardar cuentas. Revisa la consola para más detalles.", self.mensaje)

    def return_dialog(self, dialog, formato):
        """Cierra el diálogo de opciones de atributo; no reabre la estructura (ya está debajo)."""
        self._config_cache = None
        self.page.pop_dialog()
