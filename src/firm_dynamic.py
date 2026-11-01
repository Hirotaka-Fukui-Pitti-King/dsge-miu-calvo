"""Численная задача фирмы при экзогенных агрегатных траекториях; не общее равновесие."""
from dataclasses import dataclass
import numpy as np
from scipy.interpolate import RegularGridInterpolator
from scipy.optimize import minimize, minimize_scalar

@dataclass(frozen=True)
class FirmEnvironment:
    productivity: tuple[float, ...]
    demand: tuple[float, ...]
    real_wage: tuple[float, ...]
    gross_inflation: tuple[float, ...]
    sdf: tuple[float, ...]
    alpha: float = .33
    epsilon: float = 6.
    delta: float = .025
    adjustment: float = 4.
    theta: float = .75
    terminal_capital_value: float = 1.

    def __post_init__(self):
        length = len(self.demand)
        if not all(len(x) == length for x in
                   (self.productivity, self.real_wage, self.gross_inflation, self.sdf)):
            raise ValueError("Несогласованные агрегатные траектории.")
        if not (0 < self.alpha < 1 and self.epsilon > 1 and 0 <= self.theta < 1):
            raise ValueError("Недопустимые параметры фирмы.")
        if min(*self.productivity, *self.demand, *self.real_wage,
               *self.gross_inflation, *self.sdf) <= 0:
            raise ValueError("Агрегатные величины должны быть положительными.")

def period_dividend(env, t, capital, relative_price, investment):
    """Выплаты владельцу капитала без двойного учёта ренты."""
    y = env.demand[t] * relative_price ** (-env.epsilon)
    n = (y / (env.productivity[t] * capital ** env.alpha)) ** (1 / (1 - env.alpha))
    adj = .5 * env.adjustment * capital * (investment / capital - env.delta)**2
    return relative_price * y - env.real_wage[t] * n - investment - adj

@dataclass
class FirmSolution:
    values: list
    keep_investment: list
    reset_investment: list
    reset_price: list
    capital_grid: np.ndarray
    price_grid: np.ndarray
    environment: FirmEnvironment

def solve_firm(env, capital_grid, price_grid):
    """Обратная индукция: отдельные ветви Кальво, совместный выбор цены и капитала."""
    kg = np.asarray(capital_grid, dtype=float)
    pg = np.asarray(price_grid, dtype=float)
    if len(kg) < 4 or len(pg) < 4 or np.any(np.diff(kg)<=0) or np.any(np.diff(pg)<=0) or min(kg[0],pg[0])<=0:
        raise ValueError("Нужны возрастающие положительные сетки хотя бы с четырьмя узлами.")
    shape = (len(kg),len(pg))
    terminal = env.terminal_capital_value * np.broadcast_to(kg[:,None],shape).copy()
    values = [np.zeros(shape) for _ in env.demand]+[terminal]
    keep = [np.zeros(shape) for _ in env.demand]
    reset_i = [np.zeros(shape) for _ in env.demand]
    reset_p = [np.zeros(shape) for _ in env.demand]
    for t in range(len(env.demand)-1,-1,-1):
        future = RegularGridInterpolator((kg,pg),values[t+1],method="cubic",
                                         bounds_error=False,fill_value=None)
        inflation = env.gross_inflation[t+1] if t+1<len(env.demand) else 1.
        def objective(k,p,i):
            kn = (1-env.delta)*k+i
            return period_dividend(env,t,k,p,i)+env.sdf[t]*float(future((kn,p/inflation)))
        for a,k in enumerate(kg):
            low = max(0.,kg[0]-(1-env.delta)*k)
            high = max(low+1e-8,kg[-1]-(1-env.delta)*k)
            for b,old in enumerate(pg):
                keep_opt = minimize_scalar(lambda i:-objective(k,old,i),bounds=(low,high),
                                           method="bounded",options={"xatol":1e-11})
                reset_opt = minimize(lambda x:-objective(k,np.exp(x[0]),x[1]),
                     x0=[np.log(old),np.clip(env.delta*k,low,high)],
                     bounds=[(np.log(pg[0]),np.log(pg[-1])),(low,high)],
                     method="Powell",options={"xtol":1e-9,"ftol":1e-10,"maxiter":1000})
                if not reset_opt.success:
                    raise RuntimeError(f"Оптимизация фирмы не сошлась: t={t}, k={k}, p={old}")
                keep[t][a,b] = keep_opt.x
                reset_i[t][a,b] = reset_opt.x[1]
                reset_p[t][a,b] = np.exp(reset_opt.x[0])
                values[t][a,b] = -env.theta*keep_opt.fun-(1-env.theta)*reset_opt.fun
    return FirmSolution(values,keep,reset_i,reset_p,kg,pg,env)

