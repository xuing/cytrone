
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
# Manage the keys used for representing scenario information
#############################################################################
class Keys:
    # Values of keys for scenario information representation
    TYPES = "types"
    NAME = "name"
    CATEGORY = "category"
    SCENARIOS = "scenarios"
    LEVELS = "levels"
    CONTENT = "content"
    SPECIFICATION = "specification"  # Obsolete label
    RANGE = "range"
    PROGRESSION = "progression"


@dataclass
class Level:
    """Represents a single level within a scenario."""
    name: str
    content_file: Optional[str] = None
    range_file: Optional[str] = None
    progression_scenario: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Level":
        """Creates a Level object from a dictionary."""
        if Keys.NAME not in data:
            raise ValueError("Level data must contain a 'name' key.")

        # The original code supported an obsolete 'specification' key as a fallback for 'range'.
        range_file = data.get(Keys.RANGE) or data.get(Keys.SPECIFICATION)

        return cls(
            name=data[Keys.NAME],
            content_file=data.get(Keys.CONTENT),
            range_file=range_file,
            progression_scenario=data.get(Keys.PROGRESSION)
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Converts the Level object to a dictionary for JSON serialization.
        Note: The original code only exposed the name in the JSON representation.
        """
        return {Keys.NAME: self.name}


@dataclass
class Scenario:
    """Represents a training scenario, containing one or more levels."""
    name: str
    levels: List[Level] = field(default_factory=list)
    _levels_by_name: Dict[str, Level] = field(init=False, repr=False, default_factory=dict)

    def __post_init__(self):
        self._levels_by_name = {level.name: level for level in self.levels}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Scenario":
        """Creates a Scenario object from a dictionary."""
        if Keys.NAME not in data:
            raise ValueError("Scenario data must contain a 'name' key.")

        levels_data = data.get(Keys.LEVELS, [])
        return cls(
            name=data[Keys.NAME],
            levels=[Level.from_dict(level_data) for level_data in levels_data]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the Scenario object to a dictionary for JSON serialization."""
        return {
            Keys.NAME: self.name,
            Keys.LEVELS: [level.to_dict() for level in self.levels]
        }

    def get_level(self, level_name: str) -> Optional[Level]:
        """Gets a level by its name."""
        return self._levels_by_name.get(level_name)


@dataclass
class TrainingType:
    """Represents a type of training."""
    name: str
    category: str

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TrainingType":
        """Creates a TrainingType object from a dictionary."""
        if not all(k in data for k in [Keys.NAME, Keys.CATEGORY]):
            raise ValueError("TrainingType data must contain 'name' and 'category' keys.")
        return cls(
            name=data[Keys.NAME],
            category=data[Keys.CATEGORY]
        )

    def to_dict(self) -> Dict[str, Any]:
        """Converts the TrainingType object to a dictionary for JSON serialization."""
        return {
            Keys.NAME: self.name,
            Keys.CATEGORY: self.category
        }


#############################################################################
# Manage overall information about training
#############################################################################
class TrainingInfo:
    """Manages all training information, including types and scenarios."""

    def __init__(self):
        self.types: List[TrainingType] = []
        self.scenarios: List[Scenario] = []
        self._scenarios_by_name: Dict[str, Scenario] = {}

    def _build_lookup(self):
        """Builds dictionaries for efficient lookups."""
        self._scenarios_by_name = {s.name: s for s in self.scenarios}

    def parse_YAML_file(self, yaml_file_name: str) -> bool:
        """Parses a YAML file to populate training info. Returns True on success."""
        try:
            with open(yaml_file_name, "r") as yaml_file:
                info = yaml.safe_load(yaml_file)
        except FileNotFoundError:
            print(f"* ERROR: Cannot open file {yaml_file_name}.")
            return False
        except yaml.YAMLError as exc:
            if hasattr(exc, 'problem_mark'):
                mark = exc.problem_mark
                print(f"* ERROR: YAML error in {yaml_file_name} at position: ({mark.line+1}:{mark.column+1}).")
            return False

        return self._parse_info(info)

    def parse_JSON_data(self, json_data: str) -> bool:
        """Parses a JSON string to populate training info. Returns True on success."""
        try:
            info = json.loads(json_data)
            return self._parse_info(info)
        except json.JSONDecodeError as e:
            print(f"* ERROR: Failed to decode JSON: {e}")
            return False

    def _parse_info(self, info: List[Dict[str, Any]]) -> bool:
        """Parses the loaded information object (from YAML or JSON)."""
        try:
            types_data = next((item.get(Keys.TYPES) for item in info if Keys.TYPES in item), [])
            scenarios_data = next((item.get(Keys.SCENARIOS) for item in info if Keys.SCENARIOS in item), [])

            self.types = [TrainingType.from_dict(t) for t in types_data]
            self.scenarios = [Scenario.from_dict(s) for s in scenarios_data]
            self._build_lookup()
        except (ValueError, TypeError) as e:
            print(f"* ERROR: Failed to parse training info: {e}")
            return False
        return True

    def pretty_print(self):
        """Prints a formatted representation of the training information."""
        print(SEPARATOR)
        print(f"TRAINING INFO: {len(self.types)} type(s)  {len(self.scenarios)} scenario(s)")
        print(SEPARATOR)
        for i, t in enumerate(self.types, 1):
            print(f"TYPE #{i}:")
            print(f"  - {Keys.NAME}: {t.name}\n    {Keys.CATEGORY}: {t.category}")
        for i, s in enumerate(self.scenarios, 1):
            print(f"SCENARIO #{i}:")
            print(f"  - {Keys.NAME}: {s.name}\n    {Keys.LEVELS}: {len(s.levels)} level(s)")
            for level in s.levels:
                print(f"      - {Keys.NAME}: {level.name}")
                print(f"        {Keys.CONTENT}: {level.content_file}")
                print(f"        {Keys.RANGE}: {level.range_file}")
                print(f"        {Keys.PROGRESSION}: {level.progression_scenario}")
        print(SEPARATOR)

    def to_dict_list(self) -> List[Dict[str, Any]]:
        """
        Creates a list of dictionaries representing the training info,
        suitable for JSON serialization.
        """
        representation = [
            {Keys.TYPES: [t.to_dict() for t in self.types]},
            {Keys.SCENARIOS: [s.to_dict() for s in self.scenarios]}
        ]
        return representation

    def get_JSON_representation(self) -> str:
        """
        Creates a JSON representation of the training info for clients.
        [DEPRECATED in favor of to_dict_list, will be removed]
        """
        return json.dumps(self.to_dict_list())

    def _get_level(self, scenario_name: str, level_name: str) -> Optional[Level]:
        """Helper to find a level by scenario and level name."""
        scenario = self._scenarios_by_name.get(scenario_name)
        if scenario:
            return scenario.get_level(level_name)
        return None

    def get_content_file_name(self, scenario_name: str, level_name: str) -> Optional[str]:
        """Gets the content file name for a given scenario and level."""
        level = self._get_level(scenario_name, level_name)
        return level.content_file if level else None

    def get_range_file_name(self, scenario_name: str, level_name: str) -> Optional[str]:
        """Gets the range file name for a given scenario and level."""
        level = self._get_level(scenario_name, level_name)
        return level.range_file if level else None

    def get_progression_scenario_name(self, scenario_name: str, level_name: str) -> Optional[str]:
        """Gets the progression scenario name for a given scenario and level."""
        level = self._get_level(scenario_name, level_name)
        return level.progression_scenario if level else None


#############################################################################
# Testing code for the classes in this file
#
# This code will be executed _only_ when this module is called as the
# main program
#############################################################################
if __name__ == '__main__':
    try:

        enabled = [False, True, False]
        DATABASE_DIR = "../database/"

        #####################################################################
        # TEST #1
        if enabled[0]:
            TEST_FILE = DATABASE_DIR + "training-en.yml"
            print (SEPARATO2)
            print ("TEST #1: Get training information from YAML file: %s." % (
                TEST_FILE))
            print (SEPARATO2)
            training_info = TrainingInfo()
            training_info.parse_YAML_file(TEST_FILE)
            training_info.pretty_print()
            print ("External JSON representation: %s" % (training_info.get_JSON_representation()))

        #####################################################################
        # TEST #2
        if enabled[1]:
            TEST_FILE = DATABASE_DIR + "training-ja.yml"
            print (SEPARATO2)
            print ("TEST #2: Get training information from YAML file: %s." % (
                TEST_FILE))
            print (SEPARATO2)
            training_info = TrainingInfo()
            training_info.parse_YAML_file(TEST_FILE)
            training_info.pretty_print()
            print ("External JSON representation: %s" % (training_info.get_JSON_representation()))

        #####################################################################
        # TEST #3
        if enabled[2]:
            TEST_STRING = '[{"scenarios": [{"levels": [{"range": "NIST-level1.yml", "name": "Level 1 (Easy)"}, {"range": "NIST-level2.yml", "name": "Level 2 (Medium)"}, {"range": "NIST-level3.yml", "name": "Level 3 (Hard)"}], "name": "NIST Information Security Testing and Assessment"}, {"levels": [{"range": "IR-level1.yml", "name": "Level 1 (Detection)"}, {"range": "IR-level2.yml", "name": "Level 2 (Forensics)"}, {"range": "IR-level3.yml", "name": "Level 3 (Response)"}], "name": "Incident Response"}]}]'
            print (SEPARATO2)
            print ("TEST #3: Get training information from JSON string: %s." % (
                TEST_STRING))
            print (SEPARATO2)
            training_info = TrainingInfo()
            training_info.parse_JSON_data(TEST_STRING)
            training_info.pretty_print()

    except IOError as error:
        print ("ERROR: %s." % (error))
