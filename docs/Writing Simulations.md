In this section we'll cover best practices for writing simulations for Overseer. 

## Non-Python Simulations
The user is given complete freedom of what the functions/generators are allowed to interact with Overseer. Because you are running arbitrary Python code, there is nothing stopping you from simply writing code to tell Python to run some other interpreter, or some other binary file compiled from a different language, interface with it in some way, and pass the results on to Overseer. 

A proof of concept for this is a [project I am currently (at the time of writing this) involved in at Boston College](https://github.com/BC-LTEWG/Labor-Time-Economy-Simulation). The goal of this project is to build an agent based simulation of a labor time economy, and we have chosen C++ as our language to write the software in. Nonetheless, [I've developed a data aggregation layer](https://github.com/BC-LTEWG/LTE-Data-Aggregation-Layer) to that project which allows us to investigate our model using Overseer. In this section, I'll try and lay out how this interface works in general, so that others can easily copy and reuse the same strategy if they choose.

The structure overall of the model will look like this:
```
model_name/
├── __init__.py
├── data/
│   ├── control_panel_data.yml
│   ├── params.yml
│   └── plotting_data.yml
└── simulation/
    ├── __init__.py
    ├── parameters.py
    ├── Collector.py
    ├── Reporter.py
    └── simulation.py
```

Our C++ code will simply be
```python
EXE_PATH = "path to C++ binary"

def get_trajectories(params: Params):
    reporter = Reporter(EXE_PATH, params, LOG_PATH)
    sim_finished = False
    while not sim_finished:
        sim_finished = reporter.step()
        traj, t = reporter.get_data()
        yield traj, t
```

Just like what we did in the prior examples, we simply instantiate a model object and step through it. Only difference is that our `reporter` instance will not be running the model itself. The basic structure is this:

- The reporter instantiates a Collector object, and tells the collector instance to begin collecting.
- The collector instance runs the process as a subprocess.
- The subprocess prints the relevant data to standard output. (Yes, literally just the normal print function in whatever programming language.) 
- The collector, when running the subprocess, creates a pipe through which it can monitor the standard output. 
- The collector loops over the standard output, collecting the data bits and loading them onto a queue. 
- To 'step' the reporter is to have the reporter loop over the collector's queue until finding data that a step of the actual simulation has completed, aggregating the data together as it does so. 

The collector itself is completely general and reusable. An example implementation which you can feel free to copy and paste is:

```python
import queue, os, json
from dataclasses import dataclass
import subprocess, threading

@dataclass
class StreamItem:
    stream: str
    kind: str
    payload: object

class Collector:
    """ 
    Container class that continually unloads the standard output/standard error of 
    the simulation into a queue, where it will be safe until ready for processing
    """
    def __init__(self, bin_path: str, args: list = ["-j"]):
        self.output_queue = queue.Queue(maxsize= 10000)
        self.bin_path = bin_path
        self.args = args

    def get_next(self):
        """ Tiny wrapper for dequeueing """
        try:
            return self.output_queue.get(timeout= 0.05)
        except queue.Empty:
            return StreamItem("meta", "wait", None)

    def start_sim_and_begin_collection(self):
        """ 
        Starts the subprocess, creates threads for standard output and standard error, 
         and starts collecting.
        """
        if os.name == "nt":
            self.proc = subprocess.Popen(
                ["cmd", "/c", self.bin_path, *self.args],
                stdout= subprocess.PIPE,
                stderr= subprocess.PIPE,
                creationflags=subprocess.CREATE_NO_WINDOW,
                text= True,
                bufsize= 1,
            )
        else:
            self.proc = subprocess.Popen(
                [self.bin_path, *self.args],
                stdout= subprocess.PIPE,
                stderr= subprocess.PIPE,
                text= True,
                bufsize= 1,
            )
        assert self.proc.stdout is not None
        
        self.out_thread = threading.Thread(
            target= self.collect,
            args= (self.proc.stdout, "stdout"),
            daemon= True,
        )
        self.err_thread = threading.Thread(
            target= self.collect,
            args= (self.proc.stderr, "stderr"),
            daemon= True,
        )

        self.out_thread.start()
        self.err_thread.start()

        return self.proc

    def collect(self, pipe, stream_name):
        """ Collect standard output/error, unload it into the queue """
        try:
            for line in pipe:
                line = line.strip()
                if not line:
                    continue

                if stream_name == "stdout":
                    try:
                        self.output_queue.put(StreamItem("stdout", "json", json.loads(line)))
                    except json.JSONDecodeError:
                        self.output_queue.put(StreamItem("stdout", "text", line))
                else:
                    self.output_queue.put(StreamItem("stderr", "text", line))

        except Exception as e:
            self.output_queue.put(StreamItem(stream_name, "error", e))
        finally:
            try:
                pipe.close()
            except Exception:
                pass
            self.output_queue.put(StreamItem(stream_name, "eof", None))
```

Some details are worth noting here:
1. It is **absolutely essential** that you give the Queue a maxsize. This is because it is often the case that the subprocess hogs all of the compute, and completes its entire simulation before the reporter has a chance to drain it at all. This will not only make your simulation stall on the Overseer side, it is also dangerous, because this could easily max out your RAM and crash your computer. **With** the maxsize set to something, even if the subprocess hogs all the compute, it will find itself throttled when the queue reachess this size, giving the reporter a chance to breathe. Data will not be lost, because computation steps of the subprocess will not be run at all. 
2. I've actually created two pipes, and using Python's threading module also two threads. One thread collects standard output, while the other collects standard error. Both deposit data into the same queue. 
3. I'm using Python's build in `json` module to easily parse data that is being logged to standard output by the other program. The lines printed to standard output conform to standard json format, for example: `{"t":44,"client":"Producer","id":3,"label":"pursued_plan","values":[130,3,4,1]}`. Python can easily parse this and turn it into a dictionary without any parsing headaches on my part. 

The Reporter class will need to be little more specific to your model's purposes, but an outline would have it looking like this:

```python
class Reporter()
    def __init__(self, bin_path, params):
        self.params = params
	    
	    self.collector = Collector(bin_path, args)
        self.collector.start_sim_and_begin_collection()
        
        
    def step(self) -> bool:
        while True:
            if self.stdout_done and self.stderr_done:
                return True

            item = self.collector.get_next()

            if item.kind == "error":
                raise RuntimeError(f"{item.stream} reader failed: {item.payload}")

            if item.stream == "meta":
                if item.kind == "wait":
                    return False
                continue

            if item.stream == "stderr":
                if item.kind == "eof":
                    self.stderr_done = True
                else:
                    self.text_log.append((self.current_t, "stderr", item.payload))
                continue

            if item.stream == "stdout":
                if item.kind == "eof":
                    self.stdout_done = True
                else:
                    if self.is_logging:
                        with open(self.log_path, "a") as f:
                            print(item.payload, file= f)

                if item.kind == "json":
                    dic = item.payload
                    if self.current_t != dic["t"]:
                        if self.current_t == 0:
                            self.initialize_properties()
                            self.traj = self._declare_traj()
                        else:
                            self._update_hourly_stats()
                        self.current_t = dic["t"]
                        self.t.append(self.current_t)
                        self._process_dic(dic)
                        return False
                    else:
                        self._process_dic(dic)
                else:
                    # item.kind == "text"
                    self.text_log.append((self.current_t, "stdout", item.payload))
                continue

            if self.stdout_done and self.stderr_done:
                return True


```