def policy_residuals(s, t, a, b, step=1e-5):
    """Центральные разности исходной целевой функции в выбранном внутреннем узле."""
    e=s.environment
    k=s.capital_grid[a]
    old=s.price_grid[b]
    future=RegularGridInterpolator((s.capital_grid,s.price_grid),s.values[t+1],
                                   method="cubic",bounds_error=False,fill_value=None)
    inflation=e.gross_inflation[t+1] if t+1<len(e.demand) else 1.
    def payoff(lp,i):
        rp=np.exp(lp)
        kn=(1-e.delta)*k+i
        return period_dividend(e,t,k,rp,i)+e.sdf[t]*float(future((kn,rp/inflation)))
    ip=s.reset_investment[t][a,b]
    rp=s.reset_price[t][a,b]
    ik=s.keep_investment[t][a,b]
    return {
      "reset_investment":float((payoff(np.log(rp),ip+step)-payoff(np.log(rp),ip-step))/(2*step)),
      "reset_price":float((payoff(np.log(rp)+step,ip)-payoff(np.log(rp)-step,ip))/(2*step)),
      "keep_investment":float((payoff(np.log(old),ik+step)-payoff(np.log(old),ik-step))/(2*step))}

def propagate_distribution(s, t, capital, price, mass):
    """Ветвление меры без проецирования новых состояний на сетку."""
    e=s.environment
    k=np.asarray(capital,dtype=float)
    p=np.asarray(price,dtype=float)
    w=np.asarray(mass,dtype=float)
    if k.shape!=p.shape or p.shape!=w.shape or np.any(w<0):
        raise ValueError("Неверное распределение.")
    coords=np.column_stack([k,p])
    def interp(mat):
        return RegularGridInterpolator((s.capital_grid,s.price_grid),mat,
                                       bounds_error=False,fill_value=None)(coords)
    ik=interp(s.keep_investment[t])
    ir=interp(s.reset_investment[t])
    pr=interp(s.reset_price[t])
    chosen_p=np.concatenate([p,pr])
    chosen_i=np.concatenate([ik,ir])
    chosen_k=np.concatenate([k,k])
    masses=np.concatenate([e.theta*w,(1-e.theta)*w])
    y=e.demand[t]*chosen_p**(-e.epsilon)
    labor=(y/(e.productivity[t]*chosen_k**e.alpha))**(1/(1-e.alpha))
    adjustment=.5*e.adjustment*chosen_k*(chosen_i/chosen_k-e.delta)**2
    next_k=(1-e.delta)*chosen_k+chosen_i
    inflation=e.gross_inflation[t+1] if t+1<len(e.demand) else 1.
    checks={
      "mass":float(masses.sum()),
      "capital":float(masses@chosen_k),
      "capital_next":float(masses@next_k),
      "investment":float(masses@chosen_i),
      "adjustment_cost":float(masses@adjustment),
      "employment":float(masses@labor),
      "intermediate_output":float(masses@y),
      "final_demand":float(e.demand[t]),
      "price_index_identity":float(masses@(chosen_p**(1-e.epsilon))),
      "dividends":float(masses@(chosen_p*y-e.real_wage[t]*labor-chosen_i-adjustment)),
      "implied_consumption":float(e.demand[t]-masses@(chosen_i+adjustment))}
    return next_k,chosen_p/inflation,masses,checks
