import unittest
from sentinel_trace.engine import correlate

class SentinelTraceTests(unittest.TestCase):
    def test_known_exit_is_not_person_attribution(self):
        report = correlate({"authorized_source": True, "source_ip": "8.8.8.8"}, {"8.8.8.8"})
        self.assertEqual(report["attribution"], "unresolved")
        self.assertTrue(report["findings"][1]["evidence"]["matched"])
        self.assertEqual(len(report["event_sha256"]), 64)

    def test_rejects_unapproved_telemetry(self):
        with self.assertRaises(ValueError):
            correlate({"source_ip": "8.8.8.8"})

if __name__ == "__main__":
    unittest.main()
