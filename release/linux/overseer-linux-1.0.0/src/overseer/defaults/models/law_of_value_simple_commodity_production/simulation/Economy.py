import mesa
import logging
import numpy as np
from scipy import linalg
from scipy.integrate import solve_ivp

logger = logging.getLogger(__name__)

def softmax(u):
    z = u - np.max(u)
    e = np.exp(z)
    return e / e.sum()

def get_discrete_entropy(data):
    
    _, counts = np.unique(data, return_counts= True)
    probs = counts / counts.sum()

    H = -np.sum(probs * np.log2(probs))
    return H

def compute_gini(distn, N):
    x = sorted(distn)
    B = sum(x_i * (N-i) for i, x_i in enumerate(x)) / (N * sum(x))
    return 1 + (1/N) - 2*B

def get_l_and_c(L: int, R: int= 25, tol= 0.005, fixed_l= None, fixed_c= None):
    while True:
        if fixed_l is not None:
            l = fixed_l
        else:
            l = np.random.randint(1,R+1, L) 
        if fixed_c is not None:
            c = fixed_c
        else:
            c = np.random.randint(1, R+1, L)

        if fixed_l is not None and fixed_c is not None:
            break

        alpha = l.dot(1/c)
        if abs(alpha - 1.0) < abs(tol):
            if alpha < 1 and tol > 0:
                break
            if alpha > 1 and tol < 0:
                break

    return l, c

class EconAgent(mesa.Agent):
    def __init__(self, model):
        super().__init__(model)

        self.e = np.zeros(self.model.L) # endowment vector
        self.d = np.zeros(self.model.L) # deficit vector
        self.m = 0 # money
        self.profession_index = np.random.choice(self.model.L)
        self.prod_progress = 0
        self.trade_attempts = 0

    def produce(self):
        p = self.profession_index
        self.prod_progress = (self.prod_progress + 1) % self.model.l[p]
        if self.prod_progress == 0:
            self.e[p] += 1

    def consume(self):
        t = self.model.T
        if t == 0:
            return
        for i in range(self.model.L):
            if t % self.model.c[i] == 0:
                self.d[i] += 1

        o = np.array([np.minimum(self.e[i], self.d[i]) for i in range(self.model.L)])
        self.e = self.e - o
        self.d = self.d - o

    def offer_price(self, j):
        if self.m == 0:
            return 0
        else:
            return np.random.choice(self.m+1)

