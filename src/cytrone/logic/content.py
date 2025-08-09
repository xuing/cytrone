"""
Core business logic for the Content Server (contsrv).
"""
import subprocess
import os
from typing import Dict, Any, Tuple
import logging

from .. import query
from ..storyboard import Storyboard

logger = logging.getLogger(__name__)

def upload_content(
    cylms_path: str,
    cylms_config: str,
    content_file_name: str,
    range_id: str,
    do_debug: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handles the logic for uploading content to the LMS via CyLMS.
    Returns a tuple of (success, result_dict).
    """
    try:
        command = [
            "python3", "-u", os.path.join(cylms_path, "cylms.py"),
            "--convert-content", content_file_name,
            "--config-file", cylms_config,
            "--add-to-lms", range_id
        ]
        add_output = subprocess.check_output(command, stderr=subprocess.STDOUT, text=True)

        activity_id = None
        for output_line in add_output.splitlines():
            print(output_line)
            activity_id_tag = "activity_id="
            if activity_id_tag in output_line:
                activity_id = output_line.split(activity_id_tag)[1]
                if do_debug:
                    print(f"* DEBUG: contsrv: Extracted activity id: {activity_id}")

        if activity_id:
            return True, {"activity_id": activity_id}
        else:
            return False, {"message": "LMS upload issue: could not find activity_id in CyLMS output."}

    except subprocess.CalledProcessError as error:
        logger.error("CyLMS execution failed.\nOutput:\n%s", error.output)
        return False, {"message": "CyLMS execution issue during upload."}
    except IOError as e:
        return False, {"message": f"LMS upload I/O error: {e}"}


def remove_content(
    cylms_path: str,
    cylms_config: str,
    range_id: str,
    activity_id: str,
    do_debug: bool = False
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handles the logic for removing content from the LMS via CyLMS.
    Returns a tuple of (success, result_dict).
    """
    try:
        config_arg = f" --config-file {cylms_config}"
        remove_arg = f" --remove-from-lms {range_id},{activity_id}"
        command = f"python3 -u {os.path.join(cylms_path, 'cylms.py')}{config_arg}{remove_arg}"

        if do_debug:
            print(f"* DEBUG: contsrv: command: {command}")

        return_value = os.system(command)
        exit_status = os.WEXITSTATUS(return_value)

        if exit_status == 0:
            return True, {}
        else:
            return False, {"message": "LMS content removal issue."}
    except IOError as e:
        return False, {"message": f"LMS content removal I/O error: {e}"}
