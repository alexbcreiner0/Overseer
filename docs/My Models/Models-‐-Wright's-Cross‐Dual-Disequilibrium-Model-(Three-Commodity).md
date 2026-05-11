# Description
A cross-dual model for a capitalist economy. The model is extremely robust and has a ton of possible applications. The model is extremely robust and very well suited to experimentation. This page will mostly be a glossary of equations used on plots. For more detailed information about the model see Wright's thesis: [Ian Wright's PhD thesis](http://pinguet.free.fr/wrightthesis.pdf/) or my own upcoming paper where I investigate the effects of technical change on the rate of profit (which is what this model was particularly designed for). There is a lot I am planning on adding and doing to this, and by the time you download it it will probably already look different from the screenshot. Have fun!


# Variables
## State Variables
- Input-output matrix $A \in \mathbb{R}^{n\times n}$ 
- Vector of unit prices: $\mathbf{p} \in \mathbb{R}^n$ )
- Vector of output quantities: $\mathbf{q} \in \mathbb{R}^n$
    - More correctly seen as a vector of activity levels since it is a continuous quantity
- Overall supply vector: $\mathbf{s} \in \mathbb{R}^n$ 
- Total money: $M > 0$ 
- Total available hours of labor for hire: $L > 0$ 
- Worker savings: $m_w \in (0,M)$ 
- Capitalist savings: $m_c \in (0,M)$ 
    - $M = m_w + m_c$ (all money is possessed by someone)
- Worker propensity to consume: $\alpha_w \in (0,1)$ 
- Capitalist propensity to consume: $\alpha_c \in (0,1)$ 
    - Workers spent these proportions of their savings each period
- Worker consumption preferences: $\underline{\mathbf{b}} \in \mathbf{R}^n$
- Capitalist consumption preferences: $\underline{\mathbf{c}} \in \mathbf{R}^n$
    - (Workers and capitalists choose purchase goods in these proportions)
- Interest rate: $r \in (0,1)$
- Hourly wage: $w \in (0,1)$

## Constants
- Price-supply elasticity constants: $\mathbf{\eta} \in \mathbb{R}^n$
- Output-profit elasticity constants: $\mathbf{\kappa} \in \mathbb{R}^n$
- Wage elasticity constant: $\eta_w > 0$
- Interest rate elasticity constant: $\eta_r > 0$

## Dynamics driving dependent variables
- Total Employment: $E = \mathbf{l}\cdot \mathbf{q}$
- Reserve army size (supply of labor): $L - \mathbf{l}\cdot \mathbf{q}$
- Hourly real wage bundle: $\mathbf{b} = \frac{w}{\mathbf{p}\cdot \underline{\mathbf{b}}}\underline{\mathbf{b}}$
- Worker demand bundle: $\hat{\mathbf{b}} = \frac{\alpha_w m_w}{\mathbf{p}\cdot \underline{\mathbf{b}}}\underline{\mathbf{b}}$
- Capitalist demand bundle: $\hat{\mathbf{c}}$ $=\frac{\alpha_c m_c}{\mathbf{p}\cdot \underline{\mathbf{c}}}\underline{\mathbf{c}}$
- Total demand: $A\mathbf{q} + \hat{\mathbf{b}} + \hat{\mathbf{c}}$  
- Augmented input/output matrix: $M = A+\mathbf{b}\mathbf{l}^T$
- Vector of unit costs: $\mathbf{m} = A^T\mathbf{p} + w\mathbf{l}$
- Total Capital Advanced: $\mathbf{m} \cdot \mathbf{q}$
- $i^{th}$ Sector Total Capital Advanced: $m_i q_i$
- $i^{th}$ Sector Total Cost of Production: $(1+r)(m_i q_i)$
- $i^{th}$ Sector Total Profit: $\Pi_i = p_i d_i - (1+r)(m_i q_i)$
- Total Profit: $\Pi = \sum_{i=1}^{n} \Pi_i$
- $i^{th}$ Sector (Actual) Profit Rate: $\pi_i = \frac{\Pi_i}{(1+r)(m_i q_i)}$
    - These are **not** the sectoral profit rates plotted in the app by default. See below for those.
