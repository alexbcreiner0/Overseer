from PyQt6 import (
    QtCore as qc,
    QtGui as qg,
    QtWidgets as qw,
)
import base64
import html
import io
import re


class RichToolTip(qw.QFrame):
    def __init__(self, parent=None, max_width=500, max_height=350):
        super().__init__(parent, qc.Qt.WindowType.ToolTip)
        self.setFrameShape(qw.QFrame.Shape.StyledPanel)
        self.setFrameShadow(qw.QFrame.Shadow.Raised)

        self._browser = qw.QTextBrowser()
        self._browser.setOpenExternalLinks(False)
        self._browser.setHorizontalScrollBarPolicy(qc.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._browser.setVerticalScrollBarPolicy(qc.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self._browser.setFrameShape(qw.QFrame.Shape.NoFrame)

        self._browser.setMaximumWidth(max_width)
        self._browser.setMaximumHeight(max_height)
        self._close_on_scroll_outside = False
        self.pinned = False

        lay = qw.QVBoxLayout(self)
        lay.setContentsMargins(8, 8, 8, 8)
        lay.addWidget(self._browser)

        self._shown_at = qc.QElapsedTimer()
        self._cursor_grace_ms = 350  # time to move mouse into the tooltip

        # match native tooltip palette
        tip_pal = qw.QToolTip.palette()
        self.setPalette(tip_pal)
        self._browser.setPalette(tip_pal)
        bg = tip_pal.color(qg.QPalette.ColorRole.ToolTipBase).name()
        fg = tip_pal.color(qg.QPalette.ColorRole.ToolTipText).name()
        self.setStyleSheet(f"""
            RichToolTip {{
                background-color: {bg};
                color: {fg};
                border: 1px solid rgba(0,0,0,60);
                border-radius: 6px;
            }}
            QTextBrowser {{
                background: transparent;
                color: {fg};
            }}
        """)

        self._hide_timer = qc.QTimer(self)
        self._hide_timer.setSingleShot(True)
        self._hide_timer.timeout.connect(self.hide)

        # Track cursor so it hides when you move away
        self._track_timer = qc.QTimer(self)
        self._track_timer.setInterval(50)
        self._track_timer.timeout.connect(self._maybe_hide_by_cursor)

        self._anchor: qw.QWidget | None = None

    def show_html_at(
        self,
        html: str,
        global_pos: qc.QPoint,
        ms: int = 8000,
        anchor: qw.QWidget | None = None,
        pinned: bool = False,
    ):
        self._anchor = anchor
        self._pinned = pinned
        self._shown_at.start()

        self._browser.setHtml(html)

        doc = self._browser.document()
        doc.setTextWidth(self._browser.maximumWidth())
        h = min(int(doc.size().height()) + 14, self._browser.maximumHeight())
        self._browser.setFixedHeight(h)

        self.adjustSize()
        self.move(global_pos + qc.QPoint(12, 12))
        self.show()

        # Timer only for non-pinned tooltips (hover style)
        if pinned:
            self._hide_timer.stop()
            self._track_timer.stop()
        else:
            self._hide_timer.start(ms)
            self._track_timer.start()

        qw.QApplication.instance().installEventFilter(self)

    def hideEvent(self, e):
        self._track_timer.stop()
        self._hide_timer.stop()
        try:
            qw.QApplication.instance().removeEventFilter(self)
        except Exception:
            pass
        self._anchor = None
        super().hideEvent(e)

    def eventFilter(self, obj, event):
        t = event.type()

        # Helper: is cursor currently over tooltip or anchor?
        gp = qg.QCursor.pos()
        over_tooltip = self.isVisible() and self.geometry().contains(gp)

        over_anchor = False
        if self._anchor is not None:
            anchor_rect = qc.QRect(self._anchor.mapToGlobal(qc.QPoint(0, 0)), self._anchor.size())
            over_anchor = anchor_rect.contains(gp)

        # Let the user scroll INSIDE the tooltip without closing it
        if t == qc.QEvent.Type.Wheel:
            if over_tooltip:
                return False
            if self._close_on_scroll_outside:
                self.hide()
            return False

        # Clicks / keypresses should close ONLY if they happen outside tooltip & anchor.
        if t in (qc.QEvent.Type.MouseButtonPress, qc.QEvent.Type.KeyPress):
            if over_tooltip or over_anchor:
                return False  # interact normally (scrollbar clicks, text selection, etc.)

            # Optional: Esc closes even if pinned
            if t == qc.QEvent.Type.KeyPress:
                try:
                    if event.key() == qc.Qt.Key.Key_Escape:
                        self.hide()
                        return False
                except Exception:
                    pass

            # Click/key outside closes (pinned or not)
            self.hide()
            return False

        if t == qc.QEvent.Type.WindowDeactivate:
            self.hide()
            return False

        return False

    def _maybe_hide_by_cursor(self):
        if self._pinned: return

        if not self.isVisible():
            return

        # Grace period: don't auto-hide immediately after showing
        if self._shown_at.isValid() and self._shown_at.elapsed() < self._cursor_grace_ms:
            return

        gp = qg.QCursor.pos()

        if self.geometry().contains(gp):
            return

        if self._anchor is not None:
            anchor_rect = qc.QRect(self._anchor.mapToGlobal(qc.QPoint(0, 0)), self._anchor.size())
            if anchor_rect.contains(gp):
                return

        self.hide()

# Inline math matcher: $...$ (non-greedy). This is intentionally simple.
_INLINE_MATH = re.compile(r"\$(.+?)\$", re.DOTALL)

def _render_math_png_bytes(formula: str, font_pt: float, dpi: int, color: qg.QColor) -> bytes:
    """
    Render mathtext formula to a transparent PNG byte string.
    (Matplotlib mathtext; no system LaTeX required.)
    """
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    fig = Figure(figsize=(0.01, 0.01), dpi=dpi)
    canvas = FigureCanvasAgg(fig)

    rgba = (color.redF(), color.greenF(), color.blueF(), color.alphaF())
    # t = fig.text(0, 0, f"${formula}$", fontsize=font_pt, color=rgba)
    MATH_SCALE = 0.65  # try 0.80–0.90
    t = fig.text(
        0, 0,
        f"${formula}$",
        fontsize=font_pt * MATH_SCALE,
        color=rgba,
    )

    canvas.draw()
    renderer = canvas.get_renderer()
    bbox = t.get_window_extent(renderer=renderer)

    # Tight resize
    fig.set_size_inches(max(bbox.width / dpi, 1e-3), max(bbox.height / dpi, 1e-3))
    t.set_position((0, 0))
    fig.subplots_adjust(left=0, right=1, bottom=0, top=1)
    canvas.draw()

    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, transparent=True, bbox_inches="tight", pad_inches=0)
    return buf.getvalue()

def tooltip_with_inline_latex(
    text: str,
    widget: qw.QWidget,
    math_dpi: int = 200,
) -> str:
    """
    Convert a mixed paragraph containing inline math like:
        "Profit rate is $r = \\pi/K$ and ..."

    into HTML where each $...$ becomes an <img src="data:image/png;base64,...">.
    """
    # Choose font size from tooltip font (or widget font)
    font = qw.QToolTip.font() if hasattr(qw.QToolTip, "font") else widget.font()
    font_pt = font.pointSizeF() if font.pointSizeF() > 0 else 12.0

    # HiDPI: scale DPI and set fixed pixel size in HTML so it doesn't balloon
    screen = qg.QGuiApplication.screenAt(qg.QCursor.pos()) or qg.QGuiApplication.primaryScreen()
    ratio = float(screen.devicePixelRatio()) if screen else 1.0
    effective_dpi = int(math_dpi * ratio)

    # Match tooltip text color (dark/light theme friendly)
    tip_text_color = widget.palette().color(qg.QPalette.ColorRole.ToolTipText)

    parts = []
    last = 0
    for m in _INLINE_MATH.finditer(text):
        # normal text chunk (HTML-escaped)
        parts.append(html.escape(text[last:m.start()]))

        formula = m.group(1).strip()
        png = _render_math_png_bytes(formula, font_pt=font_pt, dpi=effective_dpi, color=tip_text_color)
        b64 = base64.b64encode(png).decode("ascii")

        # Estimate display height roughly ~ font size; keep consistent with text
        # (You can tweak the CSS vertical-align if baseline looks off.)
        img_html = (
            f'<img src="data:image/png;base64,{b64}" '
            f'style="vertical-align: middle;" />'
        )
        parts.append(img_html)
        last = m.end()

    parts.append(html.escape(text[last:]))

    # Wrap in a span so Qt treats it as rich text
    # Use <br> for newlines
    html_body = "".join(parts).replace("\n", "<br>")
    return f"<span>{html_body}</span>"

class HelpButton(qw.QToolButton):
    hovered = qc.pyqtSignal()

    def __init__(self, text, tooltip= None):
        super().__init__()
        self.text = text
        self.tooltip = tooltip or ""

        self.setText("?")
        self.setToolTip(tooltip)
        self._rich_tip = RichToolTip(self)

        self.clicked.connect(self.show_tip)

    def _latex_html(self) -> str:
        return tooltip_with_inline_latex(self.tooltip, widget=self)

    def show_tip(self):
        pos = qg.QCursor.pos()
        html_tip = tooltip_with_inline_latex(self.tooltip, widget=self)
        self._rich_tip.show_html_at(html_tip, pos, anchor= self, pinned= True)
        # qw.QToolTip.showText(pos, html_tip, self)
        # qw.QToolTip.showText(pos, self.toolTip(), self)

    def event(self, e: qc.QEvent | None) -> bool:
        # This is what Qt uses for hover tooltips
        if e is not None:
            if e.type() == qc.QEvent.Type.ToolTip:
                assert isinstance(e, qg.QHelpEvent)
                # qw.QToolTip.showText(e.globalPos(), self._latex_html(), self)
                self._rich_tip.show_html_at(self._latex_html(), e.globalPos(), anchor=self, pinned=False)
                return True  # tells Qt "handled", so it won't show any default tooltip

        return super().event(e)

    def enterEvent(self, a0):
        self.hovered.emit()
        super().enterEvent(a0)

    def setToolTip(self, a0: str | None) -> None:
        """
        IMPORTANT: store raw tooltip text (may include $...$).
        Keep QWidget tooltip empty to prevent Qt's default tooltip rendering.
        """
        self.tooltip = a0 or ""
        super().setToolTip("")


