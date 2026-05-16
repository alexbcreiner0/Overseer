from math import e
import sys
from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
)
from matplotlib import (
    pyplot as plt,
    rcParams,
)
from matplotlib.patches import Rectangle
import numpy as np
from matplotlib.backend_bases import cursors
from matplotlib import colormaps, colors as mcolors
from matplotlib.colors import ListedColormap, BoundaryNorm
import networkx as nx
from matplotlib.ticker import FormatStrFormatter
import scienceplots
import logging, json, hashlib
from mpl_toolkits.mplot3d.art3d import Poly3DCollection
from PIL import Image
plt.style.use(["grid", "notebook"])
# rcParams["figure.constrained_layout.use"] = False
# rcParams["figure.autolayout"] = False
# rcParams["figure.constrained_layout.h_pad"] = float(0)
# rcParams["figure.constrained_layout.hspace"] = float(0)
rcParams["savefig.bbox"] = "tight"
rcParams["savefig.pad_inches"] = 0.05  # or 0.0 if you want absolutely no padding

logger = logging.getLogger(__name__)

class GraphPanel(qw.QWidget):
    saved_lims_changed = qc.pyqtSignal(tuple, tuple)
    slot_axes_limits_changed = qc.pyqtSignal(int, tuple, tuple)
    slot_axes_limits_changed_3d = qc.pyqtSignal(int, tuple, tuple, tuple)
    slot_title_changed = qc.pyqtSignal(int, str)

    def __init__(self, init_traj, init_t, dropdown_choices,
                 plotting_data, canvas, figure, axis, toolbar, status_bar):
        super().__init__()
        self.start_up = True # might not be necessary anymore, iono

        self.data = plotting_data
        self.dropdown_choices = dropdown_choices
        self.canvas = canvas
        self.figure, self.axis = figure, axis
        self.toolbar = toolbar
        self.status_bar = status_bar

        self._slot_choices: dict[int, str] = {} # slot_index -> dropdown choices
        self.legend_label_overrides: dict[tuple[int, str], dict[str, str]] = {} # keeps track of legend info for each slot/category choice 
        self.runtime_labels = {}
        self._logged_plot_keys: set[tuple] = set()
        self._slot_images: dict[int, object] = {} # slot_index -> AxesImage
        self._slot_cbar: dict[int, object] = {} # slot_index -> Colorbar (optional)
        self._slot_settings: dict[int, tuple[int, dict, dict | None]] = {}

        self._slot_artists: dict[int, dict[str, object]] = {} # slot_index -> {artist_gid -> artist}
        self._slot_artists_meta: dict[int, dict[str, dict]] = {}
        self._hist_state: dict[tuple[int, str, str], dict] = {}

        self._slot_dimensions: dict[int, str] = {}
        self._camera_overrides: dict[tuple[int, str], dict] = {}

        self.box_aspect_vals = {
            (1, 1): 0.75,
            (1, 2): 0.95,
            (1, 3): 1.05,
            (2, 1): 0.75,
            (2, 2): 0.85,
            (2, 3): 0.95,
            (3, 2): 0.95,
            (3, 3): 1.0,
        }
        self._base_box_aspect = self.box_aspect_vals[(1,1)]

        self.traj = init_traj
        self.t = init_t

        # initialize grid of axes
        self.axes_rows = 1
        self.axes_cols = 1
        self.axes = [self.axis]

        # this entire call might be unnecessary at this point, not sure
        # was meant to persist things like titles after redraws but I think that happens anyway now
        self._cid_draw = self.canvas.mpl_connect(
            "draw_event", self._on_canvas_draw
        )

        # controls the size of the legend fonts based on the grid config
        self.font_vals = {(1,1): 10, (1,2): 8, (1,3): 6, (2,1): 8, (2,2): 8, (3,2): 6, (2,3): 6, (3,3): 0}

        # snap artists are what we call the coordinate boxes which appear when you click on a curve
        self.snap_artists: dict[object, tuple[object, object]] = {} # maps axes to their artists + display info
        self._init_snap_artists()

        # prevent the cursor from changing depending on what mode the user is in, because fuck that
        self._orig_canvas_set_cursor = self.canvas.set_cursor
        def custom_set_cursor(cursor):
            if cursor == cursors.MOVE:
                self.canvas.unsetCursor()
            else:
                self._orig_canvas_set_cursor(cursor)
        self.canvas.set_cursor = custom_set_cursor

        # start an initial sim
        self._sim_run_id: int = 0
        self.plot_slot_from_scratch(0,0, {}, slot_config= None)
        self.dragging = False

        self.canvas.mpl_connect("button_press_event", self._on_press)
        self.canvas.mpl_connect("motion_notify_event", self.on_motion)
        self.canvas.mpl_connect("resize_event", self.on_motion)
        self.canvas.mpl_connect("button_release_event", self.on_release)
        self.canvas.mpl_connect("scroll_event", self._on_scroll)
      
        self.camera_controls = qw.QWidget()

        layout = qw.QVBoxLayout()
        layout.addWidget(self.canvas, stretch=5)
        self.setLayout(layout)

        self.start_up = False

        self._connect_axis_callbacks()

        # self._recompute_base_box_aspect()

        # trying to get the axes to cooperate with the size of the window (spoilers: they do not)
        # try:
        #     fig_w, fig_h = self.figure.get_size_inches()
        #     dpi = self.figure.dpi
        #     fig_w_px = fig_w * dpi
        #     fig_h_px = fig_h * dpi

        #     pos = self.axis.get_position()  # in figure-relative coordinates
        #     width_px = pos.width * fig_w_px
        #     height_px = pos.height * fig_h_px

        #     self._base_box_aspect = height_px / width_px if width_px else 1.0
        # except Exception:
        #     # fallback: a reasonable wide-ish plot
        #     self._base_box_aspect = 0.6

        self._block_axis_callback = False


    def refresh_box_aspects(self):
        self._recompute_base_box_aspect()
        for ax in self.axes:
            if not hasattr(ax, "get_zlim"):   # 2D only
                ax.set_box_aspect(self._base_box_aspect)
        self.canvas.draw_idle()

    def _on_scroll(self, event) -> None:
        """ controls zooming and other scroll related stuff """
        ax = event.inaxes
        if ax is None:
            return

        # Matplotlib gives 'up'/'down' strings for wheel on many backends
        zoom_in = (event.button == "up")
        base = 0.9 if zoom_in else 1.1

        if hasattr(ax, "get_zlim3d"):   # 3D axes
            self._block_axis_callback = True
            try:
                self._scale_3d_limits(ax, base)
            finally:
                self._block_axis_callback = False
            self._clamp_3d_view(ax)
            self.canvas.draw_idle()
            return

        # fall back to your existing 2D zoom logic
        self._zoom_2d(ax, event)

    # def set_runtime_labels(self, key: str, labels):
    #     if labels is None:
    #         self.runtime_labels.pop(key, None)
    #     else:
    #         self.runtime_labels[key] = list(labels)

    def _zoom_2d(self, ax, event) -> None:
        """ 2D helper for _on_scroll """
        # ax = event.inaxes
        if ax is None or ax not in self.axes:
            return
        if event.xdata is None or event.ydata is None:
            return

        base_scale = 1.2
        if event.button == "up":
            scale_factor = 1 / base_scale
        elif event.button == "down":
            scale_factor = base_scale
        else:
            return

        xdata, ydata = event.xdata, event.ydata

        x_min, x_max = ax.get_xlim()
        y_min, y_max = ax.get_ylim()

        dx_left = xdata - x_min
        dx_right = x_max - xdata
        dy_bottom = ydata - y_min
        dy_top = y_max - ydata

        new_x_min = xdata - dx_left * scale_factor
        new_x_max = xdata + dx_right * scale_factor
        new_y_min = ydata - dy_bottom * scale_factor
        new_y_max = ydata + dy_top * scale_factor

        if new_x_max == new_x_min or new_y_max == new_y_min:
            return

        self._block_axis_callback = True
        ax.set_xlim(new_x_min, new_x_max)
        ax.set_ylim(new_y_min, new_y_max)
        self._block_axis_callback = False

        self._on_axis_limits_changed(ax)

        self.canvas.draw_idle()

    def _scale_3d_limits(self, ax, scale: float):
        """ 3D helper for _on_scroll """
        # scale < 1 zoom in, scale > 1 zoom out
        x0, x1 = ax.get_xlim3d()
        y0, y1 = ax.get_ylim3d()
        z0, z1 = ax.get_zlim3d()

        xm = 0.5 * (x0 + x1); xr = 0.5 * (x1 - x0)
        ym = 0.5 * (y0 + y1); yr = 0.5 * (y1 - y0)
        zm = 0.5 * (z0 + z1); zr = 0.5 * (z1 - z0)

        xr *= scale; yr *= scale; zr *= scale

        ax.set_xlim3d(xm - xr, xm + xr)
        ax.set_ylim3d(ym - yr, ym + yr)
        ax.set_zlim3d(zm - zr, zm + zr)

    def _clamp_3d_view(self, ax, elev_min=-85, elev_max=85):
        if not hasattr(ax, "elev"):
            return
        if ax.elev is None:
            return
        ax.elev = max(elev_min, min(elev_max, float(ax.elev)))

    def _rebuild_slot_artists_inventory(self, slot_index: int) -> None:
        ax = self.axes[slot_index]
        choice_name = self._slot_choices.get(slot_index)

        bucket = {}
        meta = {}

        is_3d = hasattr(ax, "get_zlim")

        for ln in ax.lines:
            gid = ln.get_gid()
            if gid:
                bucket[gid] = ln
                meta[gid] = {
                    "choice_name": choice_name,
                    "kind": "line",
                    "dim": 3 if is_3d else 2
                }

        # things like heatmaps and cplots are images
        for j, im in enumerate(ax.images):
            gid = im.get_gid()
            # gid = getattr(im, "get_gid", lambda: None)()
            key = gid or f"{choice_name}::image::{j}"
            bucket[key] = im
            meta[key] = {
                "choice_name": choice_name,
                "kind": "image",
                "dim": 3 if is_3d else 2
            }

        # scatter plots, surfaces and vector fields are stored as collections
        for j, coll in enumerate(ax.collections):
            gid = coll.get_gid() if hasattr(coll, "get_gid") else None
            key = gid or f"{choice_name}::collection::{j}"
            bucket[key] = coll

            if gid and gid.endswith("::surface"):
                kind = "surface"
            elif isinstance(coll, Poly3DCollection):
                kind = "surface"
            elif gid and gid.endswith("::vector"):
                kind = "vector"
            else:
                kind = "collection"

            meta[key] = {
                "choice_name": choice_name,
                "kind": kind,
                "dim": 3 if is_3d else 2
            }

        # histogram bars and pie chart wedges are patches
        for j, p in enumerate(ax.patches):
            gid = p.get_gid() if hasattr(p, "get_gid") else None
            key = gid or f"{choice_name}::patch::{j}"
            bucket[key] = p
            meta[key] = {
                "choice_name": choice_name, 
                "kind": "patch",
                "dim": 3 if is_3d else 2
            }

        cb = getattr(self, "_slot_cbar", {}).get(slot_index)
        if cb is not None:
            gid = cb.get_gid() if hasattr(cb, "get_gid") else None
            key = gid or f"{choice_name}::colorbar"
            bucket[key] = cb
            meta[key] = {
                "choice_name": choice_name, 
                "kind": "colorbar",
                "dim": 3 if is_3d else 2
            }

        self._slot_artists[slot_index] = bucket
        self._slot_artists_meta[slot_index] = meta

    def _on_axis_limits_changed(self, ax):
        if getattr(self, "_block_axis_callback", False):
            return

        if isinstance(ax, int):
            try:
                ax = self.axes[ax]
            except IndexError:
                return

        # Read current limits from the axes
        # self.xlim = ax.get_xlim()
        # self.ylim = ax.get_ylim()
        xlim = ax.get_xlim()
        ylim = ax.get_ylim()

        try:
            slot_index = self.axes.index(ax)
        except ValueError:
            slot_index = 0

        if hasattr(ax, "get_zlim"):
            zlim = ax.get_zlim()
            self.slot_axes_limits_changed_3d.emit(slot_index, xlim, ylim, zlim)
        else:
            self.slot_axes_limits_changed.emit(slot_index, xlim, ylim)

    def _connect_axis_callbacks(self):
        """ Wire axis camera positions to the appropriate functions of the app """
        for ax in self.axes:
            ax.callbacks.connect("xlim_changed", self._on_axis_limits_changed)
            ax.callbacks.connect("ylim_changed", self._on_axis_limits_changed)
            if hasattr(ax, "callbacks") and hasattr(ax, "get_zlim"):
                ax.callbacks.connect("zlim_changed", self._on_axis_limits_changed)

    def _init_snap_artists(self):
        self.snap_artists = {}

        for ax in self.axes:
            marker, = ax.plot([], [], "o", ms= 6)
            marker.set_visible(False)

            annot = ax.annotate(
                "",
                xy=(0, 0),
                xytext=(10, 10),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.3", fc="w", ec="k", lw=0.5),
            )
            annot.set_visible(False)

            self.snap_artists[ax] = (marker, annot)

    def set_axes_layout(self, rows, cols):
        if rows < 1 or cols < 1:
            return

        if rows == self.axes_rows and cols == self.axes_cols:
            return

        self.axes_rows = rows
        self.axes_cols = cols

        # Snapshot existing per-slot limits (one (xlim, ylim) per axes)
        old_limits = []
        try:
            for ax in self.axes:
                old_limits.append((ax.get_xlim(), ax.get_ylim()))
        except Exception:
            old_limits = []

        # Fallback: if we somehow have no per-slot limits, use the primary axis
        fallback_xlim = None
        fallback_ylim = None
        if old_limits:
            fallback_xlim, fallback_ylim = old_limits[0]
        else:
            try:
                fallback_xlim = self.axis.get_xlim()
                fallback_ylim = self.axis.get_ylim()
            except Exception:
                fallback_xlim = fallback_ylim = None

        # infer dimensionality
        proj = {}
        for i in range(rows * cols):
            state = self._slot_settings.get(i)
            if state:
                dropdown_choice, options, _slot_cfg = state
                dropdown_name = self._choice_name_from_index(dropdown_choice)
                proj[i] = "3d" if self.data[dropdown_name].get("projection", "2d") == "3d" else "2d"
        self._slot_dimensions = proj

        self.figure.clear()

        self._slot_artists.clear()
        self._slot_artists_meta.clear()
        self._slot_images.clear()
        self._slot_cbar.clear()

        # axes_array = self.figure.subplots(rows, cols, squeeze=False)

        self.axes = []
        for i in range(rows * cols):
            want_3d = (proj.get(i) == "3d")
            ax = self.figure.add_subplot(rows, cols, i + 1, projection=("3d" if want_3d else None))
            self.axes.append(ax)
        self.axis = self.axes[0]

        box_aspect = self.box_aspect_vals.get((rows, cols), 0.9)
        for i, ax in enumerate(self.axes):
            if not hasattr(ax, "get_zlim"):
                ax.set_box_aspect(box_aspect)
            else:
                try:
                    ax.set_box_aspect((1, 1, 1))
                except Exception:
                    pass

        self._init_snap_artists()
        self._connect_axis_callbacks()

        self._block_axis_callback = True

        if old_limits:
            last_xlim, last_ylim = old_limits[-1]
        else:
            last_xlim = fallback_xlim
            last_ylim = fallback_ylim

        for i, ax in enumerate(self.axes):
            if old_limits and i < len(old_limits):
                xlim, ylim = old_limits[i]
            else:
                xlim = last_xlim
                ylim = last_ylim

            if xlim is not None and ylim is not None:
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)

            if not hasattr(ax, "get_zlim"):   # 2D
                ax.set_box_aspect(self._base_box_aspect)
            else:
                # 3D: either leave default, or use equal-ish scaling
                try:
                    ax.set_box_aspect((1, 1, 1))
                except Exception:
                    pass
            # try:
            #     ax.set_box_aspect(self._base_box_aspect)
            # except AttributeError:
            #     pass

        self._block_axis_callback = False
        self.canvas.draw_idle()

    def edit_slot_axes(self, slot_index, xlim, ylim, zlim= None):
        """ Apply (xlim, ylim) or (xlim, ylim, zlim) to the axes corresponding to the slot_index """
        if slot_index < 0 or slot_index >= len(self.axes):
            return

        ax = self.axes[slot_index]

        self._block_axis_callback = True
        ax.set_xlim(xlim)
        ax.set_ylim(ylim)
        if zlim is not None:
            try:
                ax.set_zlim(zlim)
            except Exception:
                pass
        self._block_axis_callback = False

        # self.xlim = xlim
        # self.ylim = ylim
        # self.zlim = zlim

        self.canvas.draw_idle()

    def set_sim_run_id(self, run_id: int) -> None:
        # call this once when a new simulation run starts
        if run_id != getattr(self, "_sim_run_id", None):
            self._sim_run_id = run_id
            self._logged_plot_keys.clear()

    def _log_exception(self, level: int, msg: str, *, extra: dict | None = None, exc_info = None, key: tuple | None = None):
        extra = extra or {}

        if key is None:
            # Build a stable fingerprint.
            # Keep it cheap and deterministic; don't include huge objects.
            exc_part = None
            if exc_info:
                # exc_info can be True or a tuple; normalize
                if exc_info is True:
                    exc_part = ("exc",)  # best effort; record current exception exists
                else:
                    et, ev, _tb = exc_info
                    exc_part = (getattr(et, "__name__", str(et)), str(ev))

            extra_part = json.dumps(extra, sort_keys=True, default=str)
            raw = f"{level}|{msg}|{extra_part}|{exc_part}"
            digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()
            key = (self._sim_run_id, digest)

        if key in self._logged_plot_keys:
            return
        self._logged_plot_keys.add(key)

        logger.log(level, msg, extra=extra, exc_info=exc_info)

    def _recompute_base_box_aspect(self) -> None:
        try:
            w_px, h_px = self.canvas.get_width_height()
            pos = self.axis.get_position()  # figure-relative
            width_px = pos.width * w_px
            height_px = pos.height * h_px
            self._base_box_aspect = height_px / width_px if width_px else 1.0
        except Exception:
            self._base_box_aspect = 0.6

    def _recompute_base_box_aspect2(self):
        try:
            fig_w, fig_h = self.figure.get_size_inches()
            dpi = self.figure.dpi
            fig_w_px = fig_w * dpi
            fig_h_px = fig_h * dpi

            pos = self.axis.get_position()
            width_px = pos.width * fig_w_px
            height_px = pos.height * fig_h_px

            self._base_box_aspect = height_px / width_px if width_px else 1.0
        except Exception:
            self._base_box_aspect = 0.6

    def _plot_on_axis(self, ax, slot_index, choice_name, traj, t, dropdown_choice, options):
        _, plots = self._choice_and_plots(dropdown_choice)
        # t = np.asarray(t)

        for plot_name, plot_dict in plots.items():
            if not self._plot_enabled(plot_dict, options):
                continue

            try:
                special = plot_dict.get("special")

                if special == "scatter":
                    self._build_scatter(ax, choice_name, plot_name, plot_dict, traj, t)
                    continue

                if special == "surface":
                    self._build_surface(ax, slot_index, choice_name, plot_name, plot_dict, traj)
                    continue

                if special == "cplot":
                    self._build_cplot(ax, choice_name, plot_name, plot_dict, traj)
                    continue

                if special == "heatmap":
                    self._build_heatmap(ax, slot_index, choice_name, plot_name, plot_dict, traj)
                    continue

                if special == "hist":
                    self._build_hist(ax, slot_index, choice_name, plot_name, plot_dict, traj)
                    continue

                if special == "pie":
                    self._build_pie(ax, choice_name, plot_name, plot_dict)
                    continue

                if special == "vector":
                    self._build_vector_field(ax, slot_index, choice_name, plot_name, plot_dict)
                    continue

                if special == "discrete_graph":
                    self._build_discrete_graph(ax, slot_index, choice_name, plot_name, plot_dict)
                    continue

                key = plot_dict.get("traj_key")
                if not key or key not in traj:
                    raise KeyError(key)

                y = np.asarray(traj[key])
                # n = len(plot_dict.get("labels", [0]))
                t_base = np.asarray(traj.get("t")) if t is None else np.asarray(t)
                alt_t_name = plot_dict.get("traj_key_x", None)
                z_name = plot_dict.get("traj_key_z")
                if z_name:
                    z = np.asarray(traj.get(z_name))
                else:
                    z = None
                if alt_t_name is not None and alt_t_name in traj:
                    t_base = np.asarray(traj[alt_t_name])

                if y.ndim == 1:
                    tt, yy = self._safe_align_xy(t_base, y)
                    self._plot_line_scalar(ax, slot_index, choice_name, plot_name, plot_dict, tt, yy, z)
                else:
                    tt = t_base
                    Y = y
                    # if Y.shape[0] != len(t):
                    if Y.shape[0] != len(tt):
                        # align on time dimension
                        m = min(Y.shape[0], len(tt))
                        tt = tt[:m]
                        Y = Y[:m, :]
                    self._plot_line_vector(ax, slot_index, choice_name, plot_name, plot_dict, tt, Y, z)

            except KeyError as e:
                self.status_bar.showMessage(f"Error, no key found: {e}", 4000)
                self._log_exception(
                    logging.ERROR,
                    "Missing key in traj dict.",
                    extra={
                        "choice_name": choice_name,
                        "plot_name": plot_name,
                        "traj_key": plot_dict.get("traj_key"),
                        "sim_run_id": self._sim_run_id,
                    },
                    exc_info=True,
                    key=(self._sim_run_id, "plot_fail", choice_name, plot_dict.get("traj_key"), type(e).__name__, str(e)),
                )

            except Exception as e:
                self.status_bar.showMessage(f"Error: {e}", 4000)
                self._log_exception(
                    logging.ERROR,
                    "Unexpected error when plotting.",
                    extra={
                        "choice_name": choice_name,
                        "plot_name": plot_name,
                        "traj_key": plot_dict.get("traj_key"),
                        "sim_run_id": self._sim_run_id
                    },
                    exc_info=True,
                    key=(self._sim_run_id, "plot_fail", choice_name, plot_dict.get("traj_key"), type(e).__name__),
                )

    # helpers for _plot_on_axis
    def _plot_enabled(self, plot_dict: dict, options: dict) -> bool:
        if "checkbox_name" in plot_dict:
            name = plot_dict["checkbox_name"]
            if name not in options and not (self.start_up and "on_startup" in plot_dict):
                return False
        return True

    def _choice_and_plots(self, dropdown_choice: int):
        choice = self._choice_dict_from_index(dropdown_choice)
        return choice, choice.get("plots", {})

    def _build_scatter(self, ax, choice_name: str, plot_name: str, plot_dict: dict, traj: dict, t):
        x_key, y_key = plot_dict.get("traj_key_x"), plot_dict.get("traj_key_y")
        y = traj[y_key]
        if x_key is None or x_key == "" or x_key not in traj:
            # can't use x_key, try t
            if t is None:
                if "t" not in traj:
                    raise ValueError("No valid x axis data found")
                else:
                    x = traj["t"]
            else:
                x = t
        else:
            x = traj[x_key]

        # if not isinstance(y, np.ndarray):
        #     y = np.asarray(y)
        # if not isinstance(x, np.ndarray):
        #     x = np.asarray(x)

        z_key = plot_dict.get("traj_key_z")
        is_3d = (z_key is not None and traj.get(z_key) is not None and hasattr(ax, "get_zlim"))

        size = plot_dict.get("size")
        is_size_key = plot_dict.get("size_key", False)

        color = plot_dict.get("color")
        is_color_key = plot_dict.get("color_key", False)

        if is_size_key and traj.get("size") is not None:
            size = traj["size"]
        elif size is None:
            size = rcParams['lines.markersize'] ** 2

        if isinstance(size, str):
            try:
                size = int(size)
            except ValueError:
                size = rcParams['lines.markersize'] ** 2

        if is_color_key and traj.get("color") is not None:
            color = traj["color"]
        elif color is None or color == "":
            color = "k"

        marker = plot_dict.get("marker", 'o')
        if marker == "":
            marker = 'o'

        if is_3d:
            z = traj[z_key]
            # if not isinstance(z, np.ndarray):
            #     z = np.asarray(z)
            
            n = min(len(x), len(y), len(z))
            pc = ax.scatter(
                x[:n], y[:n],
                z[:n],
                c=color,
                s= size,
                label=plot_dict["labels"][0],
                marker=marker,
                edgecolors=plot_dict.get("edgecolors", 'none')
            )
        else:
            n = min(len(x), len(y))
            pc = ax.scatter(
                x[:n], y[:n],
                c=color,
                s= size,
                label=plot_dict["labels"][0],
                marker=marker,
                edgecolors=plot_dict.get("edgecolors", 'none')
            )
        pc.set_gid(f"{choice_name}::{plot_name}::scatter")

    def _build_cplot(self, ax, choice_name: str, plot_name: str, plot_dict: dict, traj: dict):
        xmin, xmax = traj["x"][0], traj["x"][-1]
        ymin, ymax = traj["y"][0], traj["y"][-1]

        im = ax.imshow(
            traj["rgb"],
            origin="lower",
            extent=(xmin, xmax, ymin, ymax),
            interpolation="nearest",
            aspect="auto",
        )
        im.set_gid(f"{choice_name}::{plot_name}::cplot")

        if plot_dict.get("contours", False):
            X, Y = np.meshgrid(traj["x"], traj["y"], indexing="xy")
            abs_levels = np.logspace(-2, 2, 9)
            arg_levels = [-np.pi, -np.pi/2, 0, np.pi/2, np.pi]
            ax.contour(X, Y, traj["abs_sin"], levels=abs_levels, antialiased=True, alpha=0.35, linewidths=0.9)
            ax.contour(X, Y, traj["arg_sin"], levels=arg_levels, antialiased=True, alpha=0.45, linewidths=1.2)

    def _build_heatmap(self, ax, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict, traj: dict):
        # frame2d = self._heatmap_frame_from_dict(plot_dict, traj)
        frame2d = traj.get(plot_dict.get("traj_key", {}))
        if frame2d is None:
            return

        disc = plot_dict.get("discrete", False)
        norm = None
        cmap = None
        disc_values = None
        extent= None
        disc_labels = None
        if disc:
            disc_values = traj.get(plot_dict.get("values"))
            disc_colors = traj.get(plot_dict.get("colors"))
            disc_labels = traj.get(plot_dict.get("labels", None), None)

            if disc_values is not None and disc_colors is not None:
                disc_values = [float(v) for v in disc_values]
                if len(disc_colors) != len(disc_values):
                    raise ValueError(
                        f"heatmap discrete.colors length ({len(disc_colors)}) "
                        f"!= discrete.values length ({len(disc_values)})"
                    )
                pairs = sorted(zip(disc_values, disc_colors), key= lambda p: p[0])
                disc_values = [p[0] for p in pairs]
                disc_colors = [p[1] for p in pairs]

                cmap = ListedColormap(disc_colors)
                if len(disc_values) == 1:
                    boundaries = [disc_values[0] - 0.5, disc_values[0] + 0.5]
                else:
                    mids = [(disc_values[i] + disc_values[i+1])*0.5 for i in range(len(disc_values)-1)]
                    first = disc_values[0] - (mids[0] - disc_values[0])
                    last = disc_values[-1] + (disc_values[-1] - mids[-1])
                    boundaries = [first] + mids + [last]
                norm = BoundaryNorm(boundaries, ncolors= len(disc_values), clip= True)
        else:
            gradient = plot_dict.get("cmap")
            if gradient == "None":
                cmap = None
            if gradient != None:
                cmap = colormaps.get(gradient, None)
            else:
                cmap = None

        extent = None
        if "x" in traj and "y" in traj:
            xmin, xmax = float(traj["x"][0]), float(traj["x"][-1])
            ymin, ymax = float(traj["y"][0]), float(traj["y"][-1])
            extent = (xmin, xmax, ymin, ymax) if not disc else None

        im = ax.imshow(
            frame2d,
            origin=plot_dict.get("origin", "lower"),
            interpolation=plot_dict.get("interpolation", "nearest"),
            aspect=plot_dict.get("aspect", "auto"),
            extent=extent,
            cmap= cmap,
            norm= norm
        )
        im.set_gid(f"{choice_name}::{plot_name}::heatmap")

        ov = plot_dict.get("overlay_markers", {})
        if ov:
            u = np.asarray(frame2d)
            markers = ov.get("markers", [])
            sizes = ov.get("sizes", [])
            colors = ov.get("colors", [])
            edge_colors = ov.get("edgecolors", [])
            labels = ov.get("labels", [])

            # cell centers: x = col + 0.5, y = row + 0.5 (works with origin="lower")
            for i, code in enumerate(ov.get("codes", [])):
                code = int(code)
                ys, xs = np.where(u == code)
                # offsets = np.column_stack([xs + 0.5, ys + 0.5])
                xmin, xmax, ymin, ymax = im.get_extent()
                h, w = u.shape
                dx = (xmax - xmin) / w
                dy = (ymax - ymin) / h

                ys, xs = np.where(u == code)
                xcoords = xmin + (xs + 0.5) * dx
                ycoords = ymin + (ys + 0.5) * dy
                offsets = np.column_stack([xcoords, ycoords])

                try:
                    marker = markers[i]
                except IndexError:
                    marker = 'o'
                try:
                    size = sizes[i]
                except IndexError:
                    size = rcParams['lines.markersize'] ** 2
                try:
                    color = colors[i]
                except IndexError:
                    color = "none"
                try:
                    edgecolor = edge_colors[i]
                except IndexError:
                    edgecolor = "black"
                try:
                    label = labels[i]
                except IndexError:
                    label = "_nolegend_"

                coll = ax.scatter(
                    offsets[:,0], offsets[:,1],
                    marker=marker,
                    s=size,
                    facecolors=color,
                    edgecolors=edgecolor,
                    label=label
                )
                coll.set_gid(f"{choice_name}::{plot_name}::overlay::{code}")

        self._slot_images[slot_index] = im

        if plot_dict.get("colorbar", False):
            cb = self.figure.colorbar(im, ax=ax)
            self._slot_cbar[slot_index] = cb
            if disc_values is not None:
                try:
                    cb.set_ticks(disc_values)
                    if disc_labels is not None and len(disc_labels) == len(disc_values):
                            cb.set_ticklabels([str(s) for s in disc_labels])
                except Exception:
                    pass

        if disc_values is None:
            vmin = plot_dict.get("vmin", None)
            vmax = plot_dict.get("vmax", None)
            if vmin is not None or vmax is not None:
                im.set_clim(vmin= vmin, vmax= vmax)
            else:
                im.autoscale()

    def _hist_series(self, data: np.ndarray) -> list[np.ndarray]:
        data = np.asarray(data)

        if data.ndim == 1:
            return [data]

        if data.ndim == 2:
            return [data[:, i] for i in range(data.shape[1])]

        raise ValueError(f"Histogram expects 1D or 2D vector-series data, got shape {data.shape}")

    def _build_hist(self, ax, slot_index, choice_name: str, plot_name: str, plot_dict: dict, traj: dict):
        data = np.asarray(traj[plot_dict["dist"]])
        series = self._hist_series(data)

        legacy_edge_color = plot_dict.get("edgecolor")
        rwidth = plot_dict.get("rwidth", 1)
        histtype = plot_dict.get("histtype", 'bar')
        density = plot_dict.get("density", False)

        legacy_color = plot_dict.get("color")
        label = plot_dict.get("label")

        weights = plot_dict.get("weights", None)

        labels = self._auto_vector_labels(plot_name, plot_dict, len(series))
        colors = self._auto_vector_colors(plot_dict, max(len(series),1)) #if plot_dict.get("gradient", "None") == "None" else None
        edge_colors = plot_dict.get("edgecolors")
        if edge_colors is not None:
            edge_colors = list(edge_colors)
            while len(edge_colors) <= len(series):
                edge_colors.append("black")

        if weights is not None:
            weights = traj[weights]

        bins = plot_dict.get("bins", None)
        if isinstance(bins, str):
            bins = traj[plot_dict["bins"]]
        if bins is None:
            bins = self._desired_hist_edges(data.ravel(), plot_dict)

        all_edges = None
        gradient = plot_dict.get("gradient", "None")
        for i, values in enumerate(series):
            if legacy_color is not None and gradient == "None":
                color = legacy_color
            elif gradient == "None" and colors is not None:
                color = colors[i]
            else:
                color = None
            if legacy_edge_color is not None:
                edgecolor = legacy_edge_color
            elif edge_colors is not None:
                edgecolor = edge_colors[i]
            else:
                edgecolor = None

            counts, edges, patches = ax.hist(
                values,
                bins=bins,
                edgecolor=edgecolor,
                rwidth=rwidth,
                histtype=histtype,
                density=density,
                color=color,
                label=labels[i] if label is None else label,
                weights=weights[:, i] if weights is not None and np.asarray(weights).ndim == 2 else weights,
                alpha=plot_dict.get("alpha", 1.0),
            )

            if gradient != "None":
                norm = plt.Normalize(float(np.min(counts)), float(np.max(counts)))
                cmap = colormaps.get(gradient)
                for c, p in zip(counts, patches):
                    p.set_facecolor(cmap(norm(c)))

            for k, rect in enumerate(patches):
                rect.set_gid(f"{choice_name}::{plot_name}::hist::{i}::patch::{k}")

            all_edges = edges

        # counts, edges, patches = ax.hist(
        #     data,
        #     bins=bins, 
        #     edgecolor=edge_color, 
        #     rwidth=rwidth, 
        #     histtype= histtype, 
        #     density= density, 
        #     color= color, 
        #     label= label, 
        #     weights= weights
        # )
        # for k, rect in enumerate(patches):
        #     rect.set_gid(f"{choice_name}::{plot_name}::hist::patch::{k}")
        # self._hist_state[(slot_index, choice_name, plot_name)] = {"edges": np.asarray(edges, dtype=float)}

        self._hist_state[(slot_index, choice_name, plot_name)] = {
            "edges": np.asarray(all_edges, dtype=float),
            "n_series": len(series),
        }

        # try:
        #     ax.set_xlim(0, float(np.max(data)))
        # except Exception:
        #     pass



    
    def _build_surface(self, ax, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict, traj: dict):
        """Build a 3D surface plot.

        Supports either:
          - precomputed meshgrids in traj via traj_key_X / traj_key_Y (+ traj_key_Z)
          - 1D coordinate vectors in traj via traj_key_x / traj_key_y (+ traj_key_z), in which case we meshgrid them.

        The created Poly3DCollection gets a stable GID so the rest of the slot/artist inventory system can reason about it.
        """
        # Prefer explicit meshgrid keys if provided.
        key_X = plot_dict.get("traj_key_X") or plot_dict.get("traj_key_x")
        key_Y = plot_dict.get("traj_key_Y") or plot_dict.get("traj_key_y")
        key_Z = plot_dict.get("traj_key_Z") or plot_dict.get("traj_key_z")

        X = traj.get(key_X) if key_X else None
        Y = traj.get(key_Y) if key_Y else None
        Z = traj.get(key_Z) if key_Z else None

        if Z is None:
            return

        X = np.asarray(X) if X is not None else None
        Y = np.asarray(Y) if Y is not None else None
        Z = np.asarray(Z)

        # If X/Y are 1D, build a meshgrid.
        if X is not None and Y is not None and X.ndim == 1 and Y.ndim == 1:
            X, Y = np.meshgrid(X, Y, indexing="xy")

        # If X/Y are missing but we have "x"/"y" in traj, try those.
        if X is None or Y is None:
            if "x" in traj and "y" in traj:
                xx = np.asarray(traj["x"])
                yy = np.asarray(traj["y"])
                if xx.ndim == 1 and yy.ndim == 1:
                    X, Y = np.meshgrid(xx, yy, indexing="xy")

        if X is None or Y is None:
            return

        # Basic shape sanity: allow Z to be (ny, nx) matching meshgrid.
        try:
            if Z.ndim == 2 and X.shape != Z.shape:
                # common mismatch: X/Y are (ny, nx) but Z is transposed
                if X.shape == Z.T.shape:
                    Z = Z.T
        except Exception:
            pass

        kwargs = {}
        for k in ("rstride", "cstride", "linewidth", "antialiased", "alpha", "cmap", "shade"):
            if k in plot_dict:
                kwargs[k] = plot_dict[k]


        # vmin/vmax support (useful when Z values drift over time)
        vmin = plot_dict.get("vmin", None)
        vmax = plot_dict.get("vmax", None)
        if vmin is not None:
            kwargs["vmin"] = vmin
        if vmax is not None:
            kwargs["vmax"] = vmax

        surf = ax.plot_surface(X, Y, Z, **kwargs)
        surf.set_gid(f"{choice_name}::{plot_name}::surface")

        # Optional colorbar support (mirrors heatmap bookkeeping)
        if plot_dict.get("colorbar", False):
            try:
                cb = self.figure.colorbar(surf, ax=ax, shrink=plot_dict.get("cb_shrink", 0.7), pad=plot_dict.get("cb_pad", 0.08))
                self._slot_cbar[slot_index] = cb
            except Exception:
                pass

    def _build_pie(self, ax, choice_name: str, plot_name: str, plot_dict: dict):
        data = self.traj.get(plot_dict.get("traj_key"), None)
        uniques, counts = np.unique(data, return_counts= True)
        labels_key = plot_dict.get("label_map", None)
        labels_map = self.traj[labels_key] if labels_key else None
        colors_key = plot_dict.get("color_map", None)
        colors_map = self.traj[colors_key] if colors_key else None

        if labels_map:
            labels = [labels_map[value] for value in labels_map if value in uniques]
        else:
            labels = None
        if colors_map:
            colors = [colors_map[value] for value in colors_map if value in uniques]
        else:
            colors = None

        ax.pie(counts, labels= labels, colors= colors, labeldistance= None)
        # p.set_gid(f"{choice_name}::{plot_name}::pie")

    def _build_vector_field(self, ax, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict):
        want_3d = (self.data.get(choice_name, {}).get("projection", "2d") == "3d") 
        X_key, Y_key = plot_dict.get("traj_key_X", ""), plot_dict.get("traj_key_Y", "")
        if want_3d:
            Z_key = plot_dict.get("traj_key_Z", "")
        U_key, V_key = plot_dict["traj_key_U"], plot_dict["traj_key_V"]
        if want_3d:
            W_key = plot_dict.get("traj_key_W")
        cmap = plot_dict.get("cmap", None)
        colorbar = plot_dict.get("colorbar", False)

        U, V = self.traj[U_key], self.traj[V_key]
        if want_3d:
            W = self.traj[W_key]

        args = [U, V, W] if want_3d else [U, V] 

        if not want_3d and cmap is not None:
            C_key = plot_dict.get("traj_key_C")
            if isinstance(U, list):
                U = np.array(U)
            if isinstance(V, list):
                V = np.array(V)
            C = self.traj[C_key] if C_key else np.sqrt(U**2 + V**2)
            args = args + [C]

        if want_3d:
            if X_key and Y_key and Z_key:
                X, Y, Z = self.traj[X_key], self.traj[Y_key], self.traj[Z_key]
                args = [X, Y, Z] + args
        else:
            if X_key and Y_key:
                X, Y = self.traj[X_key], self.traj[Y_key]
                args = [X, Y] + args

        q = ax.quiver(*args, cmap= (cmap if not want_3d else None), label= "_nolegend_")
        q.set_gid(f"{choice_name}::{plot_name}::vector")
        if colorbar and not want_3d:
            cb = self.figure.colorbar(q, ax= ax)
            cb.ax.yaxis.set_major_formatter(FormatStrFormatter('%6.2f'))
            self._slot_cbar[slot_index] = cb

    def _build_discrete_graph(self, ax, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict):
        matrix_key = plot_dict["traj_key"]
        A = np.asarray(self.traj[matrix_key])

        if plot_dict.get("directed", False):
            G = nx.from_numpy_array(A, create_using=nx.DiGraph)
        else:
            G = nx.from_numpy_array(A)

        colors = self._auto_vector_colors(plot_dict, A.shape[0])

        pos = plot_dict.get("pos")
        if pos is None:
            pos = nx.spring_layout(G, seed=plot_dict.get("seed", 0))

        # nodes
        nodes = nx.draw_networkx_nodes(
            G,
            pos,
            ax=ax,
            node_color=colors,
            node_size=plot_dict.get("node_size", 300),
        )
        nodes.set_gid(f"{choice_name}::{plot_name}::graph::nodes")

        # edges
        edges = nx.draw_networkx_edges(
            G,
            pos,
            ax=ax,
            edge_color=plot_dict.get("edge_color", "k"),
            arrows=plot_dict.get("directed", False),
        )

        # draw_networkx_edges may return a LineCollection or a list of FancyArrowPatch
        if isinstance(edges, list):
            for k, edge_artist in enumerate(edges):
                if hasattr(edge_artist, "set_gid"):
                    edge_artist.set_gid(f"{choice_name}::{plot_name}::graph::edge::{k}")
        else:
            edges.set_gid(f"{choice_name}::{plot_name}::graph::edges")

        # labels are texts; your inventory does not track texts, which is fine
        if plot_dict.get("with_labels", True):
            nx.draw_networkx_labels(G, pos, ax=ax)

        if plot_dict.get("show_weights", True):
            edge_labels = nx.get_edge_attributes(G, "weight")
            nx.draw_networkx_edge_labels(
                G,
                pos,
                edge_labels=edge_labels,
                ax=ax,
            )

    def _on_canvas_draw(self, event):
        """
        Called after Matplotlib redraws the figure.
        Capture titles so they persist across app-driven redraws.
        """
        if not hasattr(self, "title_overrides"):
            self.title_overrides = {}

        for i, ax in enumerate(self.axes):
            title = ax.get_title()
            if title and title.strip():
                self.title_overrides[i] = title
            else:
                self.title_overrides.pop(i, None)

        # capture legend/line labels after toolbar Apply/OK
        for slot_index, ax in enumerate(self.axes):
            choice_name = self._slot_choices.get(slot_index)
            if not choice_name:
                continue

            current = (ax.get_title() or "").strip()

            try:
                # Find the choice dict by name
                choice = self.data.get(choice_name, {})
                default_title = (choice.get("title") or choice.get("name") or "").strip()
            except Exception:
                default_title = ""

            key = (slot_index, choice_name)

            if current and current != default_title:
                self.title_overrides[key] = current
            else:
                self.title_overrides.pop(key, None)


        for slot_index, ax in enumerate(self.axes):
            choice_name = self._slot_choices.get(slot_index)
            if not choice_name:
                continue

            bucket = self.legend_label_overrides.setdefault((slot_index, choice_name), {})
            for line in ax.lines:
                gid = line.get_gid()
                if not gid:
                    continue
                lab = line.get_label()
                if lab and str(lab).strip():
                    bucket[gid] = str(lab)

    def _plot_line_scalar(self, ax, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict, t: np.ndarray, y: np.ndarray, z: np.ndarray | None = None):
        default_label = (plot_dict.get("labels", [""]) or [""])[0]
        gid = f"{choice_name}::{plot_name}::0"

        over = self.legend_label_overrides.get((slot_index, choice_name), {})
        label = over.get(gid, default_label)

        if z is not None and hasattr(ax, "get_zlim"):
            ln = ax.plot(
                t, y, z,
                color=plot_dict["colors"][0],
                linestyle=plot_dict.get("linestyle", "solid"),
                label=label,
                marker= plot_dict.get("marker", None),
                markerfacecolor= plot_dict.get("markerfacecolor", None),
                markeredgecolor= plot_dict.get("markeredgecolor", None),
                linewidth= plot_dict.get("linewidth", 1.5),
                markersize= plot_dict.get("markersize", 6.0)
            )[0]
        else:
            ln = ax.plot(
                t, y,
                color=plot_dict["colors"][0],
                linestyle=plot_dict.get("linestyle", "solid"),
                label=label,
                marker= plot_dict.get("marker", None),
                markerfacecolor= plot_dict.get("markerfacecolor", None),
                markeredgecolor= plot_dict.get("markeredgecolor", None),
                linewidth= plot_dict.get("linewidth", 1.5),
                markersize= plot_dict.get("markersize", 6.0)
            )[0]
        ln.set_gid(gid)

    def _plot_line_vector(self, ax, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict, t: np.ndarray, Y: np.ndarray, z: np.ndarray | None = None):
        # n = len(plot_dict.get("labels", [0]))
        n = int(Y.shape[1])
        labels = self._auto_vector_labels(plot_name, plot_dict, n)
        colors = self._auto_vector_colors(plot_dict, n)

        over = self.legend_label_overrides.get((slot_index, choice_name), {})

        for i in range(n):
            default_label = labels[i]
            gid = f"{choice_name}::{plot_name}::{i}"
            label = over.get(gid, default_label)

            if z is not None and hasattr(ax, "get_zlim"):
                ln = ax.plot(
                    t, Y[:, i], z,
                    color=colors[i],
                    linestyle=plot_dict.get("linestyle", "solid"),
                    label=label,
                )[0]
            else:
                ln = ax.plot(
                    t, Y[:, i],
                    color=colors[i],
                    linestyle=plot_dict.get("linestyle", "solid"),
                    label=label,
                )[0]
            ln.set_gid(gid)

    def _auto_vector_labels(self, plot_name: str, plot_dict: dict, n: int) -> list[str]:

        labels = plot_dict.get("labels")
        if isinstance(labels, list) and len(labels) == n:
            return labels

        template = plot_dict.get("label_template") # e.g. Sector {k}
        if isinstance(template, str) and template.strip():
            return [template.format(i= i, k= i+1) for i in range(n)]

        prefix = plot_dict.get("label_prefix") # e.g. Sector i
        if isinstance(prefix, str) and prefix.strip():
            return [f"{prefix} {i+1}" for i in range(n)]

        return [f"{plot_name} [{i}]" for i in range(n)]

    def _auto_vector_colors(self, plot_dict: dict, n: int):
        bs_base = plot_dict.get("colors", [])
        base = []
        for i, color in enumerate(bs_base): # I am so fucking tilted right now, sorry if this is garbage
            if color != "":
                base.append(color)
        # if base == ['']:
        #     cmap_name = plot_dict.get("colormap")
        #     if not cmap_name:
        #         cmap_name = "tab20" if n <= 20 else "turbo"

        #     cmap = colormaps.get(cmap_name).resampled(max(n, 1))
        #     base[0] = cmap(0)

        if not isinstance(base, list):
            base = []

        # print(f"{n=}")
        if len(base) >= n:
            return base[:n]

        cmap_name = plot_dict.get("colormap")
        if not cmap_name:
            cmap_name = "tab20" if n <= 20 else "turbo"

        cmap = colormaps.get(cmap_name).resampled(max(n, 1))

        used = []
        for c in base:
            try:
                used.append(mcolors.to_rgba(c))
            except Exception:
                pass

        out = list(base)
        for i in range(n):
            if len(out) >= n:
                break
            cand = cmap(i)

            # skip colors too close to already-used ones
            if any(sum((cand[k] - u[k]) ** 2 for k in range(3)) < 0.02 for u in used):
                continue

            out.append(cand)
            used.append(cand)

        # if the skipping logic was too aggressive, just fill remaining slots directly
        j = 0
        while len(out) < n:
            cand = cmap(j % n)
            out.append(cand)
            j += 1

        return out

    def _safe_align_xy(self, t: np.ndarray, y: np.ndarray):
        n = min(len(t), len(y))
        return t[:n], y[:n]

    def plot_slot_from_scratch(self, slot_index, dropdown_choice, options, slot_config=None, source= "checkbox", load_idx_defaults= False, rescale_legend= False):
        """ 
            Constructs plots 'from scratch', i.e. when GraphPanel anticipates presence
            of artist GIDs that don't exist yet, and then registersthem
        """
        if self.traj is None:
            self.canvas.draw_idle()
            return
        if slot_index < 0 or slot_index >= len(self.axes):
            return

        # populate slot data 
        choice_name = self._choice_name_from_index(dropdown_choice)
        self._slot_choices[slot_index] = choice_name
        self._slot_settings[slot_index] = (dropdown_choice, options, slot_config)

        # decide if the slot is meant to be 3D (defaults to 2D unless data says not to)
        want_3d = (self.data.get(choice_name, {}).get("projection", "2d") == "3d") 
        # if the slot is supposed to be 3d and isn't, blow it up and remake it (or vice versa)
        self._ensure_slot_projection(slot_index, want_3d, preserve_limits=True)

        # grab relevant slot data and objects
        ax = self.axes[slot_index]

        # snapshot current camera pos
        # if new_lims:
        default_lims = self.data.get(choice_name, {}).get("default_lims")

        if default_lims and load_idx_defaults and source== "dropdown":
            xlims_base = default_lims[0]
            current_xlim = tuple(float(xlim) for xlim in xlims_base)
            
            ylims_base = default_lims[1]
            current_ylim = tuple(float(ylim) for ylim in ylims_base)

            if len(default_lims) == 3:
                zlims_base = default_lims[2]
                current_zlim = tuple(float(zlim) for zlim in zlims_base)
                self.slot_axes_limits_changed_3d.emit(slot_index, current_xlim, current_ylim, current_zlim)
            else:
                current_zlim = None
                self.slot_axes_limits_changed.emit(slot_index, current_xlim, current_ylim)
        else:
            current_xlim = ax.get_xlim()
            current_ylim = ax.get_ylim()
            current_zlim = ax.get_zlim() if hasattr(ax, "get_zlim") else None

        if slot_config is not None:
            if slot_config.get("legend_fontsize") is not None and not rescale_legend:
                legend_font_size = slot_config.get("legend_fontsize", 10)
            else:
                legend_font_size = self._get_legend_font()
        else:
            legend_font_size = self._get_legend_font()

        self._clear_slot(slot_index) # die

        # build all artists for the slot
        self._plot_on_axis(ax, slot_index, choice_name, self.traj, self.t, dropdown_choice, options)

        # self explanatory
        self._restore_limits(ax, current_xlim, current_ylim, current_zlim)

        if slot_config is None:
            slot_config = {}
        choice, _ = self._choice_and_plots(dropdown_choice)
        slot_config["axis_visible"] = choice.get("axis_visible", True)
        slot_config["grid_visible"] = choice.get("grid_visible", True)
        slot_config["ticks_visible"] = choice.get("ticks_visible", True)
        slot_config["frame_visible"] = choice.get("frame_visible", True)
        self._apply_slot_config(ax, slot_index, dropdown_choice, slot_config, legend_font_size)

        self._rebuild_slot_artists_inventory(slot_index)
        self._init_snap_artists()
        self.canvas.draw_idle()

    def _get_legend_font(self) -> int:
        try:
            default_font = self.font_vals[(self.axes_rows, self.axes_cols)]
        except KeyError:
            default_font = 10

        return default_font

    def _clear_slot(self, slot_index: int) -> None:
        """ blows up a slot axis and also perform any necessary clean up """
        ax = self.axes[slot_index]
        ax.clear()

        # heatmap bookkeeping (legacy; keep until heatmap moves into _plot_on_axis)
        # old_im = getattr(self, "_slot_images", {}).pop(slot_index, None)
        # if old_im is not None:
        #     try:
        #         old_im.remove()
        #     except Exception:
        #         pass

        # if there is a colorbar, delete it
        old_cb = getattr(self, "_slot_cbar", {}).pop(slot_index, None)
        if old_cb is not None:
            try:
                old_cb.remove()
            except Exception:
                pass

        self._slot_artists.pop(slot_index, None)
        self._slot_artists_meta.pop(slot_index, None)

    def _apply_slot_config(self, ax, slot_index: int, dropdown_choice: int, slot_config: dict | None, default_font: int) -> None:
        ax.set_axis_on()
        ax.grid(True)

        # restore spines in case a previous special plot hid them
        for sp in ax.spines.values():
            sp.set_visible(True)


        if slot_config is None:
            ax.legend(fontsize=default_font)
            return

        legend_visible = slot_config.get("legend_visible", True)
        # fontsize = slot_config.get("legend_fontsize", default_font)
        fontsize = default_font
        loc = slot_config.get("legend_loc", "upper right")
        legend_title = slot_config.get("legend_title", None)
        axis_visible = slot_config.get("axis_visible", True)
        ticks_visible = slot_config.get("ticks_visible", True)
        grid_visible = slot_config.get("grid_visible", True)
        frame_visible = slot_config.get("frame_visible", True)

        if not axis_visible:
            ax.set_axis_off()
        else:
            ax.set_axis_on()
            ax.grid(bool(grid_visible))

            if ticks_visible:
                ax.tick_params(
                    axis="both",
                    which="both",
                    bottom=True, top=False, left=True, right=False,
                    labelbottom=True, labelleft=True
                )
            else:
                ax.tick_params(
                    axis="both",
                    which="both",
                    bottom=False, top=False, left=False, right=False,
                    labelbottom=False, labelleft=False
                )

            if not frame_visible:
                for sp in ax.spines.values():
                    sp.set_visible(False)

        if legend_visible:
            handles, labels = ax.get_legend_handles_labels()

            overrides = slot_config.get("legend_label_overrides", slot_config.get("legend_labels", None))
            if overrides:
                if isinstance(overrides, dict):
                    labels = [str(overrides.get(lbl, lbl)) for lbl in labels]
                elif isinstance(overrides, (list, tuple)):
                    labels = [str(overrides[i]) if i < len(overrides) else lbl for i, lbl in enumerate(labels)]

            ax.legend(handles, labels, fontsize=fontsize, loc=loc, title=legend_title)
        else:
            leg = ax.get_legend()
            if leg is not None:
                leg.remove()

        display_title = slot_config.get("title", False)
        display_x_title = slot_config.get("xlabel", True)
        display_y_title = slot_config.get("ylabel", False)

        choice = self._choice_dict_from_index(dropdown_choice)
        title = choice.get("title") or choice.get("name", "")
        x_title = choice.get("x_label") or "Time [t]"
        y_title = choice.get("y_label") or ""

        if display_title:
            choice_name = self._choice_name_from_index(dropdown_choice)  # or derive however you prefer
            override = getattr(self, "title_overrides", {}).get((slot_index, choice_name))
            ax.set_title(override if override else title)
        if display_x_title:
            ax.set_xlabel(x_title)
        if display_y_title:
            ax.set_ylabel(y_title)

    
    def _restore_limits(self, ax, xlim, ylim, zlim=None) -> None:
        self._block_axis_callback = True
        try:
            ax.set_xlim(xlim)
            ax.set_ylim(ylim)
            if zlim is not None and hasattr(ax, "set_zlim"):
                ax.set_zlim(zlim)
        finally:
            self._block_axis_callback = False

    def _ensure_slot_projection(self, slot_index: int, want_3d: bool, *, preserve_limits: bool = True) -> None:
        """Ensure the axes for this slot has the requested projection (2D vs 3D).

        Matplotlib cannot "toggle" an existing Axes between 2D and 3D in-place. The safe approach is:
          - delete the old axes
          - re-create the subplot at the same grid position with the desired projection
          - re-wire callbacks + snap artists
        """
        if slot_index < 0 or slot_index >= len(self.axes):
            return

        old_ax = self.axes[slot_index]
        is_3d = hasattr(old_ax, "get_zlim")

        if want_3d == is_3d:
            self._slot_dimensions[slot_index] = "3d" if want_3d else "2d"
            return

        # Snapshot camera/limits from the old axes.
        xlim = ylim = zlim = None
        if preserve_limits:
            try:
                xlim = old_ax.get_xlim()
                ylim = old_ax.get_ylim()
                if is_3d:
                    zlim = old_ax.get_zlim()
            except Exception:
                pass

        # Remove old snap artists (marker/annotation) for this axes.
        try:
            snap = self.snap_artists.pop(old_ax, None)
            if snap:
                for artist in snap:
                    try:
                        artist.remove()
                    except Exception:
                        pass
        except Exception:
            pass

        # Delete and recreate the subplot with the correct projection.
        try:
            self.figure.delaxes(old_ax)
        except Exception:
            pass

        new_ax = self.figure.add_subplot(
            self.axes_rows, self.axes_cols, slot_index + 1,
            projection=("3d" if want_3d else None),
        )
        self.axes[slot_index] = new_ax
        if slot_index == 0:
            self.axis = new_ax

        # Re-add snap artists for the new axes.
        try:
            marker, = new_ax.plot([], [], "o", ms=6)
            marker.set_visible(False)

            annot = new_ax.annotate(
                "",
                xy=(0, 0),
                xytext=(10, 10),
                textcoords="offset points",
                bbox=dict(boxstyle="round,pad=0.3", fc="w", ec="k", lw=0.5),
            )
            annot.set_visible(False)

            self.snap_artists[new_ax] = (marker, annot)
        except Exception:
            pass

        # Wire callbacks for the new axes.
        try:
            new_ax.callbacks.connect("xlim_changed", self._on_axis_limits_changed)
            new_ax.callbacks.connect("ylim_changed", self._on_axis_limits_changed)
            if want_3d:
                new_ax.callbacks.connect("zlim_changed", self._on_axis_limits_changed)
        except Exception:
            pass

        # Restore limits if we had them.
        if preserve_limits and xlim is not None and ylim is not None:
            self._block_axis_callback = True
            try:
                new_ax.set_xlim(xlim)
                new_ax.set_ylim(ylim)
                if want_3d and zlim is not None:
                    new_ax.set_zlim(zlim)
            finally:
                self._block_axis_callback = False

        # Keep your aspect behavior consistent for 2D; for 3D this is optional.
        if not hasattr(new_ax, "get_zlim"):   # 2D
            new_ax.set_box_aspect(self._base_box_aspect)
        else:
            # 3D: either leave default, or use equal-ish scaling
            try:
                new_ax.set_box_aspect((1, 1, 1))
            except Exception:
                pass
        # try:
        #     new_ax.set_box_aspect(self._base_box_aspect)
        # except Exception:
        #     pass

        self._slot_dimensions[slot_index] = "3d" if want_3d else "2d"




    # ----------------------------
    # Live-update (no axis clear)
    # ----------------------------

    def _choice_name_from_index(self, dropdown_choice: int) -> str:
        if self.data is None:
            return ""

        if len(self.data.keys()) == 0:
            return ""

        dropdown_list = list(self.data.keys())
        return dropdown_list[dropdown_choice]

    def _choice_dict_from_index(self, dropdown_choice: int):
        try:
            dropdown_list = list(self.data.keys())
            return self.data[dropdown_list[dropdown_choice]]
        except IndexError:
            return {}

    def _has_special_plots(self, dropdown_choice: int, options: dict) -> bool:
        """Return True if the active selection includes any plot types that we can't update in-place."""
        choice = self._choice_dict_from_index(dropdown_choice)
        plots = choice.get("plots", {})
        for _plot_name, plot_dict in plots.items():
            # skip hidden plots
            if "checkbox_name" in plot_dict:
                name = plot_dict["checkbox_name"]
                if name not in options and not (self.start_up and "on_startup" in plot_dict):
                    continue
            if "special" in plot_dict:
                if plot_dict["special"] != "heatmap":
                    return True
        return False

    def _expected_artist_gids(self, slot_index: int, dropdown_choice: int, options: dict) -> list[str]:
        """
        Returns a list of the expected artist gids for the current dropdown choice and options.

        Includes:
          - standard line plots:  choice::plot::i
          - scatter:              choice::plot::scatter
          - cplot image:          choice::plot::cplot
          - heatmap image:        choice::plot::heatmap
          - histogram bars:       choice::plot::hist::patch::k
          - surfaces:             choice::plot::surface  
        """
        if self.data is None:
            return []

        if len(self.data.keys()) == 0:
            choice_name = None
            choice_dict = {}
        else:
            dropdown_list = list(self.data.keys())
            choice_name = dropdown_list[dropdown_choice]
            choice_dict = self._choice_dict_from_index(dropdown_choice) 
        plots = choice_dict.get("plots", {})

        expected: list[str] = []

        def is_enabled(plot_dict: dict) -> bool:
            if "checkbox_name" in plot_dict:
                name = plot_dict["checkbox_name"]
                if name not in options and not (self.start_up and "on_startup" in plot_dict):
                    return False
            return True

        slot_bucket = self._slot_artists.get(slot_index, {})
        # Pattern: "{choice}::{plot}::hist::patch::{k}"
        for plot_name, plot_dict in plots.items():
            if not is_enabled(plot_dict):
                continue

            special = plot_dict.get("special")

            # we're adding these because the artists need GIDs prior to having them actually assigned
            if special == "scatter":
                expected.append(f"{choice_name}::{plot_name}::scatter")
                continue

            if special == "cplot":
                expected.append(f"{choice_name}::{plot_name}::cplot")
                continue

            if special == "heatmap":
                # you set this in plot_slot via: im.set_gid(f"{choice_name}::{hm_name}::heatmap")
                expected.append(f"{choice_name}::{plot_name}::heatmap")
                continue

            if special == "surface":
                expected.append(f"{choice_name}::{plot_name}::surface")
                continue

            if special == "pie":
                expected.append(f"{choice_name}::{plot_name}::pie")
                continue

            if special == "discrete_graph":
                expected.append(f"{choice_name}::{plot_name}::graph::nodes")
                expected.append(f"{choice_name}::{plot_name}::graph::edges")
                continue

            if special == "vector":
                expected.append(f"{choice_name}::{plot_name}::vector")

            if special == "hist":
                # infer patch keys from whatever currently exists in the slot inventory
                dist_key = plot_dict.get("dist", "dist")
                data = self.traj.get(dist_key, None)

                if data is None:
                    continue

                bins_spec = plot_dict.get("bins", None)


                if isinstance(bins_spec, int):
                    nbins = bins_spec
                elif isinstance(bins_spec, str):
                    try:
                        nbins = len(self.traj[plot_dict[bins_spec]])
                    except Exception:
                        nbins = int(np.unique(data).size)
                elif bins_spec is None:
                    nbins = int(np.unique(data).size)
                else:
                    edges = np.asarray(bins_spec, dtype= float).ravel()
                    nbins = max(0, edges.size - 1)

                # expected.extend([f"{choice_name}::{plot_name}::hist::patch::{k}" for k in range(nbins)])

                data = np.asarray(data)
                n_series = len(self._hist_series(data))

                for i in range(n_series):
                    for k in range(nbins):
                        expected.append(f"{choice_name}::{plot_name}::hist::{i}::patch::{k}")
                continue

                # prefix = f"{choice_name}::{plot_name}::hist::patch"
                # patch_gids = [gid for gid in slot_bucket.keys() if isinstance(gid, str) and gid.startswith(prefix)]
                # # Stable numeric ordering by the trailing index if possible
                # def patch_index(g: str) -> int:
                #     try:
                #         return int(g.rsplit("::", 1)[-1])
                #     except Exception:
                #         return 10**9

                # patch_gids.sort(key=patch_index)

                # # If we have none yet, we *can't* predict how many patches will exist (that’s the point of A),
                # # so we return empty here and let the caller decide to redraw.
                # expected.extend(patch_gids)
                # continue

            # ---- normal line plots
            try:
                traj_key = plot_dict["traj_key"]
                n = self.traj[traj_key].shape[1]
            except Exception:
                n = len(plot_dict.get("labels", []))
            if n <= 1:
                expected.append(f"{choice_name}::{plot_name}::0")
            else:
                for i in range(n):
                    expected.append(f"{choice_name}::{plot_name}::{i}")

        return expected

    def _line_series_from_gid(self, gid: str, traj: dict, key_name: str):
        """
        Helper for x/y/z lookup.

        For scalar data, returns the whole 1D array.
        For vector data, returns column i, where i comes from the gid:
            choice::plot::i
        """
        try:
            choice_name, plot_name, idx_s = gid.split("::")
            i = int(idx_s)
        except Exception:
            return None

        if choice_name not in self.data:
            return None

        plot_dict = self.data[choice_name].get("plots", {}).get(plot_name)
        if not plot_dict:
            return None

        key = plot_dict.get(key_name)
        if not key or key not in traj:
            return None

        try:
            arr = np.asarray(traj[key])
        except Exception:
            return None

        if arr.ndim == 1:
            return arr

        if arr.ndim >= 2:
            if i < arr.shape[1]:
                return arr[:, i]
            return None

        return None

    def _get_ydata_from_gid(self, gid: str, traj: dict):
        """Return y-data array for a given Line2D gid."""
        try:
            choice_name, plot_name, idx_s = gid.split("::")
            i = int(idx_s)
        except Exception:
            return None

        # Resolve plot spec
        if choice_name not in self.data:
            return None
        plot_dict = self.data[choice_name].get("plots", {}).get(plot_name)
        if not plot_dict:
            return None

        key = plot_dict.get("traj_key")
        if not key or key not in traj:
            return None

        y = traj[key]
        try:
            y = np.asarray(y)
        except Exception:
            return None

        # scalar vs vector
        if y.ndim == 1:
            return y
        if y.ndim >= 2:
            if i < y.shape[1]:
                return y[:, i]
            return None
        return None

    def _get_xdata_from_gid(self, gid, traj, t):
        overall_default = traj.get("t")
        x_default = t

        # x_default = np.asarray(t)
        _, _, plot_dict = self._get_spec_from_gid(gid)
        if not plot_dict:
            return overall_default if x_default is None else x_default

        key_x = plot_dict.get("traj_key_x")
        if not key_x or key_x not in traj:
            return overall_default if x_default is None else x_default

        try:
            x = traj[key_x]
            return x
        except Exception:
            return overall_default if x_default is None else x_default

    def _get_spec_from_gid(self, gid: str) -> tuple[str | None, str | None, dict | None]:
        """ Attempts to retrieve and return all the required plot info from a gid """
        try:
            choice_name, plot_name, _rest = gid.split("::", 2)
        except Exception:
            return None, None, None

        if choice_name not in self.data:
            return choice_name, plot_name, None

        plot_dict = self.data[choice_name].get("plots", {}).get(plot_name)
        return choice_name, plot_name, plot_dict

    def _get_artist_type_from_gid(self, slot_index: int, gid: str) -> str:
        metadata = self._slot_artists_meta.get(slot_index, {}).get(gid)
        if metadata and "kind" in metadata:
            return metadata["kind"]

        if gid.endswith("::scatter"): return "collection"
        if gid.endswith("::surface"): return "surface"
        if gid.endswith("::pie"): return "pie"
        if gid.endswith("::cplot") or gid.endswith("::heatmap"): return "image"
        if gid.endswith("::vector"): return "vector"
        if "::hist::patch" in gid: return "patch"
        return "line"

    def _update_line_artist(self, line, gid: str, t: np.ndarray | None, traj: dict, slot_index: int) -> None:
        y = self._get_ydata_from_gid(gid, traj)
        z = self._line_series_from_gid(gid, traj, "traj_key_z")
        x = self._get_xdata_from_gid(gid, traj, t)

        if x is None:
            logger.log(logging.ERROR, "No valid data found for x axis.")
            self.status_bar.showMessage(f"Error! No x-axis plotting data found.", msecs= 4000)
            return
        if y is None:
            return

        ax = self.axes[slot_index]

        if z is not None and hasattr(ax, "get_zlim"):
            z = np.asarray(z)
            n = min(len(x), len(y), len(z))

            line.set_data_3d(x[:n], y[:n], z[:n])
        else:
            n = min(len(x), len(y))
            line.set_data(x[:n], y[:n])

        y = np.asarray(y)
        n = min(len(x), len(y))
        line.set_data(x[:n], y[:n])

        over = self.legend_label_overrides.get((slot_index, self._slot_choices.get(slot_index)), {})
        if gid in over:
            line.set_label(over[gid])

    def _scatter_sizes_for_n(self, plot_dict: dict, traj: dict, n: int) -> np.ndarray:
        size = plot_dict.get("size")
        is_size_key = plot_dict.get("size_key", False)

        if is_size_key and traj.get("size") is not None:
            size = np.asarray(traj["size"])
            if size.ndim == 0:
                return np.full(n, float(size))
            return size[:n]

        if size is None or size == "":
            size = rcParams["lines.markersize"] ** 2

        try:
            size = float(size)
        except (TypeError, ValueError):
            size = rcParams["lines.markersize"] ** 2

        return np.full(n, size)

    def _scatter_colors_for_n(self, plot_dict: dict, traj: dict, n: int):
        color = plot_dict.get("color")
        is_color_key = plot_dict.get("color_key", False)

        if is_color_key and traj.get("color") is not None:
            color = np.asarray(traj["color"])

            # One scalar/color per point.
            if color.ndim >= 1 and len(color) == n:
                return color[:n]

            # Growing data case: slice down to current n.
            if color.ndim >= 1 and len(color) > n:
                return color[:n]

            # Scalar-ish fallback.
            if color.ndim == 0:
                return color.item()

            # If color length is wrong, avoid passing a mismatched array.
            return "k"

        if color is None or color == "":
            return "k"

        return color

    def _update_scatter_artist(self, coll, gid: str, traj: dict, slot_index: int, t) -> None:
        _, _, plot_dict = self._get_spec_from_gid(gid)

        if not plot_dict:
            return

        x_key, y_key = plot_dict.get("traj_key_x"), plot_dict.get("traj_key_y")
        z_key = plot_dict.get("traj_key_z")

        ax = self.axes[slot_index]
        is_3d = (z_key is not None and traj.get(z_key) is not None and hasattr(ax, "get_zlim"))

        y = np.asarray(traj[y_key])
        if x_key is None or x_key == "" or x_key not in traj:
            # can't use x_key, try t
            if t is None:
                if "t" not in traj:
                    raise ValueError("No valid x axis data found")
                else:
                    x = traj["t"]
            else:
                x = t
        else:
            x = traj[x_key]

        if not isinstance(x, np.ndarray):
            x = np.asarray(x)

        if is_3d:
            z = np.asarray(traj[z_key])
            n = min(x.shape[0], y.shape[0], z.shape[0])
        else:
            n = min(x.shape[0], y.shape[0])

        if n <= 0:
            if is_3d:
                empty = np.empty((0,), dtype= float)
                coll._offsets3d = (empty, empty, empty)
            else:
                coll.set_offsets(np.empty((0,2), dtype= float))
            return

        if is_3d:
            x = x[:n]
            y = y[:n]
            z = z[:n]
            sizes = self._scatter_sizes_for_n(plot_dict, traj, n)
            colors = self._scatter_colors_for_n(plot_dict, traj, n)
            coll._offsets3d = (x[:n], y[:n], z[:n])
            coll.set_sizes(sizes)
            coll._sizes3d = sizes

            coll.set_facecolors(colors)
            coll.set_edgecolors(plot_dict.get("edgecolors", "none"))
        else:
            offsets = np.column_stack((x[:n], y[:n]))
            coll.set_offsets(offsets)

    def _update_pie_artist(self, ax, gid: str) -> None:
        choice_name, plot_name, plot_dict = self._get_spec_from_gid(gid)
        self._build_pie(ax, choice_name, plot_name, plot_dict)

    def _update_vector_artist(self, q, gid: str, slot_index: int) -> None:
        choice_name, plot_name, plot_dict = self._get_spec_from_gid(gid)
        if not plot_dict:
            return

        ax = q.axes
        is_3d = hasattr(ax, "get_zlim")
        if is_3d:
            self._build_vector_field(ax, slot_index, choice_name, plot_name, plot_dict)
            return

        X_key = plot_dict.get("traj_key_X", "")
        Y_key = plot_dict.get("traj_key_Y", "")
        U_key = plot_dict.get("traj_key_U")
        V_key = plot_dict.get("traj_key_V")
        c_key = plot_dict.get("traj_key_C", "")
        cmap = plot_dict.get("cmap", None)

        if not U_key or not V_key:
            return

        U = np.asarray(self.traj[U_key])
        V = np.asarray(self.traj[V_key])

        C = None
        if cmap is not None:
            C = self.traj[c_key] if c_key else np.sqrt(U**2 + V**2)

        q.set_UVC(U, V, C)

        if X_key and Y_key:
            X = np.asarray(self.traj[X_key])
            Y = np.asarray(self.traj[Y_key])

            old_offsets = q.get_offsets()
            new_offsets = np.column_stack([X.ravel(), Y.ravel()])

            if old_offsets is None or np.shape(old_offsets) != np.shape(new_offsets) or not np.allclose(old_offsets, new_offsets):

                cb = self._slot_cbar.pop(slot_index, None)
                if cb is not None:
                    try:
                        cb.remove()
                    except Exception:
                        pass

                try:
                    q.remove()
                except Exception:
                    pass

                self._build_vector_field(ax, slot_index, choice_name, plot_name, plot_dict)

    def _update_surface_artist(self, ax, slot_index: int, gid: str, traj: dict) -> None:
        choice_name, plot_name, plot_dict = self._get_spec_from_gid(gid)
        if not plot_dict:
            return

        # Remove any existing surface collection(s) with this gid.
        for coll in list(getattr(ax, "collections", [])):
            try:
                if getattr(coll, "get_gid", lambda: None)() == gid:
                    try:
                        coll.remove()
                    except Exception:
                        try:
                            ax.collections.remove(coll)
                        except Exception:
                            pass
            except Exception:
                pass

        # Remove any colorbar owned by this slot (surface colorbars tend to be per-slot).
        cb = getattr(self, "_slot_cbar", {}).get(slot_index)
        if cb is not None:
            try:
                cb.remove()
            except Exception:
                pass
            try:
                self._slot_cbar.pop(slot_index, None)
            except Exception:
                pass

        self._build_surface(ax, slot_index, choice_name, plot_name, plot_dict, traj)

    def _update_cplot_image(self, im, traj: dict) -> None:
        if "rgb" not in traj:
            return

        im.set_data(np.asarray(traj["rgb"]))

        if "x" in traj and "y" in traj:
            xmin, xmax = float(traj["x"][0]), float(traj["x"][-1])
            ymin, ymax = float(traj["y"][0]), float(traj["y"][-1])
            im.set_extent((xmin, xmax, ymin, ymax))

    def _update_heatmap_image(self, im, gid: str, traj: dict) -> None:
        choice_name, plot_name, plot_dict = self._get_spec_from_gid(gid)

        if not plot_dict:
            return

        # frame2d = self._heatmap_frame_from_dict(plot_dict, traj)
        frame2d = traj.get(plot_dict.get("traj", {}))
        if frame2d is None:
            return

        im.set_data(frame2d)

        ov = plot_dict.get("overlay_markers", {})
        if ov.get("enabled", False):
            u = np.asarray(frame2d)
            ax = im.axes
            for code in ov.get("codes", []):
                code = int(code)
                gid2 = f"{choice_name}::{plot_name}::overlay::{code}"
                # find existing collection by gid
                target = None
                for coll in ax.collections:
                    if getattr(coll, "get_gid", lambda: None)() == gid2:
                        target = coll; break
                if target is None:
                    continue
                ys, xs = np.where(u == code)
                # offsets = np.column_stack([xs + 0.5, ys + 0.5]) if len(xs) else np.empty((0,2))
                xmin, xmax, ymin, ymax = im.get_extent()
                h, w = u.shape
                dx = (xmax - xmin) / w
                dy = (ymax - ymin) / h

                ys, xs = np.where(u == code)
                if len(xs):
                    xcoords = xmin + (xs + 0.5) * dx
                    ycoords = ymin + (ys + 0.5) * dy
                    offsets = np.column_stack([xcoords, ycoords])
                else:
                    offsets = np.empty((0, 2))
                target.set_offsets(offsets)

        if "x" in traj and "y" in traj:
            xmin, xmax = float(traj["x"][0]), float(traj["x"][-1])
            ymin, ymax = float(traj["y"][0]), float(traj["y"][-1])
            if not plot_dict.get("discrete", False):
                im.set_extent((xmin, xmax, ymin, ymax))

        disc = plot_dict.get("discrete", False)
        if not disc:
            vmin = plot_dict.get("vmin", None)
            vmax = plot_dict.get("vmax", None)
            if vmin is not None or vmax is not None:
                im.set_clim(vmin= vmin, vmax= vmax)
            else:
                im.autoscale()

    # def _desired_hist_edges(self, data: np.ndarray, plot_dict: dict) -> np.ndarray:
    #     bins = plot_dict.get("bins", None)
    #     if bins is None:
    #         # your current behavior; consider capping for perf
    #         nbins = int(np.unique(data).size)
    #         nbins = max(1, min(nbins, plot_dict.get("max_bins", 200)))
    #         return np.histogram_bin_edges(data, bins=nbins)
    #     if isinstance(bins, int):
    #         return np.histogram_bin_edges(data, bins=bins)
    #     # assume array-like edges
    #     edges = np.asarray(bins, dtype=float)


    #     # If values are basically integers, center bins on integers.
    #     # (This prevents bars from looking shifted right.)
    #     if data.size and np.all(np.isfinite(data)) and plot_dict.get("integer_bins", False) == True:
    #         rounded = np.rint(data)
    #         if np.allclose(data, rounded, atol=1e-12, rtol=0):
    #             imin = int(rounded.min())
    #             imax = int(rounded.max())
    #             # edges: imin-0.5, imin+0.5, ..., imax+0.5  (step 1)
    #             return np.arange(imin - 0.5, imax + 1.5, 1.0)

    #     return edges

    def _desired_hist_edges(self, data: np.ndarray, plot_dict: dict) -> np.ndarray:
        data = np.asarray(data)
        bins = plot_dict.get("bins", None)

        if isinstance(bins, str):
            return self.traj[plot_dict["bins"]]

        if bins is None:
            nbins = int(np.unique(data).size)
            nbins = max(1, min(nbins, plot_dict.get("max_bins", 200)))
            return np.histogram_bin_edges(data, bins=nbins)

        if isinstance(bins, int):
            return np.histogram_bin_edges(data, bins=bins)

        return bins

    def _rebuild_hist_plot(self, ax, slot_index, choice_name, plot_name, plot_dict, data):
        prefix = f"{choice_name}::{plot_name}::hist::"

        for p in list(ax.patches):
            gid = getattr(p, "get_gid", lambda: None)()
            if isinstance(gid, str) and gid.startswith(prefix):
                try:
                    p.remove()
                except Exception:
                    pass

        self._build_hist(ax, slot_index, choice_name, plot_name, plot_dict, {plot_dict["dist"]: data})
        self._rebuild_slot_artists_inventory(slot_index)

    # def _rebuild_hist_plot(self, ax, slot_index, choice_name, plot_name, plot_dict, data):
    #     # remove only this histogram's patches
    #     # prefix = f"{choice_name}::{plot_name}::hist::patch::"
    #     series_prefix = f"{choice_name}::{plot_name}::hist::"
    #     for p in list(ax.patches):
    #         gid = getattr(p, "get_gid", lambda: None)()
    #         if isinstance(gid, str) and gid.startswith(prefix):
    #             try: p.remove()
    #             except Exception: pass

    #     edge_color = plot_dict.get("edgecolor", "black")
    #     color = plot_dict.get("color", "black")
    #     rwidth = plot_dict.get("rwidth", 1)
    #     density = plot_dict.get("density", False)
    #     align = plot_dict.get("align", "mid")
    #     histtype = plot_dict.get("histtype", 'bar')
    #     label = plot_dict.get("label", "")

    #     edges = self._desired_hist_edges(data, plot_dict)
    #     counts, edges, patches = ax.hist(
    #         data, 
    #         bins=edges,
    #         edgecolor=edge_color,
    #         rwidth=rwidth,
    #         density= density,
    #         color= color,
    #         align= align,
    #         histtype= histtype,
    #         label= label
    #     )

    #     for k, rect in enumerate(patches):
    #         rect.set_gid(f"{choice_name}::{plot_name}::hist::patch::{k}")

    #     self._hist_state[(slot_index, choice_name, plot_name)] = {"edges": np.asarray(edges, dtype=float)}

    #     ax.set_xlim(float(edges[0]), float(edges[-1]))

    #     gradient = plot_dict.get("gradient", "None")
    #     if gradient != "None":
    #         norm = plt.Normalize(float(np.min(counts)), float(np.max(counts)) if np.max(counts) > 0 else 1.0)
    #         cmap = colormaps.get(gradient)
    #         for c, p in zip(counts, patches):
    #             p.set_facecolor(cmap(norm(c)))

    def _update_hist(self, slot_index, choice_name, plot_name, plot_dict, traj):
        dist_key = plot_dict.get("dist")
        if not dist_key or dist_key not in traj:
            return

        data = np.asarray(traj[dist_key])
        if data.size == 0:
            return

        ax = self.axes[slot_index]
        key = (slot_index, choice_name, plot_name)

        series = self._hist_series(data)
        desired_edges = self._desired_hist_edges(data.ravel(), plot_dict)

        state = self._hist_state.get(key)
        stored_edges = state.get("edges") if state else None
        stored_n_series = state.get("n_series") if state else None

        if (
            stored_edges is None
            or stored_edges.shape != desired_edges.shape
            or not np.allclose(stored_edges, desired_edges, rtol=0, atol=0)
            or stored_n_series != len(series)
        ):
            self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
            return

        bucket = self._slot_artists.get(slot_index, {})
        all_counts = []

        for i, values in enumerate(series):
            counts, _ = np.histogram(values, bins=stored_edges)

            if plot_dict.get("density", False):
                widths = np.diff(stored_edges)
                n = counts.sum()
                counts = counts / (n * widths) if n > 0 else counts

            prefix = f"{choice_name}::{plot_name}::hist::{i}::patch::"

            rects = []
            for gid, artist in bucket.items():
                if isinstance(gid, str) and gid.startswith(prefix):
                    try:
                        k = int(gid.rsplit("::", 1)[-1])
                    except Exception:
                        k = 10**9
                    rects.append((k, artist))

            rects.sort(key=lambda kv: kv[0])
            rects = [r for _, r in rects]

            if len(rects) != len(counts):
                self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
                return

            for rect, c in zip(rects, counts):
                if not isinstance(rect, Rectangle):
                    self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
                    return
                rect.set_height(float(c))

            all_counts.append(counts)

            gradient = plot_dict.get("gradient", "None")
            if gradient != "None":
                hi = float(np.max(counts)) if np.max(counts) > 0 else 1.0
                norm = plt.Normalize(float(np.min(counts)), hi)
                cmap = colormaps.get(gradient)
                for c, p in zip(counts, rects):
                    p.set_facecolor(cmap(norm(c)))

        ax.set_xlim(float(stored_edges[0]), float(stored_edges[-1]))

        if all_counts:
            ymax = max(float(np.max(c)) for c in all_counts if len(c))
            ax.set_ylim(0, ymax * 1.05 if ymax > 0 else 1.0)

    # def _update_hist(self, slot_index, choice_name, plot_name, plot_dict, traj):
    #     dist_key = plot_dict.get("dist")
    #     if not dist_key or dist_key not in traj:
    #         return

    #     data = np.asarray(traj[dist_key])
    #     series = self._hist_series(data)
    #     desired_edges = self._desired_hist_edges(data.ravel(), plot_dict)


    #     if data.size == 0:
    #         return

    #     ax = self.axes[slot_index]
    #     # self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
    #     # return

    #     key = (slot_index, choice_name, plot_name)

    #     desired_edges = self._desired_hist_edges(data, plot_dict)
    #     state = self._hist_state.get(key)
    #     stored_edges = state.get("edges") if state else None

    #     # decide whether to rebuild
    #     if stored_edges is None or stored_edges.shape != desired_edges.shape or not np.allclose(stored_edges, desired_edges, rtol=0, atol=0):
    #         self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
    #         return

    #     # update heights using the true edges
    #     counts, _ = np.histogram(data, bins=stored_edges)
    #     if plot_dict.get("density", False):
    #         widths = np.diff(stored_edges)
    #         n = counts.sum()
    #         counts = counts / (n * widths) if n > 0 else counts

    #     # collect rects in stable k order from inventory (or from ax.patches)
    #     bucket = self._slot_artists.get(slot_index, {})
    #     prefix = f"{choice_name}::{plot_name}::hist::patch::"
    #     # series = self._hist_series(np.asarray(traj[dist_key]))
    #     # prefix = f"{choice_name}::{plot_name}::hist::patch::"
    #     rects = []
    #     for gid, artist in bucket.items():
    #         if isinstance(gid, str) and gid.startswith(prefix):
    #             try: k = int(gid.rsplit("::", 1)[-1])
    #             except Exception: k = 10**9
    #             rects.append((k, artist))
    #     rects.sort(key=lambda kv: kv[0])
    #     rects = [r for _, r in rects]

    #     # if count mismatch, rebuild
    #     if len(rects) != len(counts):
    #         self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
    #         return

    #     for rect, c in zip(rects, counts):
    #         if not isinstance(rect, Rectangle):
    #             self._rebuild_hist_plot(ax, slot_index, choice_name, plot_name, plot_dict, data)
    #             return
    #         rect.set_height(float(c))

    #     ax.set_xlim(float(stored_edges[0]), float(stored_edges[-1]))

    #     gradient = plot_dict.get("gradient", "None")
    #     if gradient != "None":
    #         norm = plt.Normalize(float(np.min(counts)), float(np.max(counts)) if np.max(counts) > 0 else 1.0)
    #         cmap = colormaps.get(gradient)
    #         for c, p in zip(counts, rects):
    #             p.set_facecolor(cmap(norm(c)))

    # def _update_hist(self, slot_index: int, choice_name: str, plot_name: str, plot_dict: dict, traj: dict) -> None:
    #     dist_key = plot_dict.get("dist")
    #     if not dist_key or dist_key not in traj:
    #         return

    #     data = np.asarray(traj[dist_key])
    #     if data.size == 0:
    #         return

    #     bucket = self._slot_artists.get(slot_index, {})
    #     prefix = f"{choice_name}::{plot_name}::hist::patch::"
    #     patches = []
    #     for gid, artist in bucket.items():
    #         if isinstance(gid, str) and gid.startswith(prefix):
    #             try:
    #                 k = int(gid.rsplit("::", 1)[-1])
    #             except Exception:
    #                 k = 10**9
    #             patches.append((k, artist))

    #     if not patches:
    #         return

    #     patches.sort(key= lambda kv: kv[0])
    #     rects = [p for _k, p in patches]

    #     lefts = [float(r.get_x()) for r in rects]
    #     rights = [float(r.get_x() + r.get_width()) for r in rects]
    #     edges = np.array(lefts + [rights[-1]], dtype=float)

    #     if not np.all(np.isfinite(edges)) or np.any(np.diff(edges) <= 0):
    #         return

    #     counts, edges = np.histogram(data, bins= edges)

    #     for rect, c in zip(rects, counts):
    #         rect.set_height(float(c))

    #     ax = self.axes[slot_index]
    #     ax.set_xlim(edges[0], edges[-1])

    def _has_heatmap(self, dropdown_choice: int, options: dict):
        """Return (plot_name, plot_dict) for the first enabled heatmap plot in the choice, or (None, None)."""
        choice = self._choice_dict_from_index(dropdown_choice)
        plots = choice.get("plots", {})
        for plot_name, plot_dict in plots.items():
            if "checkbox_name" in plot_dict:
                name = plot_dict["checkbox_name"]
                if name not in options and not (self.start_up and "on_startup" in plot_dict):
                    continue
            if plot_dict.get("special") == "heatmap":
                return plot_name, plot_dict
        return None, None

    def _heatmap_frame_from_dict(self, plot_dict: dict, traj: dict):
        key = plot_dict.get("traj_key")
        if not key or key not in traj:
            return None

        # Plain 2D scalar heatmap
        if arr.ndim == 2:
            arr = np.asarray(traj[key])
            return arr

        if arr.ndim == 3:
            # RGB/RGBA image: (height, width, channels)
            if arr.shape[-1] in (3, 4):
                return arr

            # Time stack of scalar frames: (time, height, width)
            return arr[-1]

        if arr.ndim == 4:
            # Time stack of RGB/RGBA images: (time, height, width, channels)
            if arr.shape[-1] in (3, 4):
                return arr[-1]

        return None

    def update_slot_frame(self, slot_index: int, dropdown_choice: int, options: dict, slot_cfg: dict | None = None) -> None:
        """ This method is called when a SimWorker makes progress. It updates plots in order to animate progress """

        # step 1: compare current artists with expected ones
        expected = self._expected_artist_gids(slot_index, dropdown_choice, options)
        current = list(self._slot_artists.get(slot_index, {}).keys())

        # if anything expected is missing, (re)draw it (potentially for first time)
        if not expected or set(current) != set(expected):
            self.plot_slot_from_scratch(slot_index, dropdown_choice, options, slot_cfg)
            return

        # otherwise, attempt to update the axes more conservatively without tearing everything down and redrawing it all
        # using more specialized methods

        # Update line data in-place 
        # t = np.asarray(self.t)
        ax = self.axes[slot_index]

        is_3d = hasattr(ax, "get_zlim")
        current_xlim = ax.get_xlim()
        current_ylim = ax.get_ylim()
        current_zlim = ax.get_zlim() if is_3d else None

        bucket = self._slot_artists.get(slot_index, {})

        choice_dict = self._choice_dict_from_index(dropdown_choice)
        choice_name = self._choice_name_from_index(dropdown_choice)

        # update settings as provided by the main window
        self._slot_choices[slot_index] = choice_name
        self._slot_settings[slot_index] = (dropdown_choice, options, slot_cfg)

        for plot_name, plot_dict in choice_dict.get("plots", {}).items():
            if "checkbox_name" in plot_dict:
                name = plot_dict["checkbox_name"]
                if name not in options and not (self.start_up and "on_startup" in plot_dict):
                    continue
            if plot_dict.get("special") == "hist":
                # histograms are a little different because they are multiple artists (one per rectangle)
                # so we must handle as a special case
                self._update_hist(slot_index, choice_name, plot_name, plot_dict, self.traj)

        for gid in expected:
            artist = bucket.get(gid)
            if artist is None:
                continue

            kind = self._get_artist_type_from_gid(slot_index, gid)
            
            if kind == "line":
                self._update_line_artist(artist, gid, self.t, self.traj, slot_index)
            
            elif kind == "collection":
                if gid.endswith("::scatter"):
                    self._update_scatter_artist(artist, gid, self.traj, slot_index, self.t)
                elif "::graph::" in gid:
                    pass

            elif kind == "surface":
                self._update_surface_artist(ax, slot_index, gid, self.traj)

            elif kind == "image":
                if gid.endswith("::cplot"):
                    self._update_cplot_image(artist, self.traj)
                elif gid.endswith("::heatmap"):
                    self._update_heatmap_image(artist, gid, self.traj)

            elif kind == "patch":
                pass # histogram case, adressed in a special way above

            elif kind == "pie":
                self._update_pie_artist(ax, gid)

            elif kind == "vector":
                self._update_vector_artist(artist, gid, slot_index)

            else:
                pass

        gid_to_line = {ln.get_gid(): ln for ln in ax.lines if ln.get_gid()}
        for gid in expected:
            line = gid_to_line.get(gid)
            if line is None:
                continue

            over = self.legend_label_overrides.get((slot_index, choice_name), {})
            if gid in over:
                line.set_label(over[gid])

        leg = ax.get_legend()
        if leg is not None:
            texts = leg.get_texts()
            # legend order usually matches ax.lines order; we prefer 'expected'
            ordered_lines = [gid_to_line.get(gid) for gid in expected if gid_to_line.get(gid) is not None]
            for txt, ln in zip(texts, ordered_lines):
                try:
                    txt.set_text(ln.get_label())
                except Exception:
                    pass

        self._block_axis_callback = True
        ax.set_xlim(current_xlim)
        ax.set_ylim(current_ylim)
        if is_3d and current_zlim is not None:
            ax.set_zlim(current_zlim)
        self._block_axis_callback = False

        # Legend text update (keep your existing code if desired)
        self._rebuild_slot_artists_inventory(slot_index)
        self.canvas.draw_idle()

    # def update_all_slots_frame(self, traj: dict, t, control_panel) -> None:
    #     """Convenience: update all slots using the current control-panel slot configs."""
    #     self.traj = traj
    #     self.t = t

    #     num_slots = len(self.axes)
    #     for slot_index in range(num_slots):
    #         cfg = control_panel.get_slot_config(slot_index)
    #         if cfg is None:
    #             continue
    #         dropdown_index, options, slot_cfg = cfg
    #         self.update_slot_frame(slot_index, dropdown_index, options, slot_cfg)

    def _on_press(self, event) -> None:
        """ Decides what to do when the user clicks on an axis """

        if event.button != 1:
            return
        ax = event.inaxes
        if ax is None or ax not in self.axes:
            return
    
        self.dragging = True
        self._update_snap(event, ax)

    def _update_snap(self, event, ax) -> None:
        """ 
        displays coordinate info (the snap artist) when the user clicks while not in panning mode
        also updates it simultaneously
        """
        if ax is None or ax not in self.axes: return
        if event.xdata is None or event.ydata is None: return

        ex, ey = event.x, event.y
        best_line = None
        best_idx = None
        best_dist = np.inf

        trans = ax.transData

        for line in ax.lines:
            if not line.get_visible(): continue

            xdata = np.asarray(line.get_xdata(), dtype= float)
            ydata = np.asarray(line.get_ydata(), dtype= float)
            if xdata.size == 0: continue

            pts = np.column_stack((xdata, ydata))
            disp = trans.transform(pts)
            dx = disp[:,0] - ex
            dy = disp[:,1] - ey
            dist = dx**2 + dy**2

            idx = int(np.argmin(dist))
            d = dist[idx]

            if d < best_dist:
                best_dist = d
                best_line = line
                best_idx = idx

        marker, annot = self.snap_artists.get(ax, (None, None))
        if marker is None or annot is None:
            return

        if best_line is None:
            marker.set_visible(False)
            annot.set_visible(False)
            self.canvas.draw_idle()
            if hasattr(ax, "get_zlim3d"):
                self._clamp_3d_view(ax)
            return

        color = best_line.get_color()
        marker.set_color(color)

        x_near = best_line.get_xdata()[best_idx]
        y_near = best_line.get_ydata()[best_idx]

        marker.set_data([x_near], [y_near])
        marker.set_visible(True)

        annot.xy = (x_near, y_near)
        annot.set_text(f"({x_near:g}, {y_near:g})")
        annot.set_visible(True)

        self.canvas.draw_idle()

    def on_motion(self, event):
        if not self.dragging:
            return
        ax = event.inaxes
        if ax is None or ax not in self.axes:
            return

        self._update_snap(event, ax)

        active_tool = getattr(self.toolbar, "mode", None)
        if active_tool == "pan/zoom":
            self._on_axis_limits_changed(ax)

    def on_release(self, event):
        # updating axis limits here because for some stupid reason the lim_changed callbacks are unresponsive
        # for right-click magnifications. So instead it just updates the limits after they release their mouse
        ax = event.inaxes
        if ax is not None and ax in self.axes:
            self._on_axis_limits_changed(ax)

        if event.button != 1:
            return
        self.dragging = False
    
        for marker, annot in self.snap_artists.values():
            marker.set_visible(False)
            annot.set_visible(False)

        self.canvas.draw_idle()

    def resizeEvent(self, a0):
        super().resizeEvent(a0)
        # Only refresh when we're in a single-axes state (the thing you're treating as “base”)
        # if getattr(self, "axes_rows", 1) == 1 and getattr(self, "axes_cols", 1) == 1:
        #     self._recompute_base_box_aspect()

    def _do_tight_layout(self):
        self.figure.tight_layout()
        self.canvas.draw_idle()

    def apply_plotting_data(self, new_plotting_data: dict) -> None:
        self.data = new_plotting_data
        self.legend_label_overrides.clear()

        # 2) Clear caches that depend on prior spec / prior artists
        self._logged_plot_keys.clear()
        self._slot_images.clear()
        self._slot_cbar.clear()

        for slot_index, ax in enumerate(self.axes):
            state = self._slot_settings.get(slot_index)
            if not state:
                continue
            dropdown_choice, options, slot_cfg = state
            self.plot_slot_from_scratch(slot_index, dropdown_choice, options, slot_cfg)

        self.canvas.draw_idle()
