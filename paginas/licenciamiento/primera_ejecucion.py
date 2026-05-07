"""Gating de primera ejecución: condiciones de uso + clave de activación."""

from typing import Callable

import flet as ft

from ui.buttons import BOTON_PRINCIPAL, BOTON_SECUNDARIO_SIN
from ui.colors import PINK_200, WHITE
from ui.fields import creador_campo_texto
from utils.validators import set_campo_error


def _cerrar_app(page: ft.Page) -> None:
    """Cierra la ventana sin warnings de coroutine no awaited."""
    page.run_task(page.window.close)


def _mostrar_error_permisos_admin(page: ft.Page) -> None:
    """Informa que el flujo de licencia requiere permisos de administrador (HKLM)."""
    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Permisos insuficientes"),
            content=ft.Text(
                "No fue posible guardar la activación de licencia en el registro de Windows.\n"
                "Ejecute la aplicación como administrador e intente nuevamente."
            ),
            actions=[ft.Button(content="Cerrar", on_click=lambda _: _cerrar_app(page), style=BOTON_PRINCIPAL)],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
        )
    )
    page.update()


def _texto_condiciones_uso() -> str:
    """Texto legal previo al flujo de activación de clave."""
    base = (
        "Importante. Al iniciar el producto, el sistema despliega las Condiciones de Uso "
        "que deben ser leídas cuidadosamente. En caso de presentar inconformidades con las "
        "condiciones, comuníquese con PROASISTEMAS S.A.\n\n"
    )
    medio = (
        "Para confirmar las condiciones presione el botón Aceptar. Al hacerlo, el sistema "
        "desplegará la interfaz de Activación, donde deberá digitar la Clave de Activación "
        "obtenida en la adquisición del producto.\n\n"
    )
    cierre = (
        "La activación de empresas dentro del módulo es un proceso definitivo e irreversible. "
        "Una vez registrada y activada, la empresa quedará asociada de forma permanente a la "
        "licencia."
    )
    return base + medio + cierre


def ejecutar_si_corresponde(
    page: ft.Page,
    app,
    on_complete: Callable[[], None],
) -> None:
    """Encadena términos -> clave -> activación de empresas antes de habilitar login."""
    uc = app.container.licenciamiento_uc
    licencia_actual = uc.obtener_licencia()
    if licencia_actual and len(licencia_actual.empresas_activadas) > 0:
        on_complete()
        return

    # Si ya existe licencia (clave/cupo guardados) pero no hay empresas activadas,
    # se debe retomar directamente el paso de activación de empresas.
    if licencia_actual and len(licencia_actual.empresas_activadas) == 0:
        mostrar_activacion_empresas_pre_login(page, app, on_complete)
        return

    def _luego_condiciones() -> None:
        _mostrar_dialogo_clave(
            page,
            uc,
            lambda: mostrar_activacion_empresas_pre_login(page, app, on_complete),
        )

    if uc.condiciones_aceptadas():
        _luego_condiciones()
    else:
        _mostrar_dialogo_condiciones(page, uc, _luego_condiciones)


