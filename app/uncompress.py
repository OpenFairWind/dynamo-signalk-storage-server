import gzip
import io
import json
import tempfile
from Crypto.Cipher import PKCS1_OAEP, AES

from hashlib import sha256

from Crypto.PublicKey import RSA
from Crypto.Signature import PKCS1_v1_5
from Crypto.Hash import SHA256
from base64 import b64decode

import sys, os, shutil
from os import listdir
from os.path import isdir, isfile, join

from app.storage import store_updatelist_csv


def verify_sign(public_key_loc, signature, data):
    '''
    Verifies with a public key from whom the data came that it was indeed
    signed by their private key
    param: public_key_loc Path to public key
    param: signature String signature to be verified
    return: Boolean. True if the signature is valid; False otherwise.
    '''

    with open(public_key_loc, "r", encoding="utf-8") as public_key_file:
        pub_key = public_key_file.read()
    rsakey = RSA.importKey(pub_key)
    signer = PKCS1_v1_5.new(rsakey)
    digest = SHA256.new()
    digest.update(data)
    if signer.verify(digest, b64decode(signature)):
        return True
    return False


def unpad(padded):
    if not padded:
        raise ValueError("Encrypted payload is empty")
    pad = padded[-1]
    if pad < 1 or pad > AES.block_size or padded[-pad:] != bytes([pad]) * pad:
        raise ValueError("Invalid AES padding")
    return padded[:-pad]


def get_encoded_encrypted_symmetric_key(src_path, enc_path):
    with open(src_path, "rb") as f_in:
        encoded_encrypted_symmetric_key = f_in.readline().decode("ascii").strip()
        if not encoded_encrypted_symmetric_key:
            raise ValueError("Parcel is missing its encrypted-key header")
        with open(enc_path, 'wb') as f_out:
            data = f_in.read(10000)
            while data:
                f_out.write(data)
                data = f_in.read(10000)

    return encoded_encrypted_symmetric_key


def get_symmetric_key(private_key_filename, encoded_encrypted_symmetric_key):
    with open(private_key_filename, "rb") as private_key_file:
        rsa_key = RSA.importKey(private_key_file.read())
    rsa_key = PKCS1_OAEP.new(rsa_key)
    decoded_encrypted_symmetric_key = b64decode(encoded_encrypted_symmetric_key)
    symmetric_key = rsa_key.decrypt(decoded_encrypted_symmetric_key)
    return symmetric_key


def uncrypt_update_list(public_key_filename, symmetric_key, enc_path):
    """Decrypt and verify a DYNAMO parcel.

    Version 2 clients append the CBC IV after the encrypted payload.  Early
    server versions incorrectly read it from the start; accepting that layout
    as a fallback keeps already-uploaded legacy parcels recoverable.
    """
    with open(enc_path, mode='rb') as f_in:
        encrypted_payload = f_in.read()

    if len(encrypted_payload) < AES.block_size * 2:
        raise ValueError("Parcel payload is too short")

    key = sha256(symmetric_key).digest()

    def decrypt(iv, ciphertext):
        if len(ciphertext) == 0 or len(ciphertext) % AES.block_size:
            raise ValueError("Invalid AES ciphertext length")
        compressed = unpad(AES.new(key, AES.MODE_CBC, iv).decrypt(ciphertext))
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as gzip_file:
            return gzip_file.read()

    # The plugin's documented/current layout is ciphertext followed by IV.
    # Fall back to the pre-2.0 server interpretation for parcels already on disk.
    try:
        plaintext = decrypt(encrypted_payload[-AES.block_size:], encrypted_payload[:-AES.block_size])
    except Exception as current_layout_error:
        try:
            plaintext = decrypt(encrypted_payload[:AES.block_size], encrypted_payload[AES.block_size:])
        except Exception:
            raise current_layout_error

    header, separator, log_file = plaintext.partition(b"\n")
    if not separator:
        raise ValueError("Parcel is missing its signature header")
    meta_data = json.loads(header.decode("utf-8"))
    encrypted_signature = meta_data.get("signature")
    if not encrypted_signature or not verify_sign(public_key_filename, encrypted_signature, log_file):
        raise ValueError("Invalid signature")

    update_list = []
    for line in log_file.splitlines():
        if line:
            update_list.append(json.loads(line.decode("utf-8")))
    return update_list


