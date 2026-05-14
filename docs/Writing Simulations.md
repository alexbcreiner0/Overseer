In this section we'll cover best practices for writing simulations for Overseer. It is expected that the reader has already familiarized themselves with how to handle parameters in Overseer. If not, visit [the quick-start tutorial](Quick-Start%20Tutorial%20--%20Building%20a%20Model%20From%20Scratch) and/or [the parameters section](Parameters%20and%20Presets). 

The Python code which the user is expected to interact with is found inside of a model's `simulation` directory. The only file that they are explicitly required to edit themselves inside of here is `simulation.py`. Overseer expects to find functions in here, and it expects those functions to be usable as entry points for your model. What do these expectations amount to?
# Requirements for a valid simulation function:
- [ ] The function must accept a dataclass instance as its first input (defined in `parameters.py`). 
- [ ] The function must either output or yield either one or two things:
	 1. A dictionary with string keys.
	 2. Any (or none) of the following:
		-  A list or Numpy array $t$ representing all time steps, or more generically a default x-axis. 
		- A number (of any kind) wrapped in Overseer's Append dataclass 
		- A list or Numpy array wrapped in either Overseer's Extend dataclass or it's Replace dataclass.

The Append, Extend and Replace dataclasses are wrappers that are automatically imported in the starter code created when Overseer creates a new model, and instruct Overseer on what to do with the data it is being handed. They will be discussed in more detail below. 

The second input effectively allows you to specify a default x-axis for matplotlib to use when plotting curves. This is especially useful if you are plotting lots of different time-series curves and don't want to have to fuss over specifying an x-axis array every time. 

Alternatively to a second input, a default x-axis can also be specified by having a key in the output dictionary called `"t"`. Keep in mind that this can cause unintended behavior if you leave a field blank by accident. 

Values of the dictionary output have an identical flexibility structure to the optional $t$ output. They can be:
- Lists or Numpy arrays.
- Numbers of any kind, wrapped in the Append dataclass.
- Lists or Numpy arrays, wrapped in the Extend dataclass.
- Lists or Numpy arrays, wrapped in the Replace dataclass.

As a running example, let's define an agent based model - an implementation of the [Boltzmann wealth model](https://arxiv.org/pdf/cond-mat/0211175v1) . In this very simple model, multiple agents are initialized with the same number of coins. Each time step, two agents are selected at random, and one gives over a single coin to the other, if they have one (a trade). The `simulation.py` file for the finished model looks like this:

```python
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import random

def get_trajectories(params: Params):
    model = Model(100, 10)
    t = []
    for i in range(1000):
        traj = {
            "wealth": np.array(model.get_wealth_distn())
        }
        t.append(i)
        yield traj, np.array(t) 
        model.step()

class Agent:
    def __init__(self, id, init_money):
        self.wealth = init_money

    def trade(self, amt, other_agent):
        if amt <= self.wealth:
            other_agent.wealth += amt
            self.wealth -= amt

class Model:
    def __init__(self, n_agents, init_amt):
        self.agents = [Agent(i, init_amt) for i in range(n_agents)]

    def step(self):
        agents = random.choices(self.agents, k=2)
        agent_1 = agents[0]
        agent_2 = agents[1]
        agent_1.trade(1, agent_2)

    def get_wealth_distn(self):
        agent_wealths = [agent.wealth for agent in self.agents]
        return agent_wealths
```

The simulation function, `get_trajectories` simply instantiates a Model object, which itself instantiates multiple agents. The model is then stepped a number of times. 

If we weren't sure if the way you are doing things is valid, the Model Settings tab of Overseer has a diagnostics tool which you can run to make sure. In the case of our example we would see:

![](diagnostics.png)

We can see here that the diagnostics tool is reporting some problems, because it expects everything defined inside of the `simulation.py` file to be a function conforming to the above specifications. However, the user can create whatever other Python files they want inside of the `simulation` directory and import them. The best practice here is to define the Model and Agent classes in a different file. So our `simulation.py` file should really look like this:

```python
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
from .Resources import Model
import numpy as np

def get_trajectories(params: Params):
    model = Model(100, 10)
    t = []
    for i in range(1000):
        traj = {
            "wealth": np.array(model.get_wealth_distn())
        }
        t.append(i)
        yield traj, np.array(t) 
        model.step()
```

Where `Resources.py` is a file we have created in our `simulation` directory that contains the `Model` and `Agent` definitions. 

