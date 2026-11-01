"""Проверка условных ожиданий, премий и благосостояния во втором порядке.

Выполняется независимая гауссова квадратура по исходным нелинейным уравнениям,
а не только по коэффициентам разложения. Отчёт фиксирует ошибки приближения.
"""
from __future__ import annotations
from dataclasses import dataclass
import json
from pathlib import Path
import numpy as np
import torch
from scipy.special import roots_hermitenorm
from scipy.linalg import solve_discrete_lyapunov
from src.model import Parameters
from src.second_order import NX, NZ, DT, _primitives, _states, residual, solve_second_order, SecondOrderSolution


def _full(x, sol: SecondOrderSolution, scale=1.0):
    yy = sol.policy(np.asarray(x,float),scale)
    return np.concatenate((x,yy))


def quadrature(sol: SecondOrderSolution, x=None, scale=1., order=7):
    """Условные исходные уравнения, дисконтер и доходность капитала."""
    x = np.zeros(NX) if x is None else np.asarray(x,float)
    z=_full(x,sol,scale)
    z_t=torch.tensor(z,dtype=DT)
    m=_primitives(z_t,sol.p)
    xprime=_states(z_t,sol.p).detach().numpy()
    w=np.zeros((NX,2));w[1,0]=sol.volatility[0];w[2,1]=sol.volatility[1]
    nodes,weights=roots_hermitenorm(order)
    weights/=np.sqrt(2*np.pi)
    eq=np.zeros(NZ); em=0.;er=0.; emr=0.; var_r=0.
    for ia,a in enumerate(nodes):
        for iv,b in enumerate(nodes):
            prob=weights[ia]*weights[iv]
            xp=xprime+scale*w@np.array([a,b])
            zp=torch.tensor(_full(xp,sol,scale),dtype=DT)
            f=_primitives(zp,sol.p)
            s=(sol.p.beta*(f['C']/m['C'])**(-sol.p.sigma)).item()
            r=(f['rk']+1-sol.p.delta).item()
            em+=prob*s;er+=prob*r;emr+=prob*s*r
            eq+=prob*residual(z_t,zp,sol.p).detach().numpy()
    rate=1/em
    covariance=-(emr-em*er)/em
    return {'max_equilibrium_residual':float(abs(eq).max()),
            'capital_euler_residual':float(eq[4]),'bond_euler_residual':float(eq[5]),
            'price_F_residual':float(eq[6]),'price_G_residual':float(eq[7]),
            'risk_free':float(rate),'expected_capital':float(er),
            'risk_premium':float(er-rate),'covariance_premium':float(covariance),
            'asset_pricing_residual':float(emr-1),
            'covariance_identity_error':float((er-rate)-covariance-(emr-1)/em)}


def utility(z, p):
    """Полная аддитивная полезность, включая эндогенный спрос на деньги."""
    m=_primitives(z,p)
    c=m['C'];n=m['N']; gross=m['gross']
    nominal=gross-1
    money=(p.chi_m*c**p.sigma*gross/nominal)**(1/p.eta_m)
    if abs(p.sigma-1)<1e-12: cu=torch.log(c)
    else: cu=(c**(1-p.sigma)-1)/(1-p.sigma)
    if abs(p.eta_m-1)<1e-12: mu=p.chi_m*torch.log(money)
    else: mu=p.chi_m*(money**(1-p.eta_m)-1)/(1-p.eta_m)
    return cu + mu - p.chi_n*n**(1+p.varphi)/(1+p.varphi)


def welfare(sol: SecondOrderSolution):
    """Второпорядковая рекурсия ожидаемой полезности и стационарных моментов."""
    p=sol.p
    h=sol.h
    h2=sol.h2
    z0=torch.zeros(NZ,dtype=DT,requires_grad=True)
    u0=utility(z0,p).item()
    uz=torch.autograd.functional.jacobian(lambda z: utility(z,p),z0).detach().numpy()
    uzz=torch.autograd.functional.hessian(lambda z: utility(z,p),z0).detach().numpy()
    z1=np.vstack((np.eye(NX),h))
    g=uz@z1
    hess=z1.T@uzz@z1+np.einsum('i,ijk->jk',uz[NX:],h2)
    vterm=uz[NX:]@sol.hvv
    # Квадратичный Беллман для условной полезности.
    w1=np.linalg.solve(np.eye(NX)-p.beta*sol.t.T,g)
    w2=solve_discrete_lyapunov(np.sqrt(p.beta)*sol.t.T,
        hess + p.beta*np.einsum('i,ijk->jk',w1,sol.t2))
    w=np.zeros((NX,2));w[1,0]=sol.volatility[0];w[2,1]=sol.volatility[1]
    ww=w@w.T
    wvv=(vterm+p.beta*(w1@sol.tvv+np.sum(w2*ww)))/(1-p.beta)
    u_mean_cov=solve_discrete_lyapunov(sol.t,ww)
    mdrift=.5*np.einsum('ijk,jk->i',sol.t2,u_mean_cov)+.5*sol.tvv
    mean=np.linalg.solve(np.eye(NX)-sol.t,mdrift)
    conditional=u0/(1-p.beta)+.5*wvv
    unconditional=conditional + w1@mean + .5*np.sum(w2*u_mean_cov)
    mpolicy=sol.h@mean+.5*np.einsum('ijk,jk->i',sol.h2,u_mean_cov)+.5*sol.hvv
    return {'conditional_welfare':float(conditional),'unconditional_welfare':float(unconditional),
            'mean_states':mean,'cov_states':u_mean_cov,'mean_jump':mpolicy,
            'welfare_linear':w1,'welfare_quadratic':w2,
            'average_utility':float((1-p.beta)*unconditional),
            'steady_utility':float(u0),
            'expected_money_log_deviation':None}


