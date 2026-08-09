import tempfile
import unittest
from pathlib import Path
from app import create_app
from app.models import Group, Role, User


class IdentityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); root = Path(self.temp.name)
        self.app = create_app({"TESTING": True, "CONNECTION_STRING": f"sqlite:///{root / 'app.db'}", "MEDIA_ROOT": str(root/'media'), "SCRATCH_ROOT":str(root/'scratch'), "TRASH_ROOT":str(root/'trash'), "PUBLIC_KEY_ROOT":str(root/'keys/public'), "PRIVATE_KEY_FILENAME":str(root/'keys/private.pem'), "PUBLIC_KEY_FILENAME":str(root/'keys/public.pem'), "CELERY":{"broker_url":"memory://"}})
        self.client = self.app.test_client()
    def tearDown(self): self.temp.cleanup()
    def login(self): return self.client.post("/login", data={"username":"admin","password":"password"})
    def test_default_admin_and_closed_registration(self):
        with self.app.app_context():
            admin=self.app.extensions["db"].query(User).filter_by(username="admin").one(); self.assertEqual(admin.role, Role.ADMIN); self.assertTrue(admin.check_password("password"))
        self.assertEqual(self.client.get("/register").status_code, 403)
    def test_admin_can_open_registration_and_create_group(self):
        self.login(); self.client.post("/admin/registration", data={"open":"on"}); self.assertEqual(self.client.post("/register", data={"username":"sailor","password":"long-enough-password"}).status_code, 302)
        self.login(); response=self.client.post("/admin/groups", data={"name":"research"}); self.assertEqual(response.status_code, 200)
        with self.app.app_context(): self.assertIsNotNone(self.app.extensions["db"].query(Group).filter_by(name="research").first())
