import os
import json
from src.cytrone import trnginfo

def get_test_file_path(filename):
    """Helper function to get the full path to a test data file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "data", filename)

def test_parse_training_info_from_yaml():
    """Tests that TrainingInfo can correctly parse a YAML file."""
    test_file = get_test_file_path("training-en.yml")

    training_info = trnginfo.TrainingInfo()
    success = training_info.parse_YAML_file(test_file)

    assert success is True
    assert len(training_info.types) == 2
    assert len(training_info.scenarios) == 2

    # Check scenario 1 details
    scenario1 = training_info._scenarios_by_name.get("Test Scenario 1")
    assert scenario1 is not None
    assert len(scenario1.levels) == 2
    assert scenario1.levels[0].name == "Level 1"
    assert scenario1.levels[0].content_file == "content1.yml"
    assert scenario1.levels[0].range_file == "range1.yml"
    assert scenario1.levels[0].progression_scenario == "progression1.yml"

def test_get_file_names():
    """Tests the file name lookup methods."""
    test_file = get_test_file_path("training-en.yml")

    training_info = trnginfo.TrainingInfo()
    training_info.parse_YAML_file(test_file)

    # Test successful lookups
    assert training_info.get_content_file_name("Test Scenario 1", "Level 1") == "content1.yml"
    assert training_info.get_range_file_name("Test Scenario 1", "Level 2") == "range2.yml"
    assert training_info.get_progression_scenario_name("Test Scenario 1", "Level 1") == "progression1.yml"

    # Test unsuccessful lookups
    assert training_info.get_content_file_name("Non-existent Scenario", "Level 1") is None
    assert training_info.get_range_file_name("Test Scenario 1", "Non-existent Level") is None

def test_to_dict_list_representation():
    """Tests the dictionary list representation for JSON serialization."""
    test_file = get_test_file_path("training-en.yml")

    training_info = trnginfo.TrainingInfo()
    training_info.parse_YAML_file(test_file)

    dict_list = training_info.to_dict_list()

    # Verify the structure and content
    assert isinstance(dict_list, list)
    assert len(dict_list) == 2

    types_dict = dict_list[0]
    scenarios_dict = dict_list[1]

    assert "types" in types_dict
    assert "scenarios" in scenarios_dict

    assert len(types_dict["types"]) == 2
    assert types_dict["types"][0]["name"] == "Scenario-Based Training"

    assert len(scenarios_dict["scenarios"]) == 2
    assert scenarios_dict["scenarios"][0]["name"] == "Test Scenario 1"
    assert len(scenarios_dict["scenarios"][0]["levels"]) == 2
    assert scenarios_dict["scenarios"][0]["levels"][0]["name"] == "Level 1"
