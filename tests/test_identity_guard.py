import unittest
from sentinel_trace.identity_guard import IdentityTransferGuard

BASE=dict(tenant='a',user='ceo',device='managed',bytes_out=1,timestamp=1,
          authenticated=True,phishing_resistant_mfa=True,device_compliant=True,
          destination_approved=True,data_approved=True)
class Tests(unittest.TestCase):
    def setUp(self): self.g=IdentityTransferGuard(normal_limit=5, elevated_limit=10)
    def test_ceo_is_not_automatic_bypass(self):
        self.assertEqual(self.g.evaluate(**(BASE|{'authenticated':False})).action,'deny')
    def test_approved_transfer(self):
        self.assertEqual(self.g.evaluate(**BASE).action,'allow')
    def test_small_chunk_accumulation(self):
        for t in range(1,5): self.assertEqual(self.g.evaluate(**(BASE|{'timestamp':t})).action,'allow')
        self.assertEqual(self.g.evaluate(**(BASE|{'timestamp':5})).action,'step_up')
    def test_grant_not_unlimited(self):
        self.assertEqual(self.g.evaluate(**(BASE|{'bytes_out':6,'explicit_grant':True})).action,'allow')
        self.assertEqual(self.g.evaluate(**(BASE|{'timestamp':2,'bytes_out':4,'explicit_grant':True})).action,'step_up')
    def test_destination_denied(self):
        self.assertEqual(self.g.evaluate(**(BASE|{'destination_approved':False})).action,'deny')
    def test_anomaly(self):
        self.assertEqual(self.g.evaluate(**(BASE|{'unusual_session':True})).action,'step_up')
    def test_tenant_isolation(self):
        self.g.evaluate(**(BASE|{'bytes_out':4}))
        self.assertEqual(self.g.evaluate(**(BASE|{'tenant':'b','bytes_out':2})).action,'allow')
    def test_window_expiry(self):
        g=IdentityTransferGuard(window_seconds=2,normal_limit=5,elevated_limit=10)
        g.evaluate(**(BASE|{'bytes_out':4}))
        self.assertEqual(g.evaluate(**(BASE|{'timestamp':4,'bytes_out':2})).action,'allow')
    def test_stress(self):
        g=IdentityTransferGuard(normal_limit=1000000,elevated_limit=2000000)
        for i in range(20000):
            r=g.evaluate(**(BASE|{'user':f'u{i%100}', 'timestamp':i//100+1}))
        self.assertEqual(r.action,'allow')
if __name__=='__main__':unittest.main()
