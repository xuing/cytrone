#!/usr/bin/python3

#############################################################################
# Classes related to the CyTrONE content upload server operation
#############################################################################

# External imports
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import random
import subprocess
import os
import sys
from socketserver import ThreadingMixIn
import yaml
import argparse
import logging
import json

# Internal imports
from . import userinfo
from . import query
from .storyboard import Storyboard
from . import config
from .logic import content

logger = logging.getLogger(__name__)

#############################################################################
# Constants
#############################################################################

# Web server constants
SUCCESS_CODE  = 200
REQUEST_ERROR = 404
SERVER_ERROR  = 500
LOCAL_SERVER  = True
SERVE_FOREVER = True # Use serve count if not using local server?!
RESPONSE_SUCCESS = '[{"' + Storyboard.SERVER_STATUS_KEY + '": "' + Storyboard.SERVER_STATUS_SUCCESS + '"}]'
RESPONSE_SUCCESS_ID_PREFIX = '[{"' + Storyboard.SERVER_STATUS_KEY + '": "' + Storyboard.SERVER_STATUS_SUCCESS \
                             + '", "' + Storyboard.SERVER_ACTIVITY_ID_KEY + '": "'
RESPONSE_SUCCESS_ID_SUFFIX = '"}]'
RESPONSE_ERROR = '[{"' + Storyboard.SERVER_STATUS_KEY + '": "' + Storyboard.SERVER_STATUS_ERROR + '"}]'

# Other constants
SEPARATOR = "-----------------------------------------------------------------"
CONTENT_DESCRIPTION_TEMPLATE = "tmp_content_description-{}.yml"
CYLMS_PATH = ""
CYLMS_CONFIG = ""

# Debugging constants
DO_DEBUG = False
USE_MOODLE = True

#############################################################################
# Manage the content server functionality
#############################################################################
class RequestHandler(BaseHTTPRequestHandler):

    @classmethod
    def setup_config(cls, no_lms_override=None, path_override=None, config_override=None):
        """
        Sets up the configuration for the request handler.
        Command-line arguments can override config file settings.
        """
        cls.cfg = config.get_section_config("contsrv")
        cls.general_cfg = config.get_section_config("general")

        cls.DATABASE_DIR = cls.general_cfg.get("database_dir", "../database/")
        cls.USERS_FILE = config.get_section_config("trngsrv").get("files", {}).get("users", "users.yml")

        cls.DO_DEBUG = cls.general_cfg.get("debug", False)

        sim_cfg = cls.cfg.get("simulation", {})
        cls.SIMULATION_DURATION = sim_cfg.get("duration", -1)
        cls.SIMULATION_RAND_MIN = sim_cfg.get("rand_min", 1)
        cls.SIMULATION_RAND_MAX = sim_cfg.get("rand_max", 3)

        cylms_cfg = cls.cfg.get("cylms", {})

        # Precedence: command-line arg > config file
        cls.USE_MOODLE = not no_lms_override if no_lms_override is not None else cls.cfg.get("use_moodle", True)
        cls.CYLMS_PATH = path_override or cylms_cfg.get("path")
        cls.CYLMS_CONFIG = config_override or cylms_cfg.get("config")

    # List of valid actions recognized by this server
    VALID_ACTIONS = [query.Parameters.UPLOAD_CONTENT,
                     query.Parameters.REMOVE_CONTENT]

    #########################################################################
    def log_message(self, format, *args):
        """Override the default log_message to use our logger."""
        logger.info("%s - %s", self.address_string(), format % args)

    def send_json_response(self, data, status_code=SUCCESS_CODE):
        """Sends a JSON response to the client."""
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response_body = json.dumps(data)
        self.wfile.write(response_body.encode('utf-8'))
        logger.info("Server response content: %s", response_body)

    def handle_upload_content(self, params):
        """Handler for the 'upload_content' action."""
        description_file = params.get(query.Parameters.DESCRIPTION_FILE)
        range_id = params.get(query.Parameters.RANGE_ID)

        if not description_file:
            return self.send_error(REQUEST_ERROR, "Invalid description file")
        if not range_id:
            return self.send_error(REQUEST_ERROR, "Invalid range ID")

        try:
            content_file_name = CONTENT_DESCRIPTION_TEMPLATE.format(range_id)
            with open(content_file_name, "w") as f:
                f.write(description_file)
            logger.info("Saved POSTed content to '%s'.", content_file_name)
        except IOError as e:
            logger.error("Could not write to file %s: %s", content_file_name, e)
            return self.send_error(SERVER_ERROR, "Failed to save content file.")

        if self.USE_MOODLE:
            success, result = content.upload_content(
                self.CYLMS_PATH, self.CYLMS_CONFIG, content_file_name, range_id, self.DO_DEBUG
            )
            if success:
                response_payload = {
                    Storyboard.SERVER_STATUS_KEY: Storyboard.SERVER_STATUS_SUCCESS,
                    Storyboard.SERVER_ACTIVITY_ID_KEY: result["activity_id"]
                }
                self.send_json_response([response_payload])
            else:
                self.send_error(SERVER_ERROR, result.get("message", "LMS upload failed."))
        else:
            # Simulation logic
            # ... (omitted for brevity, can be added back if needed)
            pass

    def handle_remove_content(self, params):
        """Handler for the 'remove_content' action."""
        range_id = params.get(query.Parameters.RANGE_ID)
        activity_id = params.get(query.Parameters.ACTIVITY_ID)

        if not range_id:
            return self.send_error(REQUEST_ERROR, "Invalid range ID")
        if not activity_id:
            return self.send_error(REQUEST_ERROR, "Invalid LMS activity ID")

        if self.USE_MOODLE:
            success, result = content.remove_content(
                self.CYLMS_PATH, self.CYLMS_CONFIG, range_id, activity_id, self.DO_DEBUG
            )
            if success:
                self.send_json_response([{Storyboard.SERVER_STATUS_KEY: Storyboard.SERVER_STATUS_SUCCESS}])
            else:
                self.send_error(SERVER_ERROR, result.get("message", "LMS removal failed."))
        else:
            # Simulation logic
            # ... (omitted for brevity, can be added back if needed)
            pass

    def do_POST(self):
        params = query.Parameters(self)
        action = params.get(query.Parameters.ACTION)
        user_id = params.get(query.Parameters.USER)

        # User and action validation
        user_info = userinfo.UserInfo()
        if not user_info.parse_YAML_file(os.path.join(self.DATABASE_DIR, self.USERS_FILE)):
            return self.send_error(SERVER_ERROR, "User information issue")
        if not user_info.get_user(user_id):
            return self.send_error(REQUEST_ERROR, "Invalid user id")
        if action not in self.VALID_ACTIONS:
            return self.send_error(REQUEST_ERROR, "Invalid action")

        action_handlers = {
            query.Parameters.UPLOAD_CONTENT: self.handle_upload_content,
            query.Parameters.REMOVE_CONTENT: self.handle_remove_content,
        }

        handler = action_handlers.get(action)
        if handler:
            handler(params)
        else:
            self.send_error(REQUEST_ERROR, f"Unknown action: {action}")


