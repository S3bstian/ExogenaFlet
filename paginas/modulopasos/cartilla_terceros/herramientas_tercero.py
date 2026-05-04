import flet as ft
import time
from core.catalogues import (
    PAISES, DEPARTAMENTOS, MUNICIPIOS, TIPOSDOC,
    obtener_nombre_pais, obtener_nombre_departamento, obtener_nombre_municipio,
    obtener_codigo_tipodoc, obtener_codigo_pais, obtener_codigo_departamento, obtener_codigo_municipio,
)
from ui.colors import PINK_50, PINK_200, GREY_700, WHITE
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO, BOTON_SECUNDARIO_SIN
from ui.dropdowns import DropdownCompact
from ui.snackbars import actualizar_mensaje_en_control
from utils.validators import (
    aplicar_validacion_error_text,
    set_campo_error,
    validar_campo_obligatorio,
    validar_identidad_documento_numerica,
    validar_digito_verificacion_opcional,
)
from paginas.utils.paginacion import build_pagination_label, pagination_text_value
from paginas.utils.tooltips import TooltipId, tooltip
from utils.ui_sync import ejecutar_en_ui, loader_row_fin, loader_row_fin_y_error, loader_row_trabajo


class TerceroDialog:
    def __init__(self, page, parent):
        self.page = page
        self.parent = parent
        self.dialog = None
        self.modo = "editar"
        # origen: "insertar"/"editar" (por defecto) o "reemplazar"
        self.origen = "insertar"
        self.mensaje = ft.Text("", size=14, italic=True, visible=False)

        # referencias para dropdowns dependientes
        self.dd_pais = None
        self.dd_departamento = None
        self.dd_municipio = None

        # controles para modo "reemplazar"
        self.dd_campo = None
        self.ctrl_buscar = None
        self.ctrl_reemplazar = None
        self.row_buscar = None
        self.row_reemplazar = None
        self._campo_actual_label = None
        self.tabla_reemplazo = None
        self._terceros_encontrados = []
        self._seleccionados_ids = set()
        self.loader_reemplazo = None
        self.loader_guardado = None
        self._btn_guardar = None
        self._btn_cancelar = None
        self._pagina_resultados = 0
        self._page_size_resultados = 500
        self.nav_resultados = None

        # configuración de campos disponibles para reemplazo
        self.campos_reemplazo = [
            {"label": "Razón Social", "key": "razonsocial", "tipo": "texto"},
            {"label": "Dirección", "key": "direccion", "tipo": "texto"},
            {"label": "Primer Apellido", "key": "primerapellido", "tipo": "texto"},
            {"label": "Segundo Apellido", "key": "segundoapellido", "tipo": "texto"},
            {"label": "Primer Nombre", "key": "primernombre", "tipo": "texto"},
            {"label": "Segundo Nombre", "key": "segundonombre", "tipo": "texto"},
            {"label": "Tipo de documento", "key": "tipodocumento", "tipo": "dropdown", "fuente": "TIPOSDOC"},
            {"label": "Tipo de persona", "key": "naturaleza", "tipo": "dropdown", "opciones": ["P. Natural", "P. Juridica"]},
            {"label": "País", "key": "pais", "tipo": "dropdown", "fuente": "PAISES"},
            {"label": "Departamento", "key": "departamento", "tipo": "dropdown", "fuente": "DEPARTAMENTOS"},
            {"label": "Municipio", "key": "municipio", "tipo": "dropdown", "fuente": "MUNICIPIOS"},
        ]

    # ==========================================================
    # =============== ABRIR DIALOGO =============================
    # ==========================================================
    def abrir(self, tercero=None, origen="insertar", terceros=None):
        print("tercero", tercero)
        self.origen = origen or "insertar"
        self.modo = "editar" if tercero else "nuevo"

        # ---------------- MODO REEMPLAZAR (HERRAMIENTAS TERCERO) ---------------
        if self.origen == "reemplazar":
            self._build_dialogo_reemplazar()
            return

        # ---------------- MODO DIVIDIR NOMBRES ---------------
        if self.origen == "dividir_nombres":
            self._build_dialogo_dividir_nombres(terceros or [])
            return

        # ---------------- MODO NORMAL (NUEVO / EDITAR) ------------------------
        tercero = tercero or {
            "id": None,
            "identidad": 0,
            "tipodocumento": 0,
            "naturaleza": 0,
            "digitoverificacion": "",
            "razonsocial": "",
            "primerapellido": "",
            "segundoapellido": "",
            "primernombre": "",
            "segundonombre": "",
            "direccion": "",
            "pais": 0,
            "departamento": 0,
            "municipio": 0,
        }

        def tf(label, key=None, disabled=False, options=None, on_change=None):
            val = tercero.get(key) if tercero.get(key) != 0 else ""
            if key == "pais" and val != "":
                val = obtener_nombre_pais(val) or val
            elif key == "departamento" and val != "":
                val = obtener_nombre_departamento(val) or val
            elif key == "municipio" and val != "":
                val = obtener_nombre_municipio(val, tercero.get("departamento")) or val
            elif key == "naturaleza":
                if val == "":
                    val = options[0]
                elif val == 1:
                    val = options[1]
            if options is not None:
                return DropdownCompact(
                    label=label,
                    value=val,
                    options=[ft.DropdownOption(key=o, text=o) for o in options],
                    on_select=on_change,
                    expand=True,
                )
            else:
                # Documento y DV: solo dígitos en UI + validación al guardar (también desde hoja de trabajo).
                solo_digitos = key in ("identidad", "digitoverificacion")
                return ft.TextField(
                    label=label,
                    value=val or "",
                    disabled=disabled,
                    border_color=PINK_200,
                    label_style=ft.TextStyle(color=GREY_700),
                    keyboard_type=ft.KeyboardType.NUMBER if solo_digitos else None,
                    input_filter=ft.NumbersOnlyInputFilter() if solo_digitos else None,
                )

        # ---- Campos ----
        identidad = tf("Numero Documento", "identidad", disabled=(self.modo == "editar"))
        naturaleza = ["P. Natural", "P. Juridica"]
        dd_naturaleza = tf("Tipo Persona", "naturaleza", options=naturaleza)
        dverificacion = tf("Digito Verificacion", "digitoverificacion")
        tipodocumento = [t[1][1] for t in TIPOSDOC.items()]
        self.dd_documentos = tf("Tipo Documento", "tipodocumento", options=tipodocumento)
        razon = tf("Razón Social", "razonsocial")
        p_apellido = tf("Primer Apellido", "primerapellido")
        s_apellido = tf("Segundo Apellido", "segundoapellido")
        p_nombre = tf("Primer Nombre", "primernombre")
        s_nombre = tf("Segundo Nombre", "segundonombre")
        direccion = tf("Dirección", "direccion")

        paises = [p for p in PAISES.values()]
        self.dd_pais = tf("País", "pais", options=paises, on_change=self._on_pais_change)

        pais_cod = tercero.get("pais")
        if pais_cod is not None and pais_cod != "" and pais_cod != 0:
            try:
                pais_cod_int = int(pais_cod)
                depto_inicial = [d[0] for d in DEPARTAMENTOS.values() if int(d[1]) == pais_cod_int]
            except (ValueError, TypeError):
                depto_inicial = []
        else:
            depto_inicial = []
        self.dd_departamento = tf(
            "Departamento", "departamento", options=depto_inicial, on_change=self._on_departamento_change
        )
        
        depto_cod = tercero.get("departamento")
        if depto_cod is not None and depto_cod != "" and depto_cod != 0:
            try:
                depto_cod_int = int(depto_cod)
                munis_inicial = [m[1] for m in MUNICIPIOS.values() if int(m[2]) == depto_cod_int]
            except (ValueError, TypeError):
                munis_inicial = []
        else:
            munis_inicial = []
        self.dd_municipio = tf("Municipio", "municipio", options=munis_inicial)

        titulo = "Editar tercero" if self.modo == "editar" else "Nuevo tercero"
        btn_guardar_texto = "Guardar cambios" if self.modo == "editar" else "Crear tercero"
        from ui.progress import crear_loader_row, SIZE_SMALL
        self.loader_guardado = crear_loader_row("Guardando tercero...", size=SIZE_SMALL)
        self.loader_guardado.visible = False
        self._btn_cancelar = ft.TextButton(
            content="Cancelar",
            on_click=self.cerrar_dialog,
            style=BOTON_SECUNDARIO_SIN,
        )
        self._btn_guardar = ft.Button(
            content=btn_guardar_texto,
            on_click=lambda e: self.guardar(tercero.get("id")),
            style=BOTON_PRINCIPAL,
        )

        form = ft.Column(
            spacing=10,
            controls=[
                ft.Row(
                    [
                        ft.Container(self.dd_documentos, expand=1, width=222),
                        ft.Container(identidad, expand=1),
                        ft.Container(dd_naturaleza, width=140),
                        ft.Container(dverificacion, width=90),
                    ]
                ),
                ft.Row([ft.Container(razon, expand=1)]),
                ft.Row([ft.Container(p_apellido, expand=1), ft.Container(s_apellido, expand=1)]),
                ft.Row([ft.Container(p_nombre, expand=1), ft.Container(s_nombre, expand=1)]),
                ft.Row([ft.Container(direccion, expand=1), ft.Container(self.dd_pais, expand=1)]),
                ft.Row([ft.Container(self.dd_departamento, expand=1), ft.Container(self.dd_municipio, expand=1)]),
                self.loader_guardado,
                self.mensaje,
            ],
            tight=False,
            scroll=ft.ScrollMode.AUTO,
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text(titulo, text_align=ft.TextAlign.CENTER),
            content=form,
            bgcolor=WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                self._btn_cancelar,
                self._btn_guardar,
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.dialog)

    def _get_campo_config(self, label=None):
        lbl = label or self._campo_actual_label
        return next((c for c in self.campos_reemplazo if c["label"] == lbl), self.campos_reemplazo[0])

    def _on_campo_reemplazo_change(self, e):
        self._campo_actual_label = e.control.value
        self._crear_controles_buscar_reemplazar()
        self.page.update()

    def _crear_controles_buscar_reemplazar(self):
        campo = self._get_campo_config()
        tipo = campo.get("tipo")

        if tipo == "texto":
            self.ctrl_buscar = ft.TextField(
                label=f"Buscar en {campo['label']}",
                hint_text="Texto a buscar",
                border_color=PINK_200,
                label_style=ft.TextStyle(color=GREY_700),
                width=255,
                height=40
                
            )
            self.ctrl_reemplazar = ft.TextField(
                label="Reemplazar con",
                hint_text="Nuevo texto",
                border_color=PINK_200,
                label_style=ft.TextStyle(color=GREY_700),
                width=255,
                height=40
            )
        else:  # dropdown
            opciones = []
            fuente = campo.get("fuente")
            if fuente == "TIPOSDOC":
                opciones = [t[1][1] for t in TIPOSDOC.items()]
            elif fuente == "PAISES":
                opciones = [p for p in PAISES.values()]
            elif fuente == "DEPARTAMENTOS":
                opciones = [d[0] for d in DEPARTAMENTOS.values()]
            elif fuente == "MUNICIPIOS":
                opciones = [m[1] for m in MUNICIPIOS.values()]
            else:
                opciones = campo.get("opciones", [])

            self.ctrl_buscar = DropdownCompact(
                label=f"Valor actual de {campo['label']}",
                options=[ft.DropdownOption(key=o, text=o) for o in opciones],
            )
            self.ctrl_reemplazar = DropdownCompact(
                label=f"Nuevo valor de {campo['label']}",
                options=[ft.DropdownOption(key=o, text=o) for o in opciones],
            )

        # si ya existen las filas en el layout, actualizamos sus controles
        if self.row_buscar is not None and self.row_buscar.controls:
            self.row_buscar.controls[0] = self.ctrl_buscar
        if self.row_reemplazar is not None and self.row_reemplazar.controls:
            self.row_reemplazar.controls[0] = self.ctrl_reemplazar

    # ==========================================================
    # =============== DIALOGO REEMPLAZAR =======================
    # ==========================================================
    def _build_dialogo_reemplazar(self):
        # campo a trabajar
        self._campo_actual_label = self.campos_reemplazo[0]["label"]
        self.dd_campo = DropdownCompact(
            label="Campo a buscar / reemplazar",
            value=self._campo_actual_label,
            options=[ft.DropdownOption(key=c["label"], text=c["label"]) for c in self.campos_reemplazo],
            on_select=self._on_campo_reemplazo_change,
        )

        btn_buscar = ft.ElevatedButton(
            "Buscar coincidencias",
            icon=ft.Icons.SEARCH,
            style=BOTON_SECUNDARIO,
            on_click=self._buscar_coincidencias,
        )

        from ui.progress import crear_loader_row, SIZE_SMALL
        self.loader_reemplazo = crear_loader_row("Buscando coincidencias...", size=SIZE_SMALL)
        self.loader_reemplazo.visible = False
        self.loader_reemplazo.controls[1].size = 12
        self.loader_reemplazo.controls[1].italic = True
        self.loader_reemplazo.alignment = ft.MainAxisAlignment.START

        self.loader_aplicar = crear_loader_row("Aplicando reemplazo...", size=SIZE_SMALL)
        self.loader_aplicar.visible = False
        self.loader_aplicar.controls[1].size = 12
        self.loader_aplicar.controls[1].italic = True
        self.loader_aplicar.alignment = ft.MainAxisAlignment.START

        # tabla de resultados con selección
        self.tabla_reemplazo = ft.DataTable(
            columns=[
                ft.DataColumn(ft.Text("Sel")),
                ft.DataColumn(ft.Text("Razón Social")),
                ft.DataColumn(ft.Text("Identidad")),
                ft.DataColumn(ft.Text("Valor campo")),
            ],
            rows=[],
            heading_row_height=30,
            data_row_max_height=44,
            heading_row_color=PINK_50,
            divider_thickness=0.5,
        )

        row_seleccion = ft.Row(
            controls=[
                ft.TextButton("Seleccionar todos", icon=ft.Icons.CHECKLIST, on_click=self._seleccionar_todos, style=BOTON_SECUNDARIO_SIN),
                ft.TextButton("Deseleccionar todos", icon=ft.Icons.REMOVE_DONE, on_click=self._deseleccionar_todos, style=BOTON_SECUNDARIO_SIN),
            ],
            alignment=ft.MainAxisAlignment.END,
        )
        cont_tabla = ft.Container(
            content=ft.Column(
                controls=[row_seleccion, self.tabla_reemplazo],
                expand=True,
                scroll=ft.ScrollMode.AUTO,
            ),
            height=325,
            padding=5,
        )
        self.pagination_text_footer_reemplazo = build_pagination_label(
            1,
            1,
            tooltip_alt_pagina=tooltip(TooltipId.PAGINA_TEXTO_RESULTADOS),
        )
        pagination_row_bottom = ft.Row([self.pagination_text_footer_reemplazo], alignment=ft.MainAxisAlignment.END, tight=True)
        # navegación de resultados (paginación cada 500)
        self.nav_resultados = ft.Row(
            controls=[
                ft.ElevatedButton(
                    "Anterior",
                    icon=ft.Icons.ARROW_BACK_IOS_NEW_SHARP,
                    style=BOTON_SECUNDARIO,
                    on_click=lambda e: self._cambiar_pagina_resultados(-1),
                    tooltip=tooltip(TooltipId.PAGINA_BTN_SOLO_ANTERIOR),
                ),
                ft.ElevatedButton(
                    "Siguiente",
                    icon=ft.Icons.ARROW_FORWARD_IOS_SHARP,
                    style=BOTON_SECUNDARIO,
                    on_click=lambda e: self._cambiar_pagina_resultados(1),
                    tooltip=tooltip(TooltipId.PAGINA_BTN_SOLO_SIGUIENTE),
                ),
            ],
            alignment=ft.MainAxisAlignment.END,
            visible=False,
        )

        # crear controles iniciales de búsqueda y reemplazo
        self._crear_controles_buscar_reemplazar()
        self.row_buscar = ft.Row([self.ctrl_buscar])
        self.row_reemplazar = ft.Row([self.ctrl_reemplazar])

        cuerpo = ft.Column(
            spacing=12,
            controls=[
                ft.Text("Herramientas tercero - Reemplazar", size=16, weight=ft.FontWeight.BOLD),
                ft.Row([self.dd_campo, ft.Column([self.row_buscar, self.row_reemplazar])], alignment=ft.MainAxisAlignment.SPACE_AROUND),
                btn_buscar,
                self.loader_reemplazo,
                self.loader_aplicar,
                cont_tabla,
                pagination_row_bottom,
                self.nav_resultados,
                self.mensaje,
            ],
            tight=False,
        )

        self.dialog = ft.AlertDialog(
            title=None,
            content=ft.Container(width=750, content=cuerpo, padding=10),
            bgcolor=WHITE,
            modal=False,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(content="Cerrar", on_click=self.cerrar_dialog, style=BOTON_SECUNDARIO_SIN),
                ft.Button(
                    content="Aplicar reemplazo",
                    icon=ft.Icons.SAVE_AS,
                    on_click=self._aplicar_reemplazo,
                    style=BOTON_PRINCIPAL,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.dialog)

    def _reconstruir_tabla_reemplazo(self):
        self.tabla_reemplazo.rows.clear()
        campo = self._get_campo_config()

        inicio = self._pagina_resultados * self._page_size_resultados
        fin = inicio + self._page_size_resultados
        pagina = self._terceros_encontrados[inicio:fin]

        for t in pagina:
            identidad = t.get("identidad", "")
            razon = t.get("razonsocial", t.get("nombre", ""))
            seleccionado = identidad in self._seleccionados_ids
            valor_campo = self._obtener_valor_visible_campo(t, campo)

            chk = ft.Checkbox(
                value=seleccionado,
                active_color=PINK_200,
                check_color=ft.Colors.WHITE,
                on_change=lambda e, ident=identidad: self._toggle_seleccion(ident, e.control.value),
            )

            fila = ft.DataRow(
                cells=[
                    ft.DataCell(chk),
                    ft.DataCell(ft.Text(razon, text_align=ft.TextAlign.LEFT)),
                    ft.DataCell(ft.Text(identidad, text_align=ft.TextAlign.CENTER)),
                    ft.DataCell(ft.Text(valor_campo, text_align=ft.TextAlign.LEFT)),
                ]
            )
            self.tabla_reemplazo.rows.append(fila)

        total = len(self._terceros_encontrados) or 0
        total_paginas = max(1, (total + self._page_size_resultados - 1) // self._page_size_resultados) if total else 1
        pagina_actual = self._pagina_resultados + 1
        txt = pagination_text_value(pagina_actual, total_paginas)
        self.pagination_text_footer_reemplazo.value = txt
        self.page.update()

    def _toggle_seleccion(self, identidad, marcado):
        if marcado:
            self._seleccionados_ids.add(identidad)
        else:
            self._seleccionados_ids.discard(identidad)

    def _seleccionar_todos(self, e=None):
        """Marca todos los terceros encontrados en la lista."""
        for t in self._terceros_encontrados:
            identidad = t.get("identidad")
            if identidad is not None and identidad != "":
                self._seleccionados_ids.add(identidad)
        self._reconstruir_tabla_reemplazo()

    def _deseleccionar_todos(self, e=None):
        """Desmarca todos los terceros."""
        self._seleccionados_ids.clear()
        self._reconstruir_tabla_reemplazo()

    def _obtener_valor_visible_campo(self, tercero, campo):
        key = campo["key"]
        val = tercero.get(key)

        if key == "pais" and val not in (None, "", 0):
            return PAISES.get(str(val), "")
        if key == "departamento" and val not in (None, "", 0):
            data = DEPARTAMENTOS.get(str(val))
            return data[0] if data else ""
        if key == "municipio" and val not in (None, "", 0):
            for m in MUNICIPIOS.values():
                if int(m[0]) == val:
                    return m[1]
            return ""
        if key == "naturaleza":
            if val == 0:
                return "P. Natural"
            if val == 1:
                return "P. Juridica"
        return str(val or "")

    def _buscar_coincidencias(self, e=None):
        campo = self._get_campo_config()
        valor_buscar = (self.ctrl_buscar.value or "").strip() if campo["tipo"] == "texto" else (self.ctrl_buscar.value or "")
        self._terceros_encontrados = []
        self._seleccionados_ids = set()

        if not valor_buscar:
            self.mensaje.value = "Ingrese o seleccione un valor de búsqueda."
            self.mensaje.visible = True
            self._reconstruir_tabla_reemplazo()
            return

        loader_row_trabajo(self.page, self.loader_reemplazo, self.mensaje, "Buscando coincidencias...")

        def _worker():
            try:
                page_size = 500
                offset = 0
                self._terceros_encontrados = []
                while True:
                    candidatos = self.parent._terceros_uc.obtener_terceros(
                        offset=offset, limit=page_size
                    )[0] or []
                    if not candidatos:
                        break
                    for t in candidatos:
                        visible = self._obtener_valor_visible_campo(t, campo)
                        if campo["tipo"] == "texto":
                            if valor_buscar in visible:
                                self._terceros_encontrados.append(t)
                        elif visible == valor_buscar:
                            self._terceros_encontrados.append(t)
                    if len(candidatos) < page_size:
                        break
                    offset += page_size

                def _actualizar_ui():
                    loader_row_fin(self.page, self.loader_reemplazo)
                    if not self._terceros_encontrados:
                        self.mensaje.value = "No se encontraron terceros para ese valor."
                    else:
                        self.mensaje.value = f"Se encontraron {len(self._terceros_encontrados)} terceros."
                    self.mensaje.visible = True
                    self._pagina_resultados = 0
                    self._actualizar_nav_resultados()
                    self._reconstruir_tabla_reemplazo()
                ejecutar_en_ui(self.page, _actualizar_ui)
            except Exception as ex:
                def _err():
                    loader_row_fin_y_error(
                        self.page,
                        self.loader_reemplazo,
                        self.mensaje,
                        f"Error buscando terceros: {ex}",
                    )
                    self._pagina_resultados = 0
                    self._actualizar_nav_resultados()
                    self._reconstruir_tabla_reemplazo()
                ejecutar_en_ui(self.page, _err)

        self.page.run_thread(_worker)

    def _aplicar_reemplazo(self, e=None):
        campo = self._get_campo_config()
        if campo["tipo"] == "texto":
            buscar = (self.ctrl_buscar.value or "").strip()
            reemplazar = (self.ctrl_reemplazar.value or "").strip()
        else:
            buscar = self.ctrl_buscar.value or ""
            reemplazar = self.ctrl_reemplazar.value or ""

        if not buscar:
            self.mensaje.value = "El valor a buscar no puede estar vacío."
            self.mensaje.visible = True
            self.page.update()
            return

        if not reemplazar:
            self.mensaje.value = "El valor de reemplazo no puede estar vacío."
            self.mensaje.visible = True
            self.page.update()
            return

        if not self._seleccionados_ids:
            self.mensaje.value = "Seleccione al menos un tercero para aplicar el reemplazo."
            self.mensaje.visible = True
            self.page.update()
            return

        loader_row_trabajo(self.page, self.loader_aplicar, self.mensaje, "Aplicando reemplazo...")

        terceros_copia = list(self._terceros_encontrados)
        seleccionados = set(self._seleccionados_ids)

        def _worker():
            aplicados = 0
            for t in terceros_copia:
                identidad = t.get("identidad", "")
                if identidad not in seleccionados:
                    continue
                tercero_mod = dict(t)
                if not self._aplicar_cambio_en_tercero(tercero_mod, campo, buscar, reemplazar):
                    continue
                td_txt = tercero_mod.get("tipodocumento")
                if isinstance(td_txt, str):
                    cod_tipodoc = obtener_codigo_tipodoc(td_txt)
                    tercero_mod["tipodocumento"] = int(cod_tipodoc) if cod_tipodoc else 0
                nat = tercero_mod.get("naturaleza")
                if isinstance(nat, str):
                    tercero_mod["naturaleza"] = 0 if nat == "P. Natural" else 1
                pais_val = tercero_mod.get("pais")
                if isinstance(pais_val, str):
                    cod_pais = obtener_codigo_pais(pais_val)
                    tercero_mod["pais"] = int(cod_pais) if cod_pais else 0
                depto_val = tercero_mod.get("departamento")
                if isinstance(depto_val, str):
                    cod_depto = obtener_codigo_departamento(depto_val, pais_codigo=tercero_mod.get("pais"))
                    tercero_mod["departamento"] = int(cod_depto) if cod_depto else 0
                muni_val = tercero_mod.get("municipio")
                if isinstance(muni_val, str):
                    cod_mun = obtener_codigo_municipio(muni_val, depto_codigo=tercero_mod.get("departamento"))
                    tercero_mod["municipio"] = int(cod_mun) if cod_mun else 0
                res = self.parent._terceros_uc.actualizar_tercero(tercero_mod)
                if res and not (isinstance(res, str) and res.startswith("Error")):
                    aplicados += 1

            def _actualizar_ui():
                loader_row_fin(self.page, self.loader_aplicar)
                if aplicados == 0:
                    self.mensaje.value = "No se aplicó ningún cambio."
                    self.mensaje.color = None
                else:
                    self.mensaje.value = f"Reemplazo aplicado a {aplicados} tercero(s)."
                    self.mensaje.color = ft.Colors.GREEN
                    if hasattr(self.parent, "cargar_terceros"):
                        self.parent.cargar_terceros()
                    self._buscar_coincidencias()
                self.mensaje.visible = True
            ejecutar_en_ui(self.page, _actualizar_ui)

        self.page.run_thread(_worker)

    def _cambiar_pagina_resultados(self, delta: int):
        total = len(self._terceros_encontrados) or 0
        if total == 0:
            return

        max_page = (total - 1) // self._page_size_resultados
        nueva = self._pagina_resultados + delta
        if nueva < 0 or nueva > max_page:
            return

        self._pagina_resultados = nueva
        self._actualizar_nav_resultados()
        self._reconstruir_tabla_reemplazo()
        self.page.update()

    def _actualizar_nav_resultados(self):
        total = len(self._terceros_encontrados) or 0
        if not self.nav_resultados:
            return

        if total <= self._page_size_resultados:
            self.nav_resultados.visible = False
            return

        self.nav_resultados.visible = True
        max_page = (total - 1) // self._page_size_resultados
        # botones: 0 = anterior, 1 = siguiente
        self.nav_resultados.controls[0].visible = not self._pagina_resultados <= 0
        self.nav_resultados.controls[1].visible = not self._pagina_resultados >= max_page

    def _aplicar_cambio_en_tercero(self, tercero_mod, campo, buscar, reemplazar):
        key = campo["key"]
        tipo = campo["tipo"]

        if tipo == "texto":
            actual = str(tercero_mod.get(key) or "")
            # aquí también se respeta exactamente lo que escribe el usuario
            if not actual or buscar not in actual:
                return False
            nuevo = actual.replace(buscar, reemplazar)
            if nuevo == actual:
                return False
            tercero_mod[key] = nuevo
            return True

        # dropdown: igualdad exacta
        visible = self._obtener_valor_visible_campo(tercero_mod, campo)
        if visible != buscar:
            return False

        if key == "tipodocumento":
            # dejamos el texto, se mapea luego
            tercero_mod["tipodocumento"] = reemplazar
        elif key == "naturaleza":
            tercero_mod["naturaleza"] = 0 if reemplazar == "P. Natural" else 1
        elif key == "pais":
            tercero_mod["pais"] = reemplazar
        elif key == "departamento":
            tercero_mod["departamento"] = reemplazar
        elif key == "municipio":
            tercero_mod["municipio"] = reemplazar
        else:
            return False

        return True

    # ==========================================================
    # =============== EVENTOS ==================================
    # ==========================================================
    def _on_pais_change(self, e):
        nuevo_pais = e.control.value
        pais_cod = obtener_codigo_pais(nuevo_pais)
        if pais_cod:
            nuevos_deptos = [d[0] for d in DEPARTAMENTOS.values() if int(d[1]) == int(pais_cod)]
            self.dd_departamento.options = [ft.DropdownOption(key=d, text=d) for d in nuevos_deptos]
            self.dd_departamento.value = ""
            self.dd_municipio.options = []
            self.dd_municipio.value = ""
            self.page.update()

    def _on_departamento_change(self, e):
        nuevo_depto = e.control.value
        cod_pais = obtener_codigo_pais(self.dd_pais.value) if self.dd_pais.value else None
        depto_cod = obtener_codigo_departamento(nuevo_depto, pais_codigo=cod_pais)
        if depto_cod:
            try:
                depto_cod_int = int(depto_cod)
                nuevos_munis = [m[1] for m in MUNICIPIOS.values() if int(m[2]) == depto_cod_int]
                self.dd_municipio.options = [ft.DropdownOption(key=m, text=m) for m in nuevos_munis]
                self.dd_municipio.value = ""
                self.page.update()
            except (ValueError, TypeError):
                pass

    # ==========================================================
    # =============== GUARDAR ==================================
    # ==========================================================
    def guardar(self, codigo):
        # recolectar campos
        identidad = self.dialog.content.controls[0].controls[1].content.value or ""
        tercero_actualizado = {
            "id": codigo,
            "identidad": identidad,
            "tipodocumento": self.dd_documentos.value,
            "naturaleza":self.dialog.content.controls[0].controls[2].content.value or "",
            "digitoverificacion": self.dialog.content.controls[0].controls[3].content.value or "",
            "razonsocial": self.dialog.content.controls[1].controls[0].content.value or "",
            "primerapellido": self.dialog.content.controls[2].controls[0].content.value or "",
            "segundoapellido": self.dialog.content.controls[2].controls[1].content.value or "",
            "primernombre": self.dialog.content.controls[3].controls[0].content.value or "",
            "segundonombre": self.dialog.content.controls[3].controls[1].content.value or "",
            "direccion": self.dialog.content.controls[4].controls[0].content.value or "",
            "pais": self.dd_pais.value,
            "departamento": self.dd_departamento.value,
            "municipio": self.dd_municipio.value,
        }

        # mapear nombres a códigos
        cod_tipodoc = obtener_codigo_tipodoc(tercero_actualizado["tipodocumento"])
        tercero_actualizado["tipodocumento"] = int(cod_tipodoc) if cod_tipodoc else 0
        tercero_actualizado["naturaleza"] = 0 if tercero_actualizado["naturaleza"] == "P. Natural" else 1
        cod_pais = obtener_codigo_pais(tercero_actualizado["pais"])
        tercero_actualizado["pais"] = int(cod_pais) if cod_pais else 0
        cod_depto = obtener_codigo_departamento(tercero_actualizado["departamento"], pais_codigo=cod_pais)
        tercero_actualizado["departamento"] = int(cod_depto) if cod_depto else 0
        cod_mun = obtener_codigo_municipio(tercero_actualizado["municipio"], depto_codigo=cod_depto)
        tercero_actualizado["municipio"] = int(cod_mun) if cod_mun else 0

        # Validación mejorada con error_text
        errores = False
        
        # Identidad: obligatoria y solo dígitos (evita guardar texto en campos numéricos de BD).
        campo_identidad = self.dialog.content.controls[0].controls[1].content
        if not aplicar_validacion_error_text(
            campo_identidad,
            tercero_actualizado["identidad"],
            validar_identidad_documento_numerica,
            nombre_campo="Número de documento",
        ):
            errores = True

        campo_dv = self.dialog.content.controls[0].controls[3].content
        if not aplicar_validacion_error_text(
            campo_dv,
            tercero_actualizado["digitoverificacion"],
            validar_digito_verificacion_opcional,
        ):
            errores = True
        
        # Validar tipo de documento (obligatorio). Dropdown usa error_text en Flet 0.80
        set_campo_error(
            self.dd_documentos,
            "Tipo de documento es obligatorio" if tercero_actualizado["tipodocumento"] == 0 else None,
        )
        if tercero_actualizado["tipodocumento"] == 0:
            errores = True
        
        # Validar razón social (obligatorio)
        campo_razon = self.dialog.content.controls[1].controls[0].content
        if not aplicar_validacion_error_text(campo_razon, tercero_actualizado["razonsocial"], validar_campo_obligatorio, nombre_campo="Razón social"):
            errores = True
        
        if errores:
            actualizar_mensaje_en_control("Revise los campos marcados con error.", self.mensaje, ft.Colors.RED_700)
            if self.dialog:
                self.dialog.update()
            else:
                self.page.update()
            return
        self._set_guardado_ocupado(True, "Guardando tercero...")

        def _worker():
            try:
                if self.modo == "nuevo":
                    ok = self.parent._terceros_uc.crear_tercero(tercero_actualizado)
                else:
                    ok = self.parent._terceros_uc.actualizar_tercero(tercero_actualizado)
            except Exception as ex:
                ok = f"Error: {ex}"

            def _ui():
                # Cerrar el diálogo siempre
                if self.dialog:
                    self.page.pop_dialog()

                # Buscar parent con snackbar (puede ser directo o a través de TrabajoDialog)
                def obtener_parent_snackbar():
                    p = self.parent
                    while p:
                        if hasattr(p, 'mostrar_mensaje'):
                            return p
                        p = getattr(p, 'parent', None)
                    return None

                parent_snackbar = obtener_parent_snackbar()

                # Determinar mensaje y color
                if ok and isinstance(ok, str) and ok.startswith("Error"):
                    mensaje, color = ok, ft.Colors.RED_300
                elif ok:
                    mensaje, color = ok, ft.Colors.GREEN_300
                    # Refrescar tabla para que se vean los cambios de inmediato (síncrono)
                    if hasattr(self.parent, 'actualizar_tercero_editado'):
                        self.parent.actualizar_tercero_editado()
                    elif hasattr(self.parent, 'refrescar_tabla_desde_bd'):
                        self.parent.refrescar_tabla_desde_bd()
                    elif hasattr(self.parent, 'cargar_terceros'):
                        self.parent.cargar_terceros()
                else:
                    mensaje, color = "No se pudo guardar el tercero.", ft.Colors.RED_300

                # Mostrar mensaje
                if parent_snackbar:
                    parent_snackbar.mostrar_mensaje(mensaje, 5000, color=color)
                else:
                    actualizar_mensaje_en_control(mensaje, self.mensaje, color)

                self._set_guardado_ocupado(False)
                self.page.update()

            ejecutar_en_ui(self.page, _ui)

        self.page.run_thread(_worker)

    def _set_guardado_ocupado(self, ocupado: bool, texto_loader: str = "Guardando tercero..."):
        """Controla el estado de guardado para evitar doble submit y mostrar feedback."""
        if self.loader_guardado:
            if self.loader_guardado.controls and len(self.loader_guardado.controls) > 1:
                self.loader_guardado.controls[1].value = texto_loader
            self.loader_guardado.visible = ocupado
        if self._btn_guardar:
            self._btn_guardar.disabled = ocupado
        if self._btn_cancelar:
            self._btn_cancelar.disabled = ocupado
        if self.dialog:
            self.dialog.update()

    # ==========================================================
    # =============== DIALOGO DIVIDIR NOMBRES =================
    # ==========================================================
    def _build_dialogo_dividir_nombres(self, terceros):
        ordenes = [
            "Nombre1 Nombre2 Apellido1 Apellido2", "Apellido1 Apellido2 Nombre1 Nombre2",
            "Nombre1 Nombre2 Apellido1",  "Apellido1 Nombre1 Nombre2",
            "Nombre1 Apellido1 Apellido2", "Apellido1 Apellido2 Nombre1",
        ]
        
        self.dd_orden = DropdownCompact(
            label="Orden de los nombres",
            options=[ft.DropdownOption(key=o, text=o) for o in ordenes],
            width=300,
        )
        
        cuerpo = ft.Column(
            spacing=12,
            controls=[
                ft.Text("Dividir nombres", size=16, weight=ft.FontWeight.BOLD),
                ft.Text(f"Se dividirán {len(terceros)} tercero(s) según el orden seleccionado.", size=12),
                self.dd_orden,
                self.mensaje,
            ],
            tight=True,
        )
        
        self.dialog = ft.AlertDialog(
            title=None,
            content=ft.Container(width=400, content=cuerpo, padding=10),
            bgcolor=WHITE,
            modal=True,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(content="Cancelar", on_click=self.cerrar_dialog, style=BOTON_SECUNDARIO_SIN),
                ft.Button(
                    content="Aplicar",
                    icon=ft.Icons.CHECK,
                    on_click=lambda e: self._aplicar_dividir_nombres(terceros),
                    style=BOTON_PRINCIPAL,
                ),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )
        self.page.show_dialog(self.dialog)

    def _aplicar_dividir_nombres(self, terceros):
        orden = self.dd_orden.value
        if not orden:
            self.mensaje.value = "Seleccione un orden."
            self.mensaje.visible = True
            self.page.update()
            return
        
        partes_orden = orden.split()
        aplicados = 0
        
        for t in terceros:
            razon = (t.get("razonsocial") or "").strip()
            if not razon:
                continue
            palabras = razon.split()
            # if len(palabras) < len(partes_orden):
            #     continue
            
            tercero_mod = dict(t)
            for i, parte in enumerate(partes_orden):
                if i < len(palabras):
                    if parte == "Nombre1":
                        tercero_mod["primernombre"] = palabras[i]
                    elif parte == "Nombre2":
                        tercero_mod["segundonombre"] = palabras[i]
                    elif parte == "Apellido1":
                        tercero_mod["primerapellido"] = palabras[i]
                    elif parte == "Apellido2":
                        tercero_mod["segundoapellido"] = palabras[i]
            
            # mapear tipo documento si es string
            td_txt = tercero_mod.get("tipodocumento")
            cod_tipodoc = obtener_codigo_tipodoc(td_txt)
            tercero_mod["tipodocumento"] = int(cod_tipodoc) if cod_tipodoc else 0
            res = self.parent._terceros_uc.actualizar_tercero(tercero_mod)
            if res and not (isinstance(res, str) and res.startswith("Error")):
                aplicados += 1
        
        if aplicados == 0:
            self.mensaje.value = "No se aplicó ningún cambio."
        else:
            self.mensaje.value = f"Nombres divididos en {aplicados} tercero(s)."
            self.parent.cargar_terceros()
        
        self.mensaje.visible = True
        self.page.update()

    # ==========================================================
    def cerrar_dialog(self, e=None):
        self.page.pop_dialog()
        self.mensaje.visible = False
        self.dialog = None
        
        if hasattr(self.parent, 'dialog_trabajo_guardado') and self.parent.dialog_trabajo_guardado:
            if hasattr(self.parent, "_set_apertura_tercero_ocupada"):
                self.parent._set_apertura_tercero_ocupada(False)
            self.page.show_dialog(self.parent.dialog_trabajo_guardado)
            self.page.update()

