"""
Core business logic for the Instantiation Server (instsrv).
"""
import os
import urllib.parse
from typing import Dict, Any, Tuple
import logging

from .. import query
from ..storyboard import Storyboard

logger = logging.getLogger(__name__)

# These constants are part of the logic of how to interact with CyRIS artifacts.
CYRIS_STATUS_FILENAME = "cr_creation_status"
CYRIS_NOTIFICATION_TEMPLATE = "range_notification-cr{0}.txt"
CYRIS_DETAILS_TEMPLATE = "range_details-cr{0}.yml"
CYRIS_ENTRY_POINT_TEMPLATE = "entry_points.txt"
CYRIS_CREATION_STATUS_TEMPLATE = "cr_creation_status"
CYRIS_INITIF_TEMPLATE = "initif.conf"
CYRIS_CREATION_LOG_TEMPLATE = "creation.log"
CYRIS_DESTRUCTION_SCRIPT = "main/range_cleanup.py"

def _execute_command(command: str) -> bool:
    """Executes a shell command and returns True on success."""
    return_value = os.system(command)
    return os.WEXITSTATUS(return_value) == 0

def _read_cyris_file(
    cyris_path: str, range_dir: str, range_id: str, filename: str, do_debug: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """Helper to read a specific file from a CyRIS range directory."""
    file_path = os.path.join(cyris_path, range_dir, range_id, filename)
    if do_debug:
        print(f"* DEBUG: instsrv: Reading file: {file_path}")
    try:
        with open(file_path, 'r') as f:
            content = f.read()
        # The original code URL-encodes the message content.
        return True, {"message": urllib.parse.quote(content)}
    except FileNotFoundError:
        return False, {"message": f"File not found: {file_path}"}
    except IOError as e:
        return False, {"message": f"I/O error reading file: {e}"}

def instantiate_range(
    cyris_path: str, cyprom_path: str, cyris_config_filename: str, range_dir: str,
    range_file_name: str, range_id: str, progression_scenario: str, do_debug: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """Handles the logic for instantiating a cyber range."""
    command = f"python3 -u {os.path.join(cyris_path, 'main/cyris.py')} {range_file_name} {os.path.join(cyris_path, cyris_config_filename)}"
    if not _execute_command(command):
        # The handle_cyris_error logic from the original server should be called by the handler.
        return False, {"message": "CyRIS execution issue"}

    status_file = os.path.join(cyris_path, range_dir, range_id, CYRIS_STATUS_FILENAME)
    try:
        with open(status_file, 'r') as f:
            status_content = f.read()
        if Storyboard.SERVER_STATUS_SUCCESS not in status_content:
            return False, {"message": Storyboard.INSTANTIATION_STATUS_FILE_NOT_FOUND}
    except IOError:
        return False, {"message": Storyboard.INSTANTIATION_CYRIS_IO_ERROR}

    # Handle CyPROM if needed
    if progression_scenario:
        details_file = os.path.join(cyris_path, range_dir, range_id, CYRIS_DETAILS_TEMPLATE.format(range_id))
        cyprom_command = f"python3 -u {os.path.join(cyprom_path, 'main/cyprom.py')} --scenario {progression_scenario} --cyris {details_file} &"
        if not _execute_command(cyprom_command):
            return False, {"message": "CyPROM execution issue"}

    # Get notification message for the response
    return get_cr_notification(cyris_path, range_dir, range_id, do_debug)

def destroy_range(
    cyris_path: str, cyris_config_filename: str, range_id: str, do_debug: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """Handles the logic for destroying a cyber range."""
    destruction_script = os.path.join(cyris_path, CYRIS_DESTRUCTION_SCRIPT)
    config_path = os.path.join(cyris_path, cyris_config_filename)
    command = f"{destruction_script} {range_id} {config_path}"
    if do_debug:
        print(f"* DEBUG: instsrv: destruction_command: {command}")

    if _execute_command(command):
        return True, {}
    else:
        return False, {"message": "CyRIS destruction issue"}

def handle_cyris_error(
    cyris_path: str, cyris_config_filename: str, range_id: str, do_debug: bool = False
):
    """Cleanup logic for when a CyRIS error occurs."""
    logger.info("Error occurred in CyRIS => perform cyber range cleanup.")
    destroy_range(cyris_path, cyris_config_filename, range_id, do_debug)

def get_cr_notification(cyris_path, range_dir, range_id, do_debug=False):
    return _read_cyris_file(cyris_path, range_dir, range_id, CYRIS_NOTIFICATION_TEMPLATE.format(range_id), do_debug)

def get_cr_details(cyris_path, range_dir, range_id, do_debug=False):
    return _read_cyris_file(cyris_path, range_dir, range_id, CYRIS_DETAILS_TEMPLATE.format(range_id), do_debug)

def get_cr_entry_point(cyris_path, range_dir, range_id, do_debug=False):
    return _read_cyris_file(cyris_path, range_dir, range_id, CYRIS_ENTRY_POINT_TEMPLATE, do_debug)

def get_cr_creation_status(cyris_path, range_dir, range_id, do_debug=False):
    return _read_cyris_file(cyris_path, range_dir, range_id, CYRIS_CREATION_STATUS_TEMPLATE, do_debug)

def get_cr_initif(cyris_path, range_dir, range_id, do_debug=False):
    return _read_cyris_file(cyris_path, range_dir, range_id, CYRIS_INITIF_TEMPLATE, do_debug)

def get_cr_creation_log(cyris_path, range_dir, range_id, do_debug=False):
    return _read_cyris_file(cyris_path, range_dir, range_id, CYRIS_CREATION_LOG_TEMPLATE, do_debug)
