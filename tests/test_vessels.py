import tempfile
import unittest
from pathlib import Path
from app import create_app

class VesselTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); root=Path(self.temp.name)
        self.app=create_app({"TESTING":True,"CONNECTION_STRING":f"sqlite:///{root/'app.db'}","MEDIA_ROOT":str(root/'media'),"SCRATCH_ROOT":str(root/'scratch'),"TRASH_ROOT":str(root/'trash'),"PUBLIC_KEY_ROOT":str(root/'keys/public'),"PRIVATE_KEY_FILENAME":str(root/'keys/private.pem'),"PUBLIC_KEY_FILENAME":str(root/'keys/public.pem'),"CELERY":{"broker_url":"memory://"}}); self.client=self.app.test_client(); self.client.post("/login",data={"username":"admin","password":"password"})
    def tearDown(self): self.temp.cleanup()
    def test_user_can_create_and_delete_own_vessel(self):
        response=self.client.post("/vessels",data={"signalk_uuid":"6d75aa35-70d4-46cd-9097-ac0026f807ab","public_key":"-----BEGIN PUBLIC KEY-----\nkey\n-----END PUBLIC KEY-----"})
        self.assertEqual(response.status_code,200); self.assertIn(b"6d75aa35",response.data)
        self.assertEqual(self.client.post("/vessels/1/delete").status_code,302)
