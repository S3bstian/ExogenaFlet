"""
Dropdown compacto que envuelve ft.Dropdown nativo.
Usa content_padding para alinear el texto con el borde, igual que TextField.
Compatible con Flet 0.81+.
"""
import flet as ft
from ui.colors import PINK_200, GREY_700, FONDO_PAGINA


def _opt_key(opt) -> str:
    return getattr(opt, "key", str(opt))


class DropdownCompact(ft.Column):
    """
    Wrapper de ft.Dropdown con estilo compacto y texto alineado al borde.
    API compatible: value, options, on_select.
    """

    def __init__(
        self,
        label: str | None = None,
        value=None,
        options: list | None = None,
        width: float | None = None,
        expand: bool | int | None = None,
        on_select=None,
        tooltip: str | None = None,
        disabled: bool = False,
    ):
        self.label = label or ""
        self._value = str(value) if value not in (None, "") else None
        self._options = list(options or [])
        self._on_select = on_select
        self._width = width
        self._expand = expand
        self._tooltip = tooltip or ""
        self._disabled = disabled
        self._dropdown_ref = ft.Ref[ft.Dropdown]()
        self._wrap_ref = ft.Ref[ft.Container]()

        label_control = (
            ft.Text(
                (label or "").strip(),
                color=GREY_700,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
            )
            if label
            else None
        )

        dd = ft.Dropdown(
            ref=self._dropdown_ref,
            label=label_control,
            value=self._value,
            options=self._options,
            on_select=self._handle_select,
            border_color=PINK_200,
            label_style=ft.TextStyle(color=GREY_700),
            text_style=ft.TextStyle(color=GREY_700),
            content_padding=ft.padding.only(left=10, right=12, top=12, bottom=12),
            tooltip=self._tooltip,
            disabled=self._disabled,
            border_radius=8,
            height=48,
            dense=True,
        )
        wrap = ft.Container(
            ref=self._wrap_ref,
            content=dd,
            width=self._width,
            expand=self._expand,
            opacity=0.6 if self._disabled else 1.0,
        )
        super().__init__(controls=[wrap], spacing=4, tight=True, expand=self._expand)

    def _handle_select(self, e):
        self._value = e.control.value
        if self._on_select:
            self._on_select(e)

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self, v):
        self._value = str(v) if v not in (None, "") else None
        d = self._dropdown_ref.current
        if d:
            d.value = self._value
        page = getattr(self, "page", None)
        if page is not None:
            page.update()

    @property
    def options(self):
        return self._options

    @options.setter
    def options(self, opts):
        self._options = list(opts or [])
        d = self._dropdown_ref.current
        if d:
            d.options = self._options
        page = getattr(self, "page", None)
        if page is not None:
            page.update()

    @property
    def disabled(self):
        return self._disabled

    @disabled.setter
    def disabled(self, v):
        self._disabled = bool(v)
        d = self._dropdown_ref.current
        if d:
            d.disabled = self._disabled
        wrap = self._wrap_ref.current
        if wrap:
            wrap.opacity = 0.6 if self._disabled else 1.0
        page = getattr(self, "page", None)
        if page is not None:
            page.update()
