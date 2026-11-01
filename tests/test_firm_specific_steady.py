"""Проверка самостоятельного численного стационарного равновесия фирмы."""
import unittest
from src.model import Parameters
from src.firm_specific_steady import solve_symmetric_steady


class SymmetricFirmSteadyTest(unittest.TestCase):
    def test_nonlinear_equilibrium(self):
        p=Parameters()
        result=solve_symmetric_steady(p)
        analytical=p.steady_state()
        self.assertLess(result.maximum_residual,1e-10)
        for computed,key in (
            (result.consumption,'c'),(result.hours,'n'),(result.firm_capital,'k'),
            (result.output,'y'),(result.wage,'w'),(result.investment,'investment')):
            self.assertAlmostEqual(computed,analytical[key],delta=1e-9)
        self.assertGreater(result.firm_value,0)


if __name__=='__main__':
    unittest.main()
