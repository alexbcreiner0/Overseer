from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)
import numpy as np
import queue as py_queue
from .tools.dataclasses import Extend, Replace, Append

class BridgeWorker(qc.QObject):
    """
    Worker that rapidly drains the data queue. Later will be rejobbed into the
    guy which 'assembles' the data from smaller serialized data points.
    """
    progress = qc.pyqtSignal(object, object)
    done = qc.pyqtSignal()
    error = qc.pyqtSignal(object)

    def __init__(self, mp_queue, run_id, plotting_data, parent= None):
        super().__init__(parent)
        self.mp_queue = mp_queue
        self._running = True
        self._drain_timer = None
        self.run_id = run_id
        self.plotting_data = plotting_data
        self.traj = {}
        self.t = None

    def _find_plot_dict_in_metadata(self, key):
        for _, dic in self.plotting_data.items():
            plots = dic["plots"]
            for _, plot_dict in plots.items():
                if key in plot_dict.values():
                    return plot_dict
        return -1

    def _update_progress(self, traj, t= None):

        if t is not None:
            self.t = t

        for key, payload in traj.items():
            if isinstance(payload, Append):
                self.traj.setdefault(key, []).append(payload.value)
            elif isinstance(payload, Extend):
                self.traj.setdefault(key, []).extend(payload.value)
            elif isinstance(payload, Replace):
                self.traj[key] = payload.value
            else:
                self.traj[key] = payload

    @qc.pyqtSlot()
    def start(self):
        self._drain_timer = qc.QTimer(self)
        self._drain_timer.setInterval(10)
        self._drain_timer.timeout.connect(self._drain_once)
        self._drain_timer.start()
    
    @qc.pyqtSlot()
    def stop(self):
        if self._drain_timer is not None:
            self._drain_timer.stop()
            self._drain_timer.deleteLater()
            self._drain_timer = None

    @qc.pyqtSlot()
    def _drain_once(self):
        # latest = None
        saw_done = False
        saw_data = False

        while True:
            try:
                msg = self.mp_queue.get_nowait()
            except py_queue.Empty:
                break

            if not (isinstance(msg, tuple) and msg):
                continue

            if msg[0] != self.run_id:
                continue

            if len(msg) >= 2 and msg[1] == "DONE":
                print(f"Done!")
                saw_done = True
                continue

            if len(msg) >= 2 and msg[1] == "ERROR":
                self.stop()
                self.error.emit(msg)
                return

            output = msg[1:]
            if len(output) == 2:
                traj, t = output
                if not isinstance(traj, dict) or not isinstance(t, (list, np.ndarray)):
                    self.error.emit("Two outputs detected, but either first is not a dictionary or second is not a list/numpy array.")
                    return
                else:
                    self._update_progress(traj, t)
                saw_data = True
                    # self.progress.emit(traj, t)
            elif len(output) != 1:
                self.error.emit("Outputs yielded by sim must either be a single dictionary or a dictionary along with a list/numpy array.")
                return
            else:
                traj = output[0]
                if isinstance(traj, dict):
                    self._update_progress(traj)
                    # self.progress.emit(traj, None)
                else:
                    self.error.emit("invalid output")
                    return
                
                saw_data = True

        if saw_data:
            self.progress.emit(self.traj, self.t)

        if saw_done:
            self.stop()
            self.done.emit()

           