def _mostrar_dialogo_condiciones(page: ft.Page, uc, on_accept: Callable[[], None]) -> None:
    """Muestra el texto de Condiciones de Uso; cancelar cierra la app."""

    def cancelar(_: ft.ControlEvent) -> None:
        page.pop_dialog()
        _cerrar_app(page)

    def aceptar(_: ft.ControlEvent) -> None:
        try:
            uc.aceptar_condiciones()
        except PermissionError:
            page.pop_dialog()
            _mostrar_error_permisos_admin(page)
            return
        page.pop_dialog()
        on_accept()

    contenido = ft.Container(
        width=520,
        height=320,
        content=ft.Column(
            controls=[ft.Text(_texto_condiciones_uso(), size=12)],
            scroll=ft.ScrollMode.AUTO,
        ),
    )

    dialog = ft.AlertDialog(
        title=ft.Text("Condiciones de Uso", text_align=ft.TextAlign.CENTER),
        content=contenido,
        actions=[
            ft.TextButton(content="Cancelar", on_click=cancelar, style=BOTON_SECUNDARIO_SIN),
            ft.Button(content="Aceptar", on_click=aceptar, style=BOTON_PRINCIPAL),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=WHITE,
        modal=True,
        shadow_color=PINK_200,
        elevation=15,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    page.show_dialog(dialog)
    page.update()


def _mostrar_dialogo_clave(page: ft.Page, uc, on_activated: Callable[[], None]) -> None:
    """Captura la clave; si es válida confirma con un mensaje y avanza."""
    campo = creador_campo_texto("Clave de Activación", ["focus"])

    def activar(_: ft.ControlEvent) -> None:
        clave = (campo.value or "").strip()
        if not clave:
            set_campo_error(campo, "Ingrese la clave de activación")
            return
        try:
            licencia = uc.activar_licencia(clave)
        except PermissionError:
            page.pop_dialog()
            _mostrar_error_permisos_admin(page)
            return
        if licencia is None:
            set_campo_error(campo, "Clave de instalación no válida")
            return
        page.pop_dialog()
        on_activated()

    contenido = ft.Container(
        width=380,
        content=ft.Column(
            controls=[
                ft.Text(
                    "El producto de Información Exógena no se encuentra registrado.\n"
                    "Si ya posee la clave de activación, ingrésela ahora.",
                    size=12,
                ),
                campo,
            ],
            tight=True,
            spacing=12,
        ),
    )

    dialog = ft.AlertDialog(
        title=ft.Text("Activar producto", text_align=ft.TextAlign.CENTER),
        content=contenido,
        actions=[ft.Button(content="Activar", on_click=activar, style=BOTON_PRINCIPAL)],
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=WHITE,
        modal=True,
        shadow_color=PINK_200,
        elevation=15,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    page.show_dialog(dialog)
    page.update()


def _mostrar_dialogo_exito(page: ft.Page, on_close: Callable[[], None]) -> None:
    """Confirmación final tras activación definitiva de licencia+empresas."""

    def cerrar(_: ft.ControlEvent) -> None:
        page.pop_dialog()
        on_close()

    dialog = ft.AlertDialog(
        title=ft.Text("Información", text_align=ft.TextAlign.CENTER),
        content=ft.Text("Licencia activada con éxito."),
        actions=[ft.Button(content="Aceptar", on_click=cerrar, style=BOTON_PRINCIPAL)],
        actions_alignment=ft.MainAxisAlignment.END,
        bgcolor=WHITE,
        modal=True,
        shadow_color=PINK_200,
        elevation=15,
        shape=ft.RoundedRectangleBorder(radius=12),
    )
    page.show_dialog(dialog)
    page.update()


def mostrar_activacion_empresas_pre_login(
    page: ft.Page,
    app,
    on_complete: Callable[[], None],
) -> None:
    """
    Flujo posterior a clave de activación y previo al login:
    lista empresas de productos licenciados y obliga activación mínima.
    """
    uc = app.container.licenciamiento_uc
    licencia = uc.obtener_licencia()
    if not licencia:
        on_complete()
        return

    container = app.container
    productos_licencia = {
        producto.strip().upper()
        for producto in str(licencia.producto or "").split(",")
        if producto.strip()
    }
    empresas = []
    if "NI" in productos_licencia:
        for empresa in container.empresas_uc.obtener_empresas("NI"):
            empresas.append(
                {
                    "producto": "NI",
                    "codigo": int(empresa["codigo"]),
                    "nombre": str(empresa["nombre"]),
                }
            )
    if "PH" in productos_licencia:
        for empresa in container.empresas_uc.obtener_empresas("PH"):
            empresas.append(
                {
                    "producto": "PH",
                    "codigo": int(empresa["codigo"]),
                    "nombre": str(empresa["nombre"]),
                }
            )

    if not empresas:
        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("No hay empresas disponibles"),
                content=ft.Text(
                    "No fue posible listar empresas de los productos seleccionados.\n"
                    "Verifique configuración de Helisa (llaves de registro y credenciales Firebird)."
                ),
                actions=[
                    ft.Button(content="Cerrar", on_click=lambda _: _cerrar_app(page), style=BOTON_PRINCIPAL),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                modal=True,
            )
        )
        page.update()
        return

    empresas.sort(key=lambda x: (x["producto"], x["nombre"]))
    header = ft.Text("", size=12, weight=ft.FontWeight.W_600)
    listado = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, height=320)
    lic_base = uc.obtener_licencia()
    activas_permanentes = set(lic_base.empresas_activadas if lic_base else [])
    seleccion_temporal = set(activas_permanentes)

    def refrescar() -> None:
        lic = uc.obtener_licencia()
        if not lic:
            return
        cupo_total = int(lic.limite_empresas)
        ocupadas = len(seleccion_temporal)
        cupos = max(cupo_total - ocupadas, 0)
        header.value = (
            f"Empresas seleccionadas: {ocupadas} de {cupo_total}. "
            f"Cupos disponibles: {cupos}."
        )
        listado.controls = []
        for emp in empresas:
            clave = lic.clave_empresa(emp["producto"], emp["codigo"])
            es_permanente = clave in activas_permanentes
            seleccionada = clave in seleccion_temporal

            def _toggle(_: ft.ControlEvent, empresa_actual=emp) -> None:
                lic_local = uc.obtener_licencia()
                if not lic_local:
                    return
                clave_empresa = lic_local.clave_empresa(
                    empresa_actual["producto"], empresa_actual["codigo"]
                )
                if clave_empresa in activas_permanentes:
                    return
                if clave_empresa in seleccion_temporal:
                    seleccion_temporal.remove(clave_empresa)
                    refrescar()
                    return
                if len(seleccion_temporal) >= int(lic_local.limite_empresas):
                    return
                seleccion_temporal.add(clave_empresa)
                refrescar()

            listado.controls.append(
                ft.Row(
                    controls=[
                        ft.Text(f"[{emp['producto']}] {emp['codigo']} - {emp['nombre']}", expand=True),
                        ft.TextButton(
                            content="Activada" if es_permanente else ("Desactivar" if seleccionada else "Activar"),
                            disabled=es_permanente,
                            on_click=_toggle,
                        ),
                    ]
                )
            )
        if listado.page:
            listado.update()
        if header.page:
            header.update()

    def confirmar_y_activar(_: ft.ControlEvent) -> None:
        lic = uc.obtener_licencia()
        if not lic:
            return
        nuevas = [
            clave_empresa
            for clave_empresa in seleccion_temporal
            if clave_empresa not in activas_permanentes
        ]
        if len(seleccion_temporal) == 0:
            return

        def cancelar(_: ft.ControlEvent) -> None:
            page.pop_dialog()

        def aceptar(_: ft.ControlEvent) -> None:
            ok = True
            for key in nuevas:
                prod, cod = key.split(":")
                try:
                    if not uc.activar_empresa(prod, int(cod)):
                        ok = False
                        break
                except PermissionError:
                    page.pop_dialog()
                    _mostrar_error_permisos_admin(page)
                    return
            page.pop_dialog()
            if not ok:
                return
            page.pop_dialog()
            _mostrar_dialogo_exito(page, on_complete)

        page.show_dialog(
            ft.AlertDialog(
                title=ft.Text("¡Advertencia!"),
                content=ft.Text(
                    "La activación de las empresas seleccionadas será definitiva e irreversible.\n\n"
                    "¿Confirma activar las empresas seleccionadas?"
                ),
                actions=[
                    ft.TextButton(content="Cancelar", on_click=cancelar, style=BOTON_SECUNDARIO_SIN),
                    ft.Button(content="Aceptar", on_click=aceptar, style=BOTON_PRINCIPAL),
                ],
                actions_alignment=ft.MainAxisAlignment.END,
                modal=True,
            )
        )
        page.update()

    page.show_dialog(
        ft.AlertDialog(
            title=ft.Text("Activación de empresas"),
            content=ft.Container(width=700, content=ft.Column([header, listado], spacing=10)),
            actions=[ft.Button(content="Activar", on_click=confirmar_y_activar, style=BOTON_PRINCIPAL)],
            actions_alignment=ft.MainAxisAlignment.END,
            modal=True,
            bgcolor=WHITE,
            shadow_color=PINK_200,
            elevation=12,
        )
    )
    refrescar()
    page.update()
