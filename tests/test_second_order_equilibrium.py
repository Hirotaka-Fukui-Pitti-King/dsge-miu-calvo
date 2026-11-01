"""Тесты самостоятельного второго порядка исходной нелинейной модели."""
import unittest
import numpy as np
from dataclasses import replace
from src.model import Parameters,stable_solution,transition_matrix
from src.second_order import solve_second_order, _primitives, _states, residual, NZ
from src.stage2_equilibrium import welfare,cev,quadrature,pruned_simulation


class SecondOrderEquilibriumTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sols={name:solve_second_order(p) for name,p in [
            ('flex',Parameters(theta=0)),('calvo',Parameters())]}

    def test_recovery_first_order(self):
        for name,sol in self.sols.items():
            _,h,t=stable_solution(transition_matrix(sol.p,name))
            self.assertLess(abs(sol.h[:2,:3]-h[:2,:]).max(),1e-11)
            self.assertLess(abs(sol.t[:3,:3]-t).max(),1e-11)
            self.assertLess(sol.jacobian_residual,1e-11)

    def test_hessian_symmetry_and_solved_equations(self):
        for sol in self.sols.values():
            self.assertLess(abs(sol.h2-np.transpose(sol.h2,(0,2,1))).max(),1e-12)
            self.assertLess(abs(sol.t2-np.transpose(sol.t2,(0,2,1))).max(),1e-12)
            self.assertLess(sol.quadratic_residual,1e-10)
            self.assertLess(sol.volatility_residual,1e-10)


    def test_independent_finite_difference_hessian(self):
        """Прямая центральная разность для квадратичных производных Кальво."""
        import torch
        p=self.sols['calvo'].p
        z=np.zeros(2*NZ)
        def f(v):
            zz=torch.tensor(v,dtype=torch.float64)
            return residual(zz[:NZ],zz[NZ:],p)[6].item()
        zt=torch.zeros(2*NZ,dtype=torch.float64)
        derived=torch.autograd.functional.hessian(
            lambda v:residual(v[:NZ],v[NZ:],p)[6],zt).detach().numpy()
        step=1e-4
        for i,j in ((5,5),(6,6),(NZ+5,NZ+5),(5,NZ+5)):
            ei=np.zeros(2*NZ);ej=np.zeros(2*NZ)
            ei[i]=step;ej[j]=step
            approx=(f(z+ei+ej)-f(z+ei-ej)-f(z-ei+ej)+f(z-ei-ej))/(4*step**2)
            self.assertAlmostEqual(derived[i,j],approx,delta=1e-5)

    def test_euler_and_calvo_quadrature_at_small_volatility(self):
        for name,sol in self.sols.items():
            r=quadrature(sol,order=8)
            self.assertLess(abs(r['asset_pricing_residual']),1e-10)
            self.assertLess(r['max_equilibrium_residual'],1e-8)
            self.assertLess(abs(r['covariance_identity_error']),2e-12)
            self.assertGreater(r['risk_premium'],0.)

    def test_residual_scaling_fourth_order_at_deterministic_state(self):
        for name,sol in self.sols.items():
            a=quadrature(sol,scale=1.,order=7)['max_equilibrium_residual']
            b=quadrature(sol,scale=.5,order=7)['max_equilibrium_residual']
            # Квадратура в x=0 симметрична; ведущая ошибка второго порядка имеет четвёртый порядок.
            self.assertLess(b,0.08*a+1e-12)

    def test_risk_premium_quadratic_scaling(self):
        for name,sol in self.sols.items():
            a=quadrature(sol,scale=1)['covariance_premium']
            b=quadrature(sol,scale=.5)['covariance_premium']
            self.assertLess(abs(b/a-.25),.02)

    def test_welfare_and_cev(self):
        a=welfare(self.sols['calvo']);b=welfare(self.sols['flex'])
        self.assertTrue(np.isfinite(a['conditional_welfare']))
        self.assertTrue(np.isfinite(b['conditional_welfare']))
        self.assertGreater(a['mean_states'][3],0.)
        self.assertAlmostEqual(b['mean_states'][3],0.,delta=1e-9)
        c=cev(self.sols['calvo'],self.sols['flex'],'conditional')
        d=cev(self.sols['calvo'],self.sols['flex'],'unconditional')
        self.assertLess(c,0)
        self.assertLess(d,0)

    def test_pruned_stationary_moments(self):
        for name,sol in self.sols.items():
            x=pruned_simulation(sol,n_periods=150000,burn_in=5000,seed=100)
            a=welfare(sol)
            self.assertLess(abs(x['sample_cov'][1,1]-a['cov_states'][1,1])/a['cov_states'][1,1],.08)
            self.assertLess(abs(x['sample_cov'][0,0]-a['cov_states'][0,0])/a['cov_states'][0,0],.12)

if __name__=='__main__': unittest.main()
