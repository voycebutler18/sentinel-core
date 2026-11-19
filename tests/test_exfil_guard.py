import unittest
from sentinel_trace.exfil_guard import EgressGuard

class TestEgressGuard(unittest.TestCase):
    def test_threshold(self):
        g=EgressGuard(threshold_bytes=5_000_000)
        self.assertFalse(g.evaluate('a',4_000_000,1,True).blocked)
        self.assertTrue(g.evaluate('a',1_000_000,2,True).blocked)
    def test_window_and_isolation(self):
        g=EgressGuard(threshold_bytes=10,window_seconds=5)
        g.evaluate('a',9,1,True)
        self.assertFalse(g.evaluate('b',2,2,True).blocked)
        self.assertFalse(g.evaluate('a',2,7,True).blocked)
    def test_validation(self):
        g=EgressGuard()
        for args in [('a',-1,1,True),('a',True,1,True),('',2,1,True),('a',2,1,False)]:
            with self.assertRaises(ValueError):g.evaluate(*args)
    def test_stress(self):
        g=EgressGuard(threshold_bytes=10000,window_seconds=100)
        for i in range(10000):
            result=g.evaluate('agent-'+str(i%50),1,float(i//50),True)
        self.assertFalse(result.blocked)

if __name__=='__main__':unittest.main()
