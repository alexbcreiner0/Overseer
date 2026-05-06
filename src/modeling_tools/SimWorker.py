import logging
import traceback
logger = logging.getLogger(__name__)

from PyQt6 import (
    QtWidgets as qw,
    QtGui as qg,
    QtCore as qc
)
import time, inspect
from multiprocessing import Process, Pool
import importlib
import queue as py_queue
from modeling_tools.tools.loader import params_from_mapping, to_plain

def put_latest(q, msg, stop_event):
    while True:
        if stop_event.is_set():
            return False
        try:
            q.put_nowait(msg)
            return True
        except py_queue.Full:
            # drop one old item and try again
            try:
                q.get_nowait()
            except py_queue.Empty:
                pass

def child_run(
        queue, run_id, module_path,
        func_name, params_path, params,
        stop_event, pause_event, sleep_value,
        yield_every
    ):
    try:
        mod = importlib.import_module(module_path)
        func = getattr(mod, func_name)
        params_dataclass = params_from_mapping(params, params_path)

        result = func(params_dataclass)

        if inspect.isgenerator(result):
            iterator = result
        else:
            # make it so we can iterate over
            iterator = [result]

        for i, output in enumerate(iterator):
            if stop_event.is_set():
                break

            while not pause_event.is_set():
                if stop_event.is_set():
                    break
                time.sleep(0.02)

            dt = sleep_value.value
            if dt > 0:
                time.sleep(dt)

            if yield_every <= 1 or (i % yield_every) == 0:
                if isinstance(output, tuple):
                    payload = (run_id,)+output
                else:
                    payload = (run_id, output)

                if not put_latest(queue, payload, stop_event):
                    break
                # queue.put((run_id, traj, t))

        queue.put((run_id, "DONE",))

    except Exception as ex:
        tb = traceback.format_exc()
        queue.put((run_id, "ERROR", repr(ex), tb, module_path, func_name))

class SimController(qc.QObject):
    """ Guy who runs the sims. """
    progress = qc.pyqtSignal(object, object)          # traj, t
    finished = qc.pyqtSignal(object, object, object)  # traj, t, e

    def __init__(self, ctx, parent= None):
        super().__init__(parent)
        self.ctx = ctx

        self._proc = None
        self._run_id = None
        self._yield_every = 5

        self._pause_event = ctx.Event()
        self._pause_event.set() # default to unpaused
        self._stop_event = ctx.Event()
        self._sleep_value = ctx.Value("d", 0)

        self._stop = False
        self._pause = False

    def configure(self, env, *, run_id, model_info, params, mp_queue, sleep_time, yield_every):
        sim_model = model_info["details"]["simulation_model"]

        self._run_id = run_id
        self._yield_every = yield_every
        self.mp_queue = mp_queue
        self.env = env

        self._module_path = f"models.{sim_model}.simulation.simulation" # multiprocessing expects the string
        self._func_name = model_info["details"]["simulation_function"]
        self._params_path = self.env.models_dir / sim_model / "simulation" / "parameters.py" # but my own function needs a path
        self._params_plain = to_plain(params)
        self._sleep_value.value = float(sleep_time)

        # resetting for new runs
        self._stop_event.clear()
        self._pause_event.set() 

    def is_alive(self) -> bool:
        p = self._proc
        return bool(p is not None and p.is_alive())

    def start(self):
        if self.mp_queue is None or self._run_id is None:
            raise RuntimeError("SimController not configured before start()")

        if self.is_alive():
            return

        self._proc = self.ctx.Process(
            target= child_run, 
            args=(
                self.mp_queue, 
                self._run_id,
                self._module_path, 
                self._func_name, 
                self._params_path, 
                self._params_plain, 
                self._stop_event, 
                self._pause_event, 
                self._sleep_value,
                self._yield_every
            )
        )
        self._proc.start()

    @qc.pyqtSlot(bool)
    def request_stop(self, force: bool = False):
        self._stop_event.set()
        
        p = self._proc
        if p is None:
            return

        if not force:
            return

        if p.is_alive():
            p.terminate()
            p.join(timeout= 0.5)

        if p.is_alive():
            p.kill()
            p.join(timeout= 0.5)

    @qc.pyqtSlot()
    def toggle_pause(self):
        if self._pause_event.is_set():
            self._pause_event.clear()
        else:
            self._pause_event.set()

    def set_sleep_time(self, dt: float):
        self._sleep_value.value = float(dt)

    # def _should_stop(self) -> bool:
    #     return self._stop or qc.QThread.currentThread().isInterruptionRequested()

    def join(self, timeout= 1.0) -> bool:
        """ During a demo switch, while a sim is running, this is used to force the app to wait until the old demo is down before the new one gets made """
        p = self._proc
        if p is None:
            return True
        p.join(timeout= timeout)
        return not p.is_alive()

        # try:
        #     result = self.stream_func(self.params)

        #     # if it's a normal function output (i.e. the user is not animating)
        #     if isinstance(result, tuple) and len(result) == 2:
        #         animating = False
        #         traj, t = result
        #         latest_traj, latest_t = traj, t
        #         self.progress.emit(traj, t)

        #     else:
        #         for i, frame in enumerate(result):
        #             if self._should_stop():
        #                 break

        #             time.sleep(self.sleep_time)
        #             # stop receiving new outputs if sim is paused
        #             while self._pause and not self._should_stop():
        #                 qc.QThread.msleep(25) # recheck every 25 ms

        #             if not (isinstance(frame, tuple) and len(frame) == 2):
        #                 raise TypeError(f"Streaming sim must yield (traj, t) tuples. Got {type(frame)} {frame!r}")

        #             latest_traj, latest_t = frame
        #             if latest_traj is None or latest_t is None:
        #                 continue
        #             if (i % self.yield_every) == 0:
        #                 self.progress.emit(latest_traj, latest_t)

        # except Exception as ex:
        #     latest_t_val = latest_t[-1] if latest_t is not None else None
        #     extra = {
        #         "Sim function": self.stream_func.__name__,
        #         "Animating from generator": animating,
        #         "latest t value": latest_t_val
        #     }
        #     info = (extra, ex)
        #     self.finished.emit(latest_traj, latest_t, info)
        #     return

        # self.finished.emit(latest_traj, latest_t, e)

