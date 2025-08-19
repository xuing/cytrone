
import logging
from http.server import BaseHTTPRequestHandler, HTTPServer
import time
import random
import subprocess
import os
import sys
import getopt
from socketserver import ThreadingMixIn
import query
from storyboard import Storyboard

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

# --- Constants ---
LOCAL_ADDRESS = "0.0.0.0"
SERVER_PORT = 8084
# ... (other constants remain the same)
CYLMS_PATH = ""
CYLMS_CONFIG = ""

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

    def do_POST(self):
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            params = query.Parameters(self)
            logger.debug(f"Received POST request with params: {params.params}")

            action = params.get(query.Parameters.ACTION)
            range_id = params.get(query.Parameters.RANGE_ID)
            description_file_content = params.get(query.Parameters.DESCRIPTION_FILE)

            if action == query.Parameters.UPLOAD_CONTENT:
                self.handle_upload(params)
            else:
                logger.warning(f"Unknown action received: {action}")
                self.send_error(400, "Invalid Action")

        except Exception as e:
            logger.exception("Critical error in do_POST")
            self.send_error(500, "Internal Server Error")

    def handle_upload(self, params):
        range_id = params.get(query.Parameters.RANGE_ID)
        description_file_content = params.get(query.Parameters.DESCRIPTION_FILE)
        content_file_name = f"/tmp/tmp_content_description-{range_id}.yml"

        with open(content_file_name, "w") as f:
            f.write(description_file_content)
        logger.info(f"Saved content description to {content_file_name}")

        cmd = [
            "python3", "-u", os.path.join(CYLMS_PATH, "cylms.py"),
            "--convert-content", content_file_name,
            "--config-file", CYLMS_CONFIG,
            "--add-to-lms", range_id
        ]

        logger.info(f"Executing CyLMS command: {' '.join(cmd)}")
        try:
            process = subprocess.run(
                cmd, capture_output=True, text=True, check=True, timeout=60
            )
            logger.debug(f"CyLMS stdout: {process.stdout}")
            activity_id = self.extract_activity_id(process.stdout)

            if activity_id:
                logger.info(f"Successfully created activity with ID: {activity_id}")
                response_content = f'[{{"{Storyboard.SERVER_STATUS_KEY}": "{Storyboard.SERVER_STATUS_SUCCESS}", "{Storyboard.SERVER_ACTIVITY_ID_KEY}": "{activity_id}"}}]'
                self.send_response(200)
                self.send_header("Content-type", "application/json")
                self.end_headers()
                self.wfile.write(response_content.encode('utf-8'))
            else:
                logger.error("Failed to extract activity_id from CyLMS output.")
                self.send_error(500, "LMS Upload Issue: No Activity ID")

        except subprocess.CalledProcessError as e:
            logger.error(f"CyLMS execution failed with exit code {e.returncode}")
            logger.error(f"CyLMS stderr: {e.stderr}")
            logger.error(f"CyLMS stdout: {e.stdout}")
            self.send_error(500, f"CyLMS Execution Failed: {e.stderr[:100]}")
        except subprocess.TimeoutExpired:
            logger.error("CyLMS command timed out.")
            self.send_error(500, "CyLMS Timeout")

    def extract_activity_id(self, output):
        for line in output.splitlines():
            if "activity_id=" in line:
                return line.split("activity_id=")[1].strip()
        return None

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    pass

def main(argv):
    global CYLMS_PATH, CYLMS_CONFIG
    # ... (getopt parsing remains the same)
    try:
        opts, args = getopt.getopt(argv, "hnp:c:", ["help", "no-lms", "path=", "config="])
    except getopt.GetoptError as err:
        logger.error(f"Command-line argument error: {err}")
        sys.exit(1)
    for opt, arg in opts:
        if opt == '--path':
            CYLMS_PATH = arg
        elif opt == '--config':
            CYLMS_CONFIG = arg

    if not CYLMS_PATH or not CYLMS_CONFIG:
        logger.error("CYLMS_PATH and CYLMS_CONFIG must be provided.")
        sys.exit(1)

    server = ThreadedHTTPServer((LOCAL_ADDRESS, SERVER_PORT), RequestHandler)
    logger.info(f"CyTrONE content server starting on {LOCAL_ADDRESS}:{SERVER_PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Server shutting down.")
        server.socket.close()

if __name__ == "__main__":
    main(sys.argv[1:])
