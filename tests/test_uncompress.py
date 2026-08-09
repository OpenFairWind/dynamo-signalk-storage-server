import base64
import gzip
import json
import os
import tempfile
import unittest
from hashlib import sha256

from Crypto.Cipher import AES
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
from Crypto.Signature import pkcs1_15

from app.uncompress import uncrypt_update_list


class ParcelDecodingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.key = RSA.generate(2048)
        self.public_key_path = os.path.join(self.directory.name, "vessel-public.pem")
        with open(self.public_key_path, "wb") as public_key_file:
            public_key_file.write(self.key.publickey().export_key())

    def tearDown(self):
        self.directory.cleanup()

    def write_parcel(self, layout="trailing"):
        updates = [{"context": "vessels.test", "updates": []}]
        log = b"".join(json.dumps(update).encode("utf-8") + b"\n" for update in updates)
        signature = base64.b64encode(pkcs1_15.new(self.key).sign(SHA256.new(log))).decode("ascii")
        payload = json.dumps({"signature": signature, "type": "RSA-SHA256"}).encode("utf-8") + b"\n" + log
        secret = b"s" * 32
        iv = b"i" * AES.block_size
        cipher = AES.new(sha256(secret).digest(), AES.MODE_CBC, iv)
        padding = AES.block_size - len(gzip.compress(payload)) % AES.block_size
        compressed = gzip.compress(payload)
        ciphertext = cipher.encrypt(compressed + bytes([padding]) * padding)
        encrypted = ciphertext + iv if layout == "trailing" else iv + ciphertext
        parcel_path = os.path.join(self.directory.name, layout + ".enc")
        with open(parcel_path, "wb") as parcel_file:
            parcel_file.write(encrypted)
        return secret, parcel_path, updates

    def test_decodes_current_trailing_iv_layout(self):
        secret, parcel_path, expected = self.write_parcel()
        self.assertEqual(uncrypt_update_list(self.public_key_path, secret, parcel_path), expected)

    def test_decodes_legacy_leading_iv_layout(self):
        secret, parcel_path, expected = self.write_parcel("leading")
        self.assertEqual(uncrypt_update_list(self.public_key_path, secret, parcel_path), expected)


if __name__ == "__main__":
    unittest.main()
