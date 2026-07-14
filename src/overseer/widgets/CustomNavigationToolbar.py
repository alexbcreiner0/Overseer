from __future__ import annotations

from pathlib import Path
from dataclasses import is_dataclass, asdict

from matplotlib.backends.backend_qt import NavigationToolbar2QT
from PyQt6 import (
    QtWidgets as qw,
    QtCore as qc,
    QtGui as qg
)
from PyQt6 import QtCore as qc

from .CurveVisibilityDialog import CurveVisibilityDialog


class CustomNavigationToolbar(NavigationToolbar2QT):
    titles_applied = qc.pyqtSignal()

    def __init__(
        self,
        canvas,
        env,
        parent=None,
        default_dir=None,
        default_save_name="figure",
        params=None,
    ):
        super().__init__(canvas, parent)

        self.set_default_dir(default_dir)
        self.default_save_name = default_save_name
        self.params = params
        self.env = env
        self.graph_panel = None

        self.graph_panel = None
        self._curve_visibility_dialog: CurveVisibilityDialog | None = None
        self._curve_visibility_overrides: dict[str, bool] = {}

        self.addSeparator()
        icon_path = self.env.app_dir / "assets" / "curve_visibility.png"
        self.curve_visibility_action = self.addAction(qg.QIcon(str(icon_path)), "Curves")
        self.curve_visibility_action.setToolTip("Show/hide individual curves")
        self.curve_visibility_action.triggered.connect(self.open_curve_visibility_dialog)

    def set_graph_panel(self, graph_panel) -> None:
        """Give the toolbar access to GraphPanel's stable artist inventory."""
        self.graph_panel = graph_panel

    def set_default_dir(self, default_dir: str | None):
        self.default_dir = Path(default_dir).expanduser() if default_dir else None
        if self.default_dir:
            self.default_dir.mkdir(parents=True, exist_ok=True)

    def _format_save_name(self) -> str:
        template = self.default_save_name

        if self.params is None or not is_dataclass(self.params):
            return template

        params_dict = asdict(self.params)
        result = ""
        i = 0

        while i < len(template):
            if template[i] == "{":
                j = template.find("}", i)
                if j == -1:
                    result += template[i]
                    i += 1
                    continue

                key = template[i + 1:j]
                show_name = key.endswith("=")
                if show_name:
                    key = key[:-1]

                if key in params_dict:
                    value = params_dict[key]
                    result += f"{key}={value}" if show_name else str(value)
                else:
                    result += f"{key}"
                i = j + 1
            else:
                result += template[i]
                i += 1

        return result

    def save_figure(self, *args):
        """Same as stock toolbar, but dialog starts in self.default_dir."""
        name = self._format_save_name()

        if self.default_dir:
            fname, _ = qw.QFileDialog.getSaveFileName(
                self.parent(),
                "Save the figure",
                str(self.default_dir / f"{name}.png"),
                "PNG (*.png);;PDF (*.pdf);;SVG (*.svg);;All files (*)",
            )
            if not fname:
                return

            fig = self.canvas.figure

            w_px = self.canvas.width()
            h_px = self.canvas.height()
            dpi = fig.dpi
            fig.set_size_inches(w_px / dpi, h_px / dpi, forward=True)

            fig.tight_layout()
            fig.savefig(fname, dpi=dpi)
        else:
            super().save_figure(*args)

    def open_curve_visibility_dialog(self):
        if self._curve_visibility_dialog is None:
            self._curve_visibility_dialog = CurveVisibilityDialog(self, self.graph_panel, self.parent())
        else:
            self._curve_visibility_dialog.rebuild()

        self._curve_visibility_dialog.show()
        self._curve_visibility_dialog.raise_()
        self._curve_visibility_dialog.activateWindow()

    def curve_visibility_items(self) -> list[dict]:
        """Return checkbox-ready info for hideable curves.

        Prefer GraphPanel's GID-based inventory.  The canvas-only fallback is kept so
        the toolbar still works before MainWindow wires GraphPanel in.
        """
        if self.graph_panel is not None and hasattr(self.graph_panel, "curve_visibility_items"):
            return self.graph_panel.curve_visibility_items()

        return self._fallback_curve_visibility_items()

    def set_curve_visible(self, key, visible: bool) -> None:
        if self.graph_panel is not None and hasattr(self.graph_panel, "set_artist_visible"):
            self.graph_panel.set_artist_visible(key, visible)
            return

        self._fallback_set_curve_visible(key, visible)

    def set_all_curves_visible(self, visible: bool) -> None:
        if self.graph_panel is not None and hasattr(self.graph_panel, "set_all_curves_visible"):
            self.graph_panel.set_all_curves_visible(visible)
            return

        self._fallback_set_all_curves_visible(visible)

    def clear_curve_visibility_overrides(self) -> None:
        if self.graph_panel is not None and hasattr(self.graph_panel, "clear_artist_visibility_overrides"):
            self.graph_panel.clear_artist_visibility_overrides()
            return

        self._fallback_clear_curve_visibility_overrides()

    # ------------------------------------------------------------------
    # Fallback path for very early startup or standalone toolbar usage.
    # This path is intentionally secondary; live simulation persistence is
    # handled by GraphPanel when set_graph_panel(...) has been called.
    # ------------------------------------------------------------------

    def _fallback_curve_visibility_items(self) -> list[dict]:
        items = []
        for axis_index, ax in enumerate(self.canvas.figure.axes):
            if not hasattr(ax, "lines"):
                continue

            axis_title = ax.get_title() or ax.get_ylabel() or ax.get_xlabel() or "Untitled"

            for line_index, line in enumerate(ax.lines):
                if self._should_skip_curve_line(line):
                    continue

                key = self._curve_key(axis_index, line_index, line)
                if key in self._curve_visibility_overrides:
                    desired_visible = self._curve_visibility_overrides[key]
                    if line.get_visible() != desired_visible:
                        line.set_visible(desired_visible)

                items.append(
                    {
                        "axis_index": axis_index,
                        "axis_title": axis_title,
                        "line_index": line_index,
                        "key": key,
                        "label": self._curve_label(axis_index, line_index, line),
                        "tooltip": self._curve_tooltip(axis_index, line_index, line, key),
                        "visible": bool(line.get_visible()),
                    }
                )

        return items

    def _fallback_set_curve_visible(self, key: str, visible: bool) -> None:
        visible = bool(visible)
        self._curve_visibility_overrides[key] = visible

        changed = False
        for axis_index, ax in enumerate(self.canvas.figure.axes):
            if not hasattr(ax, "lines"):
                continue
            for line_index, line in enumerate(ax.lines):
                if self._should_skip_curve_line(line):
                    continue
                if self._curve_key(axis_index, line_index, line) != key:
                    continue
                if line.get_visible() != visible:
                    line.set_visible(visible)
                    changed = True

        self._fallback_refresh_legends()
        if changed:
            self.canvas.draw_idle()

    def _fallback_set_all_curves_visible(self, visible: bool) -> None:
        visible = bool(visible)
        changed = False

        for item in self._fallback_curve_visibility_items():
            self._curve_visibility_overrides[item["key"]] = visible

        for ax in self.canvas.figure.axes:
            if not hasattr(ax, "lines"):
                continue
            for line in ax.lines:
                if self._should_skip_curve_line(line):
                    continue
                if line.get_visible() != visible:
                    line.set_visible(visible)
                    changed = True

        self._fallback_refresh_legends()
        if changed:
            self.canvas.draw_idle()

    def _fallback_clear_curve_visibility_overrides(self) -> None:
        self._curve_visibility_overrides.clear()
        changed = False

        for ax in self.canvas.figure.axes:
            if not hasattr(ax, "lines"):
                continue
            for line in ax.lines:
                if self._should_skip_curve_line(line):
                    continue
                if not line.get_visible():
                    line.set_visible(True)
                    changed = True

        self._fallback_refresh_legends()
        if changed:
            self.canvas.draw_idle()

    def _should_skip_curve_line(self, line) -> bool:
        gid = line.get_gid() if hasattr(line, "get_gid") else None
        if isinstance(gid, str) and gid.startswith("__snap_"):
            return True

        try:
            xdata = line.get_xdata(orig=False)
            ydata = line.get_ydata(orig=False)
            if len(xdata) == 0 and len(ydata) == 0:
                return True
        except Exception:
            pass

        return False

    def _curve_key(self, axis_index: int, line_index: int, line) -> str:
        gid = line.get_gid() if hasattr(line, "get_gid") else None
        if gid:
            return f"axis:{axis_index}:gid:{gid}"

        label = line.get_label() if hasattr(line, "get_label") else ""
        if label and not str(label).startswith("_"):
            return f"axis:{axis_index}:label:{label}"

        return f"axis:{axis_index}:line:{line_index}"

    def _curve_label(self, axis_index: int, line_index: int, line) -> str:
        label = line.get_label() if hasattr(line, "get_label") else ""
        if label and not str(label).startswith("_"):
            return str(label)

        gid = line.get_gid() if hasattr(line, "get_gid") else None
        if gid:
            return str(gid)

        return f"Line {line_index + 1}"

    def _curve_tooltip(self, axis_index: int, line_index: int, line, key: str) -> str:
        gid = line.get_gid() if hasattr(line, "get_gid") else None
        label = line.get_label() if hasattr(line, "get_label") else ""
        return f"axis={axis_index}, line={line_index}, label={label}, gid={gid}, key={key}"

    def _fallback_refresh_legends(self) -> None:
        for ax in self.canvas.figure.axes:
            old_legend = ax.get_legend()
            if old_legend is None:
                continue

            handles, labels = ax.get_legend_handles_labels()
            visible_handles = []
            visible_labels = []

            for handle, label in zip(handles, labels):
                if not label or str(label).startswith("_"):
                    continue
                try:
                    if not handle.get_visible():
                        continue
                except Exception:
                    pass
                visible_handles.append(handle)
                visible_labels.append(label)

            old_title = old_legend.get_title().get_text()
            old_loc = getattr(old_legend, "_loc", "best")
            old_font_size = None
            try:
                old_font_size = old_legend.prop.get_size()
            except Exception:
                pass

            old_legend.remove()

            if visible_handles:
                kwargs = {"loc": old_loc}
                if old_title:
                    kwargs["title"] = old_title
                if old_font_size is not None:
                    kwargs["fontsize"] = old_font_size
                ax.legend(visible_handles, visible_labels, **kwargs)
