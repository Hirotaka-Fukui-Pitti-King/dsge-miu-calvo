"""Проверки условной задачи фирмы; не проверки общего равновесия."""
import unittest
import numpy as np
from src.firm_dynamic import FirmEnvironment, solve_firm, policy_residuals, propagate_distribution

class ConditionalFirmTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.env = FirmEnvironment((1.,1.),(1.,1.),(.64,.64),(1.,1.),(.99,.99))
        cls.s = solve_firm(cls.env,np.linspace(2.,6.,5),np.linspace(.7,1.3,7))

    def test_interior_first_order_conditions(self):
        for t in (0,1):
            residuals=policy_residuals(self.s,t,2,3)
            self.assertLess(max(abs(v) for v in residuals.values()),1e-5)

    def test_calvo_distribution_and_accounting(self):
        k,p,m,a=propagate_distribution(self.s,0,np.array([4.]),np.array([1.]),np.array([1.]))
        np.testing.assert_allclose(m,[.75,.25])
        self.assertAlmostEqual(a["mass"],1.)
        self.assertAlmostEqual(a["capital_next"],.975*a["capital"]+a["investment"])
        self.assertAlmostEqual(a["final_demand"],a["implied_consumption"]+a["investment"]+a["adjustment_cost"])
        # Экзогенные траектории НЕ удовлетворяют ценовому индексу общего равновесия.
        self.assertGreater(abs(a["price_index_identity"]-1.),.01)
        self.assertGreater(abs(k[0]-k[1]),1e-5)
        self.assertGreater(abs(p[0]-p[1]),1e-5)

    def test_reset_is_independent_of_previous_price_given_capital(self):
        self.assertAlmostEqual(self.s.reset_price[0][2,1],self.s.reset_price[0][2,5],delta=1e-5)
        self.assertAlmostEqual(self.s.reset_investment[0][2,1],self.s.reset_investment[0][2,5],delta=1e-5)

if __name__=="__main__":
    unittest.main()
