import logging
logger = logging.getLogger(__name__)
import mesa
from mesa.discrete_space import (
    OrthogonalMooreGrid,
    OrthogonalVonNeumannGrid,
    CellAgent,
    FixedAgent,
    CellCollection
)
import random, math
import numpy as np

class Agent(CellAgent):
    def __init__(self, model, energy, cell):
        super().__init__(model)
        self.energy = energy
        self.cell = cell

    def move(self):
        """ Abstract """

    def feed(self):
        """ Abstract """

    def try_reproduce(self):
        roll = self.random.binomialvariate(n=1, p=self.reprod_rate)
        if roll > 0:
            self.energy /= 2
            self.__class__(self.model, self.energy, self.cell)

    def on_time_step(self):
        self.energy -= 1
        if self.energy <= 0:
            self.remove()
            return
        self.move()
        self.feed()
        self.try_reproduce()

class GrassPatch(FixedAgent):
    def __init__(self, model, cell):
        super().__init__(model)
        self.regrowth_time = model.grass_regrowth_time
        self.fully_grown = False
        self.regrowth_counter = 0
        self.cell = cell

    def on_time_step(self):
        if not self.fully_grown:
            self.regrowth_counter += 1
            if self.regrowth_counter >= self.regrowth_time:
                self.fully_grown = True

    def get_eaten(self):
        self.fully_grown = False
        self.regrowth_counter = 0

class Wolf(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gain_from_food = args[0].wolf_gain_from_food
        self.reprod_rate = args[0].wolf_reprod_rate

    def move(self):
        if self.cell is None:
            raise ValueError("Nonetype for cell?")
        neighborhood = self.cell.neighborhood
        cells_with_sheep = neighborhood.select(self._has_sheep)

        target_cells = cells_with_sheep if len(cells_with_sheep) > 0 else neighborhood
        self.cell = target_cells.select_random_cell()

    def feed(self):
        for agent in self.cell.agents:
            if isinstance(agent, Sheep):
                agent.remove()
                self.energy += self.gain_from_food

    def _has_sheep(self, agent):
        return isinstance(agent, Sheep)

class Sheep(Agent):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.gain_from_food = args[0].sheep_gain_from_food
        self.reprod_rate = args[0].sheep_reprod_rate

    def move(self):
        if self.cell is None:
            raise ValueError("Nonetype for cell?")

        neighborhood = self.cell.neighborhood
        cells_without_wolves = []
        cells_with_grass = []

        for cell in neighborhood:
            has_wolf = False
            has_grass = False

            for agent in cell.agents:
                if isinstance(agent, Wolf):
                    has_wolf = True
                    break
                elif isinstance(agent, GrassPatch) and agent.fully_grown:
                    has_grass = True

            if not has_wolf:
                cells_without_wolves.append(cell)

                if has_grass:
                    cells_with_grass.append(cell)

        if len(cells_without_wolves) == 0:
            return

        target_cells = cells_with_grass if len(cells_with_grass) > 0 else cells_without_wolves
        self.cell = self.random.choice(target_cells)

    def feed(self):
        for agent in self.cell.agents:
            if isinstance(agent, GrassPatch) and agent.fully_grown:
                agent.get_eaten()
                self.energy += self.gain_from_food
                break

    def _no_wolves(self, agent):
        return not isinstance(agent, Wolf)

    def _has_grass(self, agent):
        return isinstance(agent, GrassPatch) and agent.fully_grown

class Model(mesa.Model):
    def __init__(self, params):
        super().__init__()
        self.initialize_params(params)

        self.grid = OrthogonalMooreGrid(
            (self.grid_x, self.grid_y), capacity= math.inf, torus= False
        )

        self.grass_patches = []
        for cell in self.grid:
            self.grass_patches.append(GrassPatch(self, cell))
 
        Wolf.create_agents(
            self,
            self.init_wolf_popn,
            energy= 100,
            cell= self.random.choices(
                self.grid.all_cells.cells,
                k= self.init_wolf_popn
            )
        )

        Sheep.create_agents(
            self,
            self.init_sheep_popn,
            energy= 100,
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

    def step(self):
        self.agents.shuffle_do("on_time_step")
        self.datacollector.collect(self)

    def get_grass_grid(self):
        BARREN = 0
        BUDDING = int(self.grass_regrowth_time * 1/3)
        GROWING = int(self.grass_regrowth_time * 2/3)
        FULL = self.grass_regrowth_time

        u = np.zeros((self.grid_x, self.grid_y), dtype= np.int8)

        for grass_patch in self.grass_patches:
            x, y = grass_patch.cell.coordinate

            growth = grass_patch.regrowth_counter
            if growth >= FULL:
                u[y,x] = FULL
            elif growth >= GROWING:
                u[y,x] = GROWING
            elif growth >= BUDDING:
                u[y,x] = BUDDING
            else:
                u[y,x] = BARREN

        return u

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
        self.sheep_gain_from_food = params.sheep_gain_from_food

        self.wolf_gain_from_food = params.wolf_gain_from_food
        self.wolf_reprod_rate = params.wolf_reprod_rate

        self.grass_regrowth_time = params.grass_regrowth_time
