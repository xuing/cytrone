
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any

# External imports
import yaml
import json

# Various constants
SEPARATOR = "-----------------------------------------------------------------"
SEPARATO2 = "================================================================="

# Debugging constants
DO_DEBUG = False


#############################################################################
# Manage the keys used for representing session information
#############################################################################
class Keys:
    # Values of keys for session information representation
    SESSIONS = "sessions"
    NAME = "name"
    ID = "id"
    USER = "user"
    TIME = "time"
    TYPE = "type"
    SCENARIOS = "scenarios"
    LEVELS = "levels"
    LANGUAGE = "language"
    COUNT = "count"
    ACTIVITY_ID = "activity_id"


@dataclass
class Session:
    """Represents an active training session."""
    name: str
    sess_id: str
    user_id: str
    time: str
    ttype: str
    scenarios: List[str]
    levels: List[str]
    language: str
    count: str
    activity_id: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Session":
        """Creates a Session object from a dictionary."""
        # The original code uses 'id' in the YAML/JSON representation.
        # We need to map it to 'sess_id' to avoid conflict with the built-in id().
        sess_id = data.get(Keys.ID)
        if not sess_id:
            raise ValueError("Session data must contain an 'id' key.")

        return cls(
            name=data.get(Keys.NAME, ""),
            sess_id=str(sess_id),
            user_id=data.get(Keys.USER, ""),
            time=data.get(Keys.TIME, ""),
            ttype=data.get(Keys.TYPE, ""),
            scenarios=data.get(Keys.SCENARIOS, []),
            levels=data.get(Keys.LEVELS, []),
            language=data.get(Keys.LANGUAGE, ""),
            count=data.get(Keys.COUNT, ""),
            activity_id=data.get(Keys.ACTIVITY_ID)
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Session object to a dictionary for serialization."""
        return {
            Keys.NAME: self.name,
            Keys.ID: self.sess_id,
            Keys.USER: self.user_id,
            Keys.TIME: self.time,
            Keys.TYPE: self.ttype,
            Keys.SCENARIOS: self.scenarios,
            Keys.LEVELS: self.levels,
            Keys.LANGUAGE: self.language,
            Keys.COUNT: self.count,
            Keys.ACTIVITY_ID: self.activity_id,
        }

#############################################################################
# Manage overall information about training sessions
#############################################################################
class SessionInfo:
    """Manages a collection of active Session objects."""

    def __init__(self, sessions: Optional[List[Session]] = None):
        self.sessions: List[Session] = sessions or []

    def parse_YAML_file(self, yaml_file_name: str) -> bool:
        """Parses a YAML file to populate the session list. Returns True on success."""
        self.sessions = []
        try:
            with open(yaml_file_name, "r") as yaml_file:
                info = yaml.safe_load(yaml_file)
        except FileNotFoundError:
            # It's not an error if the active sessions file doesn't exist yet.
            print(f"* WARNING: sessinfo: Cannot open file '{yaml_file_name}' for read. Assuming no active sessions.")
            return True
        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                print(f"* ERROR: sessinfo: YAML error in {yaml_file_name} at position: ({mark.line+1}:{mark.column+1}).")
            return False

        return self._parse_info(info)

    def parse_JSON_data(self, json_data: str) -> bool:
        """Parses a JSON string to populate session info. Returns True on success."""
        try:
            info = json.loads(json_data)
            return self._parse_info(info)
        except json.JSONDecodeError as e:
            print(f"* ERROR: sessinfo: Failed to decode JSON: {e}")
            return False

    def _parse_info(self, info: Optional[List[Dict[str, Any]]]) -> bool:
        """Parses the loaded information object (from YAML or JSON)."""
        self.sessions = []
        if not info:  # Handles empty or None info
            return True

        try:
            sessions_data = next((item.get(Keys.SESSIONS) for item in info if Keys.SESSIONS in item), [])
            self.sessions = [Session.from_dict(s) for s in sessions_data]
        except (ValueError, TypeError) as e:
            print(f"* ERROR: sessinfo: Failed to parse session info: {e}")
            return False
        return True

    def add_session(self, session_name: str, cyber_range_id: str, user_id: str, crt_time: str,
                    ttype: str, scenarios: List[str], levels: List[str],
                    language: str, count: str, activity_id: Optional[str]):
        """Adds a new session to the list."""
        session = Session(
            name=session_name,
            sess_id=cyber_range_id,
            user_id=user_id,
            time=crt_time,
            ttype=ttype,
            scenarios=scenarios,
            levels=levels,
            language=language,
            count=count,
            activity_id=activity_id
        )
        self.sessions.append(session)

    def remove_session(self, cyber_range_id: str, user_id: str, activity_id: Optional[str] = None) -> bool:
        """
        Removes a session. If activity_id is provided, it matches against it as well.
        Returns True if a session was removed, False otherwise.
        """
        initial_len = len(self.sessions)

        if activity_id:
            # This logic corresponds to the old 'remove_session_variation'
            self.sessions = [
                s for s in self.sessions
                if not (s.sess_id == cyber_range_id and s.user_id == user_id and s.activity_id == activity_id)
            ]
        else:
             # This logic corresponds to the old 'remove_session'
            self.sessions = [
                s for s in self.sessions
                if not (s.sess_id == cyber_range_id and s.user_id == user_id)
            ]

        return len(self.sessions) < initial_len

    def get_id_list_int(self) -> List[int]:
        """Builds a list of active session ids as integers."""
        return [int(s.sess_id) for s in self.sessions]

    def is_session_id(self, cyber_range_id: str) -> bool:
        """Checks if a session with the given id exists."""
        return any(s.sess_id == cyber_range_id for s in self.sessions)

    def is_session_id_user(self, cyber_range_id: str, user_id: str) -> bool:
        """Checks if a session with the given id exists for the specified user."""
        return any(s.sess_id == cyber_range_id and s.user_id == user_id for s in self.sessions)

    def get_activity_id(self, cyber_range_id: str, user_id: str) -> Optional[str]:
        """Gets the activity id for a session with the given id and user."""
        for session in self.sessions:
            if session.sess_id == cyber_range_id and session.user_id == user_id:
                return session.activity_id
        return None

    def get_activity_id_list(self, cyber_range_id: str, user_id: str) -> List[str]:
        """Gets a list of all activity ids for a session with the given id and user."""
        return [
            s.activity_id for s in self.sessions
            if s.sess_id == cyber_range_id and s.user_id == user_id and s.activity_id is not None
        ]

    def write_YAML_file(self, yaml_file_name: str) -> bool:
        """Stores session information in a YAML file."""
        print(f"* INFO: sessinfo: Writing session info to file '{yaml_file_name}'...")

        # This is the corrected implementation. It writes proper YAML, not a JSON string.
        representation = [{
            Keys.SESSIONS: [s.to_dict() for s in self.sessions]
        }]

        try:
            with open(yaml_file_name, "w") as yaml_file:
                yaml.dump(representation, yaml_file, default_flow_style=False)
            return True
        except IOError:
            print(f"* ERROR: sessinfo: Cannot open file '{yaml_file_name}' for write.")
            return False

    def pretty_print(self):
        """Prints a formatted representation of the session information."""
        print(SEPARATOR)
        print(f"SESSION INFO: {len(self.sessions)} session(s)")
        print(SEPARATOR)
        for session in self.sessions:
            print("SESSION:")
            for key, value in session.to_dict().items():
                print(f"  - {key}: {value}")
        print(SEPARATOR)

    def to_dict_list(self, user_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Creates a list of dictionaries for serialization.
        If user_id is provided, filters for that user.
        """
        if user_id:
            sessions_list = [s.to_dict() for s in self.sessions if s.user_id == user_id]
        else:
            sessions_list = [s.to_dict() for s in self.sessions]

        return [{Keys.SESSIONS: sessions_list}]

    def get_JSON_representation(self, user_id: str) -> str:
        """Creates a JSON representation for a specific user."""
        return json.dumps(self.to_dict_list(user_id))

    def get_JSON_representation_all(self) -> str:
        """Creates a JSON representation including all users' sessions."""
        return json.dumps(self.to_dict_list())


#############################################################################
# Testing code for the classes in this file
#
# This code will be executed _only_ when this module is called as the
# main program
#############################################################################
if __name__ == '__main__':
    try:

        enabled = [True, True]

        #####################################################################
        # TEST #1
        if enabled[0]:
            TEST_FILE = "active_sessions.yml"
            print ("\n" + SEPARATO2)
            print ("TEST #1: Get session information from YAML file: %s" % (
                TEST_FILE))
            print (SEPARATO2)
            session_info = SessionInfo()
            session_info.parse_YAML_file(TEST_FILE)
            session_info.pretty_print()
            user_id = "john_doe"
            print ("External JSON representation: %s" % (json.dumps(session_info.to_dict_list(user_id))))

        #####################################################################
        # TEST #2
        if enabled[1]:
            TEST_STRING = '[{"sessions": [{"count": "2", "activity_id": "N/A", "name": "Training Session #1", "language": "en", "scenarios": ["Information Security Testing and Assessment"], "levels": ["Level 1 (Easy)"], "user": "john_doe", "time": "Thu Jul 11 10:43:31 2019", "type": "Scenario-Based Training", "id": "1"}]}]'
            print ("\n" + SEPARATO2)
            print ("TEST #2: Get session information from JSON string: %s." % (
                TEST_STRING))
            print (SEPARATO2)
            session_info = SessionInfo()
            session_info.parse_JSON_data(TEST_STRING)
            session_info.pretty_print()

    except IOError as error:
        print ("* ERROR: sessinfo: %s." % (error))
