import tempfile
import unittest
from pathlib import Path

from app import create_app


class ProgressiveWebShellTests(unittest.TestCase):
  def test_progressive_web_shell_is_served(self):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        app = create_app({
            "TESTING": True,
            "CONNECTION_STRING": f"sqlite:///{root / 'app.db'}",
            "MEDIA_ROOT": str(root / "media"),
            "SCRATCH_ROOT": str(root / "scratch"),
            "TRASH_ROOT": str(root / "trash"),
            "PUBLIC_KEY_ROOT": str(root / "keys" / "public"),
            "PRIVATE_KEY_FILENAME": str(root / "keys" / "private.pem"),
            "PUBLIC_KEY_FILENAME": str(root / "keys" / "public.pem"),
            "CELERY": {"broker_url": "memory://", "result_backend": "cache+memory://"},
        })
        client = app.test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"bootstrap@5", response.data)
        self.assertIn(b"manifest.webmanifest", response.data)
        manifest = client.get("/manifest.webmanifest")
        self.assertTrue(manifest.is_json)
        manifest.close()
        worker = client.get("/service-worker.js")
        self.assertEqual(worker.status_code, 200)
        self.assertEqual(worker.headers["Service-Worker-Allowed"], "/")
        worker.close()
