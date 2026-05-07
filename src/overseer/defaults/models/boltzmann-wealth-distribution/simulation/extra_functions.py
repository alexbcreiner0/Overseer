import mesa
from typing import Tuple
import numpy as np
import sys

def get_discrete_entropy(model):
    
    data = [agent.wealth for agent in model.agents]
    _, counts = np.unique(data, return_counts= True)
    probs = counts / counts.sum()

    H = -np.sum(probs * np.log2(probs))
    return H

def compute_gini(model):
    agent_wealths = [agent.wealth for agent in model.agents]
    x = sorted(agent_wealths)
    n = model.num_agents
    B = sum(x_i * (n-i) for i, x_i in enumerate(x)) / (n * sum(x))
    return 1 + (1/n) - 2*B

def total_money(model):
    return sum(agent.wealth for agent in model.agents)

class MoneyAgent(mesa.Agent):
    def __init__(self, model, rand_starting_wealth= False):
        super().__init__(model)

    def exchange(self):
        if self.wealth > -self.model.max_debt:
            other_agent = self.random.choice(self.model.agents)
            if other_agent is not None:
                gross_transaction_amt = 1

                if self.model.transaction_type == "random_frac":
                    max_amt = self.wealth + self.model.max_debt
                    gross_transaction_amt = self.random.uniform(0, max_amt)

                tax = 0.0
                if self.model.taxation == "transaction":
                    # actual money exchanged is agent wealth, only tax that.
                    real_transaction_amt = min(max(self.wealth, 0), gross_transaction_amt) 
                    tax = self.model.delta * real_transaction_amt

                net_transaction_amt = gross_transaction_amt - tax

                self.model.tax_pool += tax
                other_agent.wealth += net_transaction_amt
                self.wealth -= gross_transaction_amt

class MoneyModel(mesa.Model):
    def __init__(self, params, seed= None):
        super().__init__(seed= seed)
        self.num_agents = params.n_agents
        self.datacollector = mesa.DataCollector(
            model_reporters= {
                "Gini": compute_gini, 
                "Entropy": get_discrete_entropy,
                "total_money": total_money
            },
            agent_reporters= {"Wealth": "wealth"},
        )
        self.taxation = params.taxation
        self.delta = params.delta
        self.tau_s = params.tau_s
        self.transaction_type = params.transaction_type
        self.tax_pool = 0
        self.current_t = 0
        self.max_debt = params.max_debt

        MoneyAgent.create_agents(model= self, n= params.n_agents)
        for agent in self.agents:
            agent.wealth = 1
        self.datacollector.collect(self)

    def step(self):
        a = self.agents.shuffle().select(at_most= 1)
        a.shuffle_do("exchange")
        if self.taxation != "None" and self.current_t % self.tau_s == 0:
            dist = self.tax_pool / self.num_agents
            for agent in self.agents:
                agent.wealth += dist
                self.tax_pool -= dist
            if self.tax_pool > 0.0:
                lucky = self.random.choice(self.agents)
                lucky.wealth += self.tax_pool
            self.tax_pool = 0

        self.datacollector.collect(self)
        self.current_t += 1

    def get_traj(self):
        traj = {}
        traj["wealth"] = np.array([a.wealth for a in self.agents])
        traj["gini"] = self.datacollector.get_model_vars_dataframe()["Gini"].to_numpy()
        traj["entropy"] = self.datacollector.get_model_vars_dataframe()["Entropy"].to_numpy()
        traj["total_money"] = self.datacollector.get_model_vars_dataframe()["total_money"].to_numpy()

        return traj

