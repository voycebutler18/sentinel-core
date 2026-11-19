import os
import tempfile
import threading
import unittest
from sentinel_trace.approval_store import ApprovalStore
S=dict(incident='i1',tenant='t1',principal='vendor',operation='export',resource='r1',destination='d1')
class Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory()
  self.addCleanup(self.temp.cleanup)
  self.store=ApprovalStore(os.path.join(self.temp.name,'test.sqlite'))
 def issue(self,**changes):
  return self.store.issue(**(S|dict(reviewer='officer',reviewer_authorized=True,step_up_verified=True,now=100)|changes))
 def consume(self,token,**changes):
  return self.store.consume(token,**(S|dict(now=101)|changes))
 def test_single_use(self):
  token=self.issue()
  self.assertTrue(self.consume(token))
  self.assertFalse(self.consume(token))
 def test_expiration(self):self.assertFalse(self.consume(self.issue(),now=221))
 def test_wrong_tenant(self):self.assertFalse(self.consume(self.issue(),tenant='other'))
 def test_wrong_destination(self):self.assertFalse(self.consume(self.issue(),destination='external'))
 def test_wrong_token(self):self.assertFalse(self.consume('fake'))
 def test_reviewer_mfa(self):
  with self.assertRaises(PermissionError):self.issue(step_up_verified=False)
 def test_reviewer_authorization(self):
  with self.assertRaises(PermissionError):self.issue(reviewer_authorized=False)
 def test_concurrency(self):
  token=self.issue()
  results=[]
  threads=[threading.Thread(target=lambda:results.append(self.consume(token))) for _ in range(20)]
  for t in threads:t.start()
  for t in threads:t.join()
  self.assertEqual(results.count(True),1)
 def test_stress(self):
  for i in range(2000):
   token=self.issue(now=100+i)
   self.assertTrue(self.consume(token,now=101+i))
if __name__=='__main__':unittest.main()
