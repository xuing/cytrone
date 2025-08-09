#!/usr/bin/python3

#############################################################################
# Classes related to the CyTrONE cyber range instantiation server operation
#############################################################################

# External imports
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import random
import os
import sys
from socketserver import ThreadingMixIn
import urllib
import yaml
import argparse
import logging
import json

# Internal imports
from . import userinfo
from . import query
from .storyboard import Storyboard
from . import config
from .logic import instantiation

logger = logging.getLogger(__name__)

#############################################################################
# Constants
#############################################################################

# Web server constants
HTTP_OK_CODE  = 200
REQUEST_ERROR = 404
SERVER_ERROR  = 500
LOCAL_SERVER  = True
SERVE_FOREVER = True # Use serve count if not using local server?!

# Internal constants
SEPARATOR = "-----------------------------------------------------------------"
RANGE_DESCRIPTION_TEMPLATE = "tmp_range_description-{0}.yml"

# CyRIS related constants
CYRIS_STATUS_FILENAME = "cr_creation_status"
CYRIS_NOTIFICATION_TEMPLATE = "range_notification-cr{0}.txt"
CYRIS_NOTIFICATION_SIMULATED = "range_notification-simulated.txt"
CYRIS_DETAILS_TEMPLATE = "range_details-cr{0}.yml"
CYRIS_ENTRY_POINT_TEMPLATE = "entry_points.txt"
CYRIS_CREATION_STATUS_TEMPLATE = "cr_creation_status"
CYRIS_INITIF_TEMPLATE = "initif.conf"
CYRIS_CREATION_LOG_TEMPLATE = "creation.log"
CYRIS_DESTRUCTION_SCRIPT = "main/range_cleanup.py"

# CyPROM related constants
CYPROM_PATH = ""

# Debugging constants
DEBUG = False
USE_CYRIS = True

# Temporary solution until a better way is implemented for generating scripts
# to connect to cyber range based on the output of CyRIS
# NOTE: Script generation functionality is not currently supported, so don't
#       enable it unless you know what you are doing
USE_CNT2LMS_SCRIPT_GENERATION = False
CYRIS_MASTER_HOST = "172.16.1.7"
CYRIS_MASTER_ACCOUNT = "cyuser"
CNT2LMS_PATH = "/home/cyuser/cylms/"