- Total Interest: $\Psi = (1+r)(\mathbf{m} \cdot \mathbf{q})$
- Total Capitalist Money Income: $\Pi + \Psi$
- Average profit rate: $\pi^* = \Pi / ((1+r)\mathbf{m}\cdot \mathbf{q})$

# Equations
## Dynamics
These are the differential equations which drive the system:
- Supply of $i^{th}$ commodity: $\frac{ds_i}{dt} = q_i - d_i$ 
- Worker savings: $\frac{dm_w}{dt} = w(\mathbf{l}\cdot \mathbf{q}) - \alpha_w m_w$
- Capitalist savings: $\frac{dm_c}{dt} = \Pi + \Psi - \alpha_c m_c$
- Prices: 
    - Default Equation: $\frac{1}{p_i}\frac{dp_i}{dt} = -\eta_i \frac{1}{s_i}\frac{ds_i}{dt}$
    - Cross-Dual: $\frac{1}{p_i}\frac{dp_i}{dt} = \eta_i \left( \frac{d_i - q_i}{q_i} \right)$
- Wages: $\frac{1}{w}\frac{dw}{dt} = \eta_w \frac{1}{L-E}\frac{dE}{dt}$
- Interest rate: $\frac{1}{r}\frac{dr}{dt} = -\eta_r \frac{1}{m_c}{dm_c}{dt}$
- Output: 
    - Absolute Output Scales with Profit (Default): $\frac{dq_i}{dt} = \kappa_i \Pi_i$
    - Relative Output Scales with Profit Rate: $\frac{1}{q_i}\frac{dq_i}{dt} = \kappa_i \pi_i$
    - Cross-Dual: $\frac{q}{q_i}\frac{dq_i}{dt} = \pi^* + \kappa_i (\pi_i - \pi^*)$

## Everything Else
### (Classical) Value System
- Unit value vector: $\mathbf{v} = (I-A^T)^{-1}\mathbf{l}$
    - This vector as found in the Prices and Values category of plots is being multiplied by the unit wage $w$ for the sake of comparison with prices.
- Total output value: $\mathbf{v} \cdot \mathbf{q}$
- $i^{th}$ sector output value: $q_i v_i$
- $i^{th}$ sector relative output value: $\frac{q_i v_i}{\mathbf{v} \cdot \mathbf{q}}$
- Value of constant capital: $C = (A\mathbf{q})\cdot \mathbf{v}$
- Total value of means of subsistence: $V = \hat{\mathbf{b}} \cdot \mathbf{v}$
- Total surplus value: $S = \mathbf{q} \cdot \mathbf{v} - (C+V)$
    - Note: Most theorists accept the definition that $S = \mathbf{q}\cdot \mathbf{v} - V$. I do not agree with this! Just because labor does not return to the worker in wages does not mean it is surplus! If you don't agree with my choice, try altering the code to the more common definition and see for yourself how the rate of exploitation and value rate of profit changes!
- Rate of exploitation: $e = \frac{S}{V}$
- Value rate of profit: $\pi_v = \frac{S}{C+V}$
- Value composition of capital: $k = \frac{C}{V}$
- Value of hourly wage: $\mathbf{b} \cdot \mathbf{v}$
- Total value of capitalist consumption: $\hat{\mathbf{c}}$ $\cdot \mathbf{v}$
- Value of hourly capitalist income: $\frac{\mathbf{c} \cdot \mathbf{v}}{E}$
- $i^{th}$ Sector Value Composition of Capital: $\frac{c_i}{v_i}$
- $i^{th}$ Sector Capital Intensity (Technical Composition of Capital): $\frac{(A^T\mathbf{v})_i}{l_i}$

