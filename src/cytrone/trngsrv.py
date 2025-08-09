#!/usr/bin/python3

#############################################################################
# Classes related to the CyTrONE training server operation
#############################################################################

# External imports
from http.server import BaseHTTPRequestHandler, HTTPServer
import ssl
import urllib.request
import time
import random
import sys
import getopt
from socketserver import ThreadingMixIn
import threading
from string import Template
import yaml
import logging
import re
import os
import json

# Internal imports
from . import userinfo
from . import trnginfo
from . import sessinfo
from . import query
from .storyboard import Storyboard
from .password import Password
from . import config
from .logic import trng

#############################################################################
# Constants
#############################################################################

CYTRONE_VERSION = "1.3"

# Web server constants
HTTP_STATUS_OK = 200
REQUEST_ERROR = 404
SERVER_ERROR  = 500
LOCAL_SERVER  = True # Change between accepting any or only local connections
SERVE_FOREVER = True # Use serve count if not using local server?!

# Debugging constants
DEBUG = False
EMULATE_DELAY = False

#############################################################################
# Manage the training server functionality
#############################################################################
class RequestHandler(BaseHTTPRequestHandler):

    # List of valid actions recognized by the training server
    VALID_ACTIONS = [query.Parameters.FETCH_CONTENT,
                     query.Parameters.CREATE_TRAINING,
                     query.Parameters.GET_CONFIGURATIONS,
                     query.Parameters.GET_SESSIONS,
                     query.Parameters.END_TRAINING,
                     query.Parameters.CREATE_TRAINING_Variation,
                     query.Parameters.GET_CR_CREATION_LOG,
                     query.Parameters.END_TRAINING_Variation]

    # List of valid languages recognized by the training server
    VALID_LANGUAGES = [query.Parameters.EN,
                     query.Parameters.JA]

    # List of sessions which are pending (being instantiated, etc.)
    pending_sessions = []

    # Locks for synchronizing access to shared resources, as follows:
    # - lock_active_sessions: active sessions list (and related variables: pending_sessions, cyber_range_id)
    # - lock_saved_configurations: saved configurations list
    lock_active_sessions = threading.Lock()
    lock_saved_configurations = threading.Lock()

    #########################################################################
    # Print log messages with custom format
    # Default format is shown below:
    #     127.0.0.1 - - [22/Jun/2016 14:47:56] "POST / HTTP/1.0" 200 -
    def log_message(self, format, *args):
        (client_host, client_port) = self.client_address
        print("* INFO: trngsrv: Server response to client %s - - [%s] %s" %
              (client_host, self.log_date_time_string(), format%args))

    @classmethod
    def setup_config(cls):
        """Sets up the configuration for the request handler."""
        cls.cfg = config.get_section_config("trngsrv")
        cls.general_cfg = config.get_section_config("general")
        cls.ssl_cfg = config.get_section_config("ssl")

        # Make some config values available to the instance for convenience
        # TODO: This is not ideal, a better solution would be to pass the config around
        # or use a more structured approach.
        cls.DEBUG = cls.general_cfg.get("debug", False)
        cls.EMULATE_DELAY = cls.general_cfg.get("emulate_delay", False)
        cls.DATABASE_DIR = cls.general_cfg.get("database_dir", "../database/")

        files = cls.cfg.get("files", {})
        cls.USERS_FILE = files.get("users", "users.yml")
        cls.SCENARIOS_FILE_EN = files.get("scenarios_en", "training-en.yml")
        cls.SCENARIOS_FILE_JA = files.get("scenarios_ja", "training-ja.yml")
        cls.SAVED_CONFIGURATIONS_FILE = files.get("saved_configurations", "saved_configurations.yml")
        cls.ACTIVE_SESSIONS_FILE = files.get("active_sessions", "active_sessions.yml")

        cls.CONTENT_SERVER_URL = cls.cfg.get("content_server_url")
        cls.INSTANTIATION_SERVER_URL = cls.cfg.get("instantiation_server_url")
        cls.MAX_SESSIONS = cls.cfg.get("max_sessions", 100)


    #########################################################################
    # Various functions for cyber range id generation

    ## Hexadecimal id [not in use]
    def generate_id_hexadecimal(self):
        # Create a 6-digit hexadecimal id
        RANDOM_ID_LENGTH = 6
        cyber_range_id = "%0*x" % (RANDOM_ID_LENGTH, random.randrange(16**RANDOM_ID_LENGTH))
        return cyber_range_id

    ## Random decimal id in given range [not in use]
    def generate_id_random(self):
        # Create a 3-digit decimal id that is fit for
        # becoming the first byte in an IPv4 address
        # Reference: https://en.wikipedia.org/wiki/Reserved_IP_addresses
        invalid_bytes = [10, 100, 127, 169, 172, 192, 198, 203]
        done = False
        while not done:
            cyber_range_id = random.randint(1,223)
            if cyber_range_id not in invalid_bytes:
                done = True
        return cyber_range_id

    ## Decimal id between 1 and MAX_SESSIONS with lowest available value [not in use]
    ## (pending session ids are avoided)
    ## NOTE: Requires synchronization for active sessions list
    def generate_id_max_sessions_lowest(self, pending_sessions):
        cyber_range_id = None
        # Read current session info
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(self.ACTIVE_SESSIONS_FILE)
        for id in range(1, self.MAX_SESSIONS + 1):
            # Check that id (as string) is _not_ already used for an existing or pending session
            if not (session_info.is_session_id(str(id))
                    or str(id) in pending_sessions):
                cyber_range_id = id
                break
        # Returned value should be an integer
        return cyber_range_id

    ## Decimal id between 1 and MAX_SESSIONS with next available value [in use]
    ## (if next value is unavailable, use lowest; pending session ids are avoided)
    ## NOTE: Requires synchronization for active sessions list
    def generate_id_max_sessions_next(self, pending_sessions):
        cyber_range_id = None
        # Read current session info
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(self.ACTIVE_SESSIONS_FILE)
        # For set operations we need to represent ids as integer,
        # not as string as stored internally
        possible_set = set(range(self.MAX_SESSIONS + 1)) # All possible values
        invalid_set = set([0]) # Invalid values if any
        unavailable_set = invalid_set.union(session_info.get_id_list_int()) # Union with active sessions
        pending_set = set(map(int, pending_sessions))
        unavailable_set = unavailable_set.union(pending_set) # Union with pending sessions
        max_unavailable_value = max(unavailable_set)
        available_set = possible_set.difference(unavailable_set) # Usable values
        if (max_unavailable_value+1) in available_set:
            cyber_range_id = (max_unavailable_value+1)
        elif available_set:
            cyber_range_id = min(available_set)
            # Otherwise we'll return the None value set at the beginning
        # Returned value should be an integer
        return cyber_range_id

    #########################################################################
    # Generate a cyber range id
    def generate_cyber_range_id(self, pending_sessions):

        return self.generate_id_max_sessions_next(pending_sessions)

    #########################################################################
    # Check whether a range with the given id is active for the
    # specified user_id;
    # Return the activity id if session was found, None otherwise
    # Note: Requires synchronization for active sessions list
    def check_range_id_exists(self, range_id, user_id):

        # Read current session info
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(ACTIVE_SESSIONS_FILE)

        # Check if the given range id (as string) is already used
        if session_info.is_session_id_user(range_id, user_id):
            return session_info.get_activity_id(range_id, user_id)
        else:
            return None

    #########################################################################
    # Check whether a range with the given id is active for the
    # specified user_id;
    # Return the activity id if session was found, None otherwise
    # Note: Requires synchronization for active sessions list
    def check_range_id_and_activity_id_exists(self, range_id, user_id):
        # Read current session info
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(ACTIVE_SESSIONS_FILE)

        # Check if the given range id (as string) is already used
        if session_info.is_session_id_user(range_id, user_id):
            return session_info.get_activity_id_list(range_id, user_id)
        else:
            return None

    def handle_fetch_content(self, params, **kwargs):
        """Handler for the 'fetch_content' action."""
        language = params.get(query.Parameters.LANG)
        success, result = trng.fetch_content(language)
        if success:
            self.respond_success(result.get('data'))
        else:
            self.respond_error(result.get('message'))

    def handle_create_training(self, params, user_obj, training_info, variation=False):
        """Handler for the 'create_training' and 'create_training_variation' actions."""
        # 1. Validate parameters
        instance_count_str = params.get(query.Parameters.COUNT)
        ttype = params.get(query.Parameters.TYPE)
        scenario = params.get(query.Parameters.SCENARIO)
        level = params.get(query.Parameters.LEVEL)
        language = params.get(query.Parameters.LANG)

        if not instance_count_str:
            return self.respond_error(Storyboard.INSTANCE_COUNT_MISSING_ERROR)
        try:
            instance_count = int(instance_count_str)
        except ValueError:
            return self.respond_error(Storyboard.INSTANCE_COUNT_INVALID_ERROR)
        if not ttype:
            return self.respond_error(Storyboard.TRAINING_TYPE_MISSING_ERROR)
        if not scenario:
            return self.respond_error(Storyboard.SCENARIO_NAME_MISSING_ERROR)
        if not level:
            return self.respond_error(Storyboard.LEVEL_NAME_MISSING_ERROR)

        # 2. Generate session ID and manage pending list
        self.lock_active_sessions.acquire()
        try:
            cyber_range_id = self.generate_cyber_range_id(self.pending_sessions)
            if not cyber_range_id:
                self.respond_error(Storyboard.SESSION_ALLOCATION_ERROR)
                return
            cyber_range_id = str(cyber_range_id)
            self.pending_sessions.append(cyber_range_id)
            logger.info(f"Allocated session with ID #{cyber_range_id}.")
        finally:
            self.lock_active_sessions.release()

        # 3. Call the appropriate logic function
        if variation:
            logic_func = trng.create_training_variation
            logic_kwargs = {'lock': self.lock_active_sessions, 'ttype': ttype, 'language': language}
        else:
            logic_func = trng.create_training
            logic_kwargs = {}

        success, result = logic_func(
            cyber_range_id=cyber_range_id, user=user_obj, training_info=training_info,
            instance_count=instance_count, scenario=scenario, level=level, **logic_kwargs
        )

        # 4. Handle result
        self.removePendingSession(cyber_range_id)
        if not success:
            return self.respond_error(result.get("message", "Unknown error during training creation."))

        # For non-variation, we save the session here.
        # For variation, session is saved inside the logic function loop.
        if not variation:
            session_name = f"Training Session #{cyber_range_id}"
            crt_time = time.asctime()
            logger.info(f"Instantiation successful, saving session: {session_name} (time: {crt_time}).")

            save_success = trng.save_session(
                lock=self.lock_active_sessions, session_name=session_name, cyber_range_id=cyber_range_id,
                user_id=user_obj.id, crt_time=crt_time, ttype=ttype, scenarios=[scenario],
                levels=[level], language=language, instance_count=instance_count_str,
                activity_id=result.get("activity_id")
            )
            if not save_success:
                return self.respond_error(Storyboard.SESSION_INFO_CONSISTENCY_ERROR)

        message = result.get("message")
        self.respond_success({"message": message} if message else None)

    def handle_get_sessions(self, params, user_obj, **kwargs):
        """Handler for the 'get_sessions' action."""
        success, result = trng.get_sessions(self.lock_active_sessions, user_obj.id)
        if success:
            self.respond_success(result.get('data'))
        else:
            self.respond_error(result.get('message'))

    def handle_get_configurations(self, params, user_obj, **kwargs):
        """Handler for the 'get_configurations' action."""
        success, result = trng.get_configurations(self.lock_saved_configurations, user_obj.id)
        if success:
            self.respond_success(result.get('data'))
        else:
            self.respond_error(result.get('message'))

    def handle_end_training(self, params, user_obj, **kwargs):
        """Handler for the 'end_training' action."""
        range_id = params.get(query.Parameters.RANGE_ID)
        if not range_id:
            return self.respond_error(Storyboard.SESSION_ID_MISSING_ERROR)

        success, result = trng.end_training(self.lock_active_sessions, range_id, user_obj.id)
        if success:
            self.respond_success()
        else:
            self.respond_error(result.get("message", "Unknown error during training termination."))

    def handle_end_training_variation(self, params, user_obj, **kwargs):
        """Handler for the 'end_training_variation' action."""
        range_id = params.get(query.Parameters.RANGE_ID)
        if not range_id:
            return self.respond_error(Storyboard.SESSION_ID_MISSING_ERROR)

        success, result = trng.end_training_variation(self.lock_active_sessions, range_id, user_obj.id)
        if success:
            self.respond_success()
        else:
            self.respond_error(result.get("message", "Unknown error during training termination."))

    def do_POST(self):
        """Handles all POST requests by dispatching to action-specific handlers."""
        params = query.Parameters(self)
        # Get and validate common parameters
        user_id = params.get(query.Parameters.USER)
        password = params.get(query.Parameters.PASSWORD)
        action = params.get(query.Parameters.ACTION)
        language = params.get(query.Parameters.LANG)

        if self.general_cfg.get("enable_password"):
            logger.info("Request POST parameters: [not shown because password use is enabled]")
        else:
            logger.info("Request POST parameters: %s", params)

        # --- Validation ---
        user_info = userinfo.UserInfo()
        if not user_info.parse_YAML_file(os.path.join(self.DATABASE_DIR, self.USERS_FILE)):
            return self.respond_error(Storyboard.USER_SETTINGS_LOADING_ERROR)

        user_obj = user_info.get_user(user_id)
        if not user_obj:
            return self.respond_error(Storyboard.USER_ID_INVALID_ERROR)

        if self.general_cfg.get("enable_password"):
            if not user_obj.password:
                return self.respond_error(Storyboard.USER_PASSWORD_NOT_IN_DATABASE_ERROR)
            if not password or not Password.verify(password, user_obj.password):
                return self.respond_error(Storyboard.USER_ID_PASSWORD_INVALID_ERROR)

        if not action or action not in self.VALID_ACTIONS:
            return self.respond_error(Storyboard.ACTION_INVALID_ERROR)

        if not language or language not in self.VALID_LANGUAGES:
            return self.respond_error(Storyboard.LANGUAGE_INVALID_ERROR)

        # --- Load training_info (needed by many handlers) ---
        training_info = trnginfo.TrainingInfo()
        if language == query.Parameters.JA:
            filename = self.SCENARIOS_FILE_JA
        else:
            filename = self.SCENARIOS_FILE_EN
        training_settings_file = os.path.join(self.DATABASE_DIR, filename)
        if not training_info.parse_YAML_file(training_settings_file):
            return self.respond_error(Storyboard.TRAINING_SETTINGS_LOADING_ERROR)

        # --- Dispatcher ---
        action_handlers = {
            query.Parameters.FETCH_CONTENT: self.handle_fetch_content,
            query.Parameters.CREATE_TRAINING: self.handle_create_training,
            query.Parameters.CREATE_TRAINING_Variation: lambda p, u, t: self.handle_create_training(p, u, t, variation=True),
            query.Parameters.GET_SESSIONS: self.handle_get_sessions,
            query.Parameters.GET_CONFIGURATIONS: self.handle_get_configurations,
            query.Parameters.END_TRAINING: self.handle_end_training,
            query.Parameters.END_TRAINING_Variation: self.handle_end_training_variation,
        }

        handler = action_handlers.get(action)
        if handler:
            handler(params=params, user_obj=user_obj, training_info=training_info)
        else:
            logger.warning(f"Unknown or un-refactored action: {action}")
            self.respond_error(f"Unknown or unsupported action: {action}")

    def removePendingSession(self, cyber_range_id):
        # Synchronize access to active sessions list related variable
        self.lock_active_sessions.acquire()
        try:
            self.pending_sessions.remove(cyber_range_id)
        finally:
            self.lock_active_sessions.release()

    def respond_success(self, data=None):
        """
        Sends a successful (200) response to the client, embedding the
        status in the JSON payload.
        """
        self.send_response(HTTP_STATUS_OK)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_payload = {Storyboard.SERVER_STATUS_KEY: Storyboard.SERVER_STATUS_SUCCESS}
        if data:
            # This handles the case where data is a list of dicts,
            # and we need to merge the status into the first one.
            if isinstance(data, list) and len(data) > 0 and isinstance(data[0], dict):
                data[0].update(response_payload)
                response_payload = data
            elif isinstance(data, dict):
                 data.update(response_payload)
                 response_payload = [data]
            else:
                 # Fallback for unexpected data types
                 response_payload.update({"data": data})
                 response_payload = [response_payload]
        else:
            response_payload = [response_payload]

        response_body = json.dumps(response_payload)
        self.wfile.write(response_body.encode('utf-8'))
        print(f"* INFO: trngsrv: Server response body: {response_body}")
        print(Storyboard.SEPARATOR2)


    def respond_error(self, message, status_code=HTTP_STATUS_OK):
        """
        Sends an error response to the client. The HTTP status code is
        usually 200, with the error details in the JSON payload.
        """
        self.send_response(status_code)
        self.send_header("Content-type", "application/json")
        self.end_headers()

        response_payload = [{
            Storyboard.SERVER_STATUS_KEY: Storyboard.SERVER_STATUS_ERROR,
            "message": message
        }]

        response_body = json.dumps(response_payload)
        self.wfile.write(response_body.encode('utf-8'))
        print(f"* INFO: trngsrv: Server response body: {response_body}")
        print(Storyboard.SEPARATOR2)

    #########################################################################
    # POST request to another server (the instantiation server)
    #def post_request():
    #    # Initialize variables
    #    POST_parameters = None