#############################################################################
# Manage the instantiation server functionality
#############################################################################
class RequestHandler(BaseHTTPRequestHandler):

    @classmethod
    def setup_config(cls, no_inst_override=None, path_override=None, cyprom_override=None):
        """
        Sets up the configuration for the request handler.
        Command-line arguments can override config file settings.
        """
        cls.cfg = config.get_section_config("instsrv")
        cls.general_cfg = config.get_section_config("general")

        cls.DATABASE_DIR = cls.general_cfg.get("database_dir", "../database/")
        cls.USERS_FILE = config.get_section_config("trngsrv").get("files", {}).get("users", "users.yml")

        cls.DEBUG = cls.general_cfg.get("debug", False)

        sim_cfg = cls.cfg.get("simulation", {})
        cls.SIMULATION_DURATION = sim_cfg.get("duration", -1)
        cls.SIMULATION_RAND_MIN = sim_cfg.get("rand_min", 1)
        cls.SIMULATION_RAND_MAX = sim_cfg.get("rand_max", 3)

        cyris_cfg = cls.cfg.get("cyris", {})
        cyprom_cfg = cls.cfg.get("cyprom", {})

        # Precedence: command-line arg > config file
        cls.USE_CYRIS = not no_inst_override if no_inst_override is not None else cls.cfg.get("use_cyris", True)
        cls.CYRIS_PATH = path_override or cyris_cfg.get("path")
        cls.CYPROM_PATH = cyprom_override or cyprom_cfg.get("path")

        # These are not overridable by CLI args in this version
        cls.CYRIS_RANGE_DIRECTORY = cyris_cfg.get("range_directory")
        cls.CYRIS_CONFIG_FILENAME = cyris_cfg.get("config_filename")

    # List of valid actions recognized by this server
    VALID_ACTIONS = [query.Parameters.INSTANTIATE_RANGE,
                     query.Parameters.DESTROY_RANGE,
                     query.Parameters.GET_CR_NOTIFICATION,
                     query.Parameters.GET_CR_DETAILS,
                     query.Parameters.GET_CR_ENTRY_POINT,
                     query.Parameters.GET_CR_CREATION_STATUS,
                     query.Parameters.GET_CR_INITIF,
                     query.Parameters.GET_CR_CREATION_LOG]

    #########################################################################
    def log_message(self, format, *args):
        """Override the default log_message to use our logger."""
        logger.info("%s - %s", self.address_string(), format % args)

    #########################################################################
    # Execute shell commands
    #def execute_command(self, command):
    #    p = subprocess.Popen(command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    #    with open("log.txt", "a") as myfile:
    #        for line in p.stdout.readlines():
    #            myfile.write(line)

    def send_json_response(self, data, status_code=HTTP_OK_CODE):
        """Sends a JSON response to the client."""
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response_body = json.dumps(data)
        self.wfile.write(response_body.encode('utf-8'))
        if self.DEBUG:
            logger.debug("Server response content: %s", response_body)

    def build_and_send_response(self, success, result):
        """Builds a standard response payload and sends it."""
        if success:
            payload = {Storyboard.SERVER_STATUS_KEY: Storyboard.SERVER_STATUS_SUCCESS}
            if result.get("message"):
                payload[Storyboard.SERVER_MESSAGE_KEY] = result["message"]
            self.send_json_response([payload])
        else:
            self.send_error(SERVER_ERROR, result.get("message", "Unknown instantiation error"))

    def handle_instantiate_range(self, params):
        """Handler for the 'instantiate_range' action."""
        description_file = params.get(query.Parameters.DESCRIPTION_FILE)
        range_id = params.get(query.Parameters.RANGE_ID)
        progression_scenario = params.get(query.Parameters.PROGRESSION_SCENARIO)

        if not description_file or not range_id:
            return self.send_error(REQUEST_ERROR, "Invalid description file or range_id")

        try:
            range_file_name = RANGE_DESCRIPTION_TEMPLATE.format(range_id)
            with open(range_file_name, "w") as f:
                f.write(description_file)
            logger.info("Saved cyber range description to '%s'.", range_file_name)
        except IOError:
            logger.error("Could not write range description file.", exc_info=True)
            return self.send_error(SERVER_ERROR, "Could not write range description file.")

        if not self.USE_CYRIS:
            # Simulation logic here if needed
            return self.send_json_response([{
                Storyboard.SERVER_STATUS_KEY: Storyboard.SERVER_STATUS_SUCCESS,
                Storyboard.SERVER_MESSAGE_KEY: "Simulated instantiation successful."
            }])

        success, result = instantiation.instantiate_range(
            self.CYRIS_PATH, self.CYPROM_PATH, self.CYRIS_CONFIG_FILENAME, self.CYRIS_RANGE_DIRECTORY,
            range_file_name, range_id, progression_scenario, self.DEBUG
        )
        if not success:
            instantiation.handle_cyris_error(self.CYRIS_PATH, self.CYRIS_CONFIG_FILENAME, range_id, self.DEBUG)

        self.build_and_send_response(success, result)

    def handle_destroy_range(self, params):
        """Handler for the 'destroy_range' action."""
        range_id = params.get(query.Parameters.RANGE_ID)
        if not range_id:
            return self.send_error(REQUEST_ERROR, "Invalid range_id")

        success, result = instantiation.destroy_range(
            self.CYRIS_PATH, self.CYRIS_CONFIG_FILENAME, range_id, self.DEBUG
        )
        self.build_and_send_response(success, result)

    def handle_get_cr_file(self, params, logic_func):
        """Generic handler for all GET_CR_* file reading actions."""
        range_id = params.get(query.Parameters.RANGE_ID)
        if not range_id:
            return self.send_error(REQUEST_ERROR, "Invalid range_id")

        success, result = logic_func(self.CYRIS_PATH, self.CYRIS_RANGE_DIRECTORY, range_id, self.DEBUG)
        self.build_and_send_response(success, result)

    def do_POST(self):
        params = query.Parameters(self)
        action = params.get(query.Parameters.ACTION)
        user_id = params.get(query.Parameters.USER)

        user_info = userinfo.UserInfo()
        if not user_info.parse_YAML_file(os.path.join(self.DATABASE_DIR, self.USERS_FILE)):
            return self.send_error(SERVER_ERROR, "User information issue")
        if not user_info.get_user(user_id):
            return self.send_error(REQUEST_ERROR, "Invalid user id")
        if action not in self.VALID_ACTIONS:
            return self.send_error(REQUEST_ERROR, "Invalid action")

        action_handlers = {
            query.Parameters.INSTANTIATE_RANGE: self.handle_instantiate_range,
            query.Parameters.DESTROY_RANGE: self.handle_destroy_range,
            query.Parameters.GET_CR_NOTIFICATION: lambda p: self.handle_get_cr_file(p, instantiation.get_cr_notification),
            query.Parameters.GET_CR_DETAILS: lambda p: self.handle_get_cr_file(p, instantiation.get_cr_details),
            query.Parameters.GET_CR_ENTRY_POINT: lambda p: self.handle_get_cr_file(p, instantiation.get_cr_entry_point),
            query.Parameters.GET_CR_CREATION_STATUS: lambda p: self.handle_get_cr_file(p, instantiation.get_cr_creation_status),
            query.Parameters.GET_CR_INITIF: lambda p: self.handle_get_cr_file(p, instantiation.get_cr_initif),
            query.Parameters.GET_CR_CREATION_LOG: lambda p: self.handle_get_cr_file(p, instantiation.get_cr_creation_log),
        }

        handler = action_handlers.get(action)
        if handler:
            handler(params)
        else:
            self.send_error(REQUEST_ERROR, f"Unknown action: {action}")

    def build_response(self, status, message=None):

        # Prepare status
        response_status = '"{0}": "{1}"'.format(Storyboard.SERVER_STATUS_KEY, status)

        # If a message exists we append it to the status, otherwise we
        # make an array with a dictionary containing only the status
        if message:
            response_message = '"{0}": "{1}"'.format(Storyboard.SERVER_MESSAGE_KEY, message)
            response_body = '[{' + response_status + ", " + response_message + '}]'
        else:
            response_body = '[{' + response_status + '}]'

        return response_body

    def handle_cyris_error(self, range_id):
        logger.info("Error occurred in CyRIS => perform cyber range cleanup.")
        destruction_filename = os.path.join(self.CYRIS_PATH, CYRIS_DESTRUCTION_SCRIPT)
        config_path = os.path.join(self.CYRIS_PATH, self.CYRIS_CONFIG_FILENAME)
        destruction_command = f"{destruction_filename} {range_id} {config_path}"
        logger.debug("destruction_command: %s", destruction_command)

        return_value = os.system(destruction_command)
        exit_status = os.WEXITSTATUS(return_value)
        if exit_status != 0:
            logger.error("Range cleanup failed for range_id %s.", range_id)

