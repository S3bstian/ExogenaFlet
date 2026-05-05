"""
Vista Flet del flujo Generar XML: elegir formato, validar contra XSD y generar archivo.

Por qué existe: concentra la UI del paso de exportación DIAN sin mezclar SQL ni reglas
de negocio (van en casos de uso vía `app.container`).

Qué hace: diálogo de formatos, formulario de cabecera, validación paginada, PDF de
resumen y paso de generación; puede abrir `TrabajoDialog` para corregir hoja in situ.

Cómo se usa: `GenerarXmlPage(page, app)` desde el registro de rutas; `on_enter` debe
llamar a `_cargar_formatos_y_abrir_dialogo()` cuando corresponda (ver `routing`).
"""

import flet as ft
from core.settings import PERIODO, FECHA_INICIAL, FECHA_FINAL
from ui.colors import PINK_200, GREY_700, WHITE
from ui.snackbars import mostrar_mensaje_overlay
from ui.buttons import BOTON_LISTA, BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
from ui.dropdowns import DropdownCompact
from ui.progress import crear_loader_row
from utils.ui_sync import loader_row_fin, loader_row_trabajo
from utils.dates import fechaHelisa
from utils.pdf_validacion import construir_pdf_validacion
from utils.validators import aplicar_validacion_error_text, set_campo_error, validar_numero, validar_fecha, validar_hora, validar_campo_obligatorio
import os
from datetime import datetime
from paginas.modulopasos.hoja_trabajo.trabajo_dialog import TrabajoDialog
from paginas.modulopasos.generar_xml.trabajo_dialog_bridge import TrabajoDialogBridgeGenerarXml



