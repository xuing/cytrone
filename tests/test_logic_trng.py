import pytest
from unittest.mock import MagicMock
from src.cytrone.logic import trng
from src.cytrone.storyboard import Storyboard

@pytest.fixture
def mock_config(mocker):
    """Fixture to mock the config module."""
    mocker.patch('src.cytrone.logic.trng.config.get_section_config', return_value={
        "files": {
            "scenarios_en": "training-en.yml",
            "scenarios_ja": "training-ja.yml"
        },
        "database_dir": "dummy_db"
    })

def test_fetch_content_success(mocker, mock_config):
    """
    Tests the successful fetching of content.
    """
    # Mock the TrainingInfo object and its methods
    mock_training_info_instance = MagicMock()
    mock_training_info_instance.parse_YAML_file.return_value = True
    mock_training_info_instance.get_JSON_representation.return_value = '[{"key": "value"}]'
    mocker.patch('src.cytrone.logic.trng.trnginfo.TrainingInfo', return_value=mock_training_info_instance)

    success, result = trng.fetch_content(language="en")

    assert success is True
    assert "data" in result
    assert result["data"] == [{"key": "value"}]
    mock_training_info_instance.parse_YAML_file.assert_called_once_with("dummy_db/training-en.yml")

def test_fetch_content_file_not_found(mocker, mock_config):
    """
    Tests the case where the training settings file cannot be found/parsed.
    """
    # Mock the TrainingInfo object and its methods
    mock_training_info_instance = MagicMock()
    mock_training_info_instance.parse_YAML_file.return_value = False
    mocker.patch('src.cytrone.logic.trng.trnginfo.TrainingInfo', return_value=mock_training_info_instance)

    success, result = trng.fetch_content(language="en")

    assert success is False
    assert "message" in result
    assert result["message"] == Storyboard.TRAINING_SETTINGS_LOADING_ERROR

def test_create_training_success(mocker, mock_config):
    """
    Tests the successful creation of a training session (simple path).
    """
    # Mock user and training info objects
    mock_user = MagicMock()
    mock_user.id = "test_user"
    mock_user.replace_variables.return_value = "mocked range file content"

    mock_training_info = MagicMock()
    mock_training_info.get_content_file_name.return_value = "content.yml"
    mock_training_info.get_range_file_name.return_value = "range.yml"
    mock_training_info.get_progression_scenario_name.return_value = None

    # Mock file open
    mocker.patch("builtins.open", mocker.mock_open(read_data="file content"))

    # Mock urlopen
    mock_urlopen = mocker.patch('src.cytrone.logic.trng.urllib.request.urlopen')

    # Simulate responses from content and instantiation servers
    # First call (upload_content)
    contsrv_response = MagicMock()
    contsrv_response.read.return_value = b'[{"status": "SUCCESS", "activity_id": "123"}]'
    # Second call (instantiate_range)
    instsrv_response = MagicMock()
    instsrv_response.read.return_value = b'[{"status": "SUCCESS", "message": "Range created."}]'

    mock_urlopen.side_effect = [
        MagicMock(__enter__=MagicMock(return_value=contsrv_response)),
        MagicMock(__enter__=MagicMock(return_value=instsrv_response))
    ]

    success, result = trng.create_training(
        cyber_range_id="1",
        user=mock_user,
        training_info=mock_training_info,
        instance_count=1,
        scenario="Test Scenario",
        level="Level 1"
    )

    assert success is True
    assert result["activity_id"] == "123"
    assert result["message"] == "Range created."
    assert mock_urlopen.call_count == 2
