import logging
import os
import tempfile
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

        # Push the application context
        with current_app.app_context():

            # Log a debug message
            log.debug("PUBLIC_KEY_FILENAME:" + current_app.config["PUBLIC_KEY_FILENAME"])

            # Get the public key filename
            public_key_filename = current_app.config["PUBLIC_KEY_FILENAME"]

            # Check if the filename is relative
            if not os.path.isabs(public_key_filename):

                # Move one directory level up
                public_key_filename = ".." + os.sep + public_key_filename

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
        uploaded_file = request.files['file']

        # Check if the myme is application/octet-stream
        if uploaded_file.mimetype == 'application/octet-stream':

            # Compose the destination directory
            destination = os.path.join(current_app.config.get('MEDIA_ROOT'), str(self_id) + "/")

            # Check if the directory exists
            if not os.path.exists(destination):
                # Make the directory if needed
                os.makedirs(destination)

            # Set the file path
            file_path = ""

            # Set the file name
            temp_name = ""

            # Until the random temporary file name is not unique...
            done = False
            while not done:

                # Generate a temporary file name
                temp_name = next(tempfile._get_candidate_names())

                # Create a file name
                file_path = '%s%s%s' % (destination, temp_name, '.log.gz.enc')

                # Check if the file already exists
                if os.path.isfile(file_path) is False:
                    # If the file doesn't exist, exit the cycle
                    done = True

            # Save the uploaded file as the file path
            uploaded_file.save(file_path)

            # Processing the file is potentially time-consuming, enqueue the process
            process_file_task.delay(self_id, temp_name + '.log.gz.enc')

            return {'result': 'ok'}, 200
        else:
            return {'result': 'fail', "error": "File mimetype must be application/octet-stream"}, 422