def cev(sol_a:SecondOrderSolution, sol_b:SecondOrderSolution,criterion='conditional'):
    """Эквивалент вариации потребления от экономии B к A (меняется только C)."""
    if (sol_a.p.beta,sol_a.p.sigma,sol_a.p.eta_m,sol_a.p.chi_m,sol_a.p.chi_n,sol_a.p.varphi) != (sol_b.p.beta,sol_b.p.sigma,sol_b.p.eta_m,sol_b.p.chi_m,sol_b.p.chi_n,sol_b.p.varphi):
        raise ValueError('CEV требует одинаковых предпочтений и параметров.')
    key={'conditional':'conditional_welfare','unconditional':'unconditional_welfare'}[criterion]
    wa=welfare(sol_a)[key]; wb=welfare(sol_b)[key]
    p=sol_b.p
    # В данном базовом случае sigma=1: постоянная прибавка log(1+omega)/(1-beta).
    if p.sigma==1:
        return float(np.expm1((1-p.beta)*(wa-wb)))
    # Для иной кривизны необходим ожидаемый дисконтированный уровень C^{1-sigma}.
    raise NotImplementedError('Для sigma != 1 требуется отдельная производная функции CEV.')


def pruned_simulation(sol:SecondOrderSolution,n_periods=40000,burn_in=4000,seed=127):
    """Прунинг по разделению линейного состояния и компоненты второго порядка."""
    rng=np.random.default_rng(seed)
    xfirst=np.zeros(NX);xsecond=np.zeros(NX)
    w=np.zeros((NX,2));w[1,0]=sol.volatility[0];w[2,1]=sol.volatility[1]
    records=[]
    for t in range(n_periods+burn_in):
        yy=sol.h@(xfirst+xsecond)+.5*np.einsum('ijk,j,k->i',sol.h2,xfirst,xfirst)+.5*sol.hvv
        if t>=burn_in:records.append((xfirst+xsecond).copy())
        eps=rng.standard_normal(2)
        next_second=sol.t@xsecond+.5*np.einsum('ijk,j,k->i',sol.t2,xfirst,xfirst)+.5*sol.tvv
        next_first=sol.t@xfirst+w@eps
        xfirst,xsecond=next_first,next_second
        if not np.all(np.isfinite(xfirst+xsecond)):
            raise FloatingPointError('Нестабильная траектория прунинга.')
    sample=np.array(records)
    return {'sample_mean':sample.mean(axis=0),'sample_cov':np.cov(sample.T),
            'sample_size':n_periods,'seed':seed}


def write_results(root:Path):
    """Сохранить результаты в машинно-читаемой форме, без неподтверждённых утверждений."""
    root=Path(root); (root/'results').mkdir(exist_ok=True)
    from dataclasses import replace
    vols=(0.001,0.00025)
    sols={name:solve_second_order(p,volatility=vols) for name,p in [('flex',Parameters(theta=0)),('calvo',Parameters())]}
    summary={}
    for name,sol in sols.items():
        q=quadrature(sol)
        qsmall=quadrature(sol,scale=.5)
        w=welfare(sol)
        summary[name]={'steady_eigenvalues':[[float(np.real(v)),float(np.imag(v))] for v in sol.eigenvalues if np.isfinite(v)],
                       'first_order_residual':sol.jacobian_residual,
                       'second_order_coefficient_residual':sol.quadratic_residual,
                       'volatility_coefficient_residual':sol.volatility_residual,
                       'stochastic_equilibrium':q,'half_volatility':qsmall,
                       'conditional_welfare':w['conditional_welfare'],
                       'unconditional_welfare':w['unconditional_welfare'],
                       'mean_states':w['mean_states'].tolist(),
                       'mean_jump':w['mean_jump'].tolist()}
    summary['shock_standard_deviations']={'technology':vols[0],'monetary':vols[1]}
    summary['cev_calvo_relative_flex']={crit:cev(sols['calvo'],sols['flex'],crit) for crit in ['conditional','unconditional']}
    summary['legacy_volatility_stress_test']={name:quadrature(solve_second_order(sol.p,volatility=(.01,.0025))) for name,sol in sols.items()}
    (root/'results/stage2_common_second_order.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8')
    return summary

if __name__=='__main__':
    data=write_results(Path(__file__).resolve().parents[1]);print(json.dumps(data,ensure_ascii=False,indent=2))