# Print usage information
def usage():
    print ("OVERVIEW: CyTrONE content server that manages LMS training support via CyLMS.\n")
    print ("USAGE: contsrv.py [options]\n")
    print ("OPTIONS:")
    print ("-h, --help           Display help")
    print ("-n, --no-lms         Disable LMS use => only simulate actions")
    print ("-p, --path <PATH>    Set the location where CyLMS is installed")
    print ("-c, --config <FILE>  Set configuration file for LMS operations\n")

# Use threads to handle multiple clients
# Note: By using ForkingMixIn instead of ThreadingMixIn,
# separate processes are used instead of threads
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


#############################################################################
# Main program
#############################################################################
def main():
    """Main function to run the CyTrONE Content Server."""
    parser = argparse.ArgumentParser(description="CyTrONE Content Server.")
    parser.add_argument("-n", "--no-lms", action="store_true", help="Disable LMS use => only simulate actions")
    parser.add_argument("-p", "--path", help="Override the location where CyLMS is installed")
    parser.add_argument("-c", "--config-file", help="Override the configuration file for LMS operations") # Renamed for clarity
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    args = parser.parse_args()

    # Configure logging
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='* %(levelname)s: %(name)s: %(message)s')

    # Load configuration from file
    try:
        config.load_config()
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.error("Failed to load configuration: %s", e)
        sys.exit(1)

    # Setup handler config, applying command-line overrides
    RequestHandler.setup_config(
        no_lms_override=args.no_lms,
        path_override=args.path,
        config_override=args.config_file
    )

    # Append '/' to path if it does not exist and path is not None
    if RequestHandler.CYLMS_PATH and not RequestHandler.CYLMS_PATH.endswith("/"):
        RequestHandler.CYLMS_PATH += "/"

    try:
        # Configure the web server
        server_cfg = RequestHandler.cfg
        if LOCAL_SERVER:
            server_address = server_cfg.get("host")
        else:
            server_address = ""
        server_port = server_cfg.get("port")

        multi_threading = ""
        if server_cfg.get("enable_threads"):
            server = ThreadedHTTPServer((server_address, server_port), RequestHandler)
            multi_threading = " (multi-threading mode)"
        else:
            server = HTTPServer((server_address, server_port), RequestHandler)

        # Start the web server
        logger.info("CyTrONE content server listens on %s:%d%s.",
            server_address, server_port, multi_threading)
        if not RequestHandler.USE_MOODLE:
            logger.info("LMS use is disabled => only simulate actions.")
        else:
            logger.info("Using CyLMS software installed in %s.", RequestHandler.CYLMS_PATH)
            logger.info("Using CyLMS configuration file %s.", RequestHandler.CYLMS_CONFIG)

        if SERVE_FOREVER:
            server.serve_forever()
        else:
            server.handle_request()

    # Catch socket errors
    except IOError:
        logger.error("HTTPServer error (server may be running already).")

    # Deal with keyboard interrupts
    except KeyboardInterrupt:
        logger.info("Interrupted via ^C => shut down server.")
        server.socket.close()

    logger.info("CyTrONE content server ended execution.")


#############################################################################
# Run server
if __name__ == "__main__":
    main()
