import numpy as np
from scipy.linalg import logm, expm
from .parameters import Params
from math import sqrt
import sys

class Economy:
    def __init__(self, params):
        self.params = params
        self.current_t = 0
        if params.analytic_soln:
            n_steps = int(1/params.dt)*params.T
            self.t = np.linspace(0,params.T,n_steps)
        else:
            self.t = np.array([0.0])
        
        k1, k2, e, a = params.k1, params.k2, params.e, params.a
        b = 1-a
        c1 = k1 / (1 + e + k1)
        v1 = (1 - c1) / (1 + e)
        s1 = (e * v1)
        c2 = k2 / (1 + e + k2)
        v2 = (1 - c2) / (1 + e)
        s2 = e * v2
        golden_rop = 1 / (0.5*(c1 + v2 + sqrt((c1-v2)**2 + 4*v1*c2))) - 1
        p1 = 1/(1+golden_rop) - v2
        p2 = c2
        w = p2/(1 + e)
        j1 = p1/p2*(1 + e)
        j2 = e+1
        l1, l2 = v1 + s1, v2 + s2

        self.dependent_params = {
            "k": [k1, k2], "c": [c1, c2], "v": [v1, v2], "s": [s1, s2], "l": [l1, l2],
            "p": [p1, p2], "golden_rop": golden_rop, "w": w, "j": [j1, j2]}

        if not params.money_reinvestment:
            denom = 1 - a * s2
            self.M = np.array([
                [c1, c2],
                [((1 - a) * s1 * c1 + v1) / denom, ((1 - a) * s1 * c2 + v2) / denom]
            ])
        else:
            denom = 1-b*golden_rop*(j1/j2*c2+v2)
            self.M = np.array([
                [c1, c2],
                [(b*golden_rop*(j1/j2*c1+v1)*c1+v1) / denom, (b*golden_rop*(j1/j2*c1+v1)*c2+v2) / denom]
            ])

        self.n_steps = int(1 / params.dt)

        if k1 != k2:
            M_inv = np.linalg.inv(self.M)
            log_M_inv = logm(M_inv)
            self.substep_matrix = expm(params.dt * log_M_inv)


        self.theta, self.m1, self.m2, self.r = self.get_technical_info([params.y1i, params.y2i]) 

        M11, M12, M21, M22 = self.M[0][0], self.M[0][1], self.M[1][0], self.M[1][1]
        if params.balanced:
            if params.balanced_indep == "y1":
                if k1 == k2:
                    self.params.y1i = M11 / M21 * self.params.y2i
                else:
                    self.params.y1i = self.m1[0]/self.m2[0] * self.params.y2i
            elif params.balanced_indep == "y2":
                if k1 == k2:
                    self.params.y2i = M21 / M11 * self.params.y1i
                else:
                    self.params.y2i = self.m2[0]/self.m1[0] * self.params.y1i

        E = (v1*self.params.y1i + v2*self.params.y2i) / self.dependent_params["w"]
        self.traj = {
            "y": [np.array([self.params.y1i, self.params.y2i])],
            "labor_demand": [0],
            "N": [params.N0],
            "E": [E]
        }

        # regetting in case the initial parameters change (only necessary for r, should probably do differently)
        self.theta, self.m1, self.m2, self.r = self.get_technical_info([params.y1i, params.y2i]) 

    def step(self):

        if self.params.analytic_soln:
            pass
        elif self.params.k1 == self.params.k2:
            for i in range(self.n_steps):
                self.t = np.append(self.t, self.t[-1] + self.params.dt)
        else:
            current_y = self.traj["y"][-1]
            for i in range(self.n_steps):
                new_y = self.substep_matrix @ current_y
                if self.params.enforce_nonneg:
                    new_y = np.maximum(new_y, 0)
                if self.params.enforce_population_constraints:
                    v = self.dependent_params["v"]
                    current_N = self.traj["N"][-1]
                    E = (v[0]*new_y[0] + v[1]*new_y[1]) / self.dependent_params["w"]
                    if E > current_N:
                        scale = current_N * self.dependent_params["w"] / E
                        new_y *= scale
                        E = current_N
                self.step_traj(new_y)
                self.traj["y"] = np.append(self.traj["y"], [np.real(new_y)], axis= 0)
                current_y = new_y
                self.t = np.append(self.t, self.t[-1] + self.params.dt)

    def step_traj(self, y):
        l = np.array(self.dependent_params["l"])
        v = self.dependent_params["v"]
        rep_rate = self.params.r / self.n_steps
        attrit_rate = self.params.s / self.n_steps

        E = (v[0]*y[0] + v[1]*y[1]).real / self.dependent_params["w"]
        self.traj["E"] = np.append(self.traj["E"], E)
        current_N = self.traj["N"][-1]
        current_N += (rep_rate*E) - (attrit_rate*(current_N-E))
        self.traj["N"] = np.append(self.traj["N"], current_N)

        old_y = self.traj["y"][-1]
        change_y = (y - old_y).real
        labor_change = change_y.dot(l)
        relative_labor_change = labor_change / old_y.dot(l)

        self.traj["labor_demand"] = np.append(self.traj["labor_demand"], relative_labor_change)

    def get_technical_info(self, y):
        M11, M12 = self.M[0][0], self.M[0][1]
        M21, M22 = self.M[1][0], self.M[1][1]

        m11, m21 = 1, 1
        
        theta = np.array([
            1/2*(M11+M22+sqrt((M11-M22)**2+4*M12*M21)),
            1/2*(M11+M22-sqrt((M11-M22)**2+4*M12*M21))
        ])
        
        m11, m21 = 1, 1
        m12 = (theta[0] - M11) / M12 * m11
        m22 = -1*(M11 - theta[1]) / M12 * m21

        m1 = np.array([m11, m21])
        m2 = np.array([m12, m22])

        r1 = (m22*y[0] - m21*y[1]) / (m11*m22 - m21*m12)
        r2 = (-1*m12*y[0] + m11*y[1]) / (m11*m22 - m21*m12)

        r = np.array([r1, r2])

        return theta, m1, m2, r

    def get_analytic_curves(self):
        yi = self.traj["y"][0]
        y1i, y2i = yi[0], yi[1]
        r = self.r
        M11, M12, M21, M22 = self.M[0][0], self.M[0][1], self.M[1][0], self.M[1][1]
        m1, m2, theta = self.m1, self.m2, self.theta
        l = np.array(self.dependent_params["l"])
        w = self.dependent_params["w"]
        golden_rop = self.dependent_params["golden_rop"]
        p = self.dependent_params["p"]
        c, v, s = np.array(self.dependent_params["c"]), np.array(self.dependent_params["v"]), np.array(self.dependent_params["s"])

        if self.params.analytic_soln or self.params.k1 == self.params.k2:
            N = np.zeros(len(self.t))
            E = np.zeros(len(self.t))
            self.traj["N"] = N
            self.traj["E"] = E
       
            if self.params.k1 == self.params.k2:
                y1 = M11*(y1i*M11 + y2i*M21) / (M11**2 + M21**2) * (1/theta[0])**self.t
                y2 = M21*(y1i*M11+y2i*M21) / (M11**2 + M21**2) * (1/theta[0])**self.t
                self.traj["y"] = np.column_stack((y1, y2))
            else:
                y1 = r[0]*m1[0]*(1/theta[0])**self.t + r[1]*m1[1]*(np.power(1/theta[1] + 0j, self.t).real)
                y2 = r[0]*m2[0]*(1/theta[0])**self.t + r[1]*m2[1]*(np.power(1/theta[1] + 0j, self.t).real)
                self.traj["y"] = np.stack((y1, y2), axis= 1)

            change_y = np.gradient(self.traj["y"], self.t, axis= 0)
            labor_demand = (change_y @ l) / (self.traj["y"] @ l)
            self.traj["labor_demand"] = labor_demand

        y = self.traj["y"]
        y1_balanced = r[0]*m1[0]*(1/theta[0])**self.t
        y2_balanced = r[0]*m2[0]*(1/theta[0])**self.t
        y_bal = np.stack((y1_balanced, y2_balanced), axis= 1)

        self.traj["y_bal"] = y_bal
        total_out = y[:,0] + y[:,1]
        self.traj["total_val"] = total_out

        self.traj["total_surplus"] = y @ s
        unit_cost_1 = p[0]*c[0] + p[1]*v[0]
        unit_cost_2 = p[0]*c[1] + p[1]*v[1]
        unit_costs = np.array([unit_cost_1, unit_cost_2])
        unit_profits = p - unit_costs
        self.traj["total_money_profit"] = y @ unit_profits

        self.traj["e"] = np.ones(len(self.t))*self.params.e

        k1, k2 = self.params.k1 * np.ones(len(self.t)), self.params.k2 * np.ones(len(self.t))
        self.traj["k_sects"] = np.column_stack((k1, k2))
        k = (y @ c) / (y @ v)
        self.traj["overall_composition"] = k

        P1 = s[0] / (c[0] + v[0]) * np.ones(len(self.t))
        P2 = s[1] / (c[1] + v[1]) * np.ones(len(self.t))
        self.traj["sectoral_value_profit_rates"] = np.column_stack((P1, P2))
        overall_P = (y @ s) / (y @ (c+v))
        self.traj["val_profit"] = overall_P
        overall_P_bal = (y_bal @ s) / (y_bal @ (c+v))
        self.traj["val_profit_bal"] = overall_P_bal
        self.traj["pg_out"] = golden_rop * np.ones(len(self.t))

        total_p1 = y[:,0] * p[0]
        total_p2 = y[:,1] * p[1]
        total_p = total_p1 + total_p2
        self.traj["p_vec"] = np.column_stack((total_p1, total_p2))
        self.traj["p_out"] = total_p

        len(y[:self.n_steps*(self.params.T-2)])
        y_primes = np.array([y[t+self.n_steps] for t in range(len(y[:self.n_steps*(self.params.T-2)]))])
        for i in range(len(y) - len(y_primes)):
            y_primes = np.append(y_primes, [np.array([0,0])], axis= 0)
        change_y = y_primes - y

        money_rate_of_accum = (change_y @ unit_costs) / (y @ unit_costs)
        value_rate_of_accum = (change_y @ (c + v)) / (y @ (c + v))
        self.traj["roam"] = money_rate_of_accum
        self.traj["roav"] = value_rate_of_accum

        labor_value_added = y[:,0] + y[:,1] - (y @ c)
        price_value_added_1 = total_p1 - p[0]*c[0]*y[:,0]
        price_value_added_2 = total_p2 - p[1]*c[1]*y[:,1]
        price_value_added = price_value_added_1 + price_value_added_2
        MELT = price_value_added / labor_value_added
        self.traj["MELT"] = MELT
        wages = w * np.ones(len(self.t))
        
        ni_V = (wages / MELT)*(y @ l)
        ni_S = (y @ l) - ni_V
        ni_e = ni_S / ni_V

        self.traj["NI_e"] = ni_e
        self.traj["ni_V"] = ni_V
        self.traj["NI_total_surplus"] = ni_S
        profit_adjusted_by_melt = (y @ unit_profits) / MELT
        self.traj["profit_adjusted_by_MELT"] = profit_adjusted_by_melt

        gdp_rate = (change_y @ (v + s)) / (y @ (v + s))
        self.traj["gdp"] = gdp_rate

        ideal_y1 = (1+self.params.a*P1[0])**self.t*y1i
        ideal_y2 = (1+self.params.a*P2[0])**self.t*y2i
        self.traj["ideal_y"] = np.column_stack((ideal_y1, ideal_y2))

        marx_1 = ideal_y1
        ideal_extra1 = (1+self.params.a*P1[0])**(self.t - 1)*y1i
        marx_2l = ((1/c[1])*(1-c[0]-c[0]/(c[0]+v[0])*self.params.a*s[0])*y1i-y2i)*self.t + y2i
        marx_2r = (1/c[1]*(1-c[0]-c[0]/(c[0]+v[0])*self.params.a*s[0])*ideal_extra1)
        marx_2 = np.where(self.t < 1, marx_2l, marx_2r)
        self.traj["marx_curves"] = np.column_stack((marx_1, marx_2))