### Price System
- Perron-Frobenius maximal eigenvalue of $M$: $\hat{r}$ (definition is the name)
- Equilibrium rate of profit: $\hat{\pi} = \frac{1}{\hat{r}} - 1$
- Maximum rate of profit: The same process but for $A$ instead of $M$
- Equilibrium prices: An eigenvalue $\mathbf{\hat{p}}$ of $M$ which is associated with $\hat{r}$, scaled it such that $|\mathbf{\hat{p}}| = |\mathbf{p}(t)|$ (i.e. the real price vector at time $t$)
- Money composition of capital: $\frac{(A\mathbf{p})\cdot \mathbf{q}}{\mathbf{p}\cdot \mathbf{b}}$
- $i^{th}$ Sector Rate of Profit: $\pi^* = \frac{p_i - m_i}{m_i}$
    - This is what the app lists as the profit rate of the $i^{th}$ sector. Note that it 'factors in' the interest, i.e. represents the amount of profit which capitalists receive as interest *or* as profit of enterprise. 
    - Actual profit rates, e.g. the $\pi_i$ defined above, are listed as Sectoral Rates of Profit (Enterprise)
- $i^{th}$ Sector Profit-Wage Share: $\frac{p_i - m_i}{wl_i}$
- Okishio Predicted Profit Rates: Only calculated after discrete technical change. This is calculated the Perron-Frobenius profit rate (as above) for the matrix $M' = A' + \mathbf{b}\mathbf{l}'^T$ where $A'$ and $\mathbf{l}'$ are the input-output matrix and living labor vector after the changes, and $\mathbf{b}$ is the real hourly wage vector as it currently is prior to the step which first witnesses the technical changes.

### Super-Integrated Labor Values
The calculations done here currently ignore the profit which goes towards expanding production. Adding this in would be the only way to obtain the truly correct super-integrated labor values, but this would be very hard (working on it!). Until then, consider the following equations as under-estimates of the true super-integrated labor values, which converge to the actual super-integrated values as the system settles into equilibrium. 
 
- Capitalist consumption matrix: $C = \frac{\hat{\mathbf{c}}\cdot \mathbf{m}^T}{\mathbf{m}\cdot \mathbf{q}}$
- Modified consumption input/output matrix: $\tilde{A} = A + C$
- Super-integrated labor values: $\mathbf{v}^* = (I - A^T)^{-1}\mathbf{l}$
- Super-integrated value of constant capital: $\tilde{C} = \mathbf{v}^*\cdot (A\mathbf{q})$
- Super-integrated value of variable capital: $\tilde{V} = \mathbf{v}^* \cdot \hat{\mathbf{b}}$
- Super-integrated surplus value: $\tilde{S} = \mathbf{v}^* \cdot \hat{\mathbf{c}}$
- Super-integrated rate of exploitation: $\frac{\tilde{S}}{\tilde{V}}$
- Super-integrated value composition of capital: $\frac{\tilde{C}}{\tilde{V}}$
- Super-integrated value rate of profit: $\frac{\tilde{S}}{\tilde{C}+\tilde{V}}$

### New Interpretation and 'Simultaneous' Single System Interpretation Systems
- The MELT: $\tau = \frac{\mathbf{p}\cdot \mathbf{(I-A)\mathbf{q}}}{\mathbf{l}\cdot \mathbf{q}} = \frac{\textrm{Total (price) value added}}{\textrm{Total living labor}}$
- MELT values: $\tau \mathbf{v}$. Thus these are an evaluation of how accurately prices can be predicted from the value system given the MELT. 
- MELT prices: $\frac{\mathbf{p}}{\tau}$. These are an evaluation of how accurately values can be inferred from prices given the MELT.
- New Interpretation total variable capital: $V_n = \frac{w}{\tau}E$ (i.e. MELT adjusted total wages).
- New Interpretation total surplus value: $S_n = E - V_n$
    - Equals the MELT adjusted total profit in equilibrium.
- New Interpretation rate of exploitation: $e_n = \frac{S_n}{V_n}$
- New New Interpretation (SSSI) total value of constant capital: $C_n = \frac{1}{\tau}(A^T\mathbf{p})\cdot \mathbf{q}$
- New New Interpretation (SSSI) value rate of profit: $\frac{S_n}{C_n + V_n}$
    - Equals the actual rate of profit in equilibrium. 
