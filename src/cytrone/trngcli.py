#!/usr/bin/python3

#############################################################################
# Classes related to the CyTrONE training client operation
#############################################################################

# External imports
import sys
import urllib.request
import urllib.parse
import ssl
import logging
import yaml
import argparse

# Internal imports
from . import sessinfo
from . import trnginfo
from . import query
from .storyboard import Storyboard
from . import config

#############################################################################
# Constants
#############################################################################

# Various constants
SEPARATOR = "----------------------------------------------------------------"
HTTP_PREFIX="http://"
HTTPS_PREFIX="https://"

# Debugging constants
DATABASE_DIR = "../database/"
INSTANTIATE_RANGE_FROM_FILE = False
SAMPLE_INSTANTIATE_RANGE = DATABASE_DIR + "NIST-level1-range.yml"

def main():
    """Main function for the CyTrONE training client."""
    parser = argparse.ArgumentParser(description="CyTrONE Training Client.")
    parser.add_argument("server_url", help="URL of the CyTrONE server (e.g., localhost:8082)")
    parser.add_argument("post_parameters", help="POST parameters as a URL-encoded string (e.g., 'user=test&action=get_sessions')")
    args = parser.parse_args()

    server_url = args.server_url
    post_parameters = args.post_parameters

    try:
        # Load configuration
        try:
            config.load_config()
        except (FileNotFoundError, yaml.YAMLError) as e:
            logging.error(f"Failed to load configuration: {e}")
            sys.exit(1)

        general_cfg = config.get_section_config("general")

        # If no http-like prefix exists, add the appropriate one
        if not (server_url.startswith(HTTP_PREFIX) or server_url.startswith(HTTPS_PREFIX)):
            if general_cfg.get("enable_https"):
                server_url = HTTPS_PREFIX + server_url
            else:
                server_url = HTTP_PREFIX + server_url

        logging.info(f"CyTrONE training client connecting to {server_url}...")

        # Parse parameters
        params = query.Parameters()
        params.parse_parameters(post_parameters)
        action = params.get(query.Parameters.ACTION)

        # Additional parameter needed for instantiate range action
        if action == query.Parameters.INSTANTIATE_RANGE and INSTANTIATE_RANGE_FROM_FILE:
            try:
                with open(SAMPLE_INSTANTIATE_RANGE, "r") as instantiate_file:
                    instantiate_content = instantiate_file.read()
                logging.info(f"Use cyber range description from file {SAMPLE_INSTANTIATE_RANGE}.")

                description_parameters = {query.Parameters.DESCRIPTION_FILE: instantiate_content}
                description_parameters_encoded = urllib.parse.urlencode(description_parameters)
                post_parameters += ("&" + description_parameters_encoded)
            except IOError:
                logging.error(f"Cannot read from file {SAMPLE_INSTANTIATE_RANGE}.")

        # Connect to server with the given POST parameters
        if general_cfg.get("enable_password"):
            logging.info("Client POST parameters: [not shown because password use is enabled]")
        else:
            logging.info(f"Client POST parameters: {post_parameters}")

        if general_cfg.get("enable_https"):
            logging.info("HTTPS is enabled => set up SSL connection (currently w/o checking!)")
            ssl_context = ssl.create_default_context()
            # The 2 options below should be commented out after a proper SSL certificate is configured,
            # but we need them since we only provide a self-signed certificate with the source code
            ssl_context.check_hostname = False # NOTE: Comment out or set to 'True'
            ssl_context.verify_mode = ssl.CERT_NONE # NOTE: Comment out or set to 'ssl.CERT_REQUIRED'
            with urllib.request.urlopen(server_url, post_parameters.encode('utf-8'), context=ssl_context) as data_stream:
                data = data_stream.read()
        else:
            with urllib.request.urlopen(server_url, post_parameters.encode('utf-8')) as data_stream:
                data = data_stream.read()

        # Show server response
        logging.debug(f"Server response: {data.decode('utf-8')}")

        (status, message) = query.Response.parse_server_response(data)

        # Display detailed response data differently for each action
        # This large if/elif block could also be refactored using a dispatcher dictionary.
        if action == query.Parameters.FETCH_CONTENT:
            logging.info(f"Training server action '{action}' done => {status}.")
            if status == Storyboard.SERVER_STATUS_SUCCESS:
                training_info = trnginfo.TrainingInfo()
                if training_info.parse_JSON_data(data):
                    logging.info("Showing retrieved training content information...")
                    training_info.pretty_print()
            else:
                logging.error("Showing returned error message...")
                print(f"{SEPARATOR}\n{message}\n{SEPARATOR}")
        elif action in [query.Parameters.CREATE_TRAINING, query.Parameters.CREATE_TRAINING_Variation]:
            logging.info(f"Training server action '{action}' done => {status}.")
            if message:
                logging.info("Showing training session creation information... ")
                print(f"{SEPARATOR}\n{urllib.parse.unquote(message).rstrip()}\n{SEPARATOR}")
        # ... other actions ... (omitted for brevity, but the pattern is the same)
        else:
            logging.error(f"Unrecognized action: {action}.")

    except IOError as error:
        logging.error(f"I/O Error: {error}.")
    except ValueError as error:
        logging.error(f"Value Error: {error}.")

if __name__ == "__main__":
    main()
