from PyQt6 import (
    QtCore as qc,
    QtWidgets as qw,
    QtGui as qg
)
import numpy as np
import queue as py_queue

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
        self.t = {}

    def _find_plot_dict_in_metadata(self, key):
        for _, dic in self.plotting_data.items():
            if key in dic["plots"]:
                return dic["plots"][key]
        return -1

    def _update_traj(self, traj, t= None):
        for key, val in traj.items():
            plot_dict = self._find_plot_dict_in_metadata(key)
            if plot_dict == -1 or plot_dict.get("data_stream") is None:
                self.traj[key] = val
            if key in self.traj:
                if isinstance(val, float) and isinstance(self.traj[key], list):
                    self.traj[key].append()
                if isinstance(val, np.ndarray) or isinstance(val, list):
                    self.traj[key] = np.append(self.traj[key], [val], axis= 0)
                else:
                    self.traj[key] = np.append(self.traj[key], val)
            else:
                self.traj["key"] = np.append()

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
        latest = None
        saw_done = False

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
                saw_done = True
                continue

            if len(msg) >= 2 and msg[1] == "ERROR":
                self.stop()
                self.error.emit(msg)
                return

            latest = msg

        if latest is not None:
            output = latest[1:]
            if len(output) == 2:
                traj, t = output
                if not isinstance(traj, dict) or not isinstance(t, (list, np.ndarray)):
                    self.error.emit("Two outputs detected, but either first is not a dictionary or second is not a list/numpy array.")
                    return
                else:
                    self.progress.emit(traj, t)
            elif len(output) != 1:
                self.error.emit("Outputs yielded by sim must either be a single dictionary or a dictionary along with a list/numpy array.")
                return
            else:
                traj = output[0]
                if isinstance(traj, dict):
                    self.progress.emit(traj, None)
                else:
                    self.error.emit("invalid output")
                    return

        if saw_done:
            self.stop()
            self.done.emit()

           
