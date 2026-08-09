import tempfile
import os
import shutil
import logging

from flask import current_app

from celery import shared_task
from celery import Task
from app.uncompress import get_encoded_encrypted_symmetric_key, get_symmetric_key, uncrypt_update_list
from app.storage import store_updatelist

log = logging.getLogger('tasks')
log.setLevel(logging.DEBUG)  # DEBUG

fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')
h = logging.StreamHandler()
h.setFormatter(fmt)
log.addHandler(h)


@shared_task(bind=True, ignore_result=False)
def process_file_task(self: Task, directory: str, file_item: str):

    # Retrieve the media root (where the flask route saves the "type.context/...log.gz.enc" files
    media_root = current_app.config["MEDIA_ROOT"]

    # Retrieve the scratch root (where the "type.context/...log.gz.enc" files are unzipped, decrypted and processed.
    scratch_root = current_app.config["SCRATCH_ROOT"]

    # Retrieve the trash root (where the "type.context/...log.gz.enc" files are stored before removed forever)
    trash_root = current_app.config["TRASH_ROOT"]

    # Get the connection string
    connection_string = current_app.config["CONNECTION_STRING"]

    # Get the local private key file name
    private_key_filename = current_app.config["PRIVATE_KEY_FILENAME"]

    # Check if the local private key exists
    if os.path.isfile(private_key_filename):

        # Get the public key root (where the public keys are stored in the format type.context-public.pem
        public_key_root = current_app.config["PUBLIC_KEY_ROOT"]

        # Set the public key file name
        public_key_filename = public_key_root + "/" + directory + "-public.pem"

        # Check if the file exists
        if os.path.isfile(public_key_filename):

            src_path = media_root + "/" + directory + "/" + file_item

            log.info("Processing: " + src_path)
            try:
                os.makedirs(scratch_root + "/" + directory)
            except FileExistsError as e:
                pass

            scratch_dir = tempfile.mkdtemp(dir=scratch_root + "/" + directory)
            enc_path = scratch_dir + "/" + file_item

            try:
                log.debug("Get Encoded Encrypted Symmetric Key")
                encoded_encrypted_symmetric_key = get_encoded_encrypted_symmetric_key(src_path, enc_path)

                log.debug("Get Symmetric Key")
                symmetric_key = get_symmetric_key(private_key_filename, encoded_encrypted_symmetric_key)

                log.debug("Decrypt the Update List")
                update_list = uncrypt_update_list(public_key_filename, symmetric_key, enc_path)

                log.debug("Store the Update List")
                store_updatelist(update_list, {"connection_string": connection_string})

                shutil.rmtree(scratch_dir)
                log.debug("Removed scratch directory: " + scratch_dir)

                os.makedirs(os.path.join(trash_root, directory), exist_ok=True)
                shutil.move(src_path, os.path.join(trash_root, directory, file_item))
                log.info("Processed and archived: " + src_path)

            except Exception as exception:
                # Keep failed parcels in MEDIA_ROOT so Celery/start-up retry can
                # process them once the key, database, or malformed input issue is fixed.
                log.exception("Unable to process %s: %s", src_path, exception)
                if os.path.isdir(scratch_dir):
                    shutil.rmtree(scratch_dir, ignore_errors=True)

        else:
            log.debug("Public key file missing: " + public_key_filename)
    else:
        log.debug("Private key file missing: " + private_key_filename)
