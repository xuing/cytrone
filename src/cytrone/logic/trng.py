"""
Core business logic for the Training Server (trngsrv).
"""
from typing import Dict, Any, Tuple, Optional, List
import os
import urllib.request
import urllib.parse
import json
import threading
import time
import logging

from .. import trnginfo, userinfo, sessinfo, query
from .. import config
from ..storyboard import Storyboard

logger = logging.getLogger(__name__)

def fetch_content(language: str) -> Tuple[bool, Dict[str, Any]]:
    """
    Fetches the training content information based on the language.
    """
    cfg = config.get_section_config("trngsrv")
    general_cfg = config.get_section_config("general")
    db_dir = general_cfg.get("database_dir")
    files = cfg.get("files", {})

    if language == 'ja':
        filename = files.get('scenarios_ja')
    else:
        filename = files.get('scenarios_en')

    training_settings_file = os.path.join(db_dir, filename)

    training_info = trnginfo.TrainingInfo()
    if not training_info.parse_YAML_file(training_settings_file):
        return False, {"message": Storyboard.TRAINING_SETTINGS_LOADING_ERROR}

    response_data = json.loads(training_info.get_JSON_representation())
    return True, {"data": response_data}


def save_session(
    lock: threading.Lock,
    session_name: str,
    cyber_range_id: str,
    user_id: str,
    crt_time: str,
    ttype: str,
    scenarios: List[str],
    levels: List[str],
    language: str,
    instance_count: str,
    activity_id: str
) -> bool:
    """Saves a new session to the active sessions file."""
    cfg = config.get_section_config("trngsrv")
    files = cfg.get("files", {})
    db_dir = config.get_section_config("general").get("database_dir")
    active_sessions_file = os.path.join(db_dir, files.get("active_sessions"))

    lock.acquire()
    try:
        session_info = sessinfo.SessionInfo()
        # parse_YAML_file handles non-existent file gracefully
        session_info.parse_YAML_file(active_sessions_file)

        session_info.add_session(
            session_name, cyber_range_id, user_id, crt_time, ttype,
            scenarios, levels, language, instance_count, activity_id
        )

        if not session_info.write_YAML_file(active_sessions_file):
            logger.error("Failed to write to active sessions file: %s", active_sessions_file)
            return False

    except Exception as e:
        logger.error("An exception occurred while saving session: %s", e)
        return False
    finally:
        lock.release()