- New New Interpretation (SSSI) unit values: $\mathbf{v}_n = \frac{1}{\tau}A^T\mathbf{p} + \mathbf{l}$

The New Interpretation doesn't have it's own value system, it still uses the classical unit labor values since it only revises the exploitation system. The value composition of capital is not worth computing here since it by definition equals the money composition of capital.

### Temporal Single System Interpretation Values
Let $x(t)$ and $x(t-1)$ denote the arbitrary variable $x$ at *computational steps* $t$ and $t-1$. I tried calculating values based on model time steps as well, and it did not make a difference (things were just choppier). TSSI-specific variables will be given the subscript K
- TSSI value of constant capital: $C_K(t) = (\frac{1}{\tau_K(t-1)})(A^T(t)\mathbf{p}(t-1))\cdot\mathbf{q}(t)$
- TSSI value of variable capital: $V_K(t) = (\frac{w(t-1)}{\tau_K(t-1)})E(t)$
- TSSI surplus value: $S_K(t) = E(t) - V_K(t)$
- TSSI rate of exploitation: $e_K(t) = \frac{S_K(t)}{V_K(t)}$
- TSSI MELT: $\tau_K(t) = \frac{\mathbf{p}(t)\cdot \mathbf{q}(t)}{C_K(t) + E} = \frac{\textrm{Price of gross product}}{\textrm{(TSSI) Value of gross output}}$
   - The TSSI theorists have repeatedly refused to formally define a base case for their recursive MELT. To get around this, I made the base case a parameter which is adjustable within the app. However, I don't think that this is very important, as regardless of the base case it...
   - Equals the NI/SSSI MELT in equilibrium as expected from [this paper](https://academic.oup.com/cje/article-abstract/39/3/769/1714600?redirectedFrom=fulltext). 
- TSSI unit values: $\mathbf{v}_K(t) = \frac{1}{\tau_K(t-1)}A^T\mathbf{p}(t-1) + \mathbf{l}$
- All above uses of $\mathbf{p}$ are the *actual* prices. 
- There is no point in computing TSSI prices, as these are by definition equal to the actual prices (the $\mathbf{g}$ vector fudge factor just takes on whatever values it needs to in order to ensure this). *However*, we can and should compute the TSSI *equilibrium* prices as a counterfactual price system. Let $\tau_K'(t)$ denote the counterfactual TSSI MELT (it uses the same parameter as the actual TSSI MELT as a base case), and $\mathbf{p}_K(t)$ denote the equilibrium TSSI prices at time $t$ (is initialized to equal the actual equilibrium unit price vector as a base case). 
- TSSI equilibrium value of constant capital: $C_K'(t) = (\frac{1}{\tau_K'(t-1)})(A^T\mathbf{p}_K(t-1))\cdot\mathbf{q}$
- TSSI value of variable capital: $V_K'(t) = (\frac{w(t-1)}{\tau_K'(t-1)})E(t)$
- TSSI surplus value: $S_K'(t) = E(t) - V_K'(t)$
- TSSI Equilibrium Profit Rate: $\pi_K(t) = \frac{S_K'(t)}{C_K'(t) + V_K'(t)}$
- TSSI augmented requirements matrix: $M_K(t) = A(t) + \mathbf{b}_K(t)\mathbf{l}(t)^T$ where $\mathbf{b}_K(t) = \frac{w(t-1)}{\mathbf{p}_K(t-1) \cdot \underline{\mathbf{b}}}\underline{\mathbf{b}}$
    - I.e. since the real wage is changing, we see the floating wage as a price and use it's previous value, as well as the old price TSSI vector to determine a counterfactual real wage bundle.
- TSSI Equilibrium prices: $\mathbf{p}_K(t) = (1+\pi_K(t))M_K^T(t)\mathbf{p}(t-1)$
- TSSI Equilibrium MELT: $\tau_K'(t) = \frac{\mathbf{p}_K(t)\cdot \mathbf{q}(t)}{C_K'(t) + E(t)}$