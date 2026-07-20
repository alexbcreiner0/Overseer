import numpy as np
import logging
import random
logger = logging.getLogger(__name__)
from overseer.tools.dataclasses import Replace, Extend, Append
from scipy.integrate import solve_ivp

class Peasant:
    def __init__(self, society):
        self.society = society
        self.subsistence_req = society.b_1

    def harvest_and_contribute(self):
        resources = self.society.dispense_resources()
        subsistence_req_remaining = self.society.get_remaining_subsistence_requirements()
        if resources > 0:
            subsistence_contribution = min(resources, subsistence_req_remaining)
            self.society.contribute_subsistence_bundle(subsistence_contribution)
            resources -= subsistence_contribution
        if resources > 0:
            self.society.contribute_surplus_bundle(resources)

    def consume_from_subsistence(self):
        if self.society.subsistence_pool >= self.subsistence_req:
            self.society.subsistence_pool -= self.subsistence_req
            return True
        else:
            return False

class Elite:
    def __init__(self, society):
        self.society = society
        self.tax_rate = society.a
        self.subsistence_req = society.b_2

    def deduct_subsistence(self):
        if self.society.elite_resources >= self.subsistence_req:
            self.society.elite_resources -= self.subsistence_req
            return True
        else:
            return False

class Society:
    def __init__(self, params):
        self.base_T = params.T
        self.T = params.T
        self.state_T = 0
        self.b_1 = params.b
        self.b_2 = params.b_2
        self.h = params.h
        self.m_1 = params.m
        self.m_2 = params.m_2
        self.mode = params.mode
        self.elite_conflict_mag = params.elite_conflict_mag
        self.elite_conflict_rolls = params.elite_conflict_rolls

        self.k_0 = params.T / params.b
        self.r = (params.h - params.b) / params.m
        self.res = params.res

        self.a = params.a
        self.e = params.e
        self.epsilon = params.epsilon
        self.alpha = params.alpha

        self.cts_P = 1.0
        self.y = np.array([
            self.cts_P,
            0.0
        ])

        def dydt(t, y):
            P = max(y[0], 0.0)
            S = max(y[1], 0.0)

            effective_T = self.base_T + self.alpha * S

            harvest = min(effective_T, self.h * P)
            subsistence_needed = self.b_1 * P

            surplus = max(0.0, harvest - subsistence_needed)
            shortfall = max(0.0, subsistence_needed - harvest)

            births = surplus / self.m_1
            deaths = shortfall / self.b_1

            dN = births - deaths

            if self.mode == "state_classless" or self.mode == "state_class":
                dS = surplus / self.a - P / self.e
                if S <= 1e-8 and dS < 0:
                    dS = 0.0
            else:
                dS = 0.0

            return np.array([dN, dS])

        self.dydt = dydt

        self.current_t = 0
        self.current_t_cts = 0.0
        self.total_resources = 0
        self.surplus_pool = 0
        self.subsistence_pool = 0
        self.state_resources = 0
        self.elite_resources = 0
        self.elite_surplus_pool = 0
        self.elite_subsistence_pool = 0

        self.peasants = [Peasant(self) for _ in range(params.P_0)] # start with 1 agent.
        if self.mode == "state_class":
            self.elites = [Elite(self) for _ in range(params.E_0)]
        else:
            self.elites = []

        self.traj = {
            "population": Append(len(self.peasants)),
            "elite_population": Append(len(self.elites)),
            "t": Append(self.current_t),
            "post_harvest_surplus": Append(0),
            "post_harvest_elite_surplus": Append(0)
        }

    def get_remaining_subsistence_requirements(self):
        return self.b_1 * len(self.peasants) - self.subsistence_pool

    def dispense_resources(self):
        deduction = min(self.total_resources, self.h)
        self.total_resources -= deduction
        return deduction

    def birth_new_peasants(self):
        while self.surplus_pool >= self.m_1:
            self.peasants.append(Peasant(self))
            self.surplus_pool -= self.m_1

    def birth_new_elites(self):
        while self.elite_resources >= self.m_2:
            self.elites.append(Elite(self))
            self.elite_resources -= self.m_2

    def contribute_surplus_bundle(self, amt):
        self.surplus_pool += amt

    def contribute_subsistence_bundle(self, amt):
        self.subsistence_pool += amt

    def step(self):
        self.traj = {
            "population": Append(len(self.peasants)),
            "elite_population": Append(len(self.elites)),
            "t": Append(self.current_t),
            "cts_t": Append(self.current_t_cts)
        }

        t_eval = np.linspace(self.current_t_cts, self.current_t_cts+1, self.res+1)[1:]
        sol = solve_ivp(
            self.dydt,
            (float(self.current_t_cts), float(self.current_t_cts+1)),
            self.y,
            # method= "BDF",
            t_eval= t_eval,
            max_step= 1.0
        )

        self.y = sol.y[:,0]
        m = sol.y.shape[1]
        new_cts_Ps = [self.y[0]]
        new_cts_Ss = [self.y[1]]
        new_cts_t_cts = [sol.t[0]]

        for i in range(m):
            self.y = sol.y[:, i]
            new_cts_Ps.append(self.y[0])
            new_cts_Ss.append(self.y[1])
            new_cts_t_cts.append(sol.t[i])

        self.traj["population_cts"] = Extend(new_cts_Ps)
        self.traj["state_resources_cts"] = Extend(new_cts_Ss)
        self.traj["t_cts"] = Extend(new_cts_t_cts)

        self.current_t += 1
        self.current_t_cts = new_cts_t_cts[-1]

        self.total_resources = self.T # replenish resources

        if self.mode == "state_class":
            self.elites_extract_resources()

        self.subsistence_pool = 0
        for agent in self.peasants:
            agent.harvest_and_contribute() # fill up pools

        deletions = 0
        for agent in self.peasants:
            consumed = agent.consume_from_subsistence()
            if not consumed:
                deletions += 1

        for _ in range(deletions):
            if len(self.peasants) > 0:
                del self.peasants[-1]

        if self.mode == "state_class":
            deletions = 0
            for elite in self.elites:
                consumed = elite.deduct_subsistence()
                if not consumed:
                    deletions += 1

            for _ in range(deletions):
                if len(self.elites) > 0:
                    del self.elites[-1]

        if self.mode == "state_classless":
            self.apply_state_deductions()
            self.deduct_state_expenses()
            self.apply_state_infrastructure()
        elif self.mode == "state_class":
            self.apply_state_deductions(elites= True)
            self.deduct_state_expenses(elites= True)
            self.apply_state_infrastructure()
        else:
            self.traj["state_revenue"] = Append(0)
            self.traj["state_expenses"] = Append(0)
            self.traj["state_resources"] = Append(0)

        self.traj["post_harvest_surplus"] = Append(self.surplus_pool)
        self.traj["post_harvest_surplus_elites"] = Append(self.elite_resources)
        self.birth_new_peasants()
        self.birth_new_elites()

        for i in range(self.elite_conflict_rolls):
            prob = self.elite_conflict_mag + (1 - self.elite_conflict_mag) / (1 + np.e ** (-self.state_resources))
            if len(self.elites) >= 2:
                roll = random.binomialvariate(n= 1, p= prob)
                if roll == 1:
                    del self.elites[-1]

    def apply_state_deductions(self, elites= False):
        if elites:
            new_revenue = self.elite_resources // self.a
            self.elite_resources -= new_revenue
        else:
            new_revenue = self.surplus_pool // self.a
            self.surplus_pool -= new_revenue

        self.traj["state_revenue"] = Append(new_revenue)
        self.state_resources += new_revenue

    def deduct_state_expenses(self, elites= False):
        if elites:
            expenses = len(self.elites) // self.e
        else:
            expenses = len(self.peasants) // self.e

        self.traj["state_expenses"] = Append(expenses)
        self.state_resources = max(0, self.state_resources - expenses)

    def apply_state_infrastructure(self):
        self.state_T = self.alpha * self.state_resources
        self.T = self.base_T + self.state_T
        self.traj["state_resources"] = Append(self.state_resources)

    def elites_extract_resources(self):
        extraction_rate = len(self.elites) / (1 + len(self.elites))
        extraction_total = self.epsilon * extraction_rate * self.total_resources
        self.total_resources -= extraction_total
        self.elite_resources += extraction_total

    def get_data(self):
        return self.traj
