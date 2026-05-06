import flet as ft
from core import session
from core.catalogues import (
    PAISES,
    DEPARTAMENTOS,
    MUNICIPIOS,
    obtener_nombre_pais,
    obtener_nombre_departamento,
    obtener_nombre_municipio,
    obtener_codigo_pais,
    obtener_codigo_departamento,
    obtener_codigo_municipio,
)
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

    @staticmethod
    def _valor_inicial_campo(data: dict, key: str) -> object:
        val = data.get(key)
        if val is None or val == "" or val == 0:
            return ""
        if key == "pais":
            return obtener_nombre_pais(val) or val
        if key == "departamento":
            return obtener_nombre_departamento(val) or val
        if key == "municipio":
            return obtener_nombre_municipio(val, data.get("departamento")) or val
        return val

    def _control_campo(
        self,
        data: dict,
        label: str,
        key: str | None = None,
        *,
        disabled: bool = False,
        options=None,
        on_change=None,
    ):
        val = self._valor_inicial_campo(data, key) if key else ""
        if options is not None:
            return DropdownCompact(
                label=label,
                value=val,
                options=[ft.DropdownOption(key=o, text=o) for o in options],
                on_select=on_change,
                expand=True,
            )
        return ft.TextField(
            label=label,
            value=val or "",
            disabled=disabled,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
        )

    @staticmethod
    def _lista_departamentos_por_codigo_pais(pais_cod) -> list:
        if pais_cod is None or pais_cod in ("", 0):
            return []
        try:
            pais_cod_int = int(pais_cod)
        except (ValueError, TypeError):
            return []
        return [d[0] for d in DEPARTAMENTOS.values() if int(d[1]) == pais_cod_int]

    @staticmethod
    def _lista_municipios_por_codigo_depto(depto_cod) -> list:
        if depto_cod is None or depto_cod in ("", 0):
            return []
        try:
            depto_cod_int = int(depto_cod)
        except (ValueError, TypeError):
            return []
        return [m[1] for m in MUNICIPIOS.values() if int(m[2]) == depto_cod_int]

    def _construir_formulario(self, data: dict) -> ft.Column:
        producto = session.EMPRESA_ACTUAL["producto"]
        codigo = self._control_campo(data, f"Código en {producto}", "codigo", disabled=True)
        identidad = self._control_campo(data, "Identidad", "identidad", disabled=True)
        direccion = self._control_campo(data, "Dirección", "direccion")
        self.tf_direccion = direccion

        paises = list(PAISES.values())
        self.dd_pais = self._control_campo(
            data, "País", "pais", options=paises, on_change=self._on_pais_change
        )
        depto_inicial = self._lista_departamentos_por_codigo_pais(data.get("pais"))
        self.dd_departamento = self._control_campo(
            data,
            "Departamento",
            "departamento",
            options=depto_inicial,
            on_change=self._on_departamento_change,
        )
        munis_inicial = self._lista_municipios_por_codigo_depto(data.get("departamento"))
        self.dd_municipio = self._control_campo(data, "Municipio", "municipio", options=munis_inicial)

        return ft.Column(
            spacing=10,
            controls=[
                ft.Row([ft.Container(codigo, expand=1), ft.Container(identidad, expand=1)]),
                ft.Row([ft.Container(direccion, expand=1), ft.Container(self.dd_pais, expand=1)]),
                ft.Row([ft.Container(self.dd_departamento, expand=1), ft.Container(self.dd_municipio, expand=1)]),
            ],
            tight=True,
        )

    def _alert_info_empresa(self, form: ft.Column, nombre: str) -> ft.AlertDialog:
        return ft.AlertDialog(
            title=ft.Text(
                f"Modificar datos de la empresa • {nombre}",
                text_align=ft.TextAlign.CENTER,
            ),
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

    def open_dialog(self):
        data = self._empresas_uc.obtener_info_empresa(
            session.EMPRESA_ACTUAL["producto"],
            session.EMPRESA_ACTUAL["codigo"],
        )
        if not data:
            mostrar_mensaje(self.page, "No se pudo cargar la información de la empresa.", 5000)
            return

        self._identidad_actual = data.get("identidad") or ""
        form = self._construir_formulario(data)
        self.dialog_empresa = self._alert_info_empresa(form, data.get("nombre", ""))
        self.page.show_dialog(self.dialog_empresa)

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
        if not depto_cod:
            return
        try:
            depto_cod_int = int(depto_cod)
            nuevos_munis = [m[1] for m in MUNICIPIOS.values() if int(m[2]) == depto_cod_int]
            self.dd_municipio.options = [ft.DropdownOption(key=m, text=m) for m in nuevos_munis]
            self.dd_municipio.value = ""
            self.page.update()
        except (ValueError, TypeError):
            pass

    @staticmethod
    def _codigos_ubicacion_desde_form(pais_nombre: str, depto_nombre: str, muni_nombre: str):
        codigo_pais = obtener_codigo_pais(pais_nombre) if pais_nombre else None
        codigo_depto = (
            obtener_codigo_departamento(depto_nombre, pais_codigo=codigo_pais) if depto_nombre else None
        )
        codigo_ciudad = (
            obtener_codigo_municipio(muni_nombre, depto_codigo=codigo_depto) if muni_nombre else None
        )
        return codigo_pais, codigo_depto, codigo_ciudad

    def _guardar(self, e=None):
        """Persiste dirección y ubicación (país, departamento, municipio) en la BD central."""
        if not self._identidad_actual:
            return
        try:
            direccion = (self.tf_direccion.value or "").strip() or None
            pais_nombre = (self.dd_pais.value or "").strip()
            depto_nombre = (self.dd_departamento.value or "").strip()
            muni_nombre = (self.dd_municipio.value or "").strip()
            codigo_pais, codigo_depto, codigo_ciudad = self._codigos_ubicacion_desde_form(
                pais_nombre, depto_nombre, muni_nombre
            )
            ok = self._empresas_uc.actualizar_info_empresa(
                self._identidad_actual,
                direccion,
                codigo_ciudad,
                codigo_depto,
                codigo_pais,
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
