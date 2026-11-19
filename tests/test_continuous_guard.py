import unittest
from sentinel_trace.continuous_guard import ContinuousGuard, TransferEvent
BASE=dict(tenant='company',principal='ceo',session='s1',timestamp=1,bytes_out=100,file_count=1,identity_verified=True,device_verified=True,destination_approved=True,data_approved=True)
class GuardTests(unittest.TestCase):
 def test_authorized(self):self.assertEqual(ContinuousGuard().evaluate(TransferEvent(**BASE)).action,'ALLOW')
 def test_stolen_session(self):self.assertEqual(ContinuousGuard().evaluate(TransferEvent(**(BASE|{'device_verified':False}))).action,'DENY')
 def test_bad_destination(self):self.assertEqual(ContinuousGuard().evaluate(TransferEvent(**(BASE|{'destination_approved':False}))).action,'DENY')
 def test_vendor_no_grant(self):self.assertEqual(ContinuousGuard().evaluate(TransferEvent(**(BASE|{'vendor_access':True}))).action,'DENY')
 def test_vendor_budget(self):self.assertEqual(ContinuousGuard(vendor_byte_limit=100).evaluate(TransferEvent(**(BASE|{'vendor_access':True,'vendor_grant_valid':True}))).action,'HOLD')
 def test_small_chunks_across_sessions(self):
  g=ContinuousGuard(byte_limit=500)
  for i in range(4):self.assertEqual(g.evaluate(TransferEvent(**(BASE|{'timestamp':i+1,'session':str(i)}))).action,'ALLOW')
  self.assertEqual(g.evaluate(TransferEvent(**(BASE|{'timestamp':5,'session':'new'}))).action,'HOLD')
 def test_many_small_files(self):
  g=ContinuousGuard(file_limit=5)
  for i in range(4):g.evaluate(TransferEvent(**(BASE|{'timestamp':i+1,'bytes_out':1})))
  self.assertEqual(g.evaluate(TransferEvent(**(BASE|{'timestamp':5,'bytes_out':1}))).action,'HOLD')
 def test_window_expires(self):
  g=ContinuousGuard(window_seconds=5,byte_limit=150);g.evaluate(TransferEvent(**BASE))
  self.assertEqual(g.evaluate(TransferEvent(**(BASE|{'timestamp':7}))).action,'ALLOW')
 def test_tenant_separation(self):
  g=ContinuousGuard(byte_limit=150);g.evaluate(TransferEvent(**BASE))
  self.assertEqual(g.evaluate(TransferEvent(**(BASE|{'tenant':'other'}))).action,'ALLOW')
 def test_out_of_order(self):
  g=ContinuousGuard();g.evaluate(TransferEvent(**(BASE|{'timestamp':3})))
  with self.assertRaises(ValueError):g.evaluate(TransferEvent(**BASE))
 def test_stress_50000(self):
  g=ContinuousGuard(byte_limit=10000000,file_limit=100000)
  for i in range(50000):result=g.evaluate(TransferEvent(**(BASE|{'principal':f'user{i%200}','timestamp':i//200+1})))
  self.assertEqual(result.action,'ALLOW')
if __name__=='__main__':unittest.main()
