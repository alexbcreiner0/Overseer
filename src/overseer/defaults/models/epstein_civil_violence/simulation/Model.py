import mesa
import numpy as np
from enum import Enum
import math

from mesa.discrete_space import OrthogonalMooreGrid, OrthogonalVonNeumannGrid

class CitizenState(Enum):
    ACTIVE = 1
    QUIET = 2
    ARRESTED = 3

class EpsteinAgent(mesa.discrete_space.CellAgent):
    def update_neighbors(self):
        self.neighborhood = self.cell.get_neighborhood(radius = self.vision)
        self.neighbors = self.neighborhood.agents
        self.empty_neighbors = [c for c in self.neighborhood if c.is_empty]

    def move(self):
        if self.empty_neighbors:
            new_pos = self.random.choice(self.empty_neighbors)
            self.move_to(new_pos)

class Citizen(EpsteinAgent):
    def __init__(self, model):
        super().__init__(model)

        self.hardship = self.random.random()
        self.risk_aversion = self.random.random()
        self.vision = self.model.citizen_vision

        self.state = CitizenState.QUIET
        self.jail_sentence = 0
        self.grievance = self.hardship * (1 - self.model.legitimacy)

        self.arrest_probability = None
        self.neighborhood = []
        self.neighbors = []
        self.empty_neighbors = []

    def step(self):
        if self.jail_sentence:
            self.jail_sentence -= 1
            return

        self.update_neighbors()
        self.update_estimated_arrest_probability()

        net_risk = self.risk_aversion * self.arrest_probability
        if (self.grievance - net_risk) > self.model.active_threshold:
            self.state = CitizenState.ACTIVE
        else:
            self.state = CitizenState.QUIET

        if self.model.movement:
            self.move()

    def update_estimated_arrest_probability(self):
        cops_in_vision = 0
        actives_in_vision = 1
        for neighbor in self.neighbors:
            if isinstance(neighbor, Cop):
                cops_in_vision += 1
            elif neighbor.state == CitizenState.ACTIVE:
                actives_in_vision += 1

        self.arrest_probability = 1 - math.exp(
            -1 * self.model.arrest_prob_const * math.floor(cops_in_vision / actives_in_vision)
        )

class Cop(EpsteinAgent):
    def __init__(self, model):
        super().__init__(model)
        self.vision = self.model.cop_vision

    def step(self):
        self.update_neighbors()
        active_neighbors = []
        for agent in self.neighbors:
            if isinstance(agent, Citizen) and agent.state == CitizenState.ACTIVE:
                active_neighbors.append(agent)
        if active_neighbors:
            arrestee = self.random.choice(active_neighbors)
            arrestee.jail_sentence = self.random.randint(0, self.model.max_jail_term)
            arrestee.state = CitizenState.ARRESTED

        self.move()


class EpsteinModel(mesa.Model):
    def __init__(self, params):
        super().__init__()
        
        self.width = params.width
        self.height = params.height
        self.citizen_density = params.citizen_density
        self.cop_density = params.cop_density
        self.citizen_vision = params.citizen_vision
        self.cop_vision = params.cop_vision
        self.legitimacy = params.legitimacy
        self.max_jail_term = params.max_jail_term
        self.active_threshold = params.active_threshold
        self.arrest_prob_const = params.arrest_prob_const
        self.movement = params.movement
        self.T = params.T
        self.activ_order = params.activ_order
        self.grid_type = params.grid_type

        # THIS EXISTS?!
        match self.grid_type:
            case "Moore":
                self.grid = OrthogonalMooreGrid(
                    (self.width, self.height), capacity= 1, torus= True, random= self.random
                )
            case "Von Neumann":
                self.grid = OrthogonalVonNeumannGrid(
                    (self.width, self.height), capacity= 1, torus= True, random= self.random
                )
            case _:
                raise ValueError(
                    f"Unknown value of grid_type: {self.grid_type}"
                )

        model_reporters = {
            "active": CitizenState.ACTIVE.name,
            "quiet": CitizenState.QUIET.name,
            "arrested": CitizenState.ARRESTED.name,
        }
        agent_reporters = {
            "jail_sentence": lambda a: getattr(a, "jail_sentence", None),
            "arrest_probability": lambda a: getattr(a, "arrest_probability", None),
        }
        self.datacollector = mesa.DataCollector(
            model_reporters= model_reporters, agent_reporters= agent_reporters
        )
        
        if self.cop_density + self.citizen_density > 1:
            raise ValueError("Cop density + citizen density must be less than 1")

        for cell in self.grid.all_cells:
            klass = self.random.choices(
                [Citizen, Cop, None],
                cum_weights = [
                    self.citizen_density,
                    self.citizen_density + self.cop_density,
                    1,
                ]
            )[0]

            if klass is not None:
                agent = klass(self)
                agent.move_to(cell)

        self.running = True
        self._update_counts()
        self.datacollector.collect(self)

    def step(self):
        self.agents.shuffle_do("step")

        self._update_counts()
        self.datacollector.collect(self)

        if self.time > self.T:
            self.running = False

    def _update_counts(self):
        counts = self.agents_by_type[Citizen].groupby("state").count()

        for state in CitizenState:
            setattr(self, state.name, counts.get(state, 0))

    def get_agent_states(self):
        state_map = {
            CitizenState.ACTIVE: 1,
            CitizenState.QUIET: 2,
            CitizenState.ARRESTED: 3,
        }
        states= np.array([state_map[agent.state] for agent in self.agents if isinstance(agent, Citizen)])
        _, counts = np.unique(states, return_counts= True)
        return states

    def get_agent_states_lazy(self):
        state_map = {
            CitizenState.ACTIVE: 1,
            CitizenState.QUIET: 2,
            CitizenState.ARRESTED: 3,
        }
        states= np.array([state_map[agent.state] for agent in self.agents if isinstance(agent, Citizen)])
        _, counts = np.unique(states, return_counts= True)

    def get_grid(self):
        EMPTY   = 0
        COP     = 1
        QUIET   = 2
        ACTIVE  = 3
        ARRESTED= 4

        u = np.zeros((self.height, self.width), dtype= np.int8)

        for cell in self.grid.all_cells:
            x, y = cell.coordinate

            if cell.is_empty:
                u[y,x] = EMPTY
                continue

            agent = cell.agents[0]

            # Note: matplotlib expects a 2D array of the form (rows, columns), but the cell (x,y) coordinates specify x (i.e. the column) first
            # so we have to reverse, hence the u[y,x] stuff here.
            if isinstance(agent, Cop):
                u[y,x] = COP
            elif isinstance(agent, Citizen):
                if agent.state == CitizenState.ARRESTED:
                    u[y,x] = ARRESTED
                elif agent.state == CitizenState.ACTIVE:
                    u[y,x] = ACTIVE
                else:
                    u[y,x] = QUIET
            else:
                u[y,x] = EMPTY

        return u

    
