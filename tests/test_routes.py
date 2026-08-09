import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from app import create_app

class RouteTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); root=Path(self.temp.name); self.media=root/"media"
        self.app=create_app({"TESTING":True,"CONNECTION_STRING":f"sqlite:///{root/'app.db'}","MEDIA_ROOT":str(self.media),"SCRATCH_ROOT":str(root/'scratch'),"TRASH_ROOT":str(root/'trash'),"PUBLIC_KEY_ROOT":str(root/'keys/public'),"PRIVATE_KEY_FILENAME":str(root/'keys/private.pem'),"PUBLIC_KEY_FILENAME":str(root/'keys/public.pem'),"CELERY":{"broker_url":"memory://"}}); self.client=self.app.test_client()
    def tearDown(self): self.temp.cleanup()
    def test_upload_rejects_invalid_input(self):
        self.assertEqual(self.client.post("/upload/vessels.demo").status_code,400)
        response=self.client.post("/upload/vessels.demo",data={"file":(io.BytesIO(b"x"),"x.enc","text/plain")})
        self.assertEqual(response.status_code,422)
    def test_upload_persists_and_enqueues(self):
        with patch("app.tasks.process_file_task.delay") as delay:
            response=self.client.post("/upload/vessels.demo",data={"file":(io.BytesIO(b"parcel"),"x.enc","application/octet-stream")})
        self.assertEqual(response.status_code,200); self.assertEqual(len(list((self.media/"vessels.demo").glob("*.log.gz.enc"))),1); delay.assert_called_once()
    def test_admin_api_requires_login_then_creates_user(self):
        self.assertIn(self.client.post("/api/users",json={}).status_code,(302,401))
        self.client.post("/login",data={"username":"admin","password":"password"})
        response=self.client.post("/api/users",json={"username":"api-user","password":"sufficient-password"})
        self.assertEqual(response.status_code,201)