def end_training(lock: threading.Lock, range_id: str, user_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Handles the logic for the 'end_training' action."""
    cfg = config.get_section_config("trngsrv")
    content_server_url = cfg.get("content_server_url")
    instantiation_server_url = cfg.get("instantiation_server_url")
    db_dir = config.get_section_config("general").get("database_dir")
    active_sessions_file = os.path.join(db_dir, cfg.get("files", {}).get("active_sessions"))

    # 1. Check session and get activity_id
    lock.acquire()
    try:
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(active_sessions_file)
        activity_id = session_info.get_activity_id(range_id, user_id)
        if not activity_id:
            return False, {"message": f"Session with ID {range_id} doesn't exist for user {user_id}"}
    finally:
        lock.release()

    # 2. Remove content from LMS
    try:
        query_tuples = {
            query.Parameters.USER: user_id,
            query.Parameters.ACTION: query.Parameters.REMOVE_CONTENT,
            query.Parameters.RANGE_ID: range_id,
            query.Parameters.ACTIVITY_ID: activity_id
        }
        query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
        with urllib.request.urlopen(content_server_url, query_params) as data_stream:
            data = data_stream.read().decode('utf-8')

        if Storyboard.SERVER_STATUS_SUCCESS not in data:
            logger.error("Content removal error.")
            return False, {"message": Storyboard.CONTENT_REMOVAL_ERROR}
    except IOError as e:
        logger.error("URL error during content removal: %s", e)
        return False, {"message": Storyboard.CONTENT_SERVER_ERROR}

    # 3. Destroy range from CyRIS
    try:
        query_tuples = {
            query.Parameters.USER: user_id,
            query.Parameters.ACTION: query.Parameters.DESTROY_RANGE,
            query.Parameters.RANGE_ID: range_id
        }
        query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
        with urllib.request.urlopen(instantiation_server_url, query_params) as data_stream:
            data = data_stream.read()

        status, _ = query.Response.parse_server_response(data)
        if status != Storyboard.SERVER_STATUS_SUCCESS:
            return False, {"message": Storyboard.DESTRUCTION_ERROR}
    except IOError as e:
        logger.error("URL error during range destruction: %s", e)
        return False, {"message": Storyboard.INSTANTIATION_SERVER_ERROR}

    # 4. Remove session from file
    lock.acquire()
    try:
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(active_sessions_file)
        if not session_info.remove_session(range_id, user_id):
             return False, {"message": Storyboard.SESSION_INFO_CONSISTENCY_ERROR}
        session_info.write_YAML_file(active_sessions_file)
    finally:
        lock.release()

    return True, {}


def end_training_variation(lock: threading.Lock, range_id: str, user_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Handles the logic for the 'end_training_variation' action."""
    cfg = config.get_section_config("trngsrv")
    content_server_url = cfg.get("content_server_url")
    instantiation_server_url = cfg.get("instantiation_server_url")
    db_dir = config.get_section_config("general").get("database_dir")
    active_sessions_file = os.path.join(db_dir, cfg.get("files", {}).get("active_sessions"))

    # 1. Get all activity_ids for the session
    lock.acquire()
    try:
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(active_sessions_file)
        activity_id_list = session_info.get_activity_id_list(range_id, user_id)
        if not activity_id_list:
            return False, {"message": f"Session with ID {range_id} doesn't exist for user {user_id}"}
    finally:
        lock.release()

    # 2. Remove content for each activity
    for activity_id in activity_id_list:
        try:
            query_tuples = {
                query.Parameters.USER: user_id,
                query.Parameters.ACTION: query.Parameters.REMOVE_CONTENT,
                query.Parameters.RANGE_ID: range_id,
                query.Parameters.ACTIVITY_ID: activity_id
            }
            query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
            with urllib.request.urlopen(content_server_url, query_params) as data_stream:
                data = data_stream.read().decode('utf-8')

            if Storyboard.SERVER_STATUS_SUCCESS not in data:
                logger.error("Content removal error for activity %s.", activity_id)
                return False, {"message": Storyboard.CONTENT_REMOVAL_ERROR}
        except IOError as e:
            logger.error("URL error while removing content: %s.", e)
            return False, {"message": Storyboard.CONTENT_SERVER_ERROR}

    # 3. Destroy the single range
    try:
        query_tuples = {
            query.Parameters.USER: user_id,
            query.Parameters.ACTION: query.Parameters.DESTROY_RANGE,
            query.Parameters.RANGE_ID: range_id
        }
        query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
        with urllib.request.urlopen(instantiation_server_url, query_params) as data_stream:
            data = data_stream.read()

        status, _ = query.Response.parse_server_response(data)
        if status != Storyboard.SERVER_STATUS_SUCCESS:
            return False, {"message": Storyboard.DESTRUCTION_ERROR}
    except IOError as e:
        logger.error("URL error while destroying range: %s.", e)
        return False, {"message": Storyboard.INSTANTIATION_SERVER_ERROR}

    # 4. Remove all session entries from file
    lock.acquire()
    try:
        session_info = sessinfo.SessionInfo()
        session_info.parse_YAML_file(active_sessions_file)
        for activity_id in activity_id_list:
            if not session_info.remove_session(range_id, user_id, activity_id=activity_id):
                 logger.error("Could not remove session for activity %s.", activity_id)
                 return False, {"message": Storyboard.SESSION_INFO_CONSISTENCY_ERROR}
        session_info.write_YAML_file(active_sessions_file)
    finally:
        lock.release()

    return True, {}

    return True


def _instantiate_range(
    user: userinfo.User,
    training_info: trnginfo.TrainingInfo,
    cyber_range_id: str,
    instance_count: int,
    scenario: str,
    level: str,
) -> Tuple[bool, Dict[str, Any]]:
    """Helper function to instantiate a cyber range."""
    cfg = config.get_section_config("trngsrv")
    general_cfg = config.get_section_config("general")
    db_dir = general_cfg.get("database_dir")
    instantiation_server_url = cfg.get("instantiation_server_url")

    range_file_name = training_info.get_range_file_name(scenario, level)
    if range_file_name is None:
        return False, {"message": Storyboard.TEMPLATE_IDENTIFICATION_ERROR}

    range_file_path = os.path.join(db_dir, range_file_name)
    progression_scenario_name = training_info.get_progression_scenario_name(scenario, level)

    try:
        with open(range_file_path, "r") as f:
            range_file_content = f.read()
    except IOError as e:
        logger.error("File error while reading range file: %s", e)
        return False, {"message": Storyboard.TEMPLATE_LOADING_ERROR}

    try:
        range_file_content = user.replace_variables(range_file_content, cyber_range_id, instance_count)
        query_tuples = {
            query.Parameters.USER: user.id,
            query.Parameters.ACTION: query.Parameters.INSTANTIATE_RANGE,
            query.Parameters.DESCRIPTION_FILE: range_file_content,
            query.Parameters.RANGE_ID: cyber_range_id
        }
        if progression_scenario_name:
            query_tuples[query.Parameters.PROGRESSION_SCENARIO] = progression_scenario_name

        query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
        with urllib.request.urlopen(instantiation_server_url, query_params) as data_stream:
            data = data_stream.read().decode('utf-8')

        status, message = query.Response.parse_server_response(data)
        if status != Storyboard.SERVER_STATUS_SUCCESS:
            logger.error("Range instantiation failed.")
            return False, {"message": Storyboard.INSTANTIATION_ERROR}

        return True, {"message": message}
    except IOError as e:
        logger.error("URL error during range instantiation: %s", e)
        return False, {"message": Storyboard.INSTANTIATION_SERVER_ERROR}


def create_training(
    cyber_range_id: str,
    user: userinfo.User,
    training_info: trnginfo.TrainingInfo,
    instance_count: int,
    scenario: str,
    level: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handles the logic for the simple 'create_training' action.
    """
    cfg = config.get_section_config("trngsrv")
    general_cfg = config.get_section_config("general")
    db_dir = general_cfg.get("database_dir")
    content_server_url = cfg.get("content_server_url")

    # 1. Handle content upload
    content_file_name = training_info.get_content_file_name(scenario, level)
    if content_file_name is None:
        return False, {"message": Storyboard.CONTENT_IDENTIFICATION_ERROR}

    content_file_path = os.path.join(db_dir, content_file_name)
    try:
        with open(content_file_path, "r") as f:
            content_file_content = f.read()
    except IOError as e:
        logger.error("File error while reading content file: %s", e)
        return False, {"message": Storyboard.CONTENT_LOADING_ERROR}

    try:
        query_tuples = {
            query.Parameters.USER: user.id,
            query.Parameters.ACTION: query.Parameters.UPLOAD_CONTENT,
            query.Parameters.DESCRIPTION_FILE: content_file_content,
            query.Parameters.RANGE_ID: cyber_range_id
        }
        query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
        with urllib.request.urlopen(content_server_url, query_params) as data_stream:
            data = data_stream.read().decode('utf-8')

        status, activity_id = query.Response.parse_server_response(data)
        if status != Storyboard.SERVER_STATUS_SUCCESS:
            logger.error("Content upload failed.")
            return False, {"message": Storyboard.CONTENT_UPLOAD_ERROR}
    except IOError as e:
        logger.error("URL error during content upload: %s", e)
        return False, {"message": Storyboard.CONTENT_SERVER_ERROR}

    # 2. Handle instantiation
    instantiation_success, result = _instantiate_range(
        user, training_info, cyber_range_id, instance_count, scenario, level
    )
    if not instantiation_success:
        # TODO: Should also delete the content uploaded above before returning
        return False, result

    return True, {"activity_id": activity_id, "message": result.get("message")}


def _get_creation_log(user_id: str, cyber_range_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Helper to get the creation log from the instantiation server."""
    cfg = config.get_section_config("trngsrv")
    instantiation_server_url = cfg.get("instantiation_server_url")

    try:
        query_tuples = {
            query.Parameters.USER: user_id,
            query.Parameters.ACTION: query.Parameters.GET_CR_CREATION_LOG,
            query.Parameters.RANGE_ID: cyber_range_id
        }
        query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
        with urllib.request.urlopen(instantiation_server_url, query_params) as data_stream:
            # The response is not standard JSON, but a custom string format.
            log_content = data_stream.read().decode('utf-8')
        return True, {"log_content": log_content}
    except IOError as e:
        logger.error("URL error while getting creation log: %s", e)
        return False, {"message": Storyboard.INSTANTIATION_SERVER_ERROR}


def _parse_creation_log(log_content: str) -> Dict[int, List[Dict[str, str]]]:
    """
    Parses the creation log to extract meta answers.
    This function replicates the brittle parsing from the original codebase.
    """
    meta_answer_dic = {}
    try:
        if (log_content.startswith('[{"') and log_content.endswith('"}]')):
            content = log_content[2:-2]
            # This parsing is fragile, as it assumes a very specific format.
            _, creation_log_message = content.split(',', 1)
            _, body = creation_log_message.split(':', 1)
            decode_mesage = urllib.parse.unquote(body).split("\n")

            result_list = [line.replace("exec-result: ", "") for line in decode_mesage if 'exec-result:' in line]

            all_result = []
            for result in result_list:
                tag, ans = result.split(' ', 1)
                ans = urllib.parse.unquote(ans).strip()
                ins, guest, num, var = tag.split(",")
                ins_num = int(ins.replace("ins", ""))
                user_def = f"{guest},{num},{var}"
                all_result.append({ins_num: {user_def: ans}})

            for inst in all_result:
                for i in inst:
                    meta_answer_dic.setdefault(i, []).append(inst[i])
    except Exception as e:
        logger.error("Failed to parse creation log: %s", e)

    return meta_answer_dic


def create_training_variation(
    lock: threading.Lock,
    cyber_range_id: str,
    user: userinfo.User,
    training_info: trnginfo.TrainingInfo,
    instance_count: int,
    scenario: str,
    level: str,
    ttype: str,
    language: str,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Handles the logic for the 'create_training_variation' action.
    """
    # 1. Instantiate Range
    inst_success, inst_result = _instantiate_range(
        user, training_info, cyber_range_id, instance_count, scenario, level
    )
    if not inst_success:
        return False, inst_result

    # 2. Get and Parse Creation Log
    log_success, log_result = _get_creation_log(user.id, cyber_range_id)
    if not log_success:
        return False, log_result

    meta_answer_dic = _parse_creation_log(log_result['log_content'])
    if not meta_answer_dic:
        return False, {"message": "Failed to parse meta answers from creation log."}

    # 3. Get Content File Template
    content_file_name = training_info.get_content_file_name(scenario, level)
    if content_file_name is None:
        return False, {"message": Storyboard.CONTENT_IDENTIFICATION_ERROR}

    db_dir = config.get_section_config("general").get("database_dir")
    content_file_path = os.path.join(db_dir, content_file_name)
    try:
        with open(content_file_path, "r") as f:
            content_file_content = f.read()
    except IOError as e:
        logger.error("File error while reading content file for variation: %s", e)
        return False, {"message": Storyboard.CONTENT_LOADING_ERROR}

    # 4. Loop through instances, patch content, upload, and save session
    from ..utils import MetaAnswerTemplate # Avoid circular import at top level

    for i in range(1, instance_count + 1):
        meta_answers = {}
        for item in meta_answer_dic.get(i, []):
            meta_answers.update(item)

        content_template = MetaAnswerTemplate(content_file_content)
        patched_content_str = content_template.safe_substitute(meta_answers)

        try:
            content_list = yaml.safe_load(patched_content_str)
            for item in content_list:
                for training_section in item.values():
                    for quest in training_section[0].get("questions", []):
                        if "meta_answer" in quest:
                            quest["answer"] = quest.pop("meta_answer")
            final_content_description = yaml.dump(content_list, default_flow_style=False)
        except (yaml.YAMLError, KeyError, IndexError) as e:
            logger.error("Failed to patch content YAML: %s", e)
            return False, {"message": "Error processing content template."}

        # Upload content
        content_server_url = config.get_section_config("trngsrv").get("content_server_url")
        try:
            query_tuples = {
                query.Parameters.USER: user.id,
                query.Parameters.ACTION: query.Parameters.UPLOAD_CONTENT,
                query.Parameters.DESCRIPTION_FILE: final_content_description,
                query.Parameters.RANGE_ID: cyber_range_id
            }
            query_params = urllib.parse.urlencode(query_tuples).encode('utf-8')
            with urllib.request.urlopen(content_server_url, query_params) as data_stream:
                data = data_stream.read().decode('utf-8')

            status, activity_id = query.Response.parse_server_response(data)
            if status != Storyboard.SERVER_STATUS_SUCCESS:
                return False, {"message": Storyboard.CONTENT_UPLOAD_ERROR}
        except IOError as e:
            logger.error("URL error during variation content upload: %s", e)
            return False, {"message": Storyboard.CONTENT_SERVER_ERROR}

        # Save session for this instance
        session_name = f"Training Session #{cyber_range_id}"
        crt_time = time.asctime()
        save_success = save_session(
            lock, session_name, cyber_range_id, user.id, crt_time, ttype,
            [scenario], [level], language, str(instance_count), activity_id
        )
        if not save_success:
            return False, {"message": Storyboard.SESSION_INFO_CONSISTENCY_ERROR}

    return True, {"message": inst_result.get("message")}


def get_sessions(lock: threading.Lock, user_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Gets active sessions for a given user."""
    cfg = config.get_section_config("trngsrv")
    files = cfg.get("files", {})
    db_dir = config.get_section_config("general").get("database_dir")
    active_sessions_file = os.path.join(db_dir, files.get("active_sessions"))

    lock.acquire()
    try:
        session_info = sessinfo.SessionInfo()
        if not session_info.parse_YAML_file(active_sessions_file):
            return False, {"message": "Failed to parse active sessions file."}

        data = session_info.to_dict_list(user_id)
        return True, {"data": data}
    finally:
        lock.release()


def get_configurations(lock: threading.Lock, user_id: str) -> Tuple[bool, Dict[str, Any]]:
    """Gets saved configurations for a given user."""
    cfg = config.get_section_config("trngsrv")
    files = cfg.get("files", {})
    db_dir = config.get_section_config("general").get("database_dir")
    saved_configs_file = os.path.join(db_dir, files.get("saved_configurations"))

    lock.acquire()
    try:
        config_info = sessinfo.SessionInfo()
        if not config_info.parse_YAML_file(saved_configs_file):
            return False, {"message": "Failed to parse saved configurations file."}

        data = config_info.to_dict_list(user_id)
        return True, {"data": data}
    finally:
        lock.release()
