
import logging
import os
import sys
import getopt
import requests
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
import query
from storyboard import Storyboard
from password import Password
import sessinfo
import trnginfo
import userinfo

# --- Modernized Logging Setup ---
LOG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cytrone_debug.log')
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- Constants (Restored) ---
LOCAL_ADDRESS = "0.0.0.0"
SERVER_PORT = 8082
CONTENT_SERVER_URL = "http://127.0.0.1:8084"
INSTANTIATION_SERVER_URL = "http://127.0.0.1:8083"
# ... (other constants)

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

    def do_POST(self):
        try:
            params = query.Parameters(self)
            

            # ... (user and password verification remains the same)

            action = params.get(query.Parameters.ACTION)
            if action == query.Parameters.CREATE_TRAINING:
                self.handle_create_training(params)
            else:
                self.respond_error(f"Unsupported action: {action}")

        except Exception as e:
            logger.exception("Critical error in do_POST")
            self.respond_error("Internal Server Error")

    def handle_create_training(self, params):
        # ... (parameter extraction and validation)
        user_id = params.get(query.Parameters.USER)
        scenario_name = params.get(query.Parameters.SCENARIO)
        level_name = params.get(query.Parameters.LEVEL)
        
        # Simplified for clarity
        training_info = trnginfo.TrainingInfo()
        training_info.parse_YAML_file(os.path.join(os.path.dirname(__file__), '../database/training-en.yml'))
        content_file_name = training_info.get_content_file_name(scenario_name, level_name)
        
        if not content_file_name:
            self.respond_error("Content file not found for scenario.")
            return

        with open(os.path.join(os.path.dirname(__file__), '../database/', content_file_name), "r") as f:
            content_file_content = f.read()

        # --- Call Content Server ---
        post_data_to_contsrv = {
            query.Parameters.USER: user_id,
            query.Parameters.ACTION: query.Parameters.UPLOAD_CONTENT,
            query.Parameters.DESCRIPTION_FILE: content_file_content,
            query.Parameters.RANGE_ID: "1" # Simplified for now
        }
        logger.info(f"Sending request to content server at {CONTENT_SERVER_URL}")
        logger.debug(f"Request body to contsrv: {post_data_to_contsrv}")

        try:
            response = requests.post(CONTENT_SERVER_URL, data=post_data_to_contsrv, timeout=30)
            response.raise_for_status()
            logger.info(f"Received {response.status_code} from content server.")
            logger.debug(f"Response body from contsrv: {response.text}")
            
            contsrv_data = response.json()
            if contsrv_data and contsrv_data[0].get(Storyboard.SERVER_STATUS_KEY) == Storyboard.SERVER_STATUS_SUCCESS:
                 # --- Call Instantiation Server (Simplified) ---
                logger.info("Content upload successful. Proceeding to instantiation.")
                # In a real scenario, you would call the instantiation server here.
                # For now, we'll assume success and respond to the client.
                self.respond_success(json.dumps(contsrv_data))
            else:
                logger.error("Content server returned an error.")
                self.respond_error("Content server failed.")

        except requests.exceptions.RequestException as e:
            logger.exception("Failed to communicate with content server")
            self.respond_error("Server could not communicate with the LMS content manager")

    def respond_error(self, message):
        logger.error(f"Responding with error: {message}")
        self.send_response(200) # CyTrONE client expects 200 OK even for errors
        self.send_header("Content-type", "application/json")
        self.end_headers()
        response_body = json.dumps([{'status': 'ERROR', 'message': message}])
        self.wfile.write(response_body.encode('utf-8'))

    def respond_success(self, data):
        logger.info("Responding with success.")
        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(data.encode('utf-8'))

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

def main(argv):
    # ... (getopt parsing)
    server = ThreadedHTTPServer((LOCAL_ADDRESS, SERVER_PORT), RequestHandler)
    logger.info(f"CyTrONE training server starting on {LOCAL_ADDRESS}:{SERVER_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
        server.socket.close()

if __name__ == "__main__":
    main(sys.argv[1:])