Below are other examples of valid simulation functions:
```python
def example_sim1(params):
	t = np.linspace(-5,5,300)
	data = {"sin": np.sin(t), "cos": np.cos(t)}
	return data, t
	
def example_sim2(params):
	t = np.linspace(-5,5,300)
	data = {"sin": np.sin(t), "cos": np.cos(t), "t": t}
	return data
	
def example_sim3(params):
	t = -5.0
	eps = 0.03
	for _ in range(300):
		t += eps
		data = {"sin": Append(np.sin(t)), "cos": Append(np.cos(t))}
	return data, Append(t)
	
def example_sim4(params):
	t = -5.0
	eps = 0.03
	for _ in range(300):
		t += eps
		data = {"sin": Append(np.sin(t)), "cos": Append(np.cos(t)), "t": Append(t)}
	return data
```

All of the above simulation functions are perfectly valid, and they all produce (effectively) the same output (please ignore the missing initial point in examples 3 and 4). To understand why all of these options are here, we need to discuss how the choices we make in this regard affect the efficiency of the simulation.
# Efficiency Tips
Suppose we wished to track the Gini coefficient in our Boltzmann wealth model from above. We might first modify our Model class to keep track of data on it's own each step:

```python
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import random

def get_trajectories(params: Params):
    model = Model(100, 10)
    t = []
    for i in range(1000):
        t.append(i)
        yield model.traj, t 
        model.step()

class Agent:
    def __init__(self, id, init_money):
        self.wealth = init_money
        self.id = id

    def trade(self, amt, other_agent):
        if amt <= self.wealth:
            other_agent.wealth += amt
            self.wealth -= amt

class Model:
    def __init__(self, n_agents, init_amt):
        self.agents = [Agent(i, init_amt) for i in range(n_agents)]
        self.traj = {
	        "wealth": self.get_wealth_distn(),
	        "gini": np.array([self.get_gini()])
        }

    def step(self):
        agents = random.choices(self.agents, k=2)
        agent_1 = agents[0]
        agent_2 = agents[1]
        agent_1.trade(1, agent_2)
        self._update_traj()
        
    def _update_traj(self):
	    self.traj["wealth"] = self.get_wealth_distn()
	    self.traj["gini"] = np.append(self.traj["gini"], self.get_gini())
    
    def get_gini(self):
        wealths = sorted([agent.wealth for agent in self.agents])
        num = 0
        den = 0
        n = len(self.agents)
        for i,y in enumerate(wealths):
            num += (n+1-i)*y
            den += y

        gini = (1/n)*(n+1-2*(num/den))
        return gini

    def get_wealth_distn(self):
        agent_wealths = [agent.wealth for agent in self.agents]
        return agent_wealths
```

This simulation works perfectly well with Overseer, but there are some choices made which are going to have a detrimental effect on efficiency. The first no no is here in the `get_gini` function:

`self.traj["gini"] = np.append(self.traj["gini"], self.get_gini())`

Numpy arrays are not efficient at appending. This operation will run in time $O(n^2)$, where $n$  is the number of steps of the simulation, because we are constructing a new array every step. A better choice would be to keep the data as a regular Python list instead:

`self.traj["gini"].append(self.get_gini())` 

Python lists are dynamic arrays, which makes appending operation amortized $O(1)$ time. 

The next issue is more conceptual. The current simulation function is of the same form as `example_sim1`. Is this inefficient? Let's consider all three pieces of data being passed to Overseer:
- The wealth array is changing in its entirety every time step, so it is not redundant at all to pass the entire wealth array each step.
- Passing the entire Gini array, however, *is* redundant, because it is only being appended to every step. We are passing the same data over and over again. 
- The $t$ array has the same problem as the Gini array. We are passing all of the old values repeatedly. 
Overall, the amount of data being sent over is $O(nm)$, where $m$ is the size of the data and $n$ is the number of steps. We are passing more and more redundant information every time step. This data transfer is not free, because your simulation runs in a separate process from Overseer itself. This data must be serialized and sent over, which takes linear time in the data. The solution to these efficiency problems are to use the Extend, Append, and Replace dataclasses to instruct Overseer more explicitly how it should manage the data you feed it on a case-by-case basis. 
## Extend, Append, and Replace
You may have noticed the following imports in the starter code when you create a model:
```python
from overseer.tools.dataclasses import Replace, Extend, Append
```
Here is how we use these in our code to avoid sending Overseer redundant data each step. In the `get_trajectories` function, we make the following change:

```python
def get_trajectories(params: Params):
    model = Model(100, 10)
    for t in range(10000):
        yield model.traj, Append(t)
        model.step()
```

There is no `t` array anymore. Now, `t` is the loop variable, and we are returning that number, with the `Append` dataclass wrapped around it. When Overseer sees this, it infers that it should be managing it's *own* `t` array, and should be appending the latest `t` value to that array. We'll do the exact same thing for the gini coefficient itself:

```python
	# in the __init__ function:
	self.traj = {
	    "wealth": self.get_wealth_distn(),
	    "gini": Append(self.get_gini())
    }

	# and then our revised _update_traj method:
    def _update_traj(self):
	    self.traj["wealth"] = self.get_wealth_distn()
	    self.traj["gini"] = Append(self.get_gini())
```

