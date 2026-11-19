import unittest
from datetime import datetime,timezone,timedelta
from sentinel_trace.incident_review import Incident,create_approval,validate_approval
I=Incident('incident1','tenant1','vendor1','export','records','approved-api','volume')
NOW=datetime(2026,11,19,tzinfo=timezone.utc)
class Tests(unittest.TestCase):
 def make(self):return create_approval(I,'security-officer',True,True,NOW)
 def test_valid(self):
  a,t=self.make();self.assertTrue(validate_approval(a,I,t,NOW))
 def test_expired(self):
  a,t=self.make();self.assertFalse(validate_approval(a,I,t,NOW+timedelta(minutes=3)))
 def test_wrong_vendor(self):
  a,t=self.make();self.assertFalse(validate_approval(a,Incident('incident1','tenant1','attacker','export','records','approved-api','volume'),t,NOW))
 def test_wrong_destination(self):
  a,t=self.make();self.assertFalse(validate_approval(a,Incident('incident1','tenant1','vendor1','export','records','external','volume'),t,NOW))
 def test_wrong_token(self):
  a,t=self.make();self.assertFalse(validate_approval(a,I,'bad',NOW))
 def test_unverified_reviewer(self):
  with self.assertRaises(PermissionError):create_approval(I,'officer',True,False,NOW)
 def test_unauthorized_reviewer(self):
  with self.assertRaises(PermissionError):create_approval(I,'officer',False,True,NOW)
 def test_stress(self):
  a,t=self.make()
  for _ in range(10000):self.assertTrue(validate_approval(a,I,t,NOW))
if __name__=='__main__':unittest.main()
