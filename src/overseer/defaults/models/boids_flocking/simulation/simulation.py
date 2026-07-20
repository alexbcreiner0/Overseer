from typing import Any
from .parameters import Params
from overseer.tools.dataclasses import Replace, Extend, Append
from mesa.experimental.continuous_space import ContinuousSpaceAgent
import numpy as np
from mesa import Model
from mesa.experimental.continuous_space import ContinuousSpace

class Boid(ContinuousSpaceAgent):
    def __init__(self, model, space, *, pos= (0,0), speed= 1, direction= (1,1), vision= 1, separation= 1, cohere= 0.03, separate= 0.015, match= 0.05):    
        super().__init__(space, model)
        self.position = pos
        self.speed = speed
        self.direction = direction
        self.vision = vision
        self.separation = separation
        self.cohere_factor = cohere
        self.separate_factor = separate
        self.match_factor = match
        self.neighbors = []
        self.angle = 0.0  # represents the angle at which the boid is moving

    def step(self):
        neighbors, dists = self.get_neighbors_in_radius(radius= self.vision)
        self.neighbors = [n for n in neighbors if n is not self]

        # just keep going where you're going if no other boids in vision
        if len(neighbors) == 0:
            self.position += self.direction * self.speed
            return
        
        # vector of all dists from neighbors
        delta = self.space.calculate_difference_vector(self.position, agents= neighbors)
        
        cohere_vector = delta.sum(axis= 0) * self.cohere_factor
        separation_vector = -1*delta[dists < self.separation].sum(axis= 0)*self.separate_factor
        match_vector = np.asarray([n.direction for n in neighbors]).sum(axis= 0)*self.match_factor
        
        self.direction += (cohere_vector + separation_vector + match_vector) / len(neighbors)
        self.direction /= np.linalg.norm(self.direction)

        self.position += self.direction * self.speed

class BoidModel(Model):
    def __init__(self, params):
        self.n_agents = params.n_boids
        self.space_width = params.space_width
        self.space_height = params.space_height
        self.vision = params.vision
        self.speed = params.speed
        self.separation = params.separation
        self.cohere = params.cohere
        self.separate = params.separate
        self.match = params.match

        super().__init__()

        self.agent_angles = np.zeros(self.n_agents)
        self.space = ContinuousSpace(
            [[0, self.space_width], [0, self.space_height]],
            torus= True,
            random= self.random,
            n_agents= self.n_agents
        )

        # size (100*self.n_agents, 200)?
        positions = self.rng.random(size= (self.n_agents, 2)) * self.space.size

        # random vectors from origin, n_agents many vectors of length 2
        directions = self.rng.uniform(-1,1, size= (self.n_agents, 2))

        Boid.create_agents(
            self,
            self.n_agents,
            self.space,
            pos= positions,
            direction= directions,
            cohere= self.cohere,
            separate= self.separate,
            match= self.match,
            speed= self.speed,
            vision= self.vision,
            separation= self.separation
        )

        self.average_heading = None
        self.update_average_heading()

    def update_average_heading(self):
        if not self.agents:
            self.average_heading = 0
            
        headings = np.array([agent.direction for agent in self.agents])
        mean_heading = np.mean(headings, axis= 0)
        self.average_heading = np.arctan2(mean_heading[1], mean_heading[0])

    def calculate_angles(self):
        d1 = np.array([agent.direction[0] for agent in self.agents])
        d2 = np.array([agent.direction[1] for agent in self.agents])

        self.agent_angles = np.degrees(np.arctan2(d1, d2))
        for agent, angle in zip(self.agents, self.agent_angles):
            agent.angle = angle

    def step(self):
        self.agents.shuffle_do("step")
        self.update_average_heading()
        self.calculate_angles()

    def get_positions(self):
        return [agent.position for agent in self.agents]

    def get_directions(self):
        return [agent.direction for agent in self.agents]

    def get_data_to_pass(self):
        data = {
            "boid_x": Replace([agent.position[0] for agent in self.agents]),
            "boid_y": Replace([agent.position[1] for agent in self.agents]),
            "boid_u": Replace([agent.direction[0] for agent in self.agents]),
            "boid_v": Replace([agent.direction[1] for agent in self.agents])
        }

        return data

def get_trajectories(params: Params, event_queue):
    boid_model = BoidModel(params)

    for _ in range(params.T):
        boid_model.step()

        yield boid_model.get_data_to_pass()


