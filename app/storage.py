import logging

from sqlalchemy import create_engine, Column, Table, JSON, Text, Float, MetaData, DateTime, select, insert
from geoalchemy2 import Geometry

import json
import datetime

# Create the logger
log = logging.getLogger('app')

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

def store_updatelist_csv(update_list, options):
    csv_root = options["csv_root"]
    for update_item in update_list:
        context = update_item["context"]
        updates = update_item["updates"]
        for update in updates:
            timestamp = update["timestamp"]
            values = update["values"]
            for value in values:
                path = value["path"]
                value = value["value"]
                csv_path = csv_root + "/" + path + ".csv"

                if isinstance(value, dict):
                    value = json.dumps(value)

                if isinstance(value, str):
                    value = "'" + value + "'"

                row = context + ";" + timestamp + ";" + str(value) + "\n"
                with open(csv_path, 'a') as fd:
                    fd.write(row)


# Perform update list storage
def store_updatelist(update_list, options):
    # Get the connection string
    connection_string = options["connection_string"]

    # Connect the database server
    engine = create_engine(connection_string, echo=False)

    # Retrieve the metadata
    metadata = MetaData()

    # Keep the source registry stable across batches.  The previous code only
    # declared this table for a subset of updates and then queried a string
    # literal instead of the table, so source inserts could never work.
    sources_table = Table("sources", metadata,
                          Column('context', Text, nullable=False, primary_key=True),
                          Column('label', Text, nullable=False, primary_key=True),
                          Column('type', Text, nullable=False),
                          Column('value', JSON))
    metadata.create_all(engine)

    # For each update item in the update list
    for update_item in update_list:

        # Skip this iteration if context is not in the update item
        if "context" not in update_item:

            # Log a error message
            log.error("Context not present in the update item")

            # Go to the next update item
            continue

        # Get the context
        context = update_item["context"]

        # Log a debug message
        log.debug("Processing context:"+context)

        # Skip this iteration if updates is not in the update item
        if "updates" not in update_item:

            # Log a error message
            log.error("The updates array is not present in the update item")

            # Go to the next update item
            continue

        # Get the updates
        updates = update_item["updates"]

        # For each update in the updates array
        for update in updates:

            # Check if the mandatory timestamp for the update is set
            if "timestamp" not in update:

                # Log a error message
                log.error("The timestamp is not present in the update")

                # Go to the next update
                continue

            # Get the timestamp
            try:
                timestamp = datetime.datetime.fromisoformat(
                    update["timestamp"].replace("Z", "+00:00"))
            except (TypeError, ValueError):
                log.error("Invalid timestamp: %r", update["timestamp"])
                continue

            # Set the source to  none
            source = None

            # Set the source reference to none
            source_ref = ""

            # Check if the update has a source reference
            if "$source" in update:
                # Get the source reference
                source_ref = update["$source"]

            # Check if the source full description is present
            if not source_ref and "source" in update:

                # Get the source full description
                source = update["source"]

                # Check if the label is present
                if "label" in source:
                    # Get the source reference
                    source_ref = source["label"]

            # Log da debug message
            log.debug(str(timestamp) + " source_ref: " + source_ref)

            if source is not None and source_ref:
                # Search by the same composite key used by the table.
                sql_string = select(sources_table.c.label).where(
                    sources_table.c.context == context,
                    sources_table.c.label == source_ref)

                try:
                    with engine.connect() as conn:
                        result = conn.execute(sql_string)

                        # Check if the source label is not present
                        if result.first() is None:
                            params = {
                                "context": context,
                                "label": source_ref,
                                "type": source.get("type", "unknown"),
                                "value": source
                            }

                            # Prepare the sql string for the insert given the parameters above
                            sql_string = insert(sources_table).values(params)

                            # Execute the insert
                            conn.execute(sql_string)

                            # Commit the changes
                            conn.commit()

                            # Log a debug message
                            log.debug("Added " + source_ref + " to the sources table")

                except Exception as exception:
                    log.error("SQL:" + str(exception))

                    continue

            # Check if the update has a list of values
            if "values" not in update: #and update["values"]:

                # Log an error message
                log.error("values not in the update")

                # Go to the next update
                continue

            # Get the list of values
            values = update["values"]

            # For each value in the list of values
            for value in values:

                # Check if the path is present
                if "path" in value:

                    # Get the path
                    path = value["path"]

                    # Check if the path is empty
                    if path == "":

                        # Set the table name as "context"
                        table_name = "context"

                    else:
                        # Create the table name
                        table_name = path.replace(".", "_")

                    # Get the value
                    if "value" not in value:
                        log.error("Value missing for path: %s", path)
                        continue
                    value_data = value["value"]

                    # Check if the table must be created
                    if table_name not in metadata.tables:

                        # Check if the path is related to a position
                        if path == "navigation.position":

                            # Define the data table
                            Table(table_name, metadata,
                                  Column('context', Text, nullable=False, primary_key=True),
                                  Column('timestamp', DateTime, nullable=False, primary_key=True),
                                  Column('source', Text, nullable=False, primary_key=True),
                                  Column('value', JSON),
                                  Column('lon', Float),
                                  Column('lat', Float),
                                  Column('point', Geometry('POINT'))
                                  )
                        else:
                            # Check if the value is a dictionary
                            if isinstance(value_data, dict):

                                # Set the value type as JSON
                                value_datatype = JSON

                            # Check if the value is a string
                            elif isinstance(value_data, str):

                                # Set the value type as text
                                value_datatype = Text

                            # Otherwise consider the value as a float
                            else:

                                # Set the value type as Float
                                value_datatype = Float

                            # Define the data table
                            Table(table_name, metadata,
                                  Column('context', Text, nullable=False, primary_key=True),
                                  Column('timestamp', DateTime, nullable=False, primary_key=True),
                                  Column('source', Text, nullable=False, primary_key=True),
                                  Column('value', value_datatype)
                                  )
                        # Create the table
                        metadata.create_all(engine)

                        # Log a debug message
                        log.debug("Table " + table_name + " created!")

                    # Get the table reference
                    data_table = metadata.tables[table_name]

                    # Check if the table reference is consistent
                    if data_table is None:

                        # Log an error message
                        log.error("Table " + table_name + " not present.")

                        # Go to the next value
                        continue

                    # Check if the path is a position
                    if path == "navigation.position":

                        # Prepare the parameters considering the position as geographic point
                        params = {
                            "context": context,
                            "timestamp": timestamp,
                            "source": source_ref,
                            "value": value_data,
                            "lon": value_data["longitude"],
                            "lat": value_data["latitude"],
                            # WKT point order is longitude then latitude.
                            "point": "POINT (" +
                                     str(value_data["longitude"]) + " " + str(value_data["latitude"]) +
                                     ")"
                        }
                    else:

                        # Prepare the parameters
                        params = {
                            "context": context,
                            "timestamp": timestamp,
                            "source": source_ref,
                            "value": value_data
                        }

                    # Create the sql string
                    sql_string = insert(data_table).values(params)

                    # Log a debug message
                    log.debug("SQL string: " + str(sql_string))

                    try:
                        # Create a connection
                        with engine.connect() as conn:

                            # Insert data
                            conn.execute(sql_string)

                            # Commit the changes
                            conn.commit()

                            # Log a debug message
                            log.debug("Added: " + context + "." + path + " -> " + str(value_data))

                    except Exception as exception:

                        # Log a debug message
                        log.error("While adding data: " + str(exception))




