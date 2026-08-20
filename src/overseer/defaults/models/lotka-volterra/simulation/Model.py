import logging
logger = logging.getLogger(__name__)
import mesa
from overseer.tools.dataclasses import Replace, Extend, Append
from mesa.discrete_space import (
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
    CellAgent,
    FixedAgent,
    CellCollection
)
import random, math
import numpy as np
from scipy.integrate import solve_ivp

class Agent(CellAgent):
    def __init__(self, model, cell):
        super().__init__(model)
        self.cell = cell

    def try_reproduce(self):
        roll = self.random.binomialvariate(n=1, p=self.reprod_rate)
        if roll > 0:
            self.__class__(self.model, self.cell)

class Wolf(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reprod_rate = args[0].wolf_reprod_rate
        self.death_rate = args[0].wolf_death_rate

    def move(self):
        neighborhood = self.cell.neighborhood
        cells_with_sheep = neighborhood.select(self._has_sheep)

        target_cells = cells_with_sheep if len(cells_with_sheep) > 0 else neighborhood
        self.cell = target_cells.select_random_cell()

    def feed(self):
        for agent in self.cell.agents:
            if isinstance(agent, Sheep):
                agent.remove()

                self.try_reproduce()

    def maybe_die(self):
        roll = self.random.binomialvariate(n=1, p=self.death_rate)
        if roll > 0:
            self.remove()

    def on_time_step(self):
        self.move()
        self.feed()
        self.maybe_die()

    def _has_sheep(self, cell):
        for agent in cell.agents:
            if isinstance(agent, Sheep):
                return True
        return False

class Sheep(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.reprod_rate = args[0].sheep_reprod_rate

    def move(self):
        neighborhood = self.cell.neighborhood
        cells_without_wolves = []

        for cell in neighborhood:
            has_wolf = False

            for agent in cell.agents:
                if isinstance(agent, Wolf):
                    has_wolf = True
                    break

            if not has_wolf:
                cells_without_wolves.append(cell)

        if len(cells_without_wolves) == 0:
            return

        target_cells = cells_without_wolves
        self.cell = self.random.choice(target_cells)

    def on_time_step(self):
        self.move()
        self.try_reproduce()

    def _no_wolves(self, agent):
        return not isinstance(agent, Wolf)

class Model(mesa.Model):
    def __init__(self, params):
        super().__init__()
        self.initializing = True
        self.initialize_params(params)

        self.grid = OrthogonalMooreGrid(
            (self.grid_x, self.grid_y), capacity= math.inf, torus= False
        )

        Wolf.create_agents(
            self,
            self.init_wolf_popn,
            cell= self.random.choices(
                self.grid.all_cells.cells,
                k= self.init_wolf_popn
            )
        )

        Sheep.create_agents(
            self,
            self.init_sheep_popn,
            cell= self.random.choices(
                self.grid.all_cells.cells,
                k= self.init_sheep_popn
            )
        )

        model_reporters = {
            "Wolves": lambda m: len(m.agents_by_type[Wolf]),
            "Sheep": lambda m: len(m.agents_by_type[Sheep])
        }

        self.datacollector = mesa.DataCollector(model_reporters= model_reporters)

        self.res = params.res

        self.current_t = 0
        self.traj = self.update_traj()

        self.encounter_rate = 9 / (self.grid_x * self.grid_y)

        def dydt(t, y):
            S = y[0]
            W = y[1]

            delta_S = self.sheep_reprod_rate * S - self.encounter_rate * W * S
            delta_W = self.encounter_rate * self.wolf_reprod_rate * W * S - self.wolf_death_rate * W

            return np.array([delta_S, delta_W])

        self.dydt = dydt

        self.initializing = False

    def step(self):
        if self.current_t == 0:
            cts_sheep_current = self.traj["n_sheep_cts"].value
            cts_wolves_current = self.traj["n_wolves_cts"].value
        else:
            cts_sheep_current = self.traj["n_sheep_cts"].values[-1]
            cts_wolves_current = self.traj["n_wolves_cts"].values[-1]

        y = np.array([
            cts_sheep_current,
            cts_wolves_current
        ])
        t_eval = np.linspace(self.current_t, self.current_t+1, self.res+1)[1:]
        sol = solve_ivp(
            self.dydt,
            (float(self.current_t), float(self.current_t+1)),
            y,
            t_eval= t_eval,
            max_step= 1.0
        )

        self.agents.shuffle_do("on_time_step")
        self.datacollector.collect(self)
        self.traj = self.update_traj()

        m = sol.y.shape[1]
        new_wolf_data = []
        new_sheep_data = []
        new_t_data = []

        for i in range(m):
            new_y = sol.y[:,i]
            self.current_t_cts = sol.t[i]
            new_wolf_data.append(new_y[1])
            new_sheep_data.append(new_y[0])
            new_t_data.append(self.current_t_cts)

        self.traj["n_sheep_cts"] = Extend(new_sheep_data)
        self.traj["n_wolves_cts"] = Extend(new_wolf_data)
        self.traj["t_cts"] = Extend(new_t_data)

        self.current_t += 1

    def get_agents_grid(self):
        EMPTY = 0
        HAS_SHEEP = 1
        HAS_WOLVES = 2

        u = np.zeros((self.grid_x, self.grid_y), dtype= np.int8)

        for cell in self.grid.all_cells:
            x, y = cell.coordinate
            u[y,x] = EMPTY
            for agent in cell.agents:
                if isinstance(agent, Wolf):
                    u[y,x] = HAS_WOLVES
                    break
                elif isinstance(agent, Sheep):
                    u[y,x] = HAS_SHEEP

        return u

    def get_num_agents(self, type):
        if type == "sheep":
            return len(self.agents_by_type[Sheep])
        elif type == "wolf":
            return len(self.agents_by_type[Wolf])

    def initialize_params(self, params):
        self.grid_x = params.grid_x
        self.grid_y = params.grid_y

        self.init_sheep_popn = params.init_sheep_popn
        self.init_wolf_popn = params.init_wolf_popn

        self.sheep_reprod_rate = params.sheep_reprod_rate

        self.wolf_reprod_rate = params.wolf_reprod_rate
        self.wolf_death_rate = params.wolf_death_rate

    def update_traj(self):
        traj = {
            "agent_grid": Replace(self.get_agents_grid()),
            "t": Append(self.current_t),
            "n_sheep": Append(self.get_num_agents("sheep")),
            "n_wolves": Append(self.get_num_agents("wolf"))
        }

        if self.initializing:
            traj["grass_values"] = Replace([0,1,2])
            traj["grass_colors"] = Replace(["#717171" for _ in range(3)])
            traj["t_cts"] = Append(self.current_t)
            traj["n_sheep_cts"] = Append(self.get_num_agents("sheep"))
            traj["n_wolves_cts"] = Append(self.get_num_agents("wolf"))

        return traj
