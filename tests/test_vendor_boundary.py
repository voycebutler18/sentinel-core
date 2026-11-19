import unittest
from sentinel_trace.vendor_boundary import BoundaryEvent, VendorGrant, evaluate_boundary
G=VendorGrant('bank','payroll',frozenset({'read'}),frozenset({'payroll'}),frozenset({'internal-api'}))
E=dict(tenant='bank',vendor_id='payroll',principal_id='svc1',operation='read',resource_class='payroll',destination='internal-api',grant_active=True,trusted_telemetry=True)
class Tests(unittest.TestCase):
 def test_normal_vendor_work(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**E),G).action,'ALLOW')
 def test_other_tenant(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**(E|{'tenant':'other'})),G).action,'DENY')
 def test_other_vendor(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**(E|{'vendor_id':'unknown'})),G).action,'DENY')
 def test_disallowed_operation(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**(E|{'operation':'export'})),G).action,'DENY')
 def test_disallowed_data(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**(E|{'resource_class':'customer-ssn'})),G).action,'DENY')
 def test_disallowed_destination(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**(E|{'destination':'external'})),G).action,'DENY')
 def test_untrusted_telemetry(self):self.assertEqual(evaluate_boundary(BoundaryEvent(**(E|{'trusted_telemetry':False})),G).action,'DENY')
 def test_stress(self):
  for _ in range(30000):self.assertEqual(evaluate_boundary(BoundaryEvent(**E),G).action,'ALLOW')
if __name__=='__main__':unittest.main()
