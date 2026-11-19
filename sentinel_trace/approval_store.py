"""SQLite-backed single-use incident approvals. Trusted caller supplies reviewer authorization."""
import hashlib
import secrets
import sqlite3
import time
from contextlib import contextmanager

class ApprovalStore:
    def __init__(self, path):
        self.path = path
        with self.db() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS approvals (
                token_hash TEXT PRIMARY KEY, incident TEXT, tenant TEXT, principal TEXT,
                operation TEXT, resource TEXT, destination TEXT, reviewer TEXT,
                expires REAL, used INTEGER DEFAULT 0)""")
            db.execute("""CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY, incident TEXT, tenant TEXT, event TEXT,
                actor TEXT, timestamp REAL)""")

    @contextmanager
    def db(self):
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def issue(self, incident, tenant, principal, operation, resource, destination,
              reviewer, reviewer_authorized, step_up_verified, now=None, ttl=120):
        if not all((incident, tenant, principal, operation, resource, destination, reviewer)):
            raise ValueError('missing scope')
        if not reviewer_authorized or not step_up_verified:
            raise PermissionError('verified reviewer required')
        if type(ttl) is not int or not 1 <= ttl <= 300:
            raise ValueError('invalid lifetime')
        now = time.time() if now is None else now
        token = secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db() as db:
            db.execute("INSERT INTO approvals VALUES (?,?,?,?,?,?,?,?,?,0)",
                       (digest, incident, tenant, principal, operation, resource,
                        destination, reviewer, now + ttl))
            db.execute("INSERT INTO audit (incident,tenant,event,actor,timestamp) VALUES (?,?,?,?,?)",
                       (incident, tenant, 'issued', reviewer, now))
        return token

    def consume(self, token, incident, tenant, principal, operation, resource,
                destination, now=None):
        if not isinstance(token, str) or not token:
            return False
        now = time.time() if now is None else now
        digest = hashlib.sha256(token.encode()).hexdigest()
        with self.db() as db:
            db.execute('BEGIN IMMEDIATE')
            result = db.execute("""UPDATE approvals SET used=1 WHERE token_hash=?
                AND incident=? AND tenant=? AND principal=? AND operation=?
                AND resource=? AND destination=? AND used=0 AND expires>?""",
                (digest, incident, tenant, principal, operation, resource, destination, now))
            if result.rowcount != 1:
                return False
            db.execute("INSERT INTO audit (incident,tenant,event,actor,timestamp) VALUES (?,?,?,?,?)",
                       (incident, tenant, 'consumed', principal, now))
            return True