def main():
    # sqlite:///temporary.db
    # postgresql://dynamo:Dynamo2019@localhost/dynamo
    options = {"connection_string": "postgresql://dynamo:Dynamo2019@localhost/dynamo"}

    update_list = [
        {
            "context": "vessels.urn:mrn:signalk:uuid:d8cf5bc8-ad83-4269-baac-184cf12e3d79",
            "updates": [
                {
                    "source": {"src": "derived_data", "label": "derived-data"},
                    "timestamp": "2019-08-20T03:41:46.606Z",
                    "values": [
                        {
                            "path": "navigation.courseOverGroundMagnetic",
                            "value": 4.032583237653657
                        }
                    ]
                }
            ]
        },
        {
            "updates": [
                {
                    "source": {"sentence": "RMC", "talker": "GP", "type": "NMEA0183", "label": "USB1"},
                    "timestamp": "2019-08-20T03:41:46.000Z",
                    "values": [
                        {
                            "path": "navigation.position",
                            "value": {"longitude": 14.029045, "latitude": 40.76749}
                        },
                        {
                            "path": "navigation.courseOverGroundTrue",
                            "value": 4.032583237653657
                        },
                        {
                            "path": "navigation.speedOverGround",
                            "value": 0
                        },
                        {
                            "path": "navigation.magneticVariation",
                            "value": 0
                        },
                        {
                            "path": "navigation.magneticVariationAgeOfService",
                            "value": 1566272506
                        },
                        {
                            "path": "navigation.datetime",
                            "value": "2019-08-20T03:41:46.000Z"
                        }
                    ]
                }
            ],
            "context": "vessels.urn:mrn:signalk:uuid:d8cf5bc8-ad83-4269-baac-184cf12e3d79"
        },
        {
            "updates": [
                {
                    "source": {"sentence": "GGA", "talker": "GP", "type": "NMEA0183", "label": "USB1"},
                    "timestamp": "2019-08-20T03:41:47.000Z",
                    "values": [
                        {
                            "path": "navigation.position",
                            "value": {"longitude": 14.029045, "latitude": 40.76749}
                        },
                        {
                            "path": "navigation.gnss.methodQuality",
                            "value": "GNSS Fix"
                        },
                        {
                            "path": "navigation.gnss.satellites",
                            "value": 10
                        },
                        {
                            "path": "navigation.gnss.antennaAltitude",
                            "value": 6
                        },
                        {
                            "path": "navigation.gnss.horizontalDilution",
                            "value": 1
                        },
                        {
                            "path": "navigation.gnss.differentialAge",
                            "value": 0
                        },
                        {
                            "path": "navigation.gnss.differentialReference",
                            "value": 0
                        }
                    ]
                }
            ],
            "context": "vessels.urn:mrn:signalk:uuid:d8cf5bc8-ad83-4269-baac-184cf12e3d79"
        }
    ]

    store_updatelist(update_list, options)

    connection_string = options["connection_string"]

    engine = create_engine(connection_string, echo=True)
    conn = engine.connect()
    metadata = MetaData(bind=conn, reflect=True)
    navigation_position = metadata.tables["navigation_position"]
    s = select([navigation_position])
    rows = conn.execute(s)
    for row in rows:
        print(row)


if __name__ == "__main__":
    main()
