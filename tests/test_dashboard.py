import tempfile
import unittest
from pathlib import Path
from app import create_app

class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); root=Path(self.temp.name)
        self.app=create_app({"TESTING":True,"CONNECTION_STRING":f"sqlite:///{root/'app.db'}","MEDIA_ROOT":str(root/'media'),"SCRATCH_ROOT":str(root/'scratch'),"TRASH_ROOT":str(root/'trash'),"PUBLIC_KEY_ROOT":str(root/'keys/public'),"PRIVATE_KEY_FILENAME":str(root/'keys/private.pem'),"PUBLIC_KEY_FILENAME":str(root/'keys/public.pem'),"CELERY":{"broker_url":"memory://"}}); self.client=self.app.test_client()
    def tearDown(self): self.temp.cleanup()
    def test_anonymous_dashboard_exposes_only_heatmap(self):
        self.assertEqual(self.client.get('/dashboard').status_code,200)
        self.assertEqual(self.client.get('/api/dashboard/heatmap').status_code,200)
        self.assertIn(self.client.get('/api/dashboard/tracks').status_code,(302,401))
    def test_admin_tracks_endpoint_is_available_after_login(self):
        self.client.post('/login',data={'username':'admin','password':'password'})
        self.assertEqual(self.client.get('/api/dashboard/tracks').status_code,200)