Now, no redundant data is being sent over to Overseer at all. If you value consistency, you can be more explicit about the wealth entry as well:

```python
	# in the __init__ function:
	self.traj = {
	    "wealth": self.get_wealth_distn(),
	    "gini": Append(self.get_gini())
    }

	# and then our revised _update_traj method:
    def _update_traj(self):
	    self.traj["wealth"] = Replace(self.get_wealth_distn())
	    self.traj["gini"] = Append(self.get_gini())
```

The default behavior of Overseer is to use what it's given for a key to replace what was there before it, so the `Replace` wrapper doesn't actually do anything here. It only exists for the sake of verbal clarity. 

Finally, the third type, `Extend`, is functionally the same as `Append`, except that you would use it when you want to pass multiple new pieces of data at a time in a list format. For example, if we only wanted to report progress every 100 steps, we could do something like this:

```python
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
import numpy as np
import random

def get_trajectories(params: Params):
    model = Model(100, 10)
    yield model.traj
    for t in range(10000):
        model.step()
        if t % 100 == 0 and t > 0:
            yield model.traj

class Agent:
    def __init__(self, id, init_money):
        self.wealth = init_money
        self.id = id

    def trade(self, amt, other_agent):
        if amt <= self.wealth:
            other_agent.wealth += amt
            self.wealth -= amt

class Model:
    def __init__(self, n_agents, init_amt):
        self.agents = [Agent(i, init_amt) for i in range(n_agents)]
        self.current_t = 0
        self.new_ts = [self.current_t]
        self.new_ginis = [self.get_gini()]
        self.update_interval = 100
        self.traj = {
            "wealth": Replace(self.get_wealth_distn()),
            "gini": Append(self.get_gini()),
            "t": Append(self.current_t)
        }

    def step(self):
        agents = random.choices(self.agents, k=2)
        agent_1 = agents[0]
        agent_2 = agents[1]
        agent_1.trade(1, agent_2)
        self.current_t += 1
        self.new_ts.append(self.current_t)
        self.new_ginis.append(self.get_gini())
        if self.current_t % 100 == 0 and self.current_t > 0:
            self._update_traj()
            self.new_ginis.clear()
            self.new_ts.clear()
        
    def _update_traj(self):
        print(f"{self.new_ginis=}")
        print(f"{self.new_ts=}")

        self.traj["wealth"] = self.get_wealth_distn()
        self.traj["gini"] = Extend(self.new_ginis)
        self.traj["t"] = Extend(self.new_ts)
    
    def get_gini(self):
        wealths = sorted([agent.wealth for agent in self.agents])
        num = 0
        den = 0
        n = len(self.agents)
        for i,y in enumerate(wealths):
            num += (n+1-i)*y
            den += y

        gini = (1/n)*(n+1-2*(num/den))
        return gini

    def get_wealth_distn(self):
        agent_wealths = [agent.wealth for agent in self.agents]
        return agent_wealths
```

**Warning**: If you attempt to **Append** a list-like set of numbers rather than **Extend** them, Overseer will interpret that as you trying to plot a **vector** quantity, and interpret that set of numbers as a **single** piece of data. See [the curve plotting documentation](Plots%20and%20Categories#Vector%20Plots) for more information on this feature.

One final note about building efficient simulations in Overseer is to avoid passing Numpy arrays whenever possible. Since Overseer expects to be managing its own datasets, and it wants to be ready to append the data quickly, it will always automatically convert any Numpy arrays that it's been handed into regular Python lists. This itself takes time $O(n)$. Numpy arrays are great, and no doubt have their use within your simulation. However, you should try to keep them inside of your simulation as much as possible, and avoid passing them in their raw form to Overseer. 
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

The Reporter class will need to be more specific to your model's purposes, but generic outline would look something like this:

```python
class Reporter()
    def __init__(self, bin_path, params):
        self.params = params
	    
	    self.collector = Collector(bin_path, args)
        self.collector.start_sim_and_begin_collection()
        self.current_t = 0
        self.stdout_done = False
        self.stderr_done = False
        
        self.traj = {} # initialize whatever you want
        
        # placeholder for declaring whatever you will use to aggregate your data
        self.declare_datakeeping_structures()
        
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
                        self.current_t = dic["t"]
                        self._update_traj()
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
    
    def _process_dict(self, dic):
	    # update data aggregates based on the packet
	    
	def _update_traj(self):
		# prepare a new round of data to feed to Overseer
```

The reporter initializes the Collector, tells it to start collecting, and then whenever it is told to step, it loops over the collector's queue updating its aggregates until if finds that the reported time is not the same as what the current time is according to the reporter. At this point, it takes an extra moment to prepare a new round of data for Overseer from those aggregates. 