def process_updates(media_root, scratch_root, trash_root, csv_root, private_key_filename, public_key_root):
    vessels = [f for f in listdir(media_root) if isdir(join(media_root, f))]
    for vessel in vessels:
        public_key_filename = public_key_root + "/" + vessel + "-public.pem"
        vessel_root = media_root + "/" + vessel
        files = [f for f in listdir(vessel_root) if isfile(join(vessel_root, f))]
        for file in files:
            src_path = vessel_root + "/" + file
            try:
                os.mkdir(scratch_root + "/" + vessel)
            except:
                pass
            scratch_dir = tempfile.mkdtemp(dir=scratch_root + "/" + vessel)
            enc_path = scratch_dir + "/" + file

            encoded_encrypted_symmetric_key = get_encoded_encrypted_symmetric_key(src_path, enc_path)

            symmetric_key = get_symmetric_key(private_key_filename, encoded_encrypted_symmetric_key)
            update_list = uncrypt_update_list(public_key_filename, symmetric_key, enc_path)
            store_updatelist_csv(update_list, {"csv_root": csv_root})

            shutil.rmtree(scratch_dir)

            try:
                os.mkdir(trash_root + "/" + vessel)
            except:
                pass

            os.rename(src_path, trash_root + "/" + vessel + "/" + file)


def main():
    media_root = "data/media/"
    scratch_root = "data/scratch/"
    trash_root = "data/trash/"
    csv_root = "data/csv/"
    private_key_filename = "../data/keys/dynamo-signalk-storage-server-private.pem"
    public_key_root = "../data/keys/public"

    process_updates(media_root, scratch_root, trash_root, csv_root, private_key_filename, public_key_root)


def static_test():
    media_root = "data/media/"
    scratch_root = "data/scratch/"
    private_key_filename = "../data/keys/dynamo-signalk-storage-server-private.pem"

    enc_file = "RKB5p1.log.gz.enc"

    src_path = media_root + "/" + enc_file
    scratch_dir = tempfile.mkdtemp(dir=scratch_root)

    enc_path = scratch_dir + "/" + enc_file

    with open(src_path, "rb") as f_in:
        encoded_encrypted_symmetric_key = f_in.readline().decode('utf-8')
        with open(enc_path, 'wb') as f_out:
            data = f_in.read(10000)
            while data:
                f_out.write(data)
                data = f_in.read(10000)

    rsa_key = RSA.importKey(open(private_key_filename, "rb").read())
    rsa_key = PKCS1_OAEP.new(rsa_key)
    decoded_encrypted_symmetric_key = b64decode(encoded_encrypted_symmetric_key)
    symmetric_key = rsa_key.decrypt(decoded_encrypted_symmetric_key)

    # print ("Symmetric Key:"+str(symmetric_key))

    with open(enc_path, mode='rb') as f_in:
        enc = bytearray(f_in.read())

        iv = enc[:16]
        # print ("len(iv):"+str(len(iv)))
        # print ','.join('{:02x}'.format(x) for x in iv)

        m = sha256()
        m.update(symmetric_key)
        key = m.digest()
        aes = AES.new(key, AES.MODE_CBC, buffer(iv[:16]))
        result = aes.decrypt(buffer(enc[16:]))
        result = unpad(result)

        # bbb=bytearray(result)
        # print ','.join('{:02x}'.format(x) for x in bbb)

        in_ = io.BytesIO()
        in_.write(result)
        in_.seek(0)
        with gzip.GzipFile(fileobj=in_, mode='rb') as fo:
            gunzipped_bytes_obj = fo.read()

        result = gunzipped_bytes_obj.decode()
        result = result.decode("utf-8")

        lines = result.splitlines()
        meta_data = json.loads(lines[0])
        encrypted_signature = meta_data["signature"]
        # print ("Encrypted Signature:" + encrypted_signature)

        log_file = ''.join(line + "\n" for line in lines[1:])

        if encrypted_signature is not None:
            if verify_sign(public_key_filename, encrypted_signature, log_file):
                print("OK")
            else:
                print("Invalid")


if __name__ == "__main__":
    main()
