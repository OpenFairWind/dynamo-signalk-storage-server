import logging
import os
import tempfile
import re
import xml.etree.cElementTree as ET

from flask import current_app, send_file, render_template, request, Response
from sqlalchemy import create_engine, text
from werkzeug.datastructures import FileStorage
from datetime import datetime, timedelta

from celery.result import AsyncResult
from flask import request, jsonify
from flask_restx import Api, Resource, fields
from flask_httpauth import HTTPBasicAuth

# Create the logger
log = logging.getLogger('routes')

# Set the default logger level as debug
log.setLevel(logging.DEBUG)

# Create the logger formatter
fmt = logging.Formatter('%(levelname)s:%(name)s:%(message)s')

# Get the handler
h = logging.StreamHandler()

# Set the formatter
h.setFormatter(fmt)

# Add the handler to the logger
log.addHandler(h)

# Create the api object using restx
api = Api(current_app)

# Get the HTTP Basic Authentication object
auth = HTTPBasicAuth()

log.debug("Routes")


@api.route('/publickey')
class PublicKey(Resource):
    def get(self):
        public_key_filename = current_app.config["PUBLIC_KEY_FILENAME"]
        log.debug("PUBLIC_KEY_FILENAME:" + public_key_filename)
        return send_file(public_key_filename, as_attachment=True)


# Create an api parser
upload_parser = api.parser()

# Add parser for file storage
upload_parser.add_argument('file', location='files', type=FileStorage, required=True, help='DYNAMO log.gz.enc file')

# Add parser for session id
upload_parser.add_argument('sessionId', required=True, help="Session unique identifier")


@api.route('/upload/<self_id>')
@api.expect(upload_parser)
class ParcelUpload(Resource):
    def post(self, self_id):
        # Import the process file
        from app.tasks import process_file_task

        # This is FileStorage instance
        uploaded_file = request.files.get('file')
        if uploaded_file is None:
            return {'result': 'fail', 'error': 'Missing file field'}, 400

        # Context identifiers are used as directory names.  Keep the accepted
        # Signal K form while rejecting path traversal and control characters.
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:-]*", self_id):
            return {'result': 'fail', 'error': 'Invalid vessel identifier'}, 400

        # Check if the myme is application/octet-stream
        if uploaded_file.mimetype == 'application/octet-stream':

            # Compose the destination directory
            destination = os.path.join(current_app.config.get('MEDIA_ROOT'), str(self_id) + "/")

            # Check if the directory exists
            if not os.path.exists(destination):
                # Make the directory if needed
                os.makedirs(destination)

            descriptor, file_path = tempfile.mkstemp(suffix='.log.gz.enc', dir=destination)
            os.close(descriptor)
            temp_name = os.path.basename(file_path)
            uploaded_file.save(file_path)

            # Processing the file is potentially time-consuming, enqueue the process
            process_file_task.delay(self_id, temp_name)

            return {'result': 'ok'}, 200
        else:
            return {'result': 'fail', "error": "File mimetype must be application/octet-stream"}, 422