class Economy(mesa.Model):
    def __init__(self, params, seed= None):
        super().__init__(seed= seed)
        self.params = params
        self.N = params.N
        self.M = params.M
        self.L = params.L
        self.T = 0
        
        k = np.inf if params.max_trade_attempts == 0 else params.max_trade_attempts
        self.max_trade_attempts = k
        self.avg_interval = params.avg_interval

        if params.use_custom_l:
            self.l = params.l
        else:
            self.l = None

        if params.use_custom_c:
            self.c = params.c
        else:
            self.c = None

        print("computing l and c")
        self.l, self.c = get_l_and_c(self.L, params.R, tol= params.tol, fixed_l= self.l, fixed_c = self.c)
        print("done computing l and c")

        self.switching_period = params.C * np.max(self.c)

        EconAgent.create_agents(model= self, n= self.N)

        for agent in self.agents:
            agent.m = int(self.M / self.N)

        self.consump_errors = {agent: 0 for agent in self.agents}
        wealth = [agent.m for agent in self.agents]

        self.datacollector = mesa.DataCollector(
            model_reporters = {
                "living_labor_times": lambda m: m.l,
                "consumption_indices": lambda m: m.c,
            },
            agent_reporters = {
                "wealth": "m"
            },
        )

        self.datacollector.collect(self)

        self.traj = {
            "living_labor_times": np.array([self.l]),
            "consumption_indices": np.array([self.c]),
            "wealth": np.array(wealth),
            "gini": np.array([compute_gini(wealth, self.N)]),
            "avg_prices": np.array([np.zeros(self.L)]),
            "avg_prices_per_period": np.array([np.zeros(self.L)]),
            "sector_sizes": np.array([np.zeros(self.L)]),
            "avg_discontent": np.array([np.zeros(self.L)]),
            "MELT": np.array([0]),
            "per_period_MELT": np.array([0]),
            "values": np.array([np.zeros(self.L)]),
            "diff_eq_adjusted_values": np.array([self.params.const_gamma * self.M / self.N * self.l]),
            "per_period_values": np.array([np.zeros(self.L)]),
            "social_demand": np.array([self.N / self.c]),
            "efficient_distn": np.array([self.N * self.l / self.c]),
            "eqb_points": np.array([self.l / self.c]),
            "avg_interval_T": np.array([0]),
            "diff_eq_T": np.array([0]),
            "avg_wealth": np.array([self.M / self.N]),
            "sigma": np.array([self.M]),
            "per_period_sigma": np.array([self.M / 2]),
            "sectoral_per_period_income_proportions": np.array([np.zeros(self.L)]),
            "sectoral_per_period_income_rates": np.array([np.zeros(self.L)]),
            "sectoral_income_props": np.array([np.zeros(self.L)]),
            "long_run_ideal_expenditure_rates": np.array([np.zeros(self.L)]),
            "total_supply": np.array([np.zeros(self.L)]),
            "eta": np.array([np.sum(self.l.dot(1/self.c))])
        }

        self.new_deficit_norms = {agent: 0 for agent in self.agents}
        self.traj["p_v_corr"] = np.array([0])
        sector_sizes = np.array(self._get_sector_sizes())
        self.traj["sector_sizes"] = np.array([sector_sizes])
        self.traj["productive_capacities"] = np.array([sector_sizes / self.l])

        a = sector_sizes / self.N
        b = np.ones(self.L) / self.L

        self.traj["diff_eq_sector_sizes"] = np.array([a*self.N])
        self.traj["diff_eq_sector_props"] = np.array([a])
        self.traj["diff_eq_sector_income_props"] = np.array([b])
        self.traj["diff_eq_prices"] = np.array([self.traj["sigma"] / self.N * b / a * self.l])
        eps = 1e-7
        self.y = self._repack(np.log(a+eps),np.log(b+eps))

        self.total_prices = np.zeros(self.L)
        self.total_per_period_prices = np.zeros(self.L)
        self.total_money_exchanged = 0
        self.total_com_exchanges = np.zeros(self.L)
        self.com_exchanges_per_period = np.zeros(self.L)
        self.money_exchanged_per_period = 0
        self.total_sectoral_income = np.zeros(self.L)

        self.dydt = self._get_dydt()
    
    def _unpack(self, y):
        u = y[:self.L]
        v = y[self.L:2*self.L]

        return u, v

    def _repack(self, a, b):
        y = np.concatenate([a, b])
        return y

    def _get_dydt(self):
        
        def rhs(t: float, y: np.ndarray) -> np.ndarray:
            u, v = self._unpack(y)

            a = softmax(u)
            b = softmax(v)

            eps = 1e-12
            a_safe = np.maximum(a, eps)
            c_safe = np.maximum(self.c, eps)
            b_safe = np.maximum(b, eps)

            psi = self.params.psi
            omega = self.params.omega
            # const_gamma = self.params.const_gamma
            const_gamma = self.traj["sigma"][-1] / max(self.T, 1.0)
            # const_gamma = self.traj["per_period_sigma"][-1]

            ideal_prices = const_gamma / self.N * (b_safe / a_safe)*self.l
 
            delta_a = psi * (const_gamma*b_safe - self.N*(ideal_prices.dot(1/c_safe))*a_safe)
            delta_b = -omega * self.N * (a_safe / self.l - 1 / c_safe)

            delta_u = delta_a / a - np.sum(delta_a)
            delta_v = delta_b / b - np.sum(delta_b)

            return self._repack(delta_u, delta_v)

        return rhs
            
    def step(self):

        t_eval = np.linspace(self.T, self.T+1, 2)[1:]
        sol = solve_ivp(
            self.dydt,
            (float(self.T), float(self.T+1)),
            self.y,
            method= "BDF",
            rtol= 1e-6,
            atol= 1e-9,
            t_eval= t_eval,
            max_step= 1.0
        )

        self.y = sol.y[:,0]
        m = sol.y.shape[1]
        for i in range(m):
            self.y = sol.y[:, i]
            u, v = self._unpack(self.y)
            a, b = softmax(u), softmax(v)
            self._update_data("diff_eq_sector_income_props", b)
            self._update_data("diff_eq_sector_sizes", a*self.N)
            self._update_data("diff_eq_sector_props", a)
            # const_gamma = self.traj["sigma"][-1] / max(self.T, 1.0)
            const_gamma = self.traj["per_period_sigma"][-1]

            prices = const_gamma / self.N * b / np.maximum(a, 1e-7) * self.l
            adjusted_values = const_gamma / self.N * self.l
            self._update_data("diff_eq_adjusted_values", adjusted_values)
            self._update_data("diff_eq_prices", prices)
            self._update_data("diff_eq_T", sol.t[i])

        self.T += 1

        self.agents.do("produce")
        self.agents.do("consume")

        # Market clearing and exchange rules
        C = [i for i in range(self.L)]
        while len(C) > 0:

            c = np.random.choice(C)
            S = self._get_sellers(c)
            B = self._get_buyers(c)

            if len(S) == 0 or len(B) == 0:
                C.remove(c)
                continue

            b = np.random.choice(B)
            s = np.random.choice(S)

            b.trade_attempts += 1
            s.trade_attempts += 1

            b_price = b.offer_price(c)
            s_price = s.offer_price(c)
            p_int = np.arange(min(b_price, s_price), max(b_price, s_price)+1)
            # p_int = np.arange(b_price, s_price + 1)
            if len(p_int) == 0:
                continue

            price = np.random.choice(p_int)

            if b.m >= price:
                b.m -= price
                s.m += price
                b.e[c] += 1
                s.e[c] -= 1

                self.total_com_exchanges[c] += 1
                self.com_exchanges_per_period[c] += 1
                self.total_money_exchanged += price
                self.money_exchanged_per_period += price
                self.total_prices[c] += price
                self.total_per_period_prices[c] += price
                self.total_sectoral_income[c] += price

        for agent in self.agents:
            agent.trade_attempts = 0

        self.new_deficit_norms = {agent: np.sqrt(agent.d.dot(agent.d)) for agent in self.agents}


        self.datacollector.collect(self)
        self._update_traj()
        # Sector-switching rules
        if self.T % self.switching_period != 0:
            return

        for agent in self.agents:
            if self.new_deficit_norms[agent] > self.consump_errors[agent]:
                profs = list(np.arange(self.L))
                del profs[agent.profession_index]
                agent.profession_index = np.random.choice(profs)
        self.consump_errors = self.new_deficit_norms

    def _get_sellers(self, c):
        sellers = [agent for agent in self.agents if agent.e[c] > agent.d[c] and agent.trade_attempts < self.max_trade_attempts]
        return sellers

    def _get_buyers(self, c):
        buyers = [agent for agent in self.agents if agent.d[c] > agent.e[c] and agent.trade_attempts < self.max_trade_attempts]
        return buyers

    def _update_traj(self):
        wealth = [agent.m for agent in self.agents]
        self.traj["wealth"] = self.datacollector.get_agent_vars_dataframe()["wealth"].to_numpy()
        self._update_data("gini", compute_gini(wealth, self.N))
        avg_wealth = np.sum(self.traj["wealth"]) / self.N
        self._update_data("avg_wealth", avg_wealth)
        self.traj["living_labor_times"] = np.stack(self.datacollector.get_model_vars_dataframe()["living_labor_times"].to_numpy())
        self.traj["consumption_indices"] = np.stack(self.datacollector.get_model_vars_dataframe()["consumption_indices"].to_numpy())
        # self._update_data("consumption_indices", self.c)
        self._update_data("social_demand", self.traj["social_demand"][-1])
        self._update_data("efficient_distn", self.traj["efficient_distn"][-1])
        self._update_data("eqb_points", self.traj["eqb_points"][-1])
        self._update_data("eta", self.traj["eta"][-1])

        discontents = np.array(list(self.new_deficit_norms.values()))
        avg_discontent = np.sum(discontents) / self.N
        self._update_data("avg_discontent", avg_discontent)

        avg_prices = np.zeros(self.L)
        for c in range(self.L):
            if self.total_com_exchanges[c] == 0:
                avg_prices[c] = self.traj["avg_prices"][-1][c]
            else:
                avg_prices[c] = self.total_prices[c] / self.total_com_exchanges[c]

        self._update_data("avg_prices", avg_prices)
        if np.std(avg_prices) == 0 or np.std(self.l) == 0:
            r = self.traj["p_v_corr"][-1]
        else:
            r = np.corrcoef(avg_prices, self.l)[0,1]

        self._update_data("p_v_corr", r)

        if self.total_money_exchanged > 0:
            sectoral_income_props = self.total_sectoral_income / self.total_money_exchanged
        else:
            sectoral_income_props = self.traj["sectoral_income_props"][-1]
        self._update_data("sectoral_income_props", sectoral_income_props)

        total_val_transferred = np.sum(self.l * self.total_com_exchanges)
        sigma_m = self.total_money_exchanged
        self._update_data("sigma", sigma_m)
        MELT = sigma_m / total_val_transferred if total_val_transferred > 0 else self.traj["MELT"][-1]

        self._update_data("MELT", MELT)
        MELT_adjusted_values = MELT * self.l
        self._update_data("values", MELT_adjusted_values)

        if self.T % self.avg_interval == 0:

            supply = np.zeros(self.L)
            for agent in self.agents:
                for i, c in enumerate(agent.e):
                    supply[i] += c
            self._update_data("total_supply", supply)

            avg_prices = np.zeros(self.L)
            for c in range(self.L):
                if self.com_exchanges_per_period[c] == 0:
                    avg_prices[c] = self.traj["avg_prices_per_period"][-1][c]
                else:
                    avg_prices[c] = self.total_per_period_prices[c] / self.com_exchanges_per_period[c]

            self._update_data("avg_prices_per_period", avg_prices)
            
            total_val_transferred_per_period = self.l.dot(self.com_exchanges_per_period)
            sigma_m_per_period = self.money_exchanged_per_period
            self._update_data("per_period_sigma", sigma_m_per_period)
            per_period_MELT = sigma_m_per_period / total_val_transferred_per_period if total_val_transferred_per_period > 0 else self.traj["per_period_MELT"][-1]
            self._update_data("per_period_MELT", per_period_MELT)
            self._update_data("per_period_values", per_period_MELT * self.l)

            sectoral_per_period_incomes = self.total_per_period_prices
            self._update_data("sectoral_per_period_income_proportions", sectoral_per_period_incomes / sigma_m_per_period)
            self._update_data("sectoral_per_period_income_rates", sectoral_per_period_incomes)

            self.total_per_period_prices = np.zeros(self.L)
            self.money_exchanged_per_period = 0
            self.com_exchanges_per_period = np.zeros(self.L)
            self.total_per_period_prices = np.zeros(self.L)

            self._update_data("avg_interval_T", self.T)

        # sector sizes
        sector_sizes = np.array(self._get_sector_sizes())
        self._update_data("sector_sizes", sector_sizes)

        com_bundle_avg_costs = np.sum(avg_prices / self.c)
        ideal_expenditure_rates = sector_sizes * com_bundle_avg_costs
        self._update_data("long_run_ideal_expenditure_rates", ideal_expenditure_rates)

        productive_capacities = sector_sizes / self.l
        self._update_data("productive_capacities", productive_capacities)

    def _update_data(self, key, val):
        if isinstance(val, np.ndarray) or isinstance(val, list):
            self.traj[key] = np.append(self.traj[key], [val], axis= 0)
        else:
            self.traj[key] = np.append(self.traj[key], val)

    def _get_sector_sizes(self):
        sector_sizes = []
        for c in range(self.L):
            sector_sizes.append(len([agent for agent in self.agents if agent.profession_index == c]))
        return sector_sizes

    # def cleanup(self):

if __name__ == "__main__":
    l, c = get_l_and_c(4)
    print(l.dot(1/c))
    print(f"{l=}")
    print(f"{c=}")
    print(l.dot(1/c))
    # print(get_l_and_c(12,  10)
