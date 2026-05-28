import logging
try:
    logger = logging.getLogger(__name__)
except Exception:
    logger = None

import numpy as np
from scipy.linalg import eig
from scipy.integrate import solve_ivp
import random
import sys

class CapitalistEconomy:
    """Basic capitalist economy"""
    def __init__(self, params, restrictions = []):
        self.params = params 
        self.n = self.params.A.shape[0]
        self.current_t = 0
        self.t = [0.0]
        self.M_timer = 0
        self.current_i = random.randint(0,self.n-1)
        
        self.y = self._repack(params.q, params.p, params.s, params.l, params.m_w, params.L, params.w, params.M, params.A)

        self.fixed_real_wage = True if "fixed_real_wage" in restrictions else False
        self.fixed_money_wage = True if "fixed_money_wage" in restrictions else False
        self.nondecreasing_employment = True if "nondecreasing_employment" in restrictions else False
        self.fixed_exploitation = True if "fixed_exploitation" in restrictions else False

        self.exo_supply_deduction = np.zeros(self.n) # carries a to-be-applied exogenous shock to supply
        self.exo_delta_l = np.zeros(self.n)
        self.exo_delta_A = np.zeros((self.n, self.n))
        self.exo_delta_M = float(0)
        self.exo_delta_w = float(0)

        # initialize the table of trajectories
        self.traj = {
            "p": np.array([params.p]),
            "q": np.array([params.q]), 
            "s": np.array([params.s]),
            "m_w": np.array([params.m_w]), 
            "L": np.array([params.L]), 
            "r": np.array([params.r]),
            "l": np.array([params.l]),
            "M": np.array([params.M]),
            "A": np.array([params.A])
        }

        for i in range(self.n):
            key = f"a_{i}"
            self.traj[key] = np.array([self.params.A[:,i]])

        if self.fixed_real_wage:
            self.traj["w"] = np.array([params.p.dot(params.b_bar)])
        else:
            self.traj["w"] = np.array([params.w])

        self.traj["labor_commanded"] = np.array([params.p / params.w])
        self.traj["okishio_pts_x"], self.traj["okishio_pts_y"] = np.array([]), np.array([])
        employment = self._get_employment(params.q, params.l)
        self.traj["total_labor_employed"] = np.array([employment])
        b, c = self._get_consumption(params.M, params.m_w, params.p)
        self.traj["b"], self.traj["c"] = np.array([b]), np.array([c])
        values = self._get_values(self.params.A, self.params.l)
        self.traj["total_val_c"] = np.array([values.dot(c)])
        self.traj["values"] = np.array([values])
        self.traj["wage_values"] = np.array([params.w * values])
        self.traj["reserve_army_size"] = np.array([self.params.L - self.traj["total_labor_employed"]])
        self.traj["m_c"] = np.array([1-params.m_w])
        self.traj["total_demand"] = np.array([self._get_total_demand(self.y)])
        val_ms, val_cc, surplus_val, e, value_rop = self._get_value_split(values, b, self.params.q, self.params.A)
        self.traj["values_ms"], self.traj["cc_vals"], self.traj["surplus_vals"], self.traj["e"], self.traj["value_rops"] = np.array([val_ms]), np.array([val_cc]), np.array([surplus_val]), np.array([e]), np.array([value_rop])
        self.traj["M"] = np.array([params.M])

        total_value_out = params.q.dot(values)
        total_price_out = params.q.dot(params.p)
        self.traj["total_value_out"] = np.array([total_value_out])
        self.traj["total_price_out"] = np.array([total_price_out])

        sectoral_out_vals = params.q * values
        sectoral_out_prices = params.q * params.p
        self.traj["sectoral_out_vals"] = np.array([sectoral_out_vals])
        self.traj["sectoral_out_prices"] = np.array([sectoral_out_prices])

        self.traj["relative_value_out"] = np.array([sectoral_out_vals / total_value_out])
        self.traj["relative_price_out"] = np.array([sectoral_out_prices / total_price_out])

        (evals, evecs) = eig(self.params.A)
        r = np.max([np.abs(eval) for eval in evals])
        self.traj["spectral_radius_A"] = np.array([r])
        self.traj["A_rop"] = np.array([1/r-1])

        epr, eq_p = self._get_equilibrium_info(params.p, params.w, params.A, params.l)
        hourly_b, ms_vals, c_vals, v_vals, s_vals = self._get_composition_info(self.params.p, self.params.w, values, self.params.A, self.params.l, e)
        self.traj["hourly_b"], self.traj["val_ms"], self.traj["c_vals"], self.traj["v_vals"], self.traj["s_vals"] = np.array([hourly_b]), np.array([ms_vals]), np.array([c_vals]), np.array([v_vals]), np.array([s_vals])
        self.traj["hourly_b_val"] = np.array([hourly_b.dot(values)])
        self.traj["sectoral_comps"] = np.array([c_vals / v_vals])
        self.traj["capital_intensities"] = np.array([c_vals / self.params.l])
        c_vals_money = (self.params.A.T@self.params.p) * params.q
        v_vals_money = (self.params.w*self.params.l) * params.q
        self.traj["money_compositions"] = np.array([c_vals_money / v_vals_money])
        self.traj["overall_money_composition"] = np.array([np.sum(c_vals_money) / np.sum(v_vals_money)])
        self.traj["money_rate_of_exploitation"] = np.array([(params.alpha_c * (params.M-params.m_w))/(params.alpha_w * params.m_w)])

        self.traj["epr"], self.traj["epr_prices"] = np.array([epr]), np.array([eq_p])
        self.traj["compos_of_capital"] = np.array([val_cc / val_ms])
        profit_rates, profit_of_enterprise_rates = self._get_profit_rates(params.A, params.p, params.w, params.l, params.r)
        self.traj["profit_rates"] = np.array([profit_rates])
        self.traj["profit_of_enterprise_rates"] = np.array([profit_of_enterprise_rates])
        self.traj["value_of_hourly_cap_income"] = np.array([c.dot(values) / self._get_employment(params.q, params.l)])

        sectoral_shares = self._get_unit_shares(params.A, params.p, params.w, params.l)
        self.traj["sectoral_shares"] = np.array([sectoral_shares])
    
        profit, interest, cost, total_capital_advanced, revenue, theoretical_profit, composition_of_capital_advanced = self._get_profit_split(self.y)
        self.traj["total_sectoral_costs"] = np.array([cost])
        self.traj["total_capital_advanced"] = np.array([total_capital_advanced])
        self.traj["composition_of_capital_advanced"] = np.array([composition_of_capital_advanced])
        self.traj["relative_costs"] = np.array([cost / np.sum(cost)])
        self.traj["profit"], self.traj["interest"], self.traj["total_cost"], self.traj["revenue"], self.traj["theoretical_profit"] = np.array([np.sum(profit)]), np.array([np.sum(interest)]), np.array([np.sum(cost)]), np.array([np.sum(revenue)]), np.array([theoretical_profit])

        total_profit = np.sum(profit) + np.sum(interest)
        self.traj["total_profit"] = np.array([total_profit])
        self.traj["total_capitalist_spending"] = np.array([self.params.alpha_c * (self.params.M - self.params.m_w)])
        hourly_profit = total_profit / self._get_employment(params.q, params.l)
        self.traj["hourly_cap_income"] = np.array([hourly_profit])
        self.traj["hourly_real_cap_income"] = np.array([hourly_profit / (self.params.p.dot(self.params.c_bar))*self.params.c_bar])

        num = params.l.dot(params.q) - 1/self.params.init_tssi_melt * (eq_p@hourly_b)*(params.l.dot(params.q))
        M = params.A+np.linalg.outer(hourly_b,params.l)
        den = eq_p.dot(M@params.q)
        kliman_profit_rate = num/den
        self.traj["kliman_prices"] = np.array([params.p])
        self.traj["kliman_values"] = np.array([values])
        self.traj["kliman_actual_values"] = np.array([values])

        LQ = float(params.l.dot(params.q))
        M_mat = params.A + np.outer(hourly_b, params.l)
        D = float(eq_p.dot(M_mat @ params.q))
        H = float(eq_p.dot(hourly_b))

        # Avoid silly zeros
        eps = 1e-12
        LQ_safe = max(LQ, eps)

        # factor = epr * D / LQ
        factor = epr * D / LQ_safe

        denom_for_M0 = 1.0 - factor
        if abs(denom_for_M0) < eps:
            init_tssi_melt = params.p.dot(params.q) / max(self.traj["values"][0].dot(params.q), eps)
        else:
            init_tssi_melt = H / denom_for_M0

        # self.params.init_tssi_melt = init_tssi_melt

        self.traj["kliman_profit_rate"] = np.array([epr])

        values = self.traj["values"][0]
        # MELT = params.p.dot(params.q) / values.dot(params.q)
        MELT = (params.p.dot(params.q) - params.p.dot(params.A@params.q)) / params.l.dot(params.q)
        self.traj["TSSI_MELT"] = np.array([params.init_tssi_melt])
        self.traj["ACTUAL_TSSI_MELT"] = np.array([params.init_tssi_melt])

        tssi_v_n = params.w / max(params.init_tssi_melt, 1e-12)
        tssi_v = tssi_v_n * params.l
        tssi_s = params.l - tssi_v
        tssi_V = tssi_v.dot(params.q)
        tssi_C = (1/params.init_tssi_melt)*(params.A.T@params.p).dot(params.q)
        tssi_S = tssi_s.dot(params.q)

        self.traj["tssi_C"] = np.array([tssi_C])
        self.traj["tssi_V"] = np.array([tssi_V])
        self.traj["tssi_S"] = np.array([tssi_S])
        self.traj["tssi_e"] = np.array([tssi_S / max(tssi_V, 1e-7)])
        self.traj["MELT"] = np.array([MELT])
        self.traj["MELT_values"] = np.array([MELT*values])
        self.traj["MELT_prices"] = np.array([params.p / MELT])
        self.traj["MELT_adjusted_m_w"] = np.array([params.m_w / MELT])
        self.traj["MELT_adjusted_m_c"] = np.array([(1 - params.m_w) / MELT])

        m = params.A.T@params.p + params.w*params.l
        total_employment = params.q.dot(params.l)
        v_n = params.w / MELT 
        ni_variable = v_n*total_employment
        ni_v = v_n * params.l
        ni_s = params.l - ni_v
        ni_surplus = ni_s.dot(params.q)
        self.traj["NI_variable"] = np.array([ni_variable])
        self.traj["NI_surplus"] = np.array([ni_surplus])
        self.traj["NI_exploitation"] = np.array([ni_surplus / ni_variable])
        self.traj["MELT_converted_profit"] = np.array([ni_surplus * MELT])
        self.traj["TSSI_MELT_converted_profit"] = np.array([tssi_S * params.init_tssi_melt])
        self.traj["TSSI_MELT_converted_profit_plus_melt_diff"] = np.array([tssi_S * params.init_tssi_melt])
        sssi_C = (params.A.T@params.p).dot(params.q) / MELT
        self.traj["sssi_C"] = np.array([sssi_C])
        sssi_c = params.A.T@params.p / MELT
        sssi_values = sssi_c + params.l
        self.traj["SSSI_vals"] = np.array([sssi_values])
        self.traj["SSSI_rop"] = np.array([ni_surplus / (ni_variable + sssi_C)])

        self.old_tssi_junk = {"p": self.traj["kliman_prices"][-1], "w": self.traj["w"][-1], "MELT": self.params.init_tssi_melt, "values": values, "A": params.A, "l": params.l}

        max_rop_epr, max_rop_eq_p = self._get_equilibrium_info(params.p, 0, params.A, params.l)
        self.traj["max_rop"] = np.array([max_rop_epr])

        initial_commodity_shares = c / np.maximum(b, 1e-3)

        initial_supply_vec = b + params.A.T @ params.q
        initial_commodity_surplus = c / np.maximum(initial_supply_vec, 1e-3)

        self.traj["commodity_shares"] = np.array([initial_commodity_shares])   # shape (1, n)
        self.traj["commodity_surplus"] = np.array([initial_commodity_surplus]) # shape (1, n)

        # C_tilde, V_tilde, S_tilde, SI_exploitation, SI_composition, SI_profit_rate = self._get_super_integrated_value_split(self.y)
        super_vals, A_tilde = self._get_super_integrated_value_split2(self.y)
        # self.traj["super_integrated_vals"] = np.array([params.p / np.maximum(params.w, 1e-8)])
        self.traj["super_integrated_vals"] = np.array([super_vals])
        self.traj["super_integrated_wage_vals"] = np.array([params.w * super_vals])

        self.dydt = self._get_dydt(self.params)

    def step(self):
        """ Simulates a single (system time) step of the simulation. Updates the independent parameters y, as well as all trajectories. """

        # Check for perturbation stuff
        if self.params.M_change_type != "none":
            if self.current_t != 0 and self.current_t % self.params.M_change_interval == 0 and self.M_timer == 0:
                self.exo_delta_M = self.params.delta_M
                self.M_timer = self.params.M_change_duration

        if self.params.atrophy_with_unemployment == "always":
            self.exo_delta_w = self.params.wage_deflation
        elif self.params.atrophy_with_unemployment == "unemployment":
            q, p, s, l, m_w, L, w, M, A = self._unpack(self.y)
            if L / self._get_employment(q,l) - 1 > self.params.gamma_L:
                self.exo_delta_w = self.params.wage_deflation

        if self.params.supply_shock_setting != "none":
            if self.params.supply_shock_setting ==  "periodic":
                if self.current_t != 0 and self.current_t % self.params.supply_shock_interval == 0:
                    q, p, s, l, m_w, L, w, M, A = self._unpack(self.y)
                    self.exo_supply_deduction = self.params.supply_shock_mag * s

        if self.params.change_type != "none":
            if self.params.change_type == "discrete" and self.current_t != 0 and self.current_t % self.params.change_interval == 0:
                if self.params.shock_type == "culs":
                    self.implement_culs_shock(self.params.shock_mag, epsilon= self.params.cost_tradeoff)
                elif self.params.shock_type == "ls":
                    self.implement_culs_shock(self.params.shock_mag, cu= False, epsilon= self.params.cost_tradeoff)
                elif self.params.shock_type == "cslu":
                    self.implement_cslu_shock(self.params.shock_mag, epsilon= self.params.cost_tradeoff)
                elif self.params.shock_type == "cs":
                    self.implement_cslu_shock(self.params.shock_mag, lu= False, epsilon= self.params.cost_tradeoff)
                elif self.params.shock_type == "none":
                    pass

        t_eval = np.linspace(self.current_t, self.current_t+1, self.params.res+1)[1:]
        # Where the magic happens
        sol = solve_ivp(
            self.dydt,
            (float(self.current_t), float(self.current_t+1)), 
            self.y,
            method= "BDF", 
            rtol= 1e-6, 
            atol=1e-9,
            t_eval=t_eval, 
            max_step=1.0
        )
        if logger is not None and (not sol.success or not np.all(np.isfinite(sol.y))):
            # Stuff that gets printed when the simulation fails
            logger.info("Simulation failed.")
            logger.info(f"  success = {sol.success}")
            logger.info(f"  status  = {sol.status}")
            logger.info(f"  message = {sol.message}")
            logger.info(f"  nfev    = {sol.nfev}, njev = {getattr(sol, 'njev', None)}, nlu = {getattr(sol, 'nlu', None)}")

            if sol.t.size > 0:
                t_last = sol.t[-1]
                y_last = sol.y[:, -1].copy()
                logger.info(f"  last t = {t_last}")
                logger.info(f"  last y = {y_last}")

                # Evaluate derivative at last state
                try:
                    f_last = self.dydt(t_last, y_last)
                    logger.info(f"  |f_last|_inf = {np.max(np.abs(f_last))}")
                    logger.info(f"  f_last = {f_last}")
                except Exception as e:
                    logger.info(f"  error evaluating dydt at last state: {e}")
                    # How far did we get?
                    if sol.t.size > 0:
                        logger.info(f"  last time reached = {sol.t[-1]}")
                        y_last = sol.y[:, -1]
                        logger.info(f"  last state (y_last) = {y_last}")

            # Where did non-finite values first appear?
            if not np.all(np.isfinite(sol.y)):
                bad_mask = ~np.isfinite(sol.y)
                idx_t, idx_var = np.where(bad_mask)
                first = np.argmin(idx_t)  # earliest time index with a bad value
                t_bad = sol.t[idx_t[first]]
                var_bad = idx_var[first]
                logger.info(f"  first non-finite at t = {t_bad}, variable index = {var_bad}")
                logger.info(f"  value there = sol.y[{var_bad}, {idx_t[first]}] = {sol.y[var_bad, idx_t[first]]}")

        # Reset all temporary perturbation variables
        self.exo_supply_deduction = np.zeros(self.n) 
        self.exo_delta_l = np.zeros(self.n)
        self.exo_delta_A = np.zeros((self.n, self.n))
        self.exo_delta_w = 0

        self.y = sol.y[:, 0]

        m = sol.y.shape[1]

        # Update trajectories
        for i in range(m):
            self.y = sol.y[:, i]
            self._step_traj(self.y)
            self.current_t = sol.t[i]
            self.t.append(float(self.current_t))

        # Tried doing the updates by time step rather than simulation step, it didn't really change anything. This line is currently useless
        self.old_tssi_junk = {"p": self.traj["kliman_prices"][-1], "MELT": self.traj["TSSI_MELT"][-1], "l": self.traj["l"][-1], "A": self.traj["A"][-1], "w": self.traj["w"][-1]}

        self.dydt = self._get_dydt(self.params) # I think this is pointless, but could be used to conditionally redefine the differential equations (I ended up just adding in conditions to the equation functions themselves)

        if self.params.fix_sector_receiving_change in [0,1,2]:
            self.current_i = self.params.fix_sector_receiving_change
        else:
            self.current_i = random.randint(0,self.n-1)

        if self.M_timer > 0:
            self.M_timer -= 1
            if self.M_timer == 0:
                self.exo_delta_M = 0

    def cleanup(self):
        """ Stuff to do at the end of the simulation, such as taking derivative plots (would be inefficient to recompute every step) """
        try:
            self.traj["deriv_employment"] = np.gradient(self.traj["total_labor_employed"])
        except (ValueError, IndexError):
            self.traj["deriv_employment"] = np.array([])
        try:
            self.traj["relative_price_change"] = np.gradient(self.traj["p"], self.t, axis= 0) / self.traj["p"]
        except (ValueError, IndexError):
            self.traj["relative_price_change"] = np.array([])

    def change_param(self, param_name, new_val):
        setattr(self.params, param_name, new_val)

    def implement_culs_shock(self, beta, cu= True, epsilon= None):
        """Implements a sudden new labor saving, capital using, super-profit generating innovation. beta is the proportion by which to reduce the living labor input by"""
        if self.params.fix_sector_receiving_change in [0,1,2]:
            i = self.params.fix_sector_receiving_change
        else:
            i = random.randint(0,self.n-1)
        # i=1
        # print(f"Improving sector {i}")

        if epsilon == None: epsilon = self.params.cost_tradeoff

        q, p, s, l, m_w, L, w, M, A = self._unpack(self.y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]
        

        a_i = A[:,i].copy()
        l_i = l[i]
        cost_ratio = a_i.dot(p) / (w*l_i)

        old_cost = np.maximum(a_i.dot(p) + w*l_i, 1e-12)
        # print(f"Old cost of commodity {i}: {old_cost}")

        gamma = cost_ratio * (1 + epsilon) # bigger epsilon => more dramatic superprofits (i think)
        alpha = beta / gamma 
        
        new_l = l.copy()
        new_l[i] *= (1-beta)

        new_A = A.copy()

        # TODO: change to only effect a single (random) input
        if cu:
            new_A[:,i] *= (1+alpha)

        eigvals = np.linalg.eigvals(new_A)
        if np.max(np.abs(eigvals)) >= 1:
            print("Warning! A matrix is not productive!")
            print("Scaling matrix to safe values")
            new_A /= (np.max(np.abs(eigvals)) + epsilon)

        new_a_i = new_A[:,i]
        new_cost = new_a_i.dot(p) + w * new_l[i]
        # print(f"New cost of commodity {i}: {new_cost}")

        new_epr, new_eqp = self._get_equilibrium_info(p, w, new_A, new_l)
        self.traj["okishio_pts_x"] = np.append(self.traj["okishio_pts_x"], self.current_t)
        self.traj["okishio_pts_y"] = np.append(self.traj["okishio_pts_y"], new_epr)

        self.exo_delta_l = new_l - l
        self.exo_delta_A = new_A - A

        return q, p, s, l, m_w, L, w, new_A

    def implement_cslu_shock(self, alpha, lu= True, epsilon= 1e-2):
        """Implements a sudden new labor saving, capital using, super-profit generating innovation. beta is the proportion by which to reduce the living labor input by"""
        if self.params.fix_sector_receiving_change in [0,1,2]:
            i = self.params.fix_sector_receiving_change
        else:
            i = random.randint(0,self.n-1)
        q, p, s, l, m_w, L, w, M, A = self._unpack(self.y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]

        a_cols = [A[:,j].copy() for j in range(self.n)]
        new_l = l.copy()
        a_i = a_cols[i]
        cost_ratio = a_i.dot(p) / (w*l[i])
        old_cost = a_i.dot(p) + w*l[i]
        # print(f"Old cost of commodity {i}: {old_cost}")
        beta = alpha * cost_ratio * (1 - epsilon) # bigger epsilon => more dramatic superprofits (i think)

        a_cols[i] *= (1-alpha)
        new_A = np.array(a_cols).T
        
        # TODO: change to only effect a single (random) input
        if lu:
            new_l[i] *= (1+beta)

        eigvals = np.linalg.eigvals(new_A)
        if np.max(np.abs(eigvals)) >= 1:
            print("Warning! A matrix is not productive!")
            print("Scaling matrix to safe values")
            new_A /= (np.max(np.abs(eigvals)) + epsilon)

        new_cost = a_i.dot(p) + w*l[i]
        # print(f"New cost of commodity {i}: {new_cost}")
        new_epr, new_eqp = self._get_equilibrium_info(p, w, new_A, new_l)
        self.traj["okishio_pts_x"] = np.append(self.traj["okishio_pts_x"], self.current_t)
        self.traj["okishio_pts_y"] = np.append(self.traj["okishio_pts_y"], new_epr)


        self.exo_delta_l = new_l - l
        self.exo_delta_A = new_A - A

        return q, p, s, l, m_w, L, new_A

    # The following three methods are meant to be filled in later to possibly model trade relations between different economies
    def check_supply(self):
        s = self.y[2*self.n:3*self.n]
        return s

    def receive_offer(self):
        # fill in with whatever seems reasonable
        pass

    def make_offer(self):
        # fill in with whatever seems reasonable
        pass

    def _repack(self, q, p, s, l, m_w, L, w, M, A):
        a_cols = np.concatenate([A[:,i] for i in range(self.n)])
        y = np.concatenate([a_cols, q, p, s, l, np.array([m_w]), np.array([L]), np.array([w]), np.array([M])])
        return y

    def _unpack(self, y):
        n = self.n
        
        A_rows = []
        for i in range(n):
            A_rows.append(y[n*i:n*(i+1)])
        A = np.array(A_rows).T
        q = y[n**2:n**2+n]
        p = y[n**2+n:n**2+2*n]
        s = y[n**2+2*n:n**2+3*n]
        l = y[n**2+3*n:n**2+4*n]
        m_w = y[n**2+4*n]
        L  = y[n**2+4*n+1]
        w = y[n**2+4*n+2]
        M = y[n**2+4*n+3]

        return q, p, s, l, m_w, L, w, M, A

    def _step_traj(self, y):
        """ Updates ALL trajectories according to a presumably new y vector """
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        self.traj["M"] = np.append(self.traj["M"], M)
        self.traj["q"] = np.append(self.traj["q"], [q], axis=0)
        self.traj["p"] = np.append(self.traj["p"], [p], axis=0)
        self.traj["s"] = np.append(self.traj["s"], [s], axis=0)
        self.traj["m_w"] = np.append(self.traj["m_w"], m_w)
        self.traj["L"] = np.append(self.traj["L"], L)
        self.traj["l"] = np.append(self.traj["l"], [l], axis=0)
        self.traj["A"] = np.append(self.traj["A"], [A], axis= 0)


        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar) 
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]
        self.traj["w"] = np.append(self.traj["w"], w)

        for i in range(self.n):
            key = f"a_{i}"
            self.traj[key] = np.append(self.traj[key], [A[:,i]], axis=0)

        r = self._get_interest_rate(m_w)
        self.traj["r"] = np.append(self.traj["r"], r)
        employment = self._get_employment(q, l)
        self.traj["total_labor_employed"] = np.append(self.traj["total_labor_employed"], employment)
        b, c = self._get_consumption(M, m_w, p)
        self.traj["b"] = np.append(self.traj["b"], [b], axis=0)
        self.traj["c"] = np.append(self.traj["c"], [c], axis=0)
        self.traj["total_demand"] = np.append(self.traj["total_demand"], [self._get_total_demand(y)], axis= 0)

        (evals, evecs) = eig(A)
        r = np.max([np.abs(eval) for eval in evals])
        self.traj["spectral_radius_A"] = np.append(self.traj["spectral_radius_A"], r)
        self.traj["A_rop"] = np.append(self.traj["A_rop"], 1/r-1)

        values = self._get_values(A, l)
        self.traj["values"] = np.append(self.traj["values"], [values], axis=0)
        self.traj["wage_values"] = np.append(self.traj["wage_values"], [w * values], axis=0)
        self.traj["reserve_army_size"] = np.append(self.traj["reserve_army_size"], L - employment)
        self.traj["m_c"] = np.append(self.traj["m_c"], M-m_w)
        self.traj["total_capitalist_spending"] = np.append(self.traj["total_capitalist_spending"], self.params.alpha_c * (M - m_w))

        self.traj["labor_commanded"] = np.append(self.traj["labor_commanded"], [p / w], axis= 0)

        self.traj["money_rate_of_exploitation"] = np.append(self.traj["money_rate_of_exploitation"], (self.params.alpha_c * (M-m_w)) / (self.params.alpha_w * m_w))
        self.traj["total_val_c"] = np.append(self.traj["total_val_c"], values.dot(c))
        self.traj["value_of_hourly_cap_income"] = np.append(self.traj["value_of_hourly_cap_income"], [values.dot(c) / self._get_employment(q, l)], axis=0) 

        val_ms, val_cc, surplus_val, e, value_rop = self._get_value_split(values, b, q, A)
        self.traj["values_ms"] = np.append(self.traj["values_ms"], val_ms)
        self.traj["cc_vals"] = np.append(self.traj["cc_vals"], val_cc)
        self.traj["surplus_vals"] = np.append(self.traj["surplus_vals"], surplus_val)
        self.traj["e"] = np.append(self.traj["e"], e)
        self.traj["value_rops"] = np.append(self.traj["value_rops"], value_rop)
        self.traj["compos_of_capital"] = np.append(self.traj["compos_of_capital"], val_cc / val_ms)
        c_vals_money = (A.T@p)*q
        v_vals_money = (w*l)*q
        self.traj["money_compositions"] = np.append(self.traj["money_compositions"], [c_vals_money / v_vals_money], axis= 0) 
        self.traj["overall_money_composition"] = np.append(self.traj["overall_money_composition"], np.sum(c_vals_money) / np.sum(v_vals_money))

        total_value_out = q.dot(values)
        total_price_out = q.dot(p)
        self.traj["total_value_out"] = np.append(self.traj["total_value_out"], total_value_out)
        self.traj["total_price_out"] = np.append(self.traj["total_price_out"], total_price_out)
        self.traj["sectoral_out_vals"] = np.append(self.traj["sectoral_out_vals"], [q * values], axis= 0)
        self.traj["sectoral_out_prices"] = np.append(self.traj["sectoral_out_prices"], [q*p], axis= 0)

        sectoral_out_vals = q * values
        sectoral_out_prices = q * p
        # out_ratios = np.array([sectoral_out_vals[0]/sectoral_out_vals[1], sectoral_out_vals[0]/sectoral_out_vals[2], sectoral_out_vals[1]/sectoral_out_vals[2]])
        # self.traj["sectoral_out_ratios"] = np.append(self.traj["sectoral_out_ratios"], [out_ratios], axis= 0)
        self.traj["relative_value_out"] = np.append(self.traj["relative_value_out"], [sectoral_out_vals / total_value_out], axis= 0)
        self.traj["relative_price_out"] = np.append(self.traj["relative_price_out"], [sectoral_out_prices / total_price_out], axis= 0)

        # out_ratios = np.array([sectoral_out_vals[0]/sectoral_out_vals[1], sectoral_out_vals[0]/sectoral_out_vals[2], sectoral_out_vals[1]/sectoral_out_vals[2]])
        # self.traj["sectoral_out_ratios"] = np.append(self.traj["sectoral_out_ratios"], [out_ratios], axis= 0)

        epr, eq_p = self._get_equilibrium_info(p, w, A, l)
        self.traj["epr"] = np.append(self.traj["epr"], epr)
        self.traj["epr_prices"] = np.append(self.traj["epr_prices"], [eq_p], axis=0)

        epr, eq_p = self._get_equilibrium_info(p, w, A, l)

        profit_of_enterprise, interest, cost, total_capital_advanced, revenue, theoretical_profit, composition_of_capital_advanced = self._get_profit_split(y)
        self.traj["profit"] = np.append(self.traj["profit"], [np.sum(profit_of_enterprise)], axis= 0)
        self.traj["interest"] = np.append(self.traj["interest"], [np.sum(interest)], axis= 0)
        self.traj["total_cost"] = np.append(self.traj["total_cost"], [np.sum(cost)], axis= 0)
        self.traj["relative_costs"] = np.append(self.traj["relative_costs"], [cost / np.sum(cost)], axis= 0)
        self.traj["total_sectoral_costs"] = np.append(self.traj["total_sectoral_costs"], [cost], axis= 0)
        self.traj["total_capital_advanced"] = np.append(self.traj["total_capital_advanced"], [total_capital_advanced], axis= 0)
        self.traj["composition_of_capital_advanced"] = np.append(self.traj["composition_of_capital_advanced"], composition_of_capital_advanced)
        self.traj["revenue"] = np.append(self.traj["revenue"], [np.sum(revenue)], axis= 0)
        self.traj["theoretical_profit"] = np.append(self.traj["theoretical_profit"], [theoretical_profit], axis= 0)

        total_profit = np.sum(profit_of_enterprise) + np.sum(interest)
        self.traj["total_profit"] = np.append(self.traj["total_profit"], total_profit)
        hourly_profit = total_profit / self._get_employment(q, l)

        self.traj["hourly_cap_income"] = np.append(self.traj["hourly_cap_income"], hourly_profit)
        self.traj["hourly_real_cap_income"] = np.append(self.traj["hourly_real_cap_income"], [hourly_profit / (p.dot(self.params.c_bar))*self.params.c_bar], axis= 0)

        hourly_b, ms_val, c_vals, v_vals, s_vals = self._get_composition_info(p, w, values, A, l, e)
        self.traj["hourly_b"] = np.append(self.traj["hourly_b"], [hourly_b], axis= 0)
        self.traj["hourly_b_val"] = np.append(self.traj["hourly_b_val"], hourly_b.dot(values))
        self.traj["val_ms"] = np.append(self.traj["val_ms"], ms_val)
        self.traj["c_vals"] = np.append(self.traj["c_vals"], [c_vals], axis= 0)
        self.traj["v_vals"] = np.append(self.traj["v_vals"], [v_vals], axis= 0)
        self.traj["s_vals"] = np.append(self.traj["s_vals"], [s_vals], axis= 0)
        self.traj["sectoral_comps"] = np.append(self.traj["sectoral_comps"], [c_vals / v_vals], axis= 0)
        self.traj["capital_intensities"] = np.append(self.traj["capital_intensities"], [c_vals / l], axis= 0)

        profit_rates, profit_of_enterprise_rates = self._get_profit_rates(A, p, w, l, self.traj["r"][-1])
        sectoral_shares = self._get_unit_shares(A, p, w, l)
        self.traj["sectoral_shares"] = np.append(self.traj["sectoral_shares"], [sectoral_shares], axis= 0)
        self.traj["profit_rates"] = np.append(self.traj["profit_rates"], [profit_rates], axis=0)
        self.traj["profit_of_enterprise_rates"] = np.append(self.traj["profit_of_enterprise_rates"], [profit_of_enterprise_rates], axis= 0)

        # MELT = p.dot(q) / values.dot(q)
        MELT = (p.dot(q) - p.dot(A@q)) / l.dot(q)
        self.traj["MELT_values"] = np.append(self.traj["MELT_values"], [MELT*values], axis= 0)
        self.traj["MELT"] = np.append(self.traj["MELT"], MELT)
        self.traj["MELT_prices"] = np.append(self.traj["MELT_prices"], [p / MELT], axis= 0)
        # old_epr, old_eqp = self._get_pf_info(A, old_l, self.params.b_bar)
        # epr, eqp = self._get_pf_info(A, l, self.params.b_bar)
        max_rop_epr, max_rop_eqp = self._get_equilibrium_info(p, 0, A, l)
        self.traj["max_rop"] = np.append(self.traj["max_rop"], max_rop_epr)
        self.traj["MELT_adjusted_m_w"] = np.append(self.traj["MELT_adjusted_m_w"], m_w / MELT)
        self.traj["MELT_adjusted_m_c"] = np.append(self.traj["MELT_adjusted_m_c"], (1-m_w) / MELT)

        old_p = self.traj["kliman_prices"][-1]
        old_actual_p = self.traj["p"][-2]
        old_w = self.traj["w"][-2]

        OLD_TSSI_MELT = self.traj["TSSI_MELT"][-1]
        ACTUAL_OLD_TSSI_MELT = self.traj["ACTUAL_TSSI_MELT"][-1]

        old_hourly_b = old_w / (old_p.dot(self.params.b_bar)) * self.params.b_bar

        tssi_v_n = old_w / OLD_TSSI_MELT
        actual_tssi_v_n = old_w / ACTUAL_OLD_TSSI_MELT
        tssi_V = tssi_v_n * employment
        actual_tssi_V = actual_tssi_v_n * employment
        actual_tssi_C = (A.T@old_actual_p).dot(q) / ACTUAL_OLD_TSSI_MELT
        self.traj["tssi_C"] = np.append(self.traj["tssi_C"], actual_tssi_C)
        self.traj["tssi_V"] = np.append(self.traj["tssi_V"], actual_tssi_V)
        tssi_C = (A.T@old_p).dot(q) / OLD_TSSI_MELT
        tssi_v = tssi_v_n * l
        actual_tssi_v = actual_tssi_v_n * l
        tssi_s = l - tssi_v
        actual_tssi_s = l - actual_tssi_v
        tssi_S = tssi_s.dot(q)
        actual_tssi_S = actual_tssi_s.dot(q)
        self.traj["tssi_S"] = np.append(self.traj["tssi_S"], actual_tssi_S)
        self.traj["tssi_e"] = np.append(self.traj["tssi_e"], tssi_S / max(tssi_V, 1e-7))

        kliman_profit_rate = tssi_S / (tssi_C + tssi_V)
        M = A + np.linalg.outer(old_hourly_b, l)
        new_kliman_prices = (1+kliman_profit_rate)*M.T@old_p
        scalar = np.linalg.norm(p) / np.linalg.norm(new_kliman_prices)
        new_kliman_prices *= scalar 

        self.traj["kliman_profit_rate"] = np.append(self.traj["kliman_profit_rate"], kliman_profit_rate)
        self.traj["kliman_prices"] = np.append(self.traj["kliman_prices"], [new_kliman_prices], axis= 0)
        TSSI_MELT = new_kliman_prices.dot(q) / (tssi_C + employment)
        ACTUAL_TSSI_MELT = p.dot(q) / (actual_tssi_C + employment)
        tssi_cost_adj = (ACTUAL_TSSI_MELT - ACTUAL_OLD_TSSI_MELT)*(actual_tssi_C + actual_tssi_V)

        self.traj["TSSI_MELT"] = np.append(self.traj["TSSI_MELT"], TSSI_MELT)
        self.traj["ACTUAL_TSSI_MELT"] = np.append(self.traj["ACTUAL_TSSI_MELT"], ACTUAL_TSSI_MELT)

        new_kliman_eqb_values = 1/OLD_TSSI_MELT * (A.T@old_p) + l
        new_kliman_values = 1/ACTUAL_OLD_TSSI_MELT * (A.T@old_actual_p) + l
        self.traj["kliman_values"] = np.append(self.traj["kliman_values"], [new_kliman_eqb_values], axis= 0)
        self.traj["kliman_actual_values"] = np.append(self.traj["kliman_actual_values"], [new_kliman_values], axis= 0)

        commodity_shares = c / np.maximum(b, 1e-3)
        self.traj["commodity_shares"] = np.append(self.traj["commodity_shares"], [commodity_shares], axis=0)

        cost_vec = b + A.T @ q
        commodity_surplus = c / np.maximum(cost_vec, 1e-3)
        self.traj["commodity_surplus"] = np.append(self.traj["commodity_surplus"], [commodity_surplus], axis=0)

        # C_tilde, V_tilde, S_tilde, SI_exploitation, SI_composition, SI_profit_rate = self._get_super_integrated_value_split(y)
        super_vals, A_tilde = self._get_super_integrated_value_split2(y)
        self.traj["super_integrated_vals"] = np.append(self.traj["super_integrated_vals"], [super_vals], axis= 0)
        self.traj["super_integrated_wage_vals"] = np.append(self.traj["super_integrated_wage_vals"], [w * super_vals], axis= 0)

        m = A.T@p+w*l
        v_n = w / MELT
        ni_variable = v_n*employment
        ni_v = v_n * l
        ni_s = l - ni_v
        ni_variable = ni_v.dot(q)
        ni_surplus = ni_s.dot(q)
        self.traj["NI_variable"] = np.append(self.traj["NI_variable"], ni_variable)
        self.traj["NI_surplus"] = np.append(self.traj["NI_surplus"], ni_surplus)
        self.traj["NI_exploitation"] = np.append(self.traj["NI_exploitation"], ni_surplus / ni_variable)

        self.traj["MELT_converted_profit"] = np.append(self.traj["MELT_converted_profit"], ni_surplus * MELT)
        self.traj["TSSI_MELT_converted_profit"] = np.append(self.traj["TSSI_MELT_converted_profit"], actual_tssi_S * ACTUAL_TSSI_MELT)
        self.traj["TSSI_MELT_converted_profit_plus_melt_diff"] = np.append(self.traj["TSSI_MELT_converted_profit_plus_melt_diff"], tssi_cost_adj + actual_tssi_S * ACTUAL_TSSI_MELT)
        sssi_C = (A.T@p).dot(q) / MELT
        self.traj["sssi_C"] = np.append(self.traj["sssi_C"], sssi_C)
        sssi_c = A.T@p / MELT
        sssi_values = sssi_c + l
        self.traj["SSSI_vals"] = np.append(self.traj["SSSI_vals"], [sssi_values], axis= 0)
        self.traj["SSSI_rop"] = np.append(self.traj["SSSI_rop"], ni_surplus / (ni_variable + sssi_C))

    def _get_employment(self, q, l):
        return q@l

    def _get_dydt(self, params):
        # Creates the right hand side of the equation dy/dt = f(t,y)
        # This is what you will want to make alterations to in order to tweak the dynamics of the system. 
        def rhs(t: float, y: np.ndarray) -> np.ndarray:
            q, p, s, l, m_w, L, w, M, A = self._unpack(y)
            if self.fixed_real_wage:
                w = p.dot(self.params.b_bar) 
            elif self.fixed_money_wage:
                w = self.traj["w"][-1]

            delta_M = self._get_delta_M(y)
            delta_L = self._get_delta_L(y)
            delta_A, delta_l = self._get_delta_technology(y)
            r = self._get_interest_rate(m_w)
            delta_m_w = self._get_delta_m_w(y, w)
            total_demand = self._get_total_demand(y)
            delta_s = self._get_delta_s(y, total_demand)
            delta_p = self._get_delta_p(y, delta_s)
            delta_q = self._get_delta_q(y, r, total_demand, delta_l, delta_L)
            delta_w = self._get_delta_w(y, delta_q, delta_l, delta_p)
            return self._repack(delta_q, delta_p, delta_s, delta_l, delta_m_w, delta_L, delta_w, delta_M, delta_A)

        return rhs

    def _get_delta_M(self, y):
        return self.exo_delta_M

    def _get_delta_w(self, y, delta_q, delta_l, delta_p):
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            return 0
        reserve_army_safe = np.maximum(L - l.dot(q), 1e-6)
        delta_w = (-1 * self.exo_delta_w * w) + (self.params.eta_w * (q.dot(delta_l) + l.dot(delta_q)) * 1 / reserve_army_safe * w)
        return delta_w

    def _get_delta_technology(self, y):
        i = self.current_i
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]

        change_type = self.params.change_type
        shock_type = self.params.shock_type
        epsilon = self.params.cost_tradeoff
        shock_mag = self.params.shock_mag

        delta_A = np.array([np.zeros(self.n) for j in range(self.n)]) + self.exo_delta_A
        delta_l = np.zeros(self.n) + self.exo_delta_l

        a_cols = [A[:,j] for j in range(self.n)]
        a_i = a_cols[i]
        cost_ratio = a_i.dot(p) / max(w*l[i], 1e-12)

        if change_type == "discrete" or change_type == "none" or (self.params.stop_cts_changes_halfway and self.current_t > self.params.T / 2):
            return delta_A, delta_l

        a_i = A[:,i].copy()
        l_i = l[i]

        cost_ratio = a_i.dot(p) / max(w*l[i], 1e-12)

        if shock_type == "culs" or shock_type == "ls":
            beta = shock_mag
            delta_l[i] += -1*beta*l_i

            gamma = cost_ratio*(1 + epsilon)
            alpha = beta / max(gamma, 1e-12)

            if shock_type != "ls":
                delta_A[:,i] += alpha * a_i
        else:
            alpha = shock_mag
            beta = alpha * cost_ratio * (1-epsilon)

            delta_A[:,i] += -1*alpha*a_i

            if shock_type != "cs":
                delta_l[i] += beta * l_i
                
        return delta_A, delta_l

    def _get_delta_L(self, y):
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        E = float(l.dot(q))
        if E <= 0:
            return 0.0

        u = L / E - 1.0
        u_max = self.params.mu_L
        alpha_L = self.params.alpha_L

        if u >= u_max:
        #     # Already at or above max unemployment: no more growth
            return 0.0

        u_raw = (L-E) / max(E, 1e-12)
        if u_raw <= 0.0:
            return 0.0

        # Scale growth by how far you are from max unemployment
        factor = 1.0 - u / u_max    # ∈ (0,1) if 0 <= u < u_max
        return alpha_L * L * factor

        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        E = float(l.dot(q))
        u_max = self.params.mu_L
        K = (1+u_max) * max(E, 1e-12)
        alpha_L = self.params.alpha_L 
        return alpha_L*L * (1 - L/K)

    def _get_delta_m_w(self, y, w):

        alpha_w = self.params.alpha_w
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]
        total_labor = l.dot(q)
        delta_m_w = total_labor * w - alpha_w * m_w

        if self.params.money_injection_target == "workers":
            delta_m_w += self.exo_delta_M

        return delta_m_w

    def _get_total_demand(self, y):

        b_bar, c_bar, alpha_w, alpha_c = self.params.b_bar, self.params.c_bar, self.params.alpha_w, self.params.alpha_c
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)

        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)

        p_dot_b = max(p.dot(b_bar), 1e-12)
        p_dot_c = max(p.dot(c_bar), 1e-12)

        b = (b_bar * alpha_w * m_w) / p_dot_b
        c = (c_bar * alpha_c * (M - m_w)) / p_dot_c
        total_demand = A@q + b + c
        return total_demand

    def _get_delta_s(self, y, total_demand):

        q, p, s, l, m_w, L, w, M, A = self._unpack(y)

        change_type = self.params.supply_shock_setting
        shock_mag = self.params.supply_shock_mag

        delta_s = q - total_demand - self.exo_supply_deduction

        if change_type == "periodic" or change_type == "none":
            return delta_s
        else:
            cts_deduction = q * shock_mag
            delta_s -= cts_deduction
            return delta_s

    def _get_delta_p(self, y, delta_s):
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)

        if self.params.output_equation == "cross-dual":
            total_demand = self._get_total_demand(y)
            demand_ratio = (total_demand - q) / q
            delta_p = self.params.eta * demand_ratio * p
        else:
            s_safe = np.maximum(s, self.params.s_floor)
            delta_p = -self.params.eta * delta_s * (p / s_safe)
        return delta_p

    def _get_delta_q(self, y, r, total_demand, delta_l= None, delta_L= None):
        
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar) # <-- Real wage change
        unit_cost = A.T@p+w*l
        revenue = p * total_demand # sectoral revenue vector (not a dot product)
        total_cost = unit_cost * (1.0 + r) * q 
        profit = revenue - total_cost # sectoral profit vector
        denom = np.maximum(unit_cost * (1.0 + r) * q, 1e-12)

        if self.params.output_equation == "relative":
            delta_q = self.params.kappa * (profit / denom) * q
        elif self.params.output_equation == "cross-dual":
            rev = np.sum(revenue)
            cost = np.sum(total_cost)
            avg_profit_rate = (rev - cost) / cost
            avg_profit_rate_vec = np.ones(self.n) * avg_profit_rate
            delta_q = (avg_profit_rate_vec + self.params.kappa * (profit / denom - avg_profit_rate_vec))*q
        else:
            # from profit, we obtain change in output
            delta_q = self.params.kappa * profit

            # denom = np.maximum(unit_cost * (1.0 + r) * q, 1e-12)
            # delta_q = self.params.kappa * (profit / (1+r))

        if self.nondecreasing_employment:
            if delta_l is None: delta_l = np.zeros(self.n)

            # 1) unconstrained q dynamics
            delta_q_unconstrained = self.params.kappa * (profit / denom)

            # 2) d/dt (l·q) under unconstrained dynamics
            employment_dot_unconstrained = delta_l.dot(q) + l.dot(delta_q_unconstrained)

            # 3) If employment would fall, project onto constant-employment direction
            if employment_dot_unconstrained < 0.0:
                l_norm2 = l.dot(l)
                if l_norm2 > 0.0:
                    gamma = (-delta_l.dot(q) - l.dot(delta_q_unconstrained)) / l_norm2
                    delta_q = delta_q_unconstrained + gamma * l
                else:
                    # pathological case l = 0, just fall back
                    delta_q = delta_q_unconstrained
            else:
                # employment not falling, no constraint applied
                delta_q = delta_q_unconstrained

        # Don't let employment exceed the labor force
        if self.params.employment_guardrails:
            if delta_l is None:
                delta_l = np.zeros(self.n)

            employment = float(l.dot(q))
            tol = getattr(self.params, "eps_u", 1e-8)   # reuse eps_u as a small tolerance

            if delta_L is None:
                L_dot = 0.0
            else:
                L_dot = float(delta_L)

            # Current employment derivative under whatever delta_q we have so far
            employment_dot = float(delta_l.dot(q) + l.dot(delta_q))

            if employment >= L - tol and employment_dot > L_dot:
                # Project delta_q so that d/dt(ℓ·q) = L_dot instead of > L_dot
                l_norm2 = float(l.dot(l))
                if l_norm2 > 0.0:
                    gamma = (L_dot - delta_l.dot(q) - l.dot(delta_q)) / l_norm2
                    delta_q = delta_q + gamma * l
                # if l_norm2 == 0, nothing sensible to do; just keep delta_q

        return delta_q

    # DEPRECATED
    # def _get_hourly_wage(self, y):

    #     """Returns the current hourly wage given the current level of employment and size of reserve army"""
    #     q, p, s, l, m_w, L, w, M, A = self._unpack(y)
    #     initial_employment = float(self.params.l.dot(self.params.q))
    #     employment = float(l.dot(q))
    #     denom = max(L - employment, self.params.eps_u)
    #     num = max(self.params.L - initial_employment, self.params.eps_u)
    #     return self.params.w * (num / denom) ** self.params.eta_w

    def _get_interest_rate(self, m_w: float) -> float:

        """Returns the current interest rate given the current capitalist savings"""
        M = self.traj["M"][-1]
        denom = max(M - float(m_w), self.params.eps_m)
        num = max(self.params.M - self.params.m_w, self.params.eps_m)
        return self.params.r * (num / denom) ** self.params.eta_r

    def _get_consumption(self, M, m_w, p):

        b = (self.params.alpha_w * m_w)/(p.dot(self.params.b_bar))*self.params.b_bar
        c = (self.params.alpha_c * (M-m_w))/(p.dot(self.params.c_bar))*self.params.c_bar
        return b, c

    def _get_values(self, A, l):

        return np.linalg.inv(np.eye(self.n) - A.T)@l

    def _get_value_split(self, values, b, q, A):

        total_value = q.dot(values)
        val_ms = b.dot(values)
        val_cc = values.dot(A@q)
        surplus_val = total_value - val_ms - val_cc
        e = surplus_val / val_ms
        value_rop = surplus_val / (val_ms + val_cc)
        return val_ms, val_cc, surplus_val, e, value_rop

    def _get_equilibrium_info(self, p, w, A, l):

        hourly_b = w / (p.dot(self.params.b_bar)) * self.params.b_bar
        r_hat, eq_p = self._get_pf_info(A, l, hourly_b)
        r_hat = np.real(r_hat)
        epr = 1/r_hat - 1
        scalar = np.linalg.norm(p) / np.linalg.norm(eq_p)
        eq_p = scalar * eq_p
        return epr, eq_p

    def _get_composition_info(self, p, w, values, A, l, e):

        hourly_b = w / (p.dot(self.params.b_bar)) * self.params.b_bar
        val_ms = values.dot(hourly_b)
        c_vals = A.T@values
        v_vals = (val_ms)*l
        s_vals = e*v_vals
        return hourly_b, val_ms, c_vals, v_vals, s_vals

    def _get_pf_info(self, A, l, b):

        M = A+np.linalg.outer(b,l)
        (evals, evecs) = eig(M.T)
        index = np.argmax(evals.real)
        r_hat = evals[index]
        p = evecs[:,index].real
        if p[0] < 0:  p *= -1
        return r_hat, p

    def _get_profit_rates(self, A, p, w, l, r):

        unit_costs = A.T@p + w*l
        interest_unit_costs = unit_costs * (1+r)
        unit_profit_rates = p - unit_costs
        unit_interest_profit_rates = p - interest_unit_costs
        for i in range(self.n):
            unit_profit_rates[i] /= unit_costs[i]
        for i in range(self.n):
            unit_interest_profit_rates[i] /= interest_unit_costs[i]
        return unit_profit_rates, unit_interest_profit_rates

    def _get_unit_shares(self, A, p, w, l):
        unit_costs = A.T@p + w*l
        unit_profits = p - unit_costs

        return unit_profits / (w*l)

    def _get_super_integrated_value_split(self,y):

        """ Calculates super-integrated value stuff from the price system by dividing by the unit wage """
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]
        C_tilde = (A.T@p).dot(q)/w
        V_tilde = l.dot(q)
        S_tilde = self.params.alpha_c * (M-m_w) / w
        SI_exploitation = S_tilde / V_tilde
        SI_composition = C_tilde / V_tilde
        SI_profit = S_tilde / (C_tilde + V_tilde)

        return C_tilde, V_tilde, S_tilde, SI_exploitation, SI_composition, SI_profit

    # TODO: Anticipate or look back on investment spending to obtain the true SI-values
    def _get_super_integrated_value_split2(self, y):

        """ Calculates super-integrated value stuff directly from labor values (this is not technically correct unless the system is in equilibrium) """
        q, p, s, l, m_w, L, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]

        m = A.T@p + w*l
        c_vec = self.params.alpha_c * (M-m_w) / (p.dot(self.params.c_bar)) * self.params.c_bar # Total capitalist consumption vector
        C = np.linalg.outer(c_vec, m) / (m.dot(q)) # Capitalist consumption matrix
        A_tilde = A+C 
        super_vals = np.linalg.inv(np.eye(self.n)-A_tilde.T)@l

        return super_vals, A_tilde

    def _get_profit_split(self, y):

        """ Get total profit related stuff """
        total_demand, r = self._get_total_demand(y), self.traj["r"][-1]
        q, p, _, l, _, _, w, M, A = self._unpack(y)
        if self.fixed_real_wage:
            w = p.dot(self.params.b_bar)
        elif self.fixed_money_wage:
            w = self.traj["w"][-1]
        unit_cost = A.T@p+w*l
        unit_cost_constant = A.T@p
        unit_cost_variable = w*l
        revenue = p * total_demand # sectoral revenue vector (not a dot product)
        total_cost = unit_cost * (1.0 + r) * q 
        total_capital_advanced = unit_cost * q
        composition_of_capital_advanced = (unit_cost_constant.dot(q)) / (unit_cost_variable.dot(q))
        profit_of_enterprise = revenue - total_cost # sectoral profit vector
        theoretical_profit = (p - unit_cost).dot(q)
        interest = unit_cost*r*q
        return profit_of_enterprise, interest, total_cost, total_capital_advanced, revenue, theoretical_profit, composition_of_capital_advanced

if __name__ == "__main__":
    pass
