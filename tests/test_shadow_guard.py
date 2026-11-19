import unittest
from sentinel_trace.shadow_guard import SessionSignal, assess

BASE = dict(account_id='ceo',session_id='s1',device_id='d1',device_bound=True,verified_device=True,authenticated=True,privileged_action=True,active_session_ids=frozenset({'s1'}))
class Tests(unittest.TestCase):
 def test_legitimate(self): self.assertEqual(assess(SessionSignal(**BASE)).action,'allow')
 def test_shared_ip_not_proof(self): self.assertEqual(assess(SessionSignal(**(BASE|{'source_ip_changed':True}))).action,'allow')
 def test_stolen_session_unbound(self): self.assertEqual(assess(SessionSignal(**(BASE|{'device_bound':False}))).action,'deny')
 def test_new_device(self): self.assertEqual(assess(SessionSignal(**(BASE|{'new_device':True}))).action,'step_up')
 def test_concurrent(self): self.assertEqual(assess(SessionSignal(**(BASE|{'active_session_ids':frozenset({'s1','s2'})}))).action,'step_up')
 def test_anomaly(self): self.assertTrue(assess(SessionSignal(**(BASE|{'anomalous_behavior':True}))).notify_owner)
 def test_missing_identity(self):
  with self.assertRaises(ValueError): assess(SessionSignal(**(BASE|{'session_id':''})))
 def test_stress(self):
  for i in range(50000):
   s=SessionSignal(**(BASE|{'session_id':f's{i}','active_session_ids':frozenset({f's{i}'})}))
   self.assertEqual(assess(s).action,'allow')
if __name__=='__main__': unittest.main()
