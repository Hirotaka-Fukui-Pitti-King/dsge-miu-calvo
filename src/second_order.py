"""Нелинейные условия и локальное решение второго порядка для общего рынка капитала.

Состояния: логарифмы K, A, отклонение ставки правила, логарифм предыдущей дисперсии.
Переменные выбора: логарифмы C, N, нормированных F и G; лог инфляции.
Состояние дисперсии учитывается даже тогда, когда оно второго порядка при обычных шоках.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
import torch
from scipy.linalg import ordqz
from src.model import Parameters

DT = torch.float64
NX = 4
NY = 5
NZ = NX + NY

def _const(v: float, reference: torch.Tensor) -> torch.Tensor:
    return reference.new_tensor(v)


def _primitives(z: torch.Tensor, p: Parameters):
    s = p.steady_state()
    k, a, v, d, c, pi, n, f, g = z.unbind()
    K = _const(s['k'], k) * torch.exp(k)
    C = _const(s['c'], k) * torch.exp(c)
    N = _const(s['n'], k) * torch.exp(n)
    mu = p.epsilon/(p.epsilon-1)
    lamb = C**(-p.sigma)
    Fbar = (s['c']**(-p.sigma)*s['mc']*s['y'])/(1-p.beta*p.theta)
    Gbar = (s['c']**(-p.sigma)*s['y'])/(1-p.beta*p.theta)
    F = _const(Fbar,k)*torch.exp(f)
    G = _const(Gbar,k)*torch.exp(g)
    reset = _const(mu,k)*F/G
    disp = (1-p.theta)*reset**(-p.epsilon) + p.theta*torch.exp(p.epsilon*pi+d)
    Y = torch.exp(a)*K**p.alpha*N**(1-p.alpha)/disp
    w = p.chi_n*N**p.varphi * C**p.sigma
    mc = w*N/((1-p.alpha)*Y*disp)
    rk = p.alpha*mc*Y*disp/K
    gross = _const(1/p.beta,k)*torch.exp(p.phi_pi*pi + p.phi_y*torch.log(Y/s['y']) + v)
    return {'K':K,'C':C,'N':N,'F':F,'G':G,'lamb':lamb,'Y':Y,'mc':mc,'rk':rk,
            'gross':gross,'pi':pi,'reset':reset,'disp':disp, 'w':w}


def _states(z: torch.Tensor, p: Parameters) -> torch.Tensor:
    m = _primitives(z,p)
    s = p.steady_state()
    new_k = torch.log(((1-p.delta)*m['K'] + m['Y']-m['C'])/s['k'])
    return torch.stack((new_k, p.rho_a*z[1], p.rho_v*z[2], torch.log(m['disp'])))


def residual(z: torch.Tensor, future: torch.Tensor, p: Parameters) -> torch.Tensor:
    m = _primitives(z,p)
    q = _primitives(future,p)
    s = p.steady_state()
    S = _states(z,p)
    sdf = p.beta*(q['C']/m['C'])**(-p.sigma)
    fbar = s['c']**(-p.sigma)*s['mc']*s['y']/(1-p.beta*p.theta)
    gbar = s['c']**(-p.sigma)*s['y']/(1-p.beta*p.theta)
    eq = list(future[:NX] - S)
    eq += [1-sdf*(q['rk']+1-p.delta),
           1-sdf*m['gross']/torch.exp(future[5]),
           (m['F']-m['lamb']*m['mc']*m['Y']-p.beta*p.theta*torch.exp(p.epsilon*future[5])*q['F'])/fbar,
           (m['G']-m['lamb']*m['Y']-p.beta*p.theta*torch.exp((p.epsilon-1)*future[5])*q['G'])/gbar,
           1-(1-p.theta)*m['reset']**(1-p.epsilon)-p.theta*torch.exp((p.epsilon-1)*z[5])]
    return torch.stack(eq)


def _derivatives(p: Parameters):
    zero = torch.zeros(2*NZ,dtype=DT,requires_grad=True)
    def r(v): return residual(v[:NZ],v[NZ:],p)
    jac = torch.autograd.functional.jacobian(r,zero).detach().numpy()
    hs=[]
    for i in range(NZ):
        hs.append(torch.autograd.functional.hessian(lambda v: r(v)[i],zero).detach().numpy())
    return jac[:,:NZ],jac[:,NZ:],np.array(hs)


def _state_derivatives(p: Parameters):
    zero = torch.zeros(NZ,dtype=DT,requires_grad=True)
    jac=torch.autograd.functional.jacobian(lambda v:_states(v,p),zero).detach().numpy()
    hess=np.array([torch.autograd.functional.hessian(lambda v:_states(v,p)[i],zero).detach().numpy() for i in range(NX)])
    return jac,hess


@dataclass
class SecondOrderSolution:
    """Коэффициенты правила выбора y=Hx+H2[x,x]/2+Hvv*scale²/2."""
    p: Parameters
    h: np.ndarray
    t: np.ndarray
    h2: np.ndarray
    t2: np.ndarray
    hvv: np.ndarray
    tvv: np.ndarray
    eigenvalues: np.ndarray
    jacobian_residual: float
    quadratic_residual: float
    volatility_residual: float
    volatility: tuple[float,float]

    def policy(self, x: np.ndarray, scale:float=1.0):
        return self.h@x + 0.5*np.einsum('ijk,j,k->i',self.h2,x,x) + .5*self.hvv*scale**2

    def next_state(self,x:np.ndarray,scale:float=1.0):
        return self.t@x+.5*np.einsum('ijk,j,k->i',self.t2,x,x)+.5*self.tvv*scale**2


def solve_second_order(p: Parameters|None=None,volatility=(0.001,0.00025)) -> SecondOrderSolution:
    """Решить уравнения коэффициентов второй производной, включая риск-коррекцию."""
    p=p or Parameters()
    if not 0 <= p.theta < 1:
        raise ValueError('Необходимы 0 ≤ theta < 1.')
    jc,jf,hess=_derivatives(p)
    sj,sh=_state_derivatives(p)
    aa=-jc
    bb=jf
    so,to,alpha,beta,Q,Z=ordqz(aa,bb,sort='iuc')
    roots=np.array([a/b if abs(b)>1e-12 else np.inf for a,b in zip(alpha,beta)],dtype=complex)
    if np.count_nonzero(np.abs(roots)<1-1e-8)!=NX:
        raise ValueError(f'Число устойчивых корней: {roots}')
    zx=Z[:NX,:NX]
    if np.linalg.matrix_rank(zx)<NX:
        raise ValueError('Не выполнено ранговое условие.')
    h=np.real_if_close(Z[NX:,:NX]@np.linalg.inv(zx)).real
    z1=np.vstack((np.eye(NX),h))
    t=sj@z1
    lhs=jc@z1+jf@z1@t
    err=float(np.max(np.abs(lhs)))
    if err>1e-7:raise ValueError(f'Ошибка первой производной: {err}')
    # Неизвестные: NY симметричных гессианов размерности NX × NX.
    ij=[(i,j) for i in range(NX) for j in range(i,NX)]
    index={(b,i,j):b*len(ij)+k for b in range(NY) for k,(i,j) in enumerate(ij)}
    nh=NY*len(ij)
    st_h=np.einsum('kij,ia,jb->kab',sh,z1,z1)
    hx=h@t
    znext1=np.vstack((t,hx))
    def source(i,j):
        vi=np.concatenate((z1[:,i],znext1[:,i]))
        vj=np.concatenate((z1[:,j],znext1[:,j]))
        return np.einsum('kij,i,j->k',hess,vi,vj)

    def residual_operator(coef,ijpair,force):
        i,j=ijpair
        # coef shape NY,NX,NX, сглаженное по симметричным индексам.
        cur2=coef[:,i,j]
        s2=sj[:,NX:]@cur2+st_h[:,i,j]
        fut2=np.concatenate((s2,h@s2+np.einsum('kij,i,j->k',coef,t[:,i],t[:,j])))
        curr2=np.concatenate((np.zeros(NX),cur2))
        return (jc@curr2+jf@fut2+source(i,j))[NX:]

    def make_coef(vec):
        val=np.zeros((NY,NX,NX))
        for b in range(NY):
            for i,j in ij:
                val[b,i,j]=val[b,j,i]=vec[index[(b,i,j)]]
        return val

    constant=np.array([residual_operator(np.zeros((NY,NX,NX)),tij,None) for tij in ij]).reshape(-1)
    mat=np.column_stack([(np.array([residual_operator(make_coef(np.eye(nh)[q]),tij,None) for tij in ij]).reshape(-1)-constant) for q in range(nh)])
    vec=np.linalg.solve(mat,-constant)
    h2=make_coef(vec)
    t2=np.einsum('ji,ikl->jkl',sj[:,NX:],h2)+st_h
    qerr=float(np.max(np.abs(mat@vec+constant)))
    # Константа второго порядка по общей амплитуде стохастических инноваций.
    w=np.zeros((NX,2));w[1,0]=volatility[0];w[2,1]=volatility[1]
    def stochastic_source():
        fromfuture=np.vstack((w,h@w))
        # Ожидание (1/2) H2[W ξ, W ξ] в будущем.
        h2noise=np.einsum('kij,ia,ja->k',h2,w,w)
        # Прямой стохастический член при фиксированном текущем состоянии.
        shockh=np.einsum('kij,ia,ja->k',hess[:,NZ:,NZ:],fromfuture,fromfuture)
        return jf[NX:,NX:]@h2noise+shockh[NX:]
    const=stochastic_source()
    # Эффект Hvv на будущие состояния плюс самостоятельный сдвиг Hvv на следующий период.
    lhsvol=jc[NX:,NX:]+jf[NX:,:NX]@sj[:,NX:]+jf[NX:,NX:]@(h@sj[:,NX:]+np.eye(NY))
    hvv=np.linalg.solve(lhsvol,-const)
    tvv=sj[:,NX:]@hvv
    verr=float(np.max(abs(lhsvol@hvv+const)))
    return SecondOrderSolution(p,h,t,h2,t2,hvv,tvv,roots,err,qerr,verr,tuple(volatility))

if __name__=='__main__':
    o=solve_second_order()
    np.set_printoptions(precision=8,suppress=True)
    print('Собственные значения:',o.eigenvalues)
    print('Разность Якобиана:',o.jacobian_residual)
    print('Остаток квадратичных коэффициентов:',o.quadratic_residual)
    print('Остаток поправки на неопределённость:',o.volatility_residual)
    print('Сдвиг второй производной:',o.hvv)
