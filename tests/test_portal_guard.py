import hashlib
import unittest
from sentinel_trace.portal_guard import LoginAttempt,evaluate_login
CODE='example-random-high-entropy-test-only'
BASE=dict(company_id='company1',submitted_code=CODE,expected_code_digest=hashlib.sha256(CODE.encode()).hexdigest(),verified_device=True,verified_passkey=True,active_company=True,attempts_last_5min=0)
class PortalTests(unittest.TestCase):
 def test_valid(self):self.assertEqual(evaluate_login(LoginAttempt(**BASE)).action,'ALLOW')
 def test_wrong_code(self):self.assertEqual(evaluate_login(LoginAttempt(**(BASE|{'submitted_code':'wrong'}))).action,'DENY')
 def test_stolen_code(self):self.assertEqual(evaluate_login(LoginAttempt(**(BASE|{'verified_passkey':False}))).action,'STEP_UP')
 def test_unknown_device(self):self.assertEqual(evaluate_login(LoginAttempt(**(BASE|{'verified_device':False}))).action,'STEP_UP')
 def test_rate_limit(self):self.assertEqual(evaluate_login(LoginAttempt(**(BASE|{'attempts_last_5min':5}))).action,'DENY')
 def test_decoy(self):self.assertEqual(evaluate_login(LoginAttempt(**(BASE|{'decoy_endpoint_touched':True}))).reason,'decoy-interaction')
 def test_inactive(self):self.assertEqual(evaluate_login(LoginAttempt(**(BASE|{'active_company':False}))).action,'DENY')
 def test_stress(self):
  for _ in range(20000):self.assertEqual(evaluate_login(LoginAttempt(**BASE)).action,'ALLOW')
if __name__=='__main__':unittest.main()