class GenerarXmlPage(ft.Column):
    PAGE_SIZE_VALIDACION_CONCEPTO = 50
    COLUMNAS_REGISTROS_VALIDACION = 4
    def __init__(self, page, app):
        super().__init__()
        self._page = page
        self._app = app
        self._generar_xml_uc = app.container.generar_xml_uc
        self._consultar_hoja_uc = app.container.consultar_hoja_uc
        self.expand = True

        # Estado general
        self.formatos = []
        self.selected_formato = None
        self.selected_formato_nombre = ""
        self.step = 1  # 1: validar, 2: generar
        self.dialog = None
        self.dialog_shown = False

        # Controles reutilizables
        self.label_formato = ft.Text("Seleccione un formato para continuar", size=14, weight=ft.FontWeight.W_500)
        self.stepper_row = ft.Row(spacing=12, alignment="center")
        self.loader = crear_loader_row("Cargando...", size=15)
        self.loader.visible = False
        self.step_content_container = ft.Container(padding=10, expand=True)

        # Campos del formulario de modificación
        self.campos_modificar = {}
        
        # Estado de expansión de conceptos en validación
        self.conceptos_expandidos = set()
        self._pagina_concepto_validacion = {}
        self.boton_exportar_pdf_header = ft.ElevatedButton(
            "Exportar PDF",
            icon=ft.Icons.PICTURE_AS_PDF,
            style=BOTON_SECUNDARIO,
            visible=False,
            on_click=lambda e: self._exportar_validacion_pdf(getattr(self, "_resultado_validacion", None)),
        )
        self._trabajo_dialog_bridge = TrabajoDialogBridgeGenerarXml(self, app)
        self._trabajo_dialog = TrabajoDialog(page, self._trabajo_dialog_bridge)

    def _forzar_revalidacion_post_correccion(self):
        """Después de guardar en diálogo, recalcula validación en la misma vista."""
        self._resultado_validacion = None
        self.conceptos_expandidos = set()
        self._pagina_concepto_validacion = {}
        self.step = 1
        self._refresh_body()
        self._page.update()

    def _buscar_registro_para_correccion(self, concepto_codigo: str, id_concepto: int, identidad: str):
        """Obtiene el registro de hoja exacto para abrir TrabajoDialog sin cambiar de ruta."""
        concepto_ref = {"codigo": str(concepto_codigo), "formato": str(self.selected_formato_nombre)}
        rows_bd, _has_more, _total = self._consultar_hoja_uc.obtener_filas(
            offset=0,
            limit=500,
            concepto=concepto_ref,
            filtro=identidad,
        )
        if not rows_bd:
            return None, None
        clave_prefijo = f"{id_concepto}|{identidad}"
        for key, row in rows_bd.items():
            if key == clave_prefijo or str(key).startswith(f"{clave_prefijo}|"):
                identidad_db = key.split("|", 1)[-1] if "|" in key else identidad
                return row, identidad_db
        return None, None

    def _ir_a_correccion_validacion(self, concepto_codigo: str, registro_data: dict):
        """Abre el diálogo de corrección sobre la vista actual (sin navegar)."""
        identidad = str(registro_data.get("identidad") or "").strip()
        id_concepto = registro_data.get("id_concepto")
        if not identidad or not id_concepto or not self.selected_formato_nombre:
            self._mostrar_mensaje("No fue posible preparar el atajo de corrección para este registro.", 4500)
            return
        loader_row_trabajo(self._page, self.loader, None, "Abriendo corrección...")
        concepto_ref = {"codigo": str(concepto_codigo), "formato": str(self.selected_formato_nombre)}

        def _worker_open():
            try:
                datos, identidad_db = self._buscar_registro_para_correccion(
                    str(concepto_codigo), int(id_concepto), identidad
                )
                if not datos or not identidad_db:
                    self._mostrar_mensaje(
                        "No se encontró el registro en Hoja de trabajo para abrir la corrección.",
                        5000,
                    )
                    return
                self._trabajo_dialog.abrir(
                    id_concepto=int(id_concepto),
                    identidad=identidad_db,
                    datos=datos,
                    concepto=concepto_ref,
                    modo="editar",
                )
            except Exception as ex:
                self._mostrar_mensaje(f"Error abriendo corrección: {ex}", 5000)
            finally:
                loader_row_fin(self._page, self.loader)

        self._page.run_thread(_worker_open)

    def view(self):
        self.formatos = []
        loader_row_trabajo(self._page, self.loader, None, "Cargando formatos...")

        contenedor = ft.Container(
            expand=True,
            alignment=ft.Alignment(0, -1),
            padding=20,
            content=ft.Column(
                [
                    ft.Row(
                        controls=[
                            ft.Text("Generar XML", size=22, weight=ft.FontWeight.BOLD),
                            ft.Container(content=self.label_formato, expand=True, alignment=ft.Alignment(0, 0)),
                            self.boton_exportar_pdf_header,
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    self.stepper_row,
                    self.loader,
                    self.step_content_container,
                ],
                expand=True,
                spacing=12,
            ),
        )

        self._refresh_body()
        return contenedor

    def _cargar_formatos_y_abrir_dialogo(self):
        """Llamar desde on_enter: carga formatos en thread y abre diálogo al terminar."""
        def _worker():
            try:
                self.formatos = self._generar_xml_uc.obtener_formatos()
                loader_row_fin(self._page, self.loader)
                self._abrir_dialogo_formato_si_aplica()
                self._refresh_body()
            except Exception as ex:
                loader_row_fin(self._page, self.loader)
                self._mostrar_mensaje(f"Error cargando formatos: {ex}", 5000)
            self._page.update()
        self._page.run_thread(_worker)

    def _abrir_dialogo_formato_si_aplica(self) -> None:
        """Evita mostrar múltiples veces el diálogo inicial de selección."""
        if self.dialog_shown:
            return
        self.dialog_shown = True
        self._open_dialog_formatos()

    # ---------- Diálogo de selección de formato ----------
    def _open_dialog_formatos(self):
        lista_botones = [
            ft.TextButton(
                content=f"{f[1]} - {f[2]}",
                style=BOTON_LISTA,
                on_click=lambda e, formato=f: self._seleccionar_formato(formato),
            )
            for f in self.formatos
        ]

        self.dialog = ft.AlertDialog(
            modal=True,
            bgcolor=WHITE,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            title=ft.Text("Seleccione el formato a generar", weight=ft.FontWeight.BOLD, size=16),
            content=ft.Container(
                width=500,
                height=320,
                content=ft.ListView(
                    expand=True,
                    spacing=8,
                    padding=10,
                    controls=[ft.Row([btn]) for btn in lista_botones],
                ),
            ),
            actions=[
                ft.TextButton(content="Cerrar", style=BOTON_SECUNDARIO_SIN, on_click=lambda e: self._page.pop_dialog())
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self._page.show_dialog(self.dialog)

    def _seleccionar_formato(self, formato):
        self._page.pop_dialog()
        loader_row_trabajo(self._page, self.loader, None, "Cargando formato...")

        def _worker():
            try:
                self._aplicar_formato_seleccionado(formato)
            finally:
                loader_row_fin(self._page, self.loader)

        self._page.run_thread(_worker)

    def _aplicar_formato_seleccionado(self, formato) -> None:
        """Carga metadatos XSD y reinicia el estado de validación para el formato elegido."""
        formato_codigo = formato[1]
        self.selected_formato = formato
        self.selected_formato_nombre = formato_codigo
        self._cache_xsd = self._cargar_cache_xsd(formato_codigo)
        self._reiniciar_estado_validacion_formato()
        self.label_formato.value = f"Formato seleccionado: {self.selected_formato_nombre}"
        self.step = 1
        self.campos_modificar = {}
        self._build_modificar_form()
        self._refresh_body()

    def _cargar_cache_xsd(self, formato_codigo: str) -> dict:
        """Obtiene estructura XSD necesaria para validar y construir XML."""
        return {
            "atributos": self._generar_xml_uc.parsear_xsd(formato_codigo),
            "orden": self._generar_xml_uc.obtener_orden_atributos_xsd(formato_codigo),
            "elemento_detalle": self._generar_xml_uc.obtener_elemento_detalle_xsd(formato_codigo),
        }

    def _reiniciar_estado_validacion_formato(self) -> None:
        """Resetea caches del flujo cuando cambia el formato seleccionado."""
        self._resultado_validacion = None
        self._cache_datos_hoja = None

    # ---------- Construcción de pasos ----------
    def _refresh_body(self):
        resultado_validacion = getattr(self, "_resultado_validacion", None)
        self.boton_exportar_pdf_header.visible = bool(
            self.selected_formato and self.step == 1 and resultado_validacion is not None
        )

        boton_izq, boton_der = self._obtener_botones_navegacion_step()
        self.stepper_row.controls = self._construir_controles_stepper(boton_izq, boton_der)
        self.stepper_row.alignment = "spaceBetween"
        self.step_content_container.content = self._construir_contenido_step_actual()

    def _obtener_botones_navegacion_step(self):
        """Define botones laterales del stepper según paso y formato seleccionado."""
        if not self.selected_formato:
            return None, None

        if self.step == 1:
            return (
                ft.TextButton(
                    content="Reelegir formato",
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=lambda _e: self._open_dialog_formatos(),
                ),
                ft.Button(
                    content="Continuar con Generar",
                    icon=ft.Icons.ARROW_FORWARD,
                    style=BOTON_PRINCIPAL,
                    on_click=lambda _e: self._ir_a_generar(),
                ),
            )

        if self.step == 2:
            return (
                ft.TextButton(
                    "Volver a Validar",
                    style=BOTON_SECUNDARIO_SIN,
                    on_click=lambda _e: self._ir_a_validar(),
                ),
                ft.ElevatedButton(
                    "Reelegir formato",
                    style=BOTON_PRINCIPAL,
                    icon=ft.Icons.LIST,
                    on_click=lambda _e: self._open_dialog_formatos(),
                ),
            )

        return None, None

    def _construir_controles_stepper(self, boton_izq, boton_der):
        """Arma la fila del stepper reutilizando chips y botones laterales."""
        controls = []
        if boton_izq:
            controls.append(boton_izq)
        controls.extend([self._chip_paso(1, "Validar"), self._chip_paso(2, "Generar")])
        if boton_der:
            controls.append(boton_der)
        return controls

    def _construir_contenido_step_actual(self):
        """Resuelve contenido central según formato seleccionado y paso activo."""
        if not self.selected_formato:
            return ft.Column(
                [
                    ft.Text("Debe seleccionar un formato para continuar.", size=14),
                    ft.TextButton(
                        content="Elegir formato",
                        on_click=lambda _e: self._open_dialog_formatos(),
                        style=BOTON_SECUNDARIO,
                    ),
                ],
                spacing=10,
            )
        if self.step == 1:
            return self._render_validar()
        return self._render_generar()

    def _chip_paso(self, numero, texto):
        activo = self.step == numero
        color_fondo = PINK_200 if activo else "#f0f0f0"
        color_texto = WHITE if activo else GREY_700
        return ft.Container(
            padding=ft.padding.symmetric(vertical=6, horizontal=12),
            bgcolor=color_fondo,
            border_radius=15,
            content=ft.Row(
                [
                    ft.CircleAvatar(bgcolor=WHITE if activo else GREY_700, content=ft.Text(str(numero), color=PINK_200 if activo else GREY_700, size=12), height=20, width=20),
                    ft.Text(texto, color=color_texto, weight=ft.FontWeight.W_600),
                ],
                spacing=5,
                alignment="center",
            ),
        )

    # ---------- Construcción del formulario de modificación ----------
    def _build_modificar_form(self):
        # valores por defecto: fecha/hora actuales y periodo de reporte
        ahora = datetime.now()
        hoy_str = ahora.strftime("%Y-%m-%d")
        hora_str = ahora.strftime("%H:%M:%S")
        periodo = PERIODO
        fecha_ini_str = f"{periodo}-01-01"
        fecha_fin_str = f"{periodo}-12-31"

        def tf(label, disabled=False, options=None, value=None):
            if options is not None:
                return DropdownCompact(
                    label=label,
                    value=value,
                    options=[ft.DropdownOption(key=v, text=v) for _, v in options.items()],
                    width=300,
                )
            return ft.TextField(
                label=label,
                value=value,
                disabled=disabled,
                border_color=PINK_200,
                label_style=ft.TextStyle(color=GREY_700),
                width=300,
                height=55,
            )

        self.campos_modificar = {
            "concepto": tf("Concepto", options={'01': "Insercion", '02': "Reemplazo"}, value="Insercion" if self.selected_formato[3] == "01" else "Reemplazo"),
            "version": tf("Version", disabled=True, value = self.selected_formato[4]),
            "numenvio": tf("Numero de envio", value=self.selected_formato[5]),
            "fechaenvio": tf("Fecha de envio", value=hoy_str ),# if self.selected_formato[6] == None else self.selected_formato[6][:9]
            "horaenvio": tf("Hora de envio", value=hora_str ),# if self.selected_formato[6] == None else self.selected_formato[6][10:]
            "fechainicial": tf("Fecha inicial", value=fecha_ini_str),
            "fechafinal": tf("Fecha fin", value=fecha_fin_str),
        }

    def _ir_a_validar(self):
        self.step = 1
        self._refresh_body()
        self._page.update()

    def _ir_a_generar(self):
        # Asegurar que el formulario esté construido; la validación se hace al clic en Generar XML
        if not self.campos_modificar:
            self._build_modificar_form()
        self.step = 2
        self._refresh_body()
        self._page.update()

    def _campos_modificar_completos(self):
        """
        Valida que todos los campos obligatorios estén completos.
        Usa error_text para mostrar errores específicos en cada campo.
        """
        # Limpiar errores previos (Flet 0.80: TextField usa .error)
        for campo in self.campos_modificar.values():
            set_campo_error(campo, None)
        
        errores = False

        # Validar campos obligatorios
        requeridos = {
            "concepto": "Concepto",
            "numenvio": "Número de envío",
            "fechaenvio": "Fecha de envío",
            "horaenvio": "Hora de envío",
            "fechainicial": "Fecha inicial",
            "fechafinal": "Fecha final"
        }

        errores |= self._validar_campos_obligatorios(requeridos)
        errores |= self._validar_formato_campos_modificar()
        errores |= self._validar_rango_fechas_modificar()

        self._page.update()
        return not errores

    def _validar_campos_obligatorios(self, requeridos: dict) -> bool:
        """Ejecuta validación de obligatoriedad para campos del formulario."""
        hay_errores = False
        for key, nombre_campo in requeridos.items():
            control = self.campos_modificar.get(key)
            if not control:
                continue
            valor = getattr(control, "value", None) or ""
            if not aplicar_validacion_error_text(control, valor, validar_campo_obligatorio, nombre_campo=nombre_campo):
                hay_errores = True
        return hay_errores

    def _validar_formato_campos_modificar(self) -> bool:
        """Valida formato de número, fechas y hora en campos diligenciados."""
        hay_errores = False
        validaciones = [
            ("numenvio", validar_numero, {"tipo": "int", "min_val": 1}),
            ("fechaenvio", validar_fecha, {}),
            ("horaenvio", validar_hora, {}),
            ("fechainicial", validar_fecha, {}),
            ("fechafinal", validar_fecha, {}),
        ]
        for key, validador, kwargs in validaciones:
            control = self.campos_modificar.get(key)
            if not control or not control.value:
                continue
            if not aplicar_validacion_error_text(control, control.value, validador, **kwargs):
                hay_errores = True
        return hay_errores

    def _validar_rango_fechas_modificar(self) -> bool:
        """Valida que la fecha inicial no sea mayor que la fecha final."""
        fechainicial_control = self.campos_modificar.get("fechainicial")
        fechafinal_control = self.campos_modificar.get("fechafinal")
        if not (
            fechainicial_control
            and fechainicial_control.value
            and fechafinal_control
            and fechafinal_control.value
        ):
            return False

        try:
            if fechainicial_control.value > fechafinal_control.value:
                set_campo_error(fechainicial_control, "La fecha inicial debe ser anterior a la fecha final")
                set_campo_error(fechafinal_control, "La fecha final debe ser posterior a la fecha inicial")
                return True
        except Exception:
            return False
        return False

    # ---------- Paso 1: Validar ----------
    def _render_validar(self):
        resultado_validacion = getattr(self, "_resultado_validacion", None)

        if resultado_validacion is not None:
            return self._construir_ui_validacion(resultado_validacion)

        # Mostrar "Validando..." e iniciar hilo de validación
        loader_validar = ft.Container(
            content=crear_loader_row("Validando..."),
            alignment=ft.Alignment(0, 0),
        )

        def validar_worker():
            formato_codigo = self.selected_formato_nombre
            rows = self._generar_xml_uc.obtener_datos_identidad(formato_codigo)
            self._cache_datos_hoja = rows
            res = self._generar_xml_uc.validar_formato_xsd(
                formato_codigo,
                atributos_xsd=self._cache_xsd["atributos"],
                rows=rows,
            )
            self._resultado_validacion = res
            self._refresh_body()
            self._page.update()

        self._page.run_thread(validar_worker)
        return loader_validar

    def _construir_ui_validacion(self, resultado_validacion):
        if not resultado_validacion:
            return ft.Column(
                spacing=12,
                controls=[
                    ft.Text("No hay datos en la hoja de trabajo para validar.", size=14, color=GREY_700),
                ],
                tight=True,
            )
        total_errores, total_avisos = self._totales_validacion(resultado_validacion)
        conceptos_ordenados = self._ordenar_conceptos_validacion(resultado_validacion)
        bloques_conceptos = [
            self._bloque_concepto_validacion(codigo, data)
            for codigo, data in conceptos_ordenados
        ]

        return ft.Container(
            expand=True,
            content=ft.Column(
                spacing=6,
                controls=[
                    self._fila_resumen_validacion(total_errores, total_avisos),
                    ft.Container(
                        content=ft.Column(
                            controls=bloques_conceptos,
                            spacing=6,
                            tight=True,
                        ),
                        expand=True,
                        padding=ft.padding.only(left=4, right=4, top=4),
                    ),
                ],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
        )

    def _totales_validacion(self, resultado_validacion):
        total_errores = sum(
            len([data for data in concepto_data.get("registros", {}).values() if data.get("errores")])
            for concepto_data in resultado_validacion.values()
        )
        total_avisos = sum(
            len([data for data in concepto_data.get("registros", {}).values() if data.get("avisos")])
            for concepto_data in resultado_validacion.values()
        )
        return total_errores, total_avisos

    def _ordenar_conceptos_validacion(self, resultado_validacion: dict) -> list:
        """Ordena (código, datos) poniendo primero conceptos con más filas en error."""

        def clave(par):
            codigo, data = par
            registros = data.get("registros") or {}
            cuenta_err = sum(1 for r in registros.values() if r.get("errores"))
            try:
                orden = int(str(codigo))
            except ValueError:
                orden = 0
            return (-cuenta_err, orden, str(codigo))

        return sorted(resultado_validacion.items(), key=clave)

    def _registros_ordenados_validacion(self, registros: dict) -> list:
        """Lista registros con hallazgos: errores antes que solo avisos; luego identidad."""
        items = []
        for data in registros.values():
            errores = data.get("errores") or []
            avisos = data.get("avisos") or []
            if not errores and not avisos:
                continue
            identidad = str(data.get("identidad", ""))
            prioridad = 0 if errores else 1
            items.append((prioridad, identidad.lower(), data))
        items.sort(key=lambda t: (t[0], t[1]))
        return [t[2] for t in items]

    def _fila_resumen_validacion(self, total_errores: int, total_avisos: int) -> ft.Row:
        """
        Resumen legible: ~la mitad de alto que las tarjetas grandes originales (dos mitades en fila),
        sin micro-tipografía.
        """
        def mitad(titulo: str, valor: int, color_num, bg):
            return ft.Container(
                expand=True,
                padding=ft.padding.symmetric(horizontal=10, vertical=6),
                bgcolor=bg,
                border_radius=6,
                border=ft.border.all(1, ft.Colors.with_opacity(0.12, GREY_700)),
                content=ft.Row(
                    [
                        ft.Column(
                            [
                                ft.Text(titulo, size=12, color=GREY_700),
                                ft.Text(str(valor), size=15, weight=ft.FontWeight.W_600, color=color_num),
                            ],
                            spacing=2,
                            tight=True,
                            expand=True,
                        ),
                    ],
                    tight=True,
                ),
            )

        return ft.Row(
            [
                mitad(
                    "Registros con errores",
                    total_errores,
                    ft.Colors.RED_700,
                    ft.Colors.with_opacity(0.07, ft.Colors.RED),
                ),
                mitad(
                    "Registros con avisos",
                    total_avisos,
                    ft.Colors.AMBER_900,
                    ft.Colors.with_opacity(0.1, ft.Colors.AMBER),
                ),
            ],
            spacing=8,
        )

    def _toggle_concepto_validacion(self, codigo):
        """
        Colapsar: ligero, sin hilo.
        Expandir: ring + hilo para pintar el loader antes de armar la lista (muchas filas).
        """
        expanding = codigo not in self.conceptos_expandidos
        if not expanding:
            self.conceptos_expandidos.discard(codigo)
            self._refresh_body()
            self._page.update()
            return

        loader_row_trabajo(self._page, self.loader, None, "Cargando…")
        self._page.update()

        def _worker():
            try:
                self.conceptos_expandidos.add(codigo)
                self._pagina_concepto_validacion.setdefault(codigo, 0)
                self._refresh_body()
            finally:
                loader_row_fin(self._page, self.loader)
            self._page.update()

        self._page.run_thread(_worker)

    def _pagina_concepto_actual(self, concepto_codigo: str) -> int:
        return int(self._pagina_concepto_validacion.get(concepto_codigo, 0))

    def _cambiar_pagina_concepto_validacion(self, concepto_codigo: str, nueva_pagina: int, total_items: int):
        page_size = max(1, int(self.PAGE_SIZE_VALIDACION_CONCEPTO))
        total_paginas = max(1, (total_items + page_size - 1) // page_size)
        nueva = max(0, min(nueva_pagina, total_paginas - 1))
        self._pagina_concepto_validacion[concepto_codigo] = nueva
        self._refresh_body()
        self._page.update()

    def _tarjeta_registro_validacion(self, concepto_codigo, error_data):
        errores = error_data.get("errores", [])
        avisos = error_data.get("avisos", [])
        identidad = error_data.get("identidad", "")
        color_borde = ft.Colors.RED_400 if errores else ft.Colors.AMBER_600
        tip = "\n".join((errores or []) + (avisos or []))
        mostrar_boton_correccion = bool(errores)

        controles_fila = [
            ft.Text(
                str(identidad),
                size=12,
                weight=ft.FontWeight.W_500,
                expand=True,
                max_lines=1,
                overflow=ft.TextOverflow.ELLIPSIS,
            ),
        ]
        if mostrar_boton_correccion:
            controles_fila.append(
                ft.IconButton(
                    icon=ft.Icons.SAVE_AS_OUTLINED,
                    icon_size=18,
                    style=BOTON_SECUNDARIO_SIN,
                    tooltip="Corregir",
                    padding=-10,
                    on_click=lambda e, cc=concepto_codigo, d=error_data: self._ir_a_correccion_validacion(cc, d),
                )
            )

        fila = ft.Row(
            controles_fila,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

        return ft.Container(
            expand=True,
            border=ft.border.only(left=ft.border.BorderSide(3, color_borde)),
            padding=ft.padding.symmetric(horizontal=8, vertical=5),
            bgcolor=ft.Colors.with_opacity(0.06, GREY_700),
            tooltip=ft.Tooltip(message=tip, wait_duration=900) if tip else None,
            content=fila,
        )

    def _grid_registros_validacion(self, concepto_codigo, registros_ordenados):
        """Rejilla densa y configurable; el orden visual se llena por filas (izq→der, luego abajo)."""
        filas = []
        cols = max(1, int(self.COLUMNAS_REGISTROS_VALIDACION))
        for i in range(0, len(registros_ordenados), cols):
            chunk = registros_ordenados[i : i + cols]
            celdas = [self._tarjeta_registro_validacion(concepto_codigo, r) for r in chunk]
            while len(celdas) < cols:
                celdas.append(ft.Container(expand=True))
            filas.append(
                ft.Row(
                    celdas,
                    spacing=8,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                )
            )
        return ft.ListView(
            controls=filas,
            spacing=5,
            auto_scroll=False,
            expand=False,
        )

    def _controles_paginacion_concepto_validacion(self, concepto_codigo: str, total_items: int):
        page_size = max(1, int(self.PAGE_SIZE_VALIDACION_CONCEPTO))
        total_paginas = max(1, (total_items + page_size - 1) // page_size)
        pagina = self._pagina_concepto_actual(concepto_codigo)
        if total_paginas <= 1:
            return None
        return ft.Row(
            [
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_LEFT,
                    icon_size=19,
                    style=BOTON_SECUNDARIO_SIN,
                    disabled=pagina <= 0,
                    on_click=lambda e, c=concepto_codigo, p=pagina: self._cambiar_pagina_concepto_validacion(c, p - 1, total_items),
                ),
                ft.Text(f"Página {pagina + 1} de {total_paginas}", size=12, color=GREY_700),
                ft.IconButton(
                    icon=ft.Icons.CHEVRON_RIGHT,
                    icon_size=19,
                    style=BOTON_SECUNDARIO_SIN,
                    disabled=pagina >= total_paginas - 1,
                    on_click=lambda e, c=concepto_codigo, p=pagina: self._cambiar_pagina_concepto_validacion(c, p + 1, total_items),
                ),
            ],
            spacing=4,
            alignment=ft.MainAxisAlignment.END,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        )

    def _bloque_concepto_validacion(self, concepto_codigo, concepto_data):
        registros_map = concepto_data.get("registros", {})
        num_errores = 0
        num_avisos = 0
        total_afectados = 0
        for r in registros_map.values():
            tiene_err = bool(r.get("errores"))
            tiene_avi = bool(r.get("avisos"))
            if not (tiene_err or tiene_avi):
                continue
            total_afectados += 1
            if tiene_err:
                num_errores += 1
            if tiene_avi:
                num_avisos += 1

        if total_afectados == 0:
            return ft.Container()
        esta_expandido = concepto_codigo in self.conceptos_expandidos
        descripcion = (concepto_data.get("descripcion") or "").strip() or "Sin descripción"
        titulo = f"{descripcion}" if concepto_codigo == "0" else f"Concepto {concepto_codigo} — {descripcion}"

        cabecera = ft.Container(
            on_click=lambda e, codigo=concepto_codigo: self._toggle_concepto_validacion(codigo),
            content=ft.Row(
                [
                    ft.Icon(
                        ft.Icons.KEYBOARD_ARROW_DOWN if esta_expandido else ft.Icons.KEYBOARD_ARROW_RIGHT,
                        size=16,
                        color=PINK_200,
                    ),
                    ft.Text(titulo, size=12, weight=ft.FontWeight.W_600, expand=True, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Text(f"{num_errores} err.", size=11, color=ft.Colors.RED_700),
                    ft.Text(f"{num_avisos} av.", size=11, color=ft.Colors.AMBER_800),
                ],
                spacing=4,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
        )
        hijos = [cabecera]
        if esta_expandido:
            registros_ordenados = self._registros_ordenados_validacion(registros_map)
            total_items = len(registros_ordenados)
            page_size = max(1, int(self.PAGE_SIZE_VALIDACION_CONCEPTO))
            pagina = self._pagina_concepto_actual(concepto_codigo)
            inicio = pagina * page_size
            fin = inicio + page_size
            hijos.append(self._grid_registros_validacion(concepto_codigo, registros_ordenados[inicio:fin]))
            nav = self._controles_paginacion_concepto_validacion(concepto_codigo, total_items)
            if nav:
                hijos.append(nav)

        return ft.Container(
            border=ft.border.all(1, ft.Colors.with_opacity(0.12, GREY_700)),
            border_radius=6,
            padding=ft.padding.symmetric(horizontal=8, vertical=6),
            bgcolor=ft.Colors.WHITE,
            content=ft.Column(hijos, spacing=6, tight=True),
        )

    def _exportar_validacion_pdf(self, resultado_validacion):
        """Genera el informe PDF de errores/avisos y abre el diálogo para guardarlo."""
        if not resultado_validacion:
            self._mostrar_mensaje("No hay información de validación para exportar.", 3500)
            return

        loader_row_trabajo(self._page, self.loader, None, "Construyendo PDF de validación...")

        def _worker_pdf():
            try:
                nombre_formato = str(self.selected_formato_nombre or "Sin formato")
                self._pdf_validacion_temp = construir_pdf_validacion(resultado_validacion, nombre_formato)
                self._pdf_validacion_nombre_temp = f"Validacion_XML_{nombre_formato}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                self._page.run_task(self._ejecutar_guardar_pdf_async_wrapper)
            except Exception as ex:
                import traceback
                traceback.print_exc()
                self._mostrar_mensaje(f"Error al generar el PDF: {ex}", 5000)
            finally:
                loader_row_fin(self._page, self.loader)

        self._page.run_thread(_worker_pdf)
    
    def _datos_cabecera(self):
        """
        Devuelve un dict sencillo con los valores del formulario de cabecera.
        Siempre que se necesiten estos datos para validar o generar, se
        centraliza el acceso aqui para evitar duplicar logica.
        """
        def val(nombre):
            ctrl = self.campos_modificar.get(nombre)
            return (getattr(ctrl, "value", "") or "").strip() if ctrl else ""

        return {
            "concepto": val("concepto"),
            "version": val("version"),
            "numenvio": val("numenvio"),
            "fechaenvio": val("fechaenvio"),
            "horaenvio": val("horaenvio"),
            "fechainicial": val("fechainicial"),
            "fechafinal": val("fechafinal"),
            "formato": self.selected_formato_nombre or "",
        }

    def _validar_datos_cabecera(self):
        """
        Valida los datos minimos que todo anexo suele requerir:
        - Formato seleccionado.
        - Fechas dentro del periodo configurado en config (FECHA_INICIAL / FECHA_FINAL).
        - Consistencia entre fecha inicial y final.
        - Formato basico de la hora de envio.

        Retorna un dict:
            {
                "errores": [str, ...],
                "avisos": [str, ...],
            }
        """
        datos = self._datos_cabecera()
        errores: list[str] = []
        avisos: list[str] = []

        # 1. Validar que haya formato seleccionado
        if not self.selected_formato:
            errores.append("No hay un formato seleccionado para generar el XML.")

        # 2. Validacion de fechas frente al periodo global
        #    Se asume entrada AAAA-MM-DD, que es el formato de fecha
        #    utilizado por los anexos de exgena mas recientes.
        def parse_fecha_iso(texto):
            partes = texto.split("-")
            if len(partes) != 3 or any(not p.isdigit() for p in partes):
                raise ValueError("La fecha debe estar en formato AAAA-MM-DD.")
            ano = int(partes[0])
            mes = int(partes[1])
            dia = int(partes[2])
            return ano, mes, dia

        def helisa_desde_texto(nombre_campo):
            valor = datos.get(nombre_campo, "")
            if not valor:
                raise ValueError(f"El campo '{nombre_campo}' es obligatorio.")
            ano, mes, dia = parse_fecha_iso(valor)
            try:
                return fechaHelisa(ano, mes, dia)
            except Exception as e:
                raise ValueError(f"La fecha de '{nombre_campo}' no es valida: {e}")

        fecha_ini_periodo = FECHA_INICIAL
        fecha_fin_periodo = FECHA_FINAL

        fecha_envio_helisa = None
        fecha_ini_helisa = None
        fecha_fin_helisa = None

        # Fecha de envio
        try:
            fecha_envio_helisa = helisa_desde_texto("fechaenvio")
            if not (fecha_ini_periodo <= fecha_envio_helisa <= fecha_fin_periodo):
                avisos.append(
                    "La fecha de envio esta fuera del rango del periodo configurado; "
                    "revise que corresponda al ano gravable actual."
                )
        except ValueError as ex:
            errores.append(str(ex))

        # Fecha inicial
        try:
            fecha_ini_helisa = helisa_desde_texto("fechainicial")
            if fecha_ini_helisa < fecha_ini_periodo:
                errores.append("La fecha inicial es anterior al inicio del periodo permitido.")
        except ValueError as ex:
            errores.append(str(ex))

        # Fecha final
        try:
            fecha_fin_helisa = helisa_desde_texto("fechafinal")
            if fecha_fin_helisa > fecha_fin_periodo:
                errores.append("La fecha final es posterior al final del periodo permitido.")
        except ValueError as ex:
            errores.append(str(ex))

        # Consistencia rango inicial / final
        if fecha_ini_helisa is not None and fecha_fin_helisa is not None:
            if fecha_ini_helisa > fecha_fin_helisa:
                errores.append("La fecha inicial no puede ser mayor que la fecha final.")

        # 3. Validacion basica de la hora de envio.
        hora_txt = datos.get("horaenvio", "")
        if not hora_txt:
            errores.append("El campo 'Hora de envio' es obligatorio.")
        else:
            partes = hora_txt.split(":")
            if len(partes) != 3 or any(not p.isdigit() for p in partes):
                errores.append("La hora de envio debe estar en formato HH:MM:SS (por ejemplo, 09:30:00).")
            else:
                hh = int(partes[0])
                mm = int(partes[1])
                ss = int(partes[2])
                if not (0 <= hh <= 23 and 0 <= mm <= 59 and 0 <= ss <= 59):
                    errores.append("La hora de envio esta fuera del rango valido (00:00:00 a 23:59:59).")

        return {"errores": errores, "avisos": avisos}

    def _mostrar_mensaje(self, texto, duration):
        mostrar_mensaje_overlay(self._page, texto, duration, size=14)
    
    async def _ejecutar_guardar_unico_async_wrapper(self):
        """
        Wrapper async para ejecutar el guardado único desde el thread principal.
        """
        # Pequeña pausa para asegurar que el overlay del diálogo se limpie completamente
        import asyncio
        await asyncio.sleep(0.1)
        self._page.update()
        
        nombre_archivo = self._nombre_archivo_temp
        xml_data = self._xmls_generados_temp[0]
        await self._abrir_filepicker_guardar(xml_data, nombre_archivo)
    
    async def _ejecutar_guardar_multiples_async_wrapper(self):
        """
        Wrapper async para ejecutar el guardado múltiple desde el thread principal.
        """
        # Pequeña pausa para asegurar que el overlay del diálogo se limpie completamente
        import asyncio
        await asyncio.sleep(0.1)
        self._page.update()
        
        await self._guardar_multiples_archivos_async(
            self._xmls_generados_temp,
            self._concepto_codigo_temp,
            self._formato_codigo_temp,
            self._version_temp,
            self._año_temp,
            self._numenvio_temp
        )

    async def _ejecutar_guardar_pdf_async_wrapper(self):
        """Wrapper async para ejecutar el guardado de PDF desde el thread principal."""
        import asyncio
        await asyncio.sleep(0.1)
        self._page.update()
        await self._abrir_filepicker_guardar_pdf(self._pdf_validacion_temp, self._pdf_validacion_nombre_temp)


    async def _abrir_filepicker_guardar_pdf(self, pdf_bytes, nombre_archivo):
        """Abre FilePicker y guarda el PDF de validación en la ruta elegida."""
        fp = ft.FilePicker()
        ruta_archivo = await fp.save_file(
            allowed_extensions=["pdf"],
            dialog_title="Guardar informe PDF de validación",
            file_name=nombre_archivo,
        )

        if not ruta_archivo:
            return

        try:
            with open(ruta_archivo, "wb") as f:
                f.write(pdf_bytes)
            self._mostrar_mensaje("PDF de validación generado correctamente.", 3000)
        except Exception as guardar_err:
            import traceback
            traceback.print_exc()
            self._mostrar_mensaje(f"Error al guardar PDF: {guardar_err}", 5000)


    async def _abrir_filepicker_guardar(self, xml_data, nombre_archivo):
        """
        Abre el FilePicker desde el thread principal para guardar un solo archivo XML.
        """
        xml_str, cant_reg = xml_data
        fp = ft.FilePicker()
        ruta_archivo = await fp.save_file(
            allowed_extensions=["xml"],
            dialog_title="Guardar archivo XML",
            file_name=nombre_archivo,
        )
        
        if not ruta_archivo:
            return
        
        try:
            with open(ruta_archivo, "w", encoding="ISO-8859-1") as f:
                f.write(xml_str)
            self._mostrar_mensaje(f"XML generado correctamente ({cant_reg} registros).", 3000)
        except Exception as guardar_err:
            import traceback
            traceback.print_exc()
            self._mostrar_mensaje(f"Error al guardar XML: {guardar_err}", 5000)
    
    async def _guardar_multiples_archivos_async(self, xmls_generados, concepto_codigo, formato_codigo, version, año, numenvio):
        """
        Guarda múltiples archivos XML cuando hay más de 5000 registros.
        Usa FilePicker para seleccionar el directorio donde guardar todos los archivos.
        Este método se ejecuta desde el thread principal.
        """
        fp = ft.FilePicker()
        directorio = await fp.get_directory_path(dialog_title="Seleccione el directorio donde guardar los archivos XML")
        
        if not directorio:
            return
        
        if not os.path.isdir(directorio):
            # Si es un archivo, usar su directorio padre
            directorio = os.path.dirname(directorio)
        
        archivos_guardados = 0
        archivos_error = 0
        
        for idx, (xml_str, cant_reg) in enumerate(xmls_generados, start=1):
            if idx == 1:
                nombre_archivo = f"Dmuisca_{concepto_codigo}{formato_codigo}{version}{año}{numenvio}.xml"
            else:
                nombre_archivo = f"Dmuisca_{concepto_codigo}{formato_codigo}{version}{año}{numenvio}_{idx}.xml"
            
            ruta_completa = os.path.join(directorio, nombre_archivo)
            
            try:
                with open(ruta_completa, "w", encoding="ISO-8859-1") as f:
                    f.write(xml_str)
                archivos_guardados += 1
            except Exception as guardar_err:
                import traceback
                traceback.print_exc()
                archivos_error += 1
        
        total_registros = sum(cant for _, cant in xmls_generados)
        
        if archivos_error == 0:
            mensaje = f"Se generaron {len(xmls_generados)} archivo(s) XML correctamente ({archivos_guardados} guardados, {total_registros} registros)."
            self._mostrar_mensaje(mensaje, 5000)
        else:
            mensaje = f"Se generaron {len(xmls_generados)} archivo(s) XML. {archivos_guardados} guardados, {archivos_error} errores ({total_registros} registros)."
            self._mostrar_mensaje(mensaje, 5000)
        self._page.update()
    

    # ---------- Paso 2: Generar ----------
    def _render_generar(self):
        if not self.campos_modificar:
            self._build_modificar_form()
        
        def generar_xml(e):
            if not self._campos_modificar_completos():
                self._mostrar_mensaje("Complete los campos obligatorios antes de generar el XML.", 4444)
                return
            resultado = self._validar_datos_cabecera()
            if resultado["errores"]:
                self._mostrar_mensaje("Hay errores en los datos. Revise y corrija antes de generar.", 5000)
                return

            loader_row_trabajo(self._page, self.loader, None, "Generando XML...")

            def generar_worker():
                try:
                    datos_cab = self._datos_cabecera()
                    self._generar_xml_uc.actualizar_formato(
                        self.campos_modificar, self.selected_formato[1]
                    )
                    
                    datos_hoja = (
                        self._generar_xml_uc.obtener_hoja_para_generar(
                            self.selected_formato_nombre, rows=self._cache_datos_hoja
                        )
                        if self._cache_datos_hoja else None
                    )
                    
                    xmls_generados = self._generar_xml_uc.generar_xml_formato(
                        self.selected_formato_nombre,
                        datos_cab,
                        orden_atributos=self._cache_xsd["orden"],
                        elemento_detalle=self._cache_xsd["elemento_detalle"],
                        datos_hoja=datos_hoja,
                    )
                except Exception as ex:
                    import traceback
                    traceback.print_exc()
                    loader_row_fin(self._page, self.loader)
                    self._mostrar_mensaje(f"Error al generar XML: {ex}", 5000)
                    return
                
                if not xmls_generados:
                    loader_row_fin(self._page, self.loader)
                    self._mostrar_mensaje("Error: No se pudo generar ningún archivo XML.", 5000)
                    return

                loader_row_fin(self._page, self.loader)

                # Preparar nombres base de archivo
                concepto_codigo = datos_cab.get("concepto", "01")
                if concepto_codigo == "Insercion":
                    concepto_codigo = "01"
                elif concepto_codigo == "Reemplazo":
                    concepto_codigo = "02"
                formato_codigo = str(self.selected_formato_nombre).zfill(5)
                version = str(datos_cab.get("version", "")).zfill(2)
                fecha_envio = datos_cab.get("fechaenvio", "")
                año = fecha_envio[:4] if len(fecha_envio) >= 4 else str(PERIODO)
                numenvio = str(datos_cab.get("numenvio", "")).zfill(8)
                
                # Guardar datos para ejecutar FilePicker desde el thread principal
                self._xmls_generados_temp = xmls_generados
                self._concepto_codigo_temp = concepto_codigo
                self._formato_codigo_temp = formato_codigo
                self._version_temp = version
                self._año_temp = año
                self._numenvio_temp = numenvio
                
                # Programar ejecución del FilePicker en el thread principal usando page.run_task()
                # Esto asegura que el FilePicker se ejecute desde el thread principal de Flet
                if len(xmls_generados) > 1:
                    self._page.run_task(self._ejecutar_guardar_multiples_async_wrapper)
                else:
                    nombre_archivo = f"Dmuisca_{concepto_codigo}{formato_codigo}{version}{año}{numenvio}.xml"
                    self._nombre_archivo_temp = nombre_archivo
                    self._page.run_task(self._ejecutar_guardar_unico_async_wrapper)

            # Ejecutar worker en thread separado usando el método de Flet
            self._page.run_thread(generar_worker)
        
        # Cantidad de registros (grupos: misma identidad + distintos valores = distintos reg)
        cantidad_registros = 0
        if hasattr(self, "_cache_datos_hoja") and self._cache_datos_hoja:
            datos_hoja = self._generar_xml_uc.obtener_hoja_para_generar(
                self.selected_formato_nombre, rows=self._cache_datos_hoja
            )
            cantidad_registros = len(datos_hoja) if datos_hoja else 0
        controles = list(self.campos_modificar.values())
        if cantidad_registros > 5000:
            num_archivos = (cantidad_registros + 4999) // 5000
            advertencia = ft.Container(
                content=ft.Row(
                    [
                        ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.AMBER, size=20),
                        ft.Text(
                            f"Se detectaron {cantidad_registros} registros. Se generarán {num_archivos} archivo(s) XML (máximo 5000 por archivo).",
                            size=13,
                            color=ft.Colors.AMBER_700,
                            weight=ft.FontWeight.W_500,
                        ),
                    ],
                    spacing=8,
                ),
                bgcolor=ft.Colors.with_opacity(0.1, ft.Colors.AMBER),
                padding=12,
                border_radius=6,
                border=ft.border.all(1, ft.Colors.AMBER_300),
            )
            controles.append(advertencia)
        
        controles.append(
            ft.ElevatedButton(
                "Generar XML",
                icon=ft.Icons.FILE_DOWNLOAD,
                style=BOTON_PRINCIPAL,
                on_click=generar_xml,
            )
        )
        
        return ft.Container(
            content=ft.Column(
                spacing=12,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                controls=controles,
                tight=True,
            ),
            alignment=ft.Alignment(0, -1),
            expand=True,
        )