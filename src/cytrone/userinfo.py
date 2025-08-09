
from dataclasses import dataclass
from typing import Optional, List, Dict, Any

# External imports
import yaml
#import string


# Various constants
SEPARATOR = "-----------------------------------------------------------------"
SEPARATO2 = "================================================================="

# Debugging constants
DO_DEBUG = False


#############################################################################
# Manage the keys used for representing user information
#############################################################################
class Keys:

    # Values of keys for representing general user information
    USERS = "users"
    NAME = "name"
    ID = "id"
    PASSWORD = "password"

    # Values of keys for representing host information
    HOST_MGMT_ADDR = "host_mgmt_addr"
    HOST_VIRBR_ADDR = "host_virbr_addr"
    HOST_ACCOUNT = "host_account"

    # Below are keys that are assigned values internally
    CLONE_INSTANCE_NUMBER = "clone_instance_number"
    CLONE_RANGE_ID = "clone_range_id"


@dataclass
class User:
    """Represents a user and their associated configuration."""
    name: str
    id: str
    password: Optional[str] = None
    host_mgmt_addr: Optional[str] = None
    host_virbr_addr: Optional[str] = None
    host_account: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "User":
        """Creates a User object from a dictionary."""
        # The original code asserted these, so we'll check for them.
        if not all(k in data for k in [Keys.NAME, Keys.ID]):
            raise ValueError("User data must contain 'name' and 'id' keys.")

        return cls(
            name=data[Keys.NAME],
            id=data[Keys.ID],
            password=data.get(Keys.PASSWORD),
            host_mgmt_addr=str(data.get(Keys.HOST_MGMT_ADDR, "")),
            host_virbr_addr=str(data.get(Keys.HOST_VIRBR_ADDR, "")),
            host_account=str(data.get(Keys.HOST_ACCOUNT, ""))
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the User object to a dictionary."""
        return {
            Keys.NAME: self.name,
            Keys.ID: self.id,
            Keys.PASSWORD: self.password,
            Keys.HOST_MGMT_ADDR: self.host_mgmt_addr,
            Keys.HOST_VIRBR_ADDR: self.host_virbr_addr,
            Keys.HOST_ACCOUNT: self.host_account,
        }

    def replace_variables(self, range_file_content: str, cyber_range_id: str, instance_count: int) -> str:
        """
        Replaces variables in a range specification file content based on user information.
        """
        variables = {
            Keys.HOST_MGMT_ADDR: self.host_mgmt_addr,
            Keys.HOST_VIRBR_ADDR: self.host_virbr_addr,
            Keys.HOST_ACCOUNT: self.host_account,
            Keys.CLONE_RANGE_ID: str(cyber_range_id),
            Keys.CLONE_INSTANCE_NUMBER: str(instance_count),
        }

        # Filter out any None values before replacement
        variables_to_replace = {k: v for k, v in variables.items() if v is not None}

        return_string = range_file_content
        for var, value in variables_to_replace.items():
            template_variable = f"{{{{ {var} }}}}"
            if DO_DEBUG:
                print(f"* DEBUG: userinfo: replacing '{template_variable}' with '{value}'")
            return_string = return_string.replace(template_variable, value)

        return return_string


#############################################################################
# Manage user information
#############################################################################
class UserInfo:
    """Manages a collection of User objects."""

    def __init__(self, users: Optional[List[User]] = None):
        self.users: List[User] = users or []
        self._users_by_id: Dict[str, User] = {user.id: user for user in self.users}

    def parse_YAML_file(self, yaml_file_name: str) -> bool:
        """
        Parses a YAML file to populate the user list.
        Returns True on success, False on failure.
        """
        try:
            with open(yaml_file_name, "r") as yaml_file:
                info = yaml.safe_load(yaml_file)
        except FileNotFoundError:
            print(f"* ERROR: userinfo: Cannot open file {yaml_file_name}.")
            return False
        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                print(f"* ERROR: userinfo: YAML error in file {yaml_file_name} at position: ({mark.line+1}:{mark.column+1}).")
            return False

        return self._parse_info(info)

    def _parse_info(self, info: List[Dict[str, Any]]) -> bool:
        """Parses the loaded YAML information object."""
        if not info or Keys.USERS not in info[0]:
            print("* ERROR: userinfo: YAML file does not contain a 'users' key.")
            return False

        users_data = info[0].get(Keys.USERS, [])

        if DO_DEBUG:
            print(SEPARATOR)
            print(f"* DEBUG: userinfo: PARSE INFO: {len(users_data)} user(s)")
            print(users_data)
            print(SEPARATOR)

        try:
            self.users = [User.from_dict(user_data) for user_data in users_data]
            self._users_by_id = {user.id: user for user in self.users}
        except ValueError as e:
            print(f"* ERROR: userinfo: Failed to parse user data: {e}")
            return False

        if DO_DEBUG:
            for user in self.users:
                print(f"* DEBUG: userinfo: LOADED USER: {user}")
            print(SEPARATOR)

        return True

    def get_user(self, user_id: str) -> Optional[User]:
        """Gets a user by their ID, returns None if not found."""
        return self._users_by_id.get(user_id)

    def pretty_print(self):
        """Prints a formatted representation of the user information."""
        print(SEPARATOR)
        print(f"USER INFO: {len(self.users)} user(s)")
        print(SEPARATOR)
        for i, user in enumerate(self.users, 1):
            print(f"USER #{i}:")
            print(f"  - {Keys.NAME}: {user.name}")
            print(f"    {Keys.ID}: {user.id}")
        print(SEPARATOR)


#############################################################################
# Testing code for the classes in this file
#
# This code will be executed _only_ when this module is called as the
# main program
#############################################################################
if __name__ == '__main__':
    try:

        enabled = [True]
        DATABASE_DIR = "../database/"

        #####################################################################
        # TEST #1
        if enabled[0]:
            TEST_FILE = DATABASE_DIR + "users.yml"
            print (SEPARATO2)
            print ("TEST #1: Get user information from YAML file: %s." % (
                TEST_FILE))
            print (SEPARATO2)
            user_info = UserInfo()
            user_info.parse_YAML_file(TEST_FILE)
            user_info.pretty_print()

    except IOError as error:
        print ("* ERROR: userinfo: %s." % (error))