# Print usage information
def usage():
    print ("OVERVIEW: CyTrONE instantiation server that manages the CyRIS cyber range instantiation system.\n")
    print ("USAGE: instsrv.py [options]\n")
    print ("OPTIONS:")
    print ("-h, --help           Display help")
    print ("-n, --no-inst        Disable instantiation => only simulate actions")
    print ("-p, --path <PATH>    Set the location where CyRIS is installed")
    print ("-m, --cyprom <PATH>  Set the location where CyPROM is installed\n")


# Use threads to handle multiple clients
# Note: By using ForkingMixIn instead of ThreadingMixIn,
# separate processes are used instead of threads
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


#############################################################################
# Main program
#############################################################################
def main():
    """Main function to run the CyTrONE Instantiation Server."""
    parser = argparse.ArgumentParser(description="CyTrONE Instantiation Server.")
    parser.add_argument("-n", "--no-inst", action="store_true", help="Disable instantiation => only simulate actions")
    parser.add_argument("-p", "--path", help="Override the location where CyRIS is installed")
    parser.add_argument("-m", "--cyprom", help="Override the location where CyPROM is installed")
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
        no_inst_override=args.no_inst,
        path_override=args.path,
        cyprom_override=args.cyprom
    )

    # Append '/' to paths names if it is not present
    if RequestHandler.CYRIS_PATH and not RequestHandler.CYRIS_PATH.endswith("/"):
        RequestHandler.CYRIS_PATH += "/"
    if RequestHandler.CYPROM_PATH and not RequestHandler.CYPROM_PATH.endswith("/"):
        RequestHandler.CYPROM_PATH += "/"

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
        logger.info("CyTrONE instantiation server listens on %s:%d%s.",
            server_address, server_port, multi_threading)
        if not RequestHandler.USE_CYRIS:
            logger.info("CyRIS use is disabled => only simulate actions.")
        else:
            logger.info("Using CyRIS software installed in %s.", RequestHandler.CYRIS_PATH)
            logger.info("Using CyPROM software installed in %s.", RequestHandler.CYPROM_PATH)

        if SERVE_FOREVER:
            server.serve_forever()
        else:
            server.handle_request()

    # Deal with keyboard interrupts
    except KeyboardInterrupt:
        logger.info("Interrupted via ^C => shut down server.")
        server.socket.close()

    logger.info("CyTrONE instantiation server ended execution.")


#############################################################################
# Run server
if __name__ == "__main__":
    main()