# Print usage information
def usage():
    print ("OVERVIEW: CyTrONE training server that manages the content and instantiation servers.\n")
    print ("USAGE: trngsrv.py [options]\n")

    print ("OPTIONS:")
    print ("-h, --help         Display help\n")


# Use threads to handle multiple clients
# Note: By using ForkingMixIn instead of ThreadingMixIn,
# separate processes are used instead of threads
class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle requests in a separate thread."""


#############################################################################
# Main program
#############################################################################
def main():
    """Main function to run the CyTrONE Training Server."""
    parser = argparse.ArgumentParser(description=f"CyTrONE v{CYTRONE_VERSION}: Integrated cybersecurity training framework")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging (DEBUG level)")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=log_level, format='* %(levelname)s: %(name)s: %(message)s')
    logger = logging.getLogger(__name__)

    logger.info(Storyboard.SEPARATOR3)
    logger.info(f"CyTrONE v{CYTRONE_VERSION}: Integrated cybersecurity training framework")
    logger.info(Storyboard.SEPARATOR3)

    # Load configuration
    try:
        config.load_config()
    except (FileNotFoundError, yaml.YAMLError) as e:
        logger.error(f"Failed to load configuration: {e}")
        sys.exit(1)

    # Setup handler config
    RequestHandler.setup_config()
    cfg = RequestHandler.cfg
    general_cfg = RequestHandler.general_cfg
    ssl_cfg = RequestHandler.ssl_cfg

    try:
        # Configure the web server
        if LOCAL_SERVER:
            server_address = cfg.get("host")
        else:
            server_address=""
        server_port = cfg.get("port")

        multi_threading = ""
        if cfg.get("enable_threads"):
            server = ThreadedHTTPServer((server_address, server_port),
                                        RequestHandler)
            multi_threading = " (multi-threading mode)"
        else:
            server = HTTPServer((server_address, server_port), RequestHandler)

        # Use SSL socket if HTTPS is enabled
        if general_cfg.get("enable_https"):
            logger.info("HTTPS is enabled => set up SSL socket")
            key = ssl_cfg.get("keyfile")
            crt = ssl_cfg.get("certfile")
            ca_certs = ssl_cfg.get("ca_certs")

            if os.path.isfile(key):
                logger.info(f"Use keyfile: {key}")
            if os.path.isfile(crt):
                logger.info(f"Use certfile: {crt}")
            if ca_certs and os.path.isfile(ca_certs):
                logger.info(f"Use ca_certs: {ca_certs}")

            try:
                # Create an SSL context, load the certificates, and disable old TLS versions
                ssl_context = ssl.create_default_context(purpose=ssl.Purpose.CLIENT_AUTH)
                ssl_context.load_cert_chain(crt, key)
                ssl_context.options |= ssl.OP_NO_TLSv1
                ssl_context.options |= ssl.OP_NO_TLSv1_1
                # Create socket wrapped in SSL based on context
                server.socket = ssl_context.wrap_socket (server.socket, server_side=True)
            except Exception as error:
                logger.error(f"{error}")
                logger.warning("Can't set up SSL socket => HTTPS disabled")
                # In a real app, we might want to exit here if HTTPS is required.
            finally:
                logger.info("Setup for HTTP(S) server done")

        # Start web server
        logger.info(f"CyTrONE training server listens on {server_address}:{server_port}{multi_threading}.")
        if SERVE_FOREVER:
            server.serve_forever()
        else:
            server.handle_request()

    # Deal with keyboard interrupts
    except KeyboardInterrupt:
        logger.info("Interrupted via ^C => shut down server.")
        server.socket.close()

    logger.info("CyTrONE training server ended execution.")

#############################################################################
# Run server
if __name__ == "__main__":
    main()
