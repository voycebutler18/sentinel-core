import unittest
from sentinel_trace.identity_seal import IdentityEvidence, decide

BASE=dict(account_id="ceo",session_id="session1",registered_key_id="key1",
          webauthn_verified=True,device_proof_verified=True,session_active=True,risk_score=5)
class TestIdentitySeal(unittest.TestCase):
    def test_verified_normal_session(self):
        self.assertEqual(decide(IdentityEvidence(**BASE)).action,"allow")
    def test_unbound_session_denied(self):
        self.assertEqual(decide(IdentityEvidence(**(BASE|{"device_proof_verified":False}))).action,"deny")
    def test_invalid_passkey_proof_denied(self):
        self.assertEqual(decide(IdentityEvidence(**(BASE|{"webauthn_verified":False}))).action,"deny")
    def test_silent_investigation(self):
        d=decide(IdentityEvidence(**(BASE|{"risk_score":60})))
        self.assertEqual((d.action,d.notify),("investigate",False))
    def test_critical_revocation(self):
        self.assertEqual(decide(IdentityEvidence(**(BASE|{"risk_score":85}))).action,"revoke")
    def test_sensitive_action_needs_fresh_proof(self):
        self.assertEqual(decide(IdentityEvidence(**(BASE|{"sensitive_action":True}))).action,"step_up")
    def test_sensitive_action_with_fresh_proof(self):
        self.assertEqual(decide(IdentityEvidence(**(BASE|{"sensitive_action":True,"fresh_user_verification":True}))).action,"allow")
    def test_reject_invalid_risk(self):
        with self.assertRaises(ValueError):decide(IdentityEvidence(**(BASE|{"risk_score":101})))
    def test_stress(self):
        for i in range(100000):
            self.assertEqual(decide(IdentityEvidence(**BASE)).action,"allow")
if __name__=="__main__": unittest.main()
