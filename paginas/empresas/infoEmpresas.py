import flet as ft
from core import session
from core.catalogues import PAISES, DEPARTAMENTOS, MUNICIPIOS, obtener_nombre_pais, obtener_nombre_departamento, obtener_nombre_municipio, obtener_codigo_pais, obtener_codigo_departamento, obtener_codigo_municipio
from ui.colors import PINK_200, PINK_600, GREY_700, WHITE
from ui.snackbars import mostrar_mensaje
from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from ui.dropdowns import DropdownCompact


class InfoEmpresasDialog:
    def __init__(self, page, container):
        self.page = page
        self._empresas_uc = container.empresas_uc
        self.dialog_empresa = None
        self.dd_pais = None
        self.dd_departamento = None
        self.dd_municipio = None
        self.tf_direccion = None
        self._identidad_actual = None

    def open_dialog(self):
        data = self._empresas_uc.obtener_info_empresa(
            session.EMPRESA_ACTUAL["producto"], session.EMPRESA_ACTUAL["codigo"]
        )
        if not data:
            mostrar_mensaje(self.page, "No se pudo cargar la información de la empresa.", 5000)
            return

        def tf(label, key=None, disabled=False, options=None, on_change=None):
            val = data.get(key)
            if val is None or val == "" or val == 0:
                val = ""
            if key == "pais" and val != "":
                val = obtener_nombre_pais(val) or val
            elif key == "departamento" and val != "":
                val = obtener_nombre_departamento(val) or val
            elif key == "municipio" and val != "":
                val = obtener_nombre_municipio(val, data.get("departamento")) or val

            if options is not None:
                return DropdownCompact(
                    label=label,
                    value=val,
                    options=[ft.DropdownOption(key=o, text=o) for o in options],
                    on_select=on_change,
                    expand=True,
                )
            else:
                return ft.TextField(
                    label=label,
                    value=val or "",
                    disabled=disabled,
                    border_color=PINK_200,
                    label_style=ft.TextStyle(color=GREY_700),
                )

        self._identidad_actual = data.get("identidad") or ""
        # Campos base
        codigo = tf(f"Código en {session.EMPRESA_ACTUAL['producto']}", "codigo", disabled=True)
        identidad = tf("Identidad", "identidad", disabled=True)
        direccion = tf("Dirección", "direccion")
        self.tf_direccion = direccion

        paises = [p for p in PAISES.values()]
        self.dd_pais = tf("País", "pais", options=paises, on_change=self._on_pais_change)

        pais_cod = data.get("pais")
        if pais_cod is not None and pais_cod != "" and pais_cod != 0:
            try:
                pais_cod_int = int(pais_cod)
                depto_inicial = [d[0] for d in DEPARTAMENTOS.values() if int(d[1]) == pais_cod_int]
            except (ValueError, TypeError):
                depto_inicial = []
        else:
            depto_inicial = []
        self.dd_departamento = tf("Departamento", "departamento", options=depto_inicial, on_change=self._on_departamento_change)
        
        depto_cod = data.get("departamento")
        if depto_cod is not None and depto_cod != "" and depto_cod != 0:
            try:
                depto_cod_int = int(depto_cod)
                munis_inicial = [m[1] for m in MUNICIPIOS.values() if int(m[2]) == depto_cod_int]
            except (ValueError, TypeError):
                munis_inicial = []
        else:
            munis_inicial = []
        # En la app se maneja como municipio
        self.dd_municipio = tf("Municipio", "municipio", options=munis_inicial)

        form = ft.Column(
            spacing=10,
            controls=[
                ft.Row([ft.Container(codigo, expand=1), ft.Container(identidad, expand=1)]),
                ft.Row([ft.Container(direccion, expand=1), ft.Container(self.dd_pais, expand=1)]),
                ft.Row([ft.Container(self.dd_departamento, expand=1), ft.Container(self.dd_municipio, expand=1)]),
            ],
            tight=True,
        )

        # Construir y abrir el diálogo (sin devolverlo)
        self.dialog_empresa = ft.AlertDialog(
            title=ft.Text(f"Modificar datos de la empresa • {data.get('nombre','')}", text_align=ft.TextAlign.CENTER),
            content=ft.Container(content=form, width=520),
            bgcolor=WHITE,
            modal=True,
            shadow_color=PINK_200,
            elevation=15,
            shape=ft.RoundedRectangleBorder(radius=12),
            actions=[
                ft.TextButton(content="Cancelar", on_click=self.close_dialog, style=BOTON_SECUNDARIO_SIN),
                ft.ElevatedButton("Guardar", on_click=self._guardar, style=BOTON_PRINCIPAL),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        )

        self.page.show_dialog(self.dialog_empresa)
    # -------------------- Eventos -------------------
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

    def _guardar(self, e=None):
        """Persiste dirección y ubicación (país, departamento, municipio) en la BD central."""
        if not self._identidad_actual:
            return
        try:
            direccion = (self.tf_direccion.value or "").strip() or None
            pais_nombre = (self.dd_pais.value or "").strip()
            depto_nombre = (self.dd_departamento.value or "").strip()
            muni_nombre = (self.dd_municipio.value or "").strip()
            codigo_pais = obtener_codigo_pais(pais_nombre) if pais_nombre else None
            codigo_depto = obtener_codigo_departamento(depto_nombre, pais_codigo=codigo_pais) if depto_nombre else None
            codigo_ciudad = obtener_codigo_municipio(muni_nombre, depto_codigo=codigo_depto) if muni_nombre else None
            ok = self._empresas_uc.actualizar_info_empresa(
                self._identidad_actual, direccion,
                codigo_ciudad, codigo_depto, codigo_pais
            )
            self.close_dialog()
            mostrar_mensaje(
                self.page,
                "Información guardada correctamente." if ok else "No se pudo guardar.",
                3000,
                color=PINK_200 if ok else PINK_600,
            )
        except Exception as ex:
            self.close_dialog()
            mostrar_mensaje(self.page, f"Error: {ex}", 5000, color=PINK_600)

    def close_dialog(self, e=None):
        if self.dialog_empresa:
            self.page.pop_dialog()
