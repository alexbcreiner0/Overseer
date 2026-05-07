import mesa
import numpy as np
from scipy import stats
import copy
import logging
from typing import Generator

logger = logging.getLogger(__name__)

def get_discrete_entropy(data):
    
    _, counts = np.unique(data, return_counts= True)
    probs = counts / counts.sum()

    H = -np.sum(probs * np.log2(probs))
    return H

class EconAgent(mesa.Agent):
    def __init__(self, model):
        super().__init__(model)
        self.m = 0
        self.employer = None
        self.employees = []
        self.annual_income = 0
        self.annual_revenue = 0
        self.annual_wages_paid = 0
        self.annual_wages_received = 0 # TODO: track and fit to a lognormal (this is what is really lognormal distributed)
        self.prior_year_employees = None
        self.prior_year_revenue = None
        self.firm_growth_persons = None
        self.firm_growth_revenue = None
        self.recent_firm_death = False

    def seek_employment(self):
        potential_employers = self.model.agents.select(filter_func = self.model._get_employers)
        potential_employers.discard(self)

        if len(potential_employers) == 0:
            return

        employer_funds = np.array([a.m for a in potential_employers])
        weights = list(employer_funds / sum(employer_funds))
        c = potential_employers.random.choices(potential_employers, weights= weights)[0]

        # seq = range(self.model.w[0], self.model.w[1]+1)
        # rand_wage = self.random.choice(seq)
        avg_wage = (self.model.w[0] + self.model.w[1]) / 2
        if c.m > avg_wage:
            c.employees.append(self)
            self.employer = c

