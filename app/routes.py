import logging
import os
import tempfile
import xml.etree.cElementTree as ET

from flask import current_app, send_file, render_template, request, Response
from sqlalchemy import create_engine
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

add_model = api.model("add", {
    "a": fields.Integer(0),
    "b": fields.Integer(0)
})

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


@auth.verify_password
def authenticate(username, password):
    if username and password:
        if username == 'admin' and password == 'password':
            return True
        else:
            return False
    return False


# Create an api parser for public key upload
upload_publickey_parser = api.parser()

# Add parser for file storage
upload_publickey_parser.add_argument('file', location='files', type=FileStorage, required=True,
                                     help='DYNAMO Public Key -public.pem file')


@api.route('/upload/publickey/<self_id>')
@api.expect(upload_publickey_parser)
class PublicKeyUpload(Resource):
    @auth.login_required
    def post(self, self_id):
        # This is FileStorage instance
        uploaded_file = request.files['file']

        # Check if the mime is plain/text
        if uploaded_file.mimetype == 'application/x-x509-ca-cert':

            # Compose the destination file path name
            file_path = os.path.join(current_app.config.get('PUBLIC_KEY_ROOT'), str(self_id) + "-public.pem")

            # Save the uploaded file as the file path
            uploaded_file.save(file_path)

            # Log the status
            log.debug("Saved public key as: " + file_path)

            return {"result": "ok", "user": auth.current_user()}, 200

        else:
            return {"result": "fail", "error": "File mimetype must be application/x-x509-ca-cert"}, 422


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


@api.route('/lastPosition')
class LastPosition(Resource):
    def get(self):
        positions = []

        connection_string = current_app.config["CONNECTION_STRING"]
        engine = create_engine(connection_string, echo=False)
        conn = engine.connect()

        try:
            result = conn.execute(
                "SELECT ctx.context, pos.timestamp, ctx.value as info, pos.position FROM public.context ctx, "
                "(SELECT context, timestamp, value as position FROM public.navigation_position np1 WHERE timestamp = "
                "(SELECT MAX(np2.timestamp) FROM public.navigation_position np2 WHERE np1.context = np2.context) "
                "ORDER BY context) pos WHERE ctx.context = pos.context LIMIT 1;"
            )
            for row in result:
                positions.append({
                    "id": row[0].split(":")[-1],
                    "timestamp": str(row[1]),
                    "info": row[2],
                    "position": row[3]
                })
            conn.close()
        except Exception as exception:
            conn.close()

        return positions


@api.route('/gpx/<self_id>')
class GPX(Resource):
    def get(self, self_id):
        query = "SELECT * FROM public.navigation_position WHERE context='" + self_id + "' "

        connection_string = current_app.config["CONNECTION_STRING"]
        engine = create_engine(connection_string, echo=False)
        conn = engine.connect()

        gpx = ET.Element("gpx", attrib={"xmlns": "http://www.topografix.com/GPX/1/1"})
        trk = ET.SubElement(gpx, "trk")
        trkseg = ET.SubElement(trk, "trkseg")

        start = request.args.get('start')
        end = request.args.get('end')
        hours = request.args.get('hours')
        minutes = request.args.get('minutes')
        seconds = request.args.get('seconds')

        try:
            if start is not None and end is not None:
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif start is not None and (hours is not None or minutes is not None or seconds is not None):
                startTime = datetime.strptime(start, '%Y%m%dZ%H%M%S')
                endTime = startTime + timedelta(hours=int(hours or 0), minutes=int(minutes or 0),
                                                seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            elif end is not None and (hours is not None or minutes is not None or seconds is not None):
                endTime = datetime.strptime(end, '%Y%m%dZ%H%M%S')
                startTime = endTime - timedelta(hours=int(hours or 0), minutes=int(minutes or 0),
                                                seconds=int(seconds or 0))
                query += f"AND timestamp >= '{startTime}' AND timestamp <= '{endTime}' ".format(startTime, endTime)

            else:
                query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "

        except Exception as e:
            query += "AND timestamp >= NOW() - INTERVAL '15 minutes' "

        query += "ORDER BY timestamp ASC;"

        try:
            result = conn.execute(query)
            for row in result:
                trkpt = ET.SubElement(trkseg, "trkpt", attrib={"lat": str(row[5]), "lon": str(row[4])})
                ET.SubElement(trkpt, "time").text = str(row[1])

            conn.close()
        except Exception as e:
            log.error("SQL: " + str(e))
            conn.close()

        return Response(ET.tostring(gpx), mimetype='text/xml')
