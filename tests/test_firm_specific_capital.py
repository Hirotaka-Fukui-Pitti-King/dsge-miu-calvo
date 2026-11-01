"""Проверки агрегированного решения и относительной оптимизации фирм."""
import unittest
import numpy as np
from src.model import Parameters
from src.firm_specific_capital import (
    woodford_coefficients,solve,irf,_current,_capital_euler,_q)
from src.stage2_foundations import (
    firm_labor, firm_marginal_cost, firm_capital_shadow,
    investment_cost, investment_cost_i, investment_cost_k)


class FirmSpecificFirstOrderTest(unittest.TestCase):
    def setUp(self):
        self.p=Parameters()
        self.adjustment=4.0

    def test_woodford_quartic_and_firm_conditions(self):
        p=self.p;c=woodford_coefficients(p,4)
        self.assertLess(c.polynomial_residual,1e-11)
        self.assertLess(c.investment_residual,1e-11)
        self.assertLess(c.reset_residual,1e-11)
        self.assertGreater(c.reset_capital,0)
        self.assertTrue(all(abs(z)<1 for z in c.relative_roots))
        self.assertLess(c.phillips_slope,(1-p.theta)*(1-p.beta*p.theta)/p.theta)
        self.assertGreater(c.phillips_slope,0)

    def test_firm_labor_cost_shadow_derivatives(self):
        p=self.p
        y,k,a,w=1.2,3.1,1.04,.83
        h=1e-5
        cost=lambda y,k:w*firm_labor(y,k,a,p.alpha)
        mc_num=(cost(y+h,k)-cost(y-h,k))/(2*h)
        shadow_num=-(cost(y,k+h)-cost(y,k-h))/(2*h)
        self.assertAlmostEqual(mc_num,firm_marginal_cost(y,k,a,w,p.alpha),delta=1e-9)
        self.assertAlmostEqual(shadow_num,firm_capital_shadow(y,k,a,w,p.alpha),delta=1e-9)
        cost_adj=lambda inv,cap:investment_cost(inv,cap,p.delta,4)
        inv=.095
        self.assertAlmostEqual((cost_adj(inv+h,k)-cost_adj(inv-h,k))/(2*h),investment_cost_i(inv,k,p.delta,4),delta=1e-9)
        self.assertAlmostEqual((cost_adj(inv,k+h)-cost_adj(inv,k-h))/(2*h),investment_cost_k(inv,k,p.delta,4),delta=1e-9)

    def test_bk_rank_and_expectation_invariance(self):
        for regime in ('calvo','flex'):
            for capital in ('common','specific'):
                s=solve(self.p,regime,capital,4)
                self.assertLess(s['bk_residual'],1e-10)
                self.assertEqual(sum(abs(s['eigenvalues'])>1),len(s['matrix'])-3)
                self.assertLess(max(abs(np.linalg.eigvals(s['transition']))),1)

    def test_flexible_equivalence_with_matched_adjustment_costs(self):
        a=solve(self.p,'flex','common',4)
        b=solve(self.p,'flex','specific',4)
        self.assertLess(abs(a['policy']-b['policy']).max(),1e-12)
        for shock in ('technology','monetary'):
            x=irf(self.p,'flex','common',shock)
            z=irf(self.p,'flex','specific',shock)
            self.assertLess(max(abs(x[t]['output']-z[t]['output']) for t in range(41)),1e-12)

    def test_monetary_neutrality_flexible(self):
        for capital in ('common','specific'):
            rows=irf(self.p,'flex',capital,'monetary')
            self.assertLess(max(abs(r['output']) for r in rows),1e-12)
            self.assertLess(max(abs(r['investment']) for r in rows),1e-12)

    def test_forward_equations_original_capital_foc(self):
        p=self.p;cost=4
        for capital in ('common','specific'):
            for regime in ('calvo','flex'):
                sol=solve(p,regime,capital,cost)
                H=sol['policy'];T=sol['transition']
                for ind in range(3):
                    x=np.eye(3)[ind]*.001
                    z=np.r_[x,H@x]
                    zf=np.r_[T@x,H@(T@x)]
                    k,a,v,c,pi=z[:5]
                    n=z[5] if regime=='calvo' else (a+p.alpha*k-p.sigma*c)/(p.varphi+p.alpha)
                    y,mc,i_hat=_current(k,a,c,n,p)
                    kn=(1-p.delta)*k+p.delta*i_hat
                    self.assertAlmostEqual(kn,zf[0],delta=3e-12)
                    cp=zf[3];an=zf[1]
                    nn=zf[5] if regime=='calvo' else (an+p.alpha*kn-p.sigma*cp)/(p.varphi+p.alpha)
                    self.assertAlmostEqual(_capital_euler(kn,an,c,cp,nn,_q(k,i_hat,p,cost),p,cost),0,delta=1e-11)
                    self.assertAlmostEqual(p.sigma*(cp-c),p.phi_pi*pi+p.phi_y*y+v-zf[4],delta=1e-11)
                    if regime=='calvo':
                        slope=woodford_coefficients(p,cost).phillips_slope if capital=='specific' else (1-p.theta)*(1-p.beta*p.theta)/p.theta
                        self.assertAlmostEqual(pi,p.beta*zf[4]+slope*mc,delta=1e-11)
                    else:self.assertAlmostEqual(mc,0,delta=1e-11)

    def test_all_irfs_finite_and_decay(self):
        for cap in ('common','specific'):
            for regime in ('calvo','flex'):
                for shock in ('technology','monetary'):
                    rows=irf(self.p,regime,cap,shock,horizon=400)
                    self.assertTrue(all(np.isfinite(v) for r in rows for v in r.values()))
                    self.assertLess(abs(rows[-1]['output']),1e-6)

    def test_adjustment_changes_predictions(self):
        vals=[]
        for adj in (2.,4.,10.):
            c=woodford_coefficients(self.p,adj)
            s=solve(self.p,'calvo','specific',adj)
            vals.append(c.phillips_slope)
            self.assertLess(s['bk_residual'],1e-10)
        self.assertGreater(max(vals)-min(vals),1e-5)

if __name__=='__main__': unittest.main()