class Economy(mesa.Model):

    def __init__(self, M, N, w, seed= None):
        super().__init__(seed= seed)
        self.N = N
        self.M = M
        self.w = w
        self.V = 0

        # internal counters
        self._current_year = 0
        self._current_month = 0
        self._value_added = 0
        self._overall_counter = 0
        self._total_wages_paid = 0

        self._current_recession = False
        self._current_recession_duration = 0

        self.traj = {
            "N_capitalists": np.array([0]),
            "N_workers": np.array([0]),
            "N_unemployed": np.array([self.N]),
            "commercial_value": np.array([self.V]),
            "gdp": np.array([0]),
            "W": np.array([]),
            "wage_share": np.array([]),
            "profit_share": np.array([]),
            "wage_share_v_profit_share": np.array([]),
            "scatter_x": np.array([]),
            "scatter_year": np.array([]),
            "N_capitalists_fit": np.array([]),
            "N_workers_fit": np.array([]),
            "N_unemployed_fit": np.array([]),
            "ccdf_x": np.array([]),
            "sorted_money_distn": np.array([]),
            "money_distn_caps_fit": np.array([]),
            "money_distn_workers_fit": np.array([]),
            "money_distn_workers_fit_pareto": np.array([]),
            "money_distn_caps_fit_lognormal": np.array([]),
            "firm_sizes": np.array([]),
            "firm_sizes_fit": np.array([]),
            "firm_growth_rates_persons": np.array([]),
            "firm_growth_rates_persons_bins": np.array([]),
            "firm_growth_rates_revenues": np.array([]),
            "firm_growth_rates_revenues_bins": np.array([]),
            "firm_deaths": np.array([]),
            "firm_deaths_x": np.array([]),
            "annual_parallel_x": np.array([0]),
            "recession_durations": np.array([]),
            "profit_rates": np.array([]),
            "profit_rates_bins": np.array([]),
            "capital_investment_weights": np.array([]),
            "firm_investment_weights": np.array([]),
            "annual_incomes": np.array([]),
            "annual_worker_incomes": np.array([]),
            "annual_capitalist_incomes": np.array([]),
            "annual_worker_incomes_fit": np.array([]),
            "annual_worker_income_fit_pareto": np.array([]),
            "annual_cap_income_fit": np.array([]),
            "annual_cap_income_fit_lognormal": np.array([]),
        }

        self.datacollector = mesa.DataCollector()

        EconAgent.create_agents(model= self, n = self.N)
        # haves = self.agents.select(at_most= 200)
        for agent in self.agents:
            agent.m = self.M // self.N

        wealths = [agent.m for agent in self.agents]
        sorted_wealths = sorted(wealths)
        B = sum(m_i * (self.N-i) for i, m_i in enumerate(sorted_wealths)) / (self.N * sum(sorted_wealths))
        self.traj["gini_coeff"] = np.array([1+(1/self.N) - 2*B])

        self.traj["entropy_wealth"] = np.array([get_discrete_entropy(wealths)])
        self.traj["N_capitalists_bins"] = self._get_discrete_bins(self.traj["N_capitalists"])
        self.traj["N_workers_bins"] = self._get_discrete_bins(self.traj["N_workers"])
        print(self.traj["entropy_wealth"])

        self.traj["money_distn"] = np.array([agent.m for agent in self.agents])
        self.traj["money_distn_workers"] = np.array([agent.m for agent in self.agents if self._is_worker(agent)])
        self.traj["money_distn_capitalists"] = np.array([agent.m for agent in self.agents if self._is_employer(agent)])
        # self.traj["money_distn_unemployed"] = np.array([agent.m for agent in self.agents if self._is_unemployed(agent)])

        self.datacollector.collect(self)

    def _get_discrete_bins(self, data):
        lo, hi = data.min(), data.max()
        return np.arange(lo, hi+1, 1)

    def my_step(self) -> Generator[int]:
        """ Step for an entire month. """
        count = 0
        for i in range(self.N):
            a, b = self.agents.shuffle().select(at_most= 2)

            if a.employer is None and len(a.employees) == 0:
                a.seek_employment()

            # commercial activity
            if b.m > 0:
                purch_amt = self.random.choice(range(0, b.m+1))
                b.m -= purch_amt
                self.V += purch_amt

            # value generation
            if a.employer is not None or len(a.employees) > 0:
                if self.V > 0:
                    value_gen = self.random.choice(range(0, self.V+1))
                    self.V -= value_gen
                    self._value_added += value_gen
                    if a.employer is not None:
                        e = a.employer
                        e.m += value_gen
                        e.annual_income += value_gen
                        e.annual_revenue += value_gen
                    else:
                        a.m += value_gen
                        a.annual_income += value_gen
                        a.annual_revenue += value_gen

            # firing and paying wages
            if len(a.employees) > 0:
                avg_wage = (self.w[0] + self.w[1]) / 2
                n = len(a.employees)
                total_wage_bill = avg_wage * n
                if total_wage_bill > a.m:
                    while total_wage_bill > a.m and a.employees:
                        idx = self.random.randint(0, n-1)
                        fired = a.employees.pop(idx)
                        fired.employer = None
                        n -= 1
                        total_wage_bill -= avg_wage
                        if len(a.employees) == 0:
                            a.recent_firm_death = True

                for emp in a.employees:
                    seq = range(self.w[0], self.w[1]+1)
                    rand_wage = self.random.choice(seq)
                    if rand_wage <= a.m:
                        emp.m += rand_wage
                        emp.annual_income += rand_wage
                        a.m -= rand_wage
                        a.annual_income -= rand_wage
                        a.annual_wages_paid += rand_wage
                        self._total_wages_paid += rand_wage
                    else:
                        seq = range(0,a.m+1)
                        if len(seq) == 0:
                            continue
                        rand_wage = self.random.choice(seq)
                        if rand_wage <= a.m:
                            emp.m += rand_wage
                            emp.annual_income += rand_wage
                            a.m -= rand_wage
                            a.annual_income -= rand_wage
                            a.annual_wages_paid += rand_wage
                            self._total_wages_paid += a.m

            count = (count + 1) % 20
            if count == 0:
                yield -1

        self._overall_counter += 1
        self._current_month = (self._current_month + 1) % 12
        if self._current_month == 0: self._current_year += 1
        self._update_traj()
        yield 1

    def _get_employers(self, a) -> bool:
        """ Filters for POTENTIAL employers (only criteria is not being employed) """
        return a.employer is None

    def _is_employer(self, a) -> bool:
        """ Filters for employers """
        return len(a.employees) > 0

    def _is_worker(self, a) -> bool:
        """ Filters for workers """
        return a.employer is not None

    def _is_unemployed(self, a) -> bool:
        """ Filters for unemployed """
        return not self._is_worker(a) and not self._is_employer(a)

    def _update_traj(self):
        N_caps = len(self.agents.select(filter_func= self._is_employer))
        self.traj["N_capitalists"] = np.append(self.traj["N_capitalists"], N_caps)
        lo, hi = self.traj["N_capitalists"].min(), self.traj["N_capitalists"].max()
        self.traj["N_capitalists_bins"] = np.arange(lo, hi+1, 1)

        N_workers = len(self.agents.select(filter_func= self._is_worker))
        self.traj["N_workers"] = np.append(self.traj["N_workers"], N_workers)
        lo, hi = self.traj["N_workers"].min(), self.traj["N_workers"].max()
        self.traj["N_workers_bins"] = np.arange(lo, hi+1, 1)

        N_unemployed = len(self.agents.select(filter_func= self._is_unemployed))
        self.traj["N_unemployed"] = np.append(self.traj["N_unemployed"], N_unemployed)

        money_distn = np.array([agent.m for agent in self.agents])
        self.traj["money_distn"] = money_distn 

        money_distn_workers = np.array([agent.m for agent in self.agents if self._is_worker(agent) or self._is_unemployed(agent)])
        self.traj["money_distn_workers"] = money_distn_workers
        self.traj["money_distn_capitalists"] = np.array([agent.m for agent in self.agents if self._is_employer(agent)])
        # self.traj["money_distn_unemployed"] = np.array([agent.m for agent in self.agents if self._is_unemployed(agent)])

        values, counts = np.unique(money_distn_workers, return_counts= True)
        proportions = counts / self.N
        self.traj["worker_income_scatter"] = proportions
        self.traj["worker_income_scatter_x"] = values

        money_distn = np.array([agent.m for agent in self.agents])
        n = len(money_distn) 
        sorted_money_distn = np.sort(money_distn)
        ccdf_y = 1 - np.arange(1, n+1) / n
        self.traj["sorted_money_distn"] = sorted_money_distn
        self.traj["ccdf_y"] = ccdf_y

        B = sum(m_i * (self.N-i) for i, m_i in enumerate(sorted_money_distn)) / (self.N * sum(money_distn))
        self.traj["gini_coeff"] = np.append(self.traj["gini_coeff"], 1+1/self.N - 2*B) 
        self.traj["entropy_wealth"] = np.append(self.traj["entropy_wealth"], get_discrete_entropy(money_distn))

        money_distn_caps = np.array([agent.m for agent in self.agents if self._is_employer(agent)])
        n = len(money_distn_caps) 
        sorted_money_distn = np.sort(money_distn_caps)
        ccdf_y = 1 - np.arange(1, n+1) / n
        self.traj["sorted_money_distn_caps"] = sorted_money_distn
        self.traj["ccdf_y_caps"] = ccdf_y

        money_distn_workers = np.array([agent.m for agent in self.agents if self._is_worker(agent) or self._is_unemployed(agent)])
        n = len(money_distn_workers) 
        sorted_money_distn = np.sort(money_distn_workers)
        ccdf_y = 1 - np.arange(1, n+1) / n
        self.traj["sorted_money_distn_workers"] = sorted_money_distn
        self.traj["ccdf_y_workers"] = ccdf_y

        firm_sizes = np.array([
            len(agent.employees) for agent in self.agents if len(agent.employees) > 0
        ])

        self.traj["firm_sizes"] = np.append(self.traj["firm_sizes"], firm_sizes)
        historical_firm_sizes = self.traj["firm_sizes"]

        values, counts = np.unique(historical_firm_sizes, return_counts= True)
        self.traj["firm_sizes_y"] = counts
        self.traj["firm_sizes_x"] = values

        recent_caps = [agent for agent in self.agents if agent.recent_firm_death]
        self.traj["firm_deaths"] = np.append(self.traj["firm_deaths"], len(recent_caps))
        values, counts = np.unique(self.traj["firm_deaths"], return_counts= True)
        self.traj["firm_deaths_y"] = counts
        self.traj["firm_deaths_x"] = values

        if self._current_month == 0:

            # macro data
            prev_gdp = self.traj["gdp"][-1]
            self.traj["gdp"] = np.append(self.traj["gdp"], self._value_added)
            current_gdp = self._value_added
            if current_gdp < prev_gdp:
                self._current_recession = True
                self._current_recession_duration += 1
            else:
                if self._current_recession:
                    # recession has ended, record its duration and reset counter
                    self.traj["recession_durations"] = np.append(self.traj["recession_durations"], self._current_recession_duration)
                    self._current_recession_duration = 0
                self._current_recession = False

            self.traj["annual_parallel_x"] = np.append(self.traj["annual_parallel_x"], self._overall_counter)
            self.traj["W"] = np.append(self.traj["W"], self._total_wages_paid)
            wage_share = float(self._total_wages_paid) / np.maximum(float(self._value_added), 1e-8)
            profit_share = 1.0 - wage_share
            ratio = wage_share / np.maximum(profit_share, 1e-8)
            self.traj["wage_share"] = np.append(self.traj["wage_share"], wage_share)
            self.traj["profit_share"] = np.append(self.traj["profit_share"], profit_share)
            self.traj["wage_share_v_profit_share"] = np.append(self.traj["wage_share_v_profit_share"], ratio)

            self.traj["scatter_x"] = np.append(self.traj["scatter_x"], self._overall_counter)
            self.traj["scatter_year"] = np.append(self.traj["scatter_year"], self._current_year)

            firms = [agent for agent in self.agents if len(agent.employees) > 0 or agent.recent_firm_death]

            growth_rates_persons = []
            growth_rates_revenue = []
            profit_rates = []
            capital_weights = []
            firm_weights = []
            for firm in firms:
                if firm.annual_wages_paid != 0:
                    profit_rate = 100 * (firm.annual_revenue - firm.annual_wages_paid) / firm.annual_wages_paid
                    profit_rates.append(profit_rate)
                    capital_weights.append(firm.annual_wages_paid)
                    firm_weights.append(len(firm.employees))

                s_t = max(len(firm.employees), 1)
                s_prev = max(firm.prior_year_employees or 1, 1)
                growth_rates_persons.append(np.log(s_t / s_prev))
                
                s_t = max(firm.annual_revenue, 1)
                s_prev = max(firm.prior_year_revenue or 1, 1)
                growth_rates_revenue.append(np.log(s_t / s_prev))

                firm.prior_year_employees = len(firm.employees)
                firm.prior_year_revenue = firm.annual_revenue

            self.traj["profit_rates"] = np.append(self.traj["profit_rates"], profit_rates)
            lo, hi = np.floor(self.traj["profit_rates"].min()), np.ceil(self.traj["profit_rates"].max())
            bins_pr = np.arange(lo, hi+1, 1)
            self.traj["profit_rates_bins"] = bins_pr
            self.traj["capital_investment_weights"] = np.append(self.traj["capital_investment_weights"], capital_weights)
            self.traj["firm_investment_weights"] = np.append(self.traj["firm_investment_weights"], firm_weights)

            self.traj["firm_growth_rates_persons"] = np.append(self.traj["firm_growth_rates_persons"], growth_rates_persons)
            gr = np.asarray(self.traj["firm_growth_rates_persons"], dtype= float)
            gr = gr[np.isfinite(gr)]

            lo, hi = np.quantile(gr, [0.01, 0.99])
            bin_width = 1.0
            bins_p = np.arange(np.floor(lo), np.ceil(hi) + bin_width, bin_width)
            self.traj["firm_growth_rates_persons_bins"] = bins_p

            self.traj["firm_growth_rates_revenues"] = np.append(self.traj["firm_growth_rates_revenues"], growth_rates_revenue)
            gr = np.asarray(self.traj["firm_growth_rates_revenues"], dtype= float)
            gr = gr[np.isfinite(gr)]

            lo, hi = np.quantile(gr, [0.01, 0.99])
            bins_r = np.arange(np.floor(lo), np.ceil(hi) + bin_width, bin_width)
            self.traj["firm_growth_rates_revenues_bins"] = bins_r

            # micro data
            annual_incomes = np.array([agent.annual_income for agent in self.agents])
            annual_worker_incomes = np.array([
                agent.annual_income for agent in self.agents 
                if self._is_worker(agent) or self._is_unemployed(agent)
            ])
            annual_cap_incomes = np.array([
                agent.annual_income for agent in self.agents 
                if self._is_employer(agent)
            ])

            annual_wages_paid = np.array([agent.annual_wages_paid for agent in self.agents if agent.annual_wages_paid > 0 and agent.annual_revenue > 0])
            annual_revenues = np.array([agent.annual_revenue for agent in self.agents if agent.annual_revenue > 0 and agent.annual_wages_paid > 0])

            self.traj["annual_incomes"] = annual_incomes
            self.traj["annual_worker_incomes"] = annual_worker_incomes
            self.traj["annual_capitalist_incomes"] = annual_cap_incomes

            for agent in self.agents:
                agent.annual_income = 0
                agent.annual_revenue = 0
                agent.annual_wages_paid = 0
            self._total_wages_paid = 0
            self._value_added = 0

        for agent in recent_caps:
            agent.recent_firm_death = 0

    def cleanup(self):

        mu_cc, sigma_c = stats.norm.fit(self.traj["N_capitalists"])
        mu_ww, sigma_w = stats.norm.fit(self.traj["N_workers"])
        mu_uu, sigma_u = stats.norm.fit(self.traj["N_unemployed"])

        print(f"Mean num capitalists: {mu_cc}, std. dev: {sigma_c}")
        print(f"Mean num workers: {mu_ww}, std. dev: {sigma_w}")
        print(f"Mean num unemployed: {mu_uu}, std. dev: {sigma_u}")
        
        mu1, sigma1 = stats.norm.fit(self.traj["wage_share"])
        mu2, sigma2 = stats.norm.fit(self.traj["profit_share"])

        x_c = np.linspace(np.min(self.traj["N_capitalists"]), np.max(self.traj["N_capitalists"]), self._overall_counter)
        self.traj["fitted_x_c"] = x_c
        mu_c, std_c = self.traj["N_capitalists"].mean(), self.traj["N_capitalists"].std(ddof= 0)
        self.traj["N_capitalists_fit"] = stats.norm.pdf(x_c, mu_c, std_c)

        x_w = np.linspace(np.min(self.traj["N_workers"]), np.max(self.traj["N_workers"]), self._overall_counter)
        self.traj["fitted_x_w"] = x_w
        mu_w, std_w = self.traj["N_workers"].mean(), self.traj["N_workers"].std(ddof= 0)
        self.traj["N_workers_fit"] = stats.norm.pdf(x_w, mu_w, std_w)

        x_u = np.linspace(np.min(self.traj["N_unemployed"]), np.max(self.traj["N_unemployed"]), self._overall_counter)
        self.traj["fitted_x_u"] = x_u
        mu_u, std_u = self.traj["N_unemployed"].mean(), self.traj["N_unemployed"].std(ddof= 0)
        self.traj["N_unemployed_fit"] = stats.norm.pdf(x_u, mu_u, std_u)

        annual_income_workers = self.traj["annual_worker_incomes"]
        annual_income_workers = annual_income_workers[annual_income_workers > 0]
        annual_income_caps = self.traj["annual_capitalist_incomes"]
        annual_income = self.traj["annual_incomes"]

        annual_income_workers_safe = np.maximum(annual_income_workers, 1e-8)
        shape, loc, scale = stats.lognorm.fit(annual_income_workers_safe, floc= 0)
        x_m_w = np.linspace(np.min(annual_income_workers), np.max(annual_income_workers), 400)
        self.traj["annual_worker_incomes_fit"] = stats.lognorm.pdf(x_m_w, shape, loc, scale)
        self.traj["fitted_x_m_w"] = x_m_w

        shape, loc, scale = stats.pareto.fit(annual_income_caps)
        x_m_c = np.linspace(np.min(annual_income_caps), np.max(annual_income_caps), self._overall_counter)
        self.traj["annual_cap_income_fit"] = stats.pareto.pdf(x_m_c, shape, loc, scale)
        self.traj["fitted_x_m_c"] = x_m_c

        money_distn_caps_safe = np.maximum(annual_income_caps, 1e-8)
        shape, loc, scale = stats.lognorm.fit(money_distn_caps_safe, floc= 0)
        self.traj["annual_cap_income_fit_lognormal"] = stats.lognorm.pdf(x_m_c, shape, loc, scale)

        shape, loc, scale = stats.pareto.fit(annual_income_workers)
        self.traj["annual_worker_income_fit_pareto"] = stats.pareto.pdf(x_m_w, shape, loc, scale)

        # least squares regression on firm sizes in log-log scale (e.g. power law regression)
        counts = self.traj["firm_sizes_y"]
        values = self.traj["firm_sizes_x"]
        mask = (values > 0) & (counts > 0)
        X = np.log(values[mask])
        Y = np.log(counts[mask])
        slope, intercept = np.polyfit(X, Y, deg= 1)
        x_vals = np.linspace(min(values), max(values), 300)
        A = np.exp(intercept)
        y_vals = A * x_vals ** slope

        self.traj["firm_sizes_fit"] = y_vals
        self.traj["firm_sizes_fit_x"] = x_vals

if __name__ == "__main__":

    # economy = Economy(100000, 20, [10,90])
    # economy.step()

    seq = range(10,40)
    import random
    print(random.choice(seq))

