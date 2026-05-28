import io
from os import device_encoding
import re
from PyQt6 import (
    QtGui as qg,
    QtWidgets as qw,
    QtCore as qc
)
from matplotlib.figure import Figure
from matplotlib.backends.backend_agg import FigureCanvasAgg

class LatexLabel(qw.QLabel):
    """
    QLabel that auto-renders LaTeX when text is surrounded by dollar signs.
    Examples that trigger math rendering:
        "$x^2 + y^2 = 1$"
        "$\\frac{a}{b}$", "$\\alpha$", "$\\sum_{i=1}^n i$"
    Otherwise, it behaves like a normal QLabel.

    Notes:
    - Uses Matplotlib mathtext (no system LaTeX required).
    - Respects the label's current font size.
    - HiDPI-aware.
    """
    _MATH_PATTERN = re.compile(r"^\s*\$(?P<formula>.*)\$\s*$", re.DOTALL)

    def __init__(self, parent=None, math_dpi=200, cache=True, base_point_size= 15.0, math_scale= 0.5):
        super().__init__(parent)
        self._base_point_size = float(base_point_size)
        self._math_scale = float(math_scale)
        self._math_dpi = int(math_dpi)
        self._cache_enabled = cache
        self._cache = {}  # key: (formula, pointSizeF, dpi*ratio) -> QPixmap
        self._last_text = ""
        self._render_failed = False

        # So pixmaps size the label sensibly
        self.setScaledContents(False)
        font = self.font()
        font.setPointSizeF(self._base_point_size)
        self.setFont(font)

    def set_base_point_size(self, size: float) -> None:
        self._base_point_size = float(size)
        font = self.font()
        font.setPointSizeF(self._base_point_size)
        self.setFont(font)
        if self._last_text:
            self.setText(self._last_text)

    def set_math_scale(self, scale: float) -> None:
        self._math_scale = float(scale)
        if self._last_text:
            self.setText(self._last_text)

    def setText(self, a0: str | None) -> None:
        self._last_text = a0 if a0 is not None else ""
        m = self._MATH_PATTERN.match(self._last_text)

        # always keep the Qt font synced to the base size
        font = self.font()
        font.setPointSizeF(self._base_point_size)
        self.setFont(font)

        if not m:
            # Non-math: behave like a normal QLabel
            self.clear()  # avoid stale pixmap
            self._render_failed = False
            super().setText(self._last_text)
            return
            # return super().setText(self._last_text)

        # Math: render with Matplotlib
        formula = m.group("formula")
        try:
            pix = self._render_formula_to_pixmap(formula)
        except Exception:
            # Graceful fallback on any rendering error
            self._render_failed = True
            return super().setText(self._last_text)

        self._render_failed = False
        super().setText("")  # clear text so only the pixmap shows
        self.setPixmap(pix)

    # def _render_formula_to_pixmap(self, formula: str) -> qg.QPixmap:
    #     # Use label's font size for consistent sizing
    #     point_size = self.font().pointSizeF()
    #     if point_size <= 0:
    #         # Sensible default if font has pixel size only
    #         point_size = 12.0

    #     # HiDPI handling: scale dpi by device ratio, and tell Qt the ratio.
    #     screen: qg.QScreen = self.window().windowHandle().screen() if self.window() and self.window().windowHandle() else None
    #     ratio = float(screen.devicePixelRatio()) if screen else 1.0
    #     effective_dpi = int(self._math_dpi * ratio)

    #     cache_key = (formula, round(point_size, 2), effective_dpi)
    #     if self._cache_enabled and cache_key in self._cache:
    #         # Cached pixmap already has the devicePixelRatio set
    #         return self._cache[cache_key]

    #     # Render once to get the tight bounding box
    #     fig = Figure(figsize=(0.01, 0.01), dpi=effective_dpi)
    #     canvas = FigureCanvasAgg(fig)

    #     # Add the text and draw
    #     text_artist = fig.text(0, 0, f"${formula}$", fontsize=point_size)
    #     canvas.draw()
    #     renderer = canvas.get_renderer()
    #     bbox = text_artist.get_window_extent(renderer=renderer)

    #     # Convert bbox size to inches and resize the figure to fit the math tightly
    #     width_in = bbox.width / effective_dpi
    #     height_in = bbox.height / effective_dpi
    #     fig.set_size_inches(max(width_in, 1e-3), max(height_in, 1e-3))

    #     # Move text to the lower-left corner of the new (tight) canvas
    #     text_artist.set_position((0, 0))
    #     fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    #     canvas.draw()

    #     # Save to PNG bytes (transparent background looks nicest on labels)
    #     buf = io.BytesIO()
    #     fig.savefig(buf, format="png", dpi=effective_dpi, transparent=True, bbox_inches="tight", pad_inches=0)
    #     buf.seek(0)

    #     pix = qg.QPixmap()
    #     pix.loadFromData(buf.getvalue(), "PNG")

    #     # Tell Qt the pixmap is HiDPI so it scales crisply
    #     pix.setDevicePixelRatio(ratio)

    #     if self._cache_enabled:
    #         self._cache[cache_key] = pix

    #     return pix

    def _render_formula_to_pixmap(self, formula: str) -> qg.QPixmap:
        point_size = self._base_point_size * self._math_scale

        screen = (
            self.window().windowHandle().screen()
            if self.window() and self.window().windowHandle()
            else None
        )
        ratio = float(screen.devicePixelRatio()) if screen else 1.0
        effective_dpi = int(self._math_dpi * ratio)

        cache_key = (
            formula,
            round(self._base_point_size, 2),
            round(self._math_scale, 3),
            effective_dpi,
        )
        if self._cache_enabled and cache_key in self._cache:
            return self._cache[cache_key]

        fig = Figure(figsize=(0.01, 0.01), dpi=effective_dpi)
        canvas = FigureCanvasAgg(fig)

        text_artist = fig.text(0, 0, f"${formula}$", fontsize=point_size)
        canvas.draw()
        renderer = canvas.get_renderer()
        bbox = text_artist.get_window_extent(renderer=renderer)

        width_in = bbox.width / effective_dpi
        height_in = bbox.height / effective_dpi
        fig.set_size_inches(max(width_in, 1e-3), max(height_in, 1e-3))

        text_artist.set_position((0, 0))
        fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
        canvas.draw()

        buf = io.BytesIO()
        fig.savefig(
            buf,
            format="png",
            dpi=effective_dpi,
            transparent=True,
            bbox_inches="tight",
            pad_inches=0,
        )
        buf.seek(0)

        pix = qg.QPixmap()
        pix.loadFromData(buf.getvalue(), "PNG")
        pix.setDevicePixelRatio(ratio)

        if self._cache_enabled:
            self._cache[cache_key] = pix
        return pix

    # # Optional: size hints that fit the pixmap snugly
    # def minimumSizeHint(self):
    #     pm = self.pixmap()
    #     if pm:
    #         return pm.size() / pm.devicePixelRatio()
    #     return super().minimumSizeHint()

    # def sizeHint(self):
    #     pm = self.pixmap()
    #     if pm:
    #         return pm.size() / pm.devicePixelRatio()
    #     return super().sizeHint()

    def minimumSizeHint(self):
        return self.sizeHint()

    def sizeHint(self):
        pm = self.pixmap()
        if pm is not None and not pm.isNull():
            return pm.deviceIndependentSize().toSize()

        # if pm:
        #     print(f"{pm.size()=}")
        #     print(f"{pm.devicePixelRatio()=}")
        #     print(f"{pm.size() / pm.devicePixelRatio()}")
        #     return pm.size() / pm.devicePixelRatio()

        text = self._last_text or ""
        if not text:
            return super().sizeHint()

        fm = self.fontMetrics()
        margins = self.contentsMargins()
        # horizontalAdvance is the actual text width
        w = fm.horizontalAdvance(text, len(text)) + margins.left() + margins.right()
        h = fm.height() + margins.top() + margins.bottom()
        return qc.QSize(w, h)


