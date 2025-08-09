import os
import yaml
from src.cytrone import sessinfo

def get_test_file_path(filename):
    """Helper function to get the full path to a test data file."""
    current_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(current_dir, "data", filename)

def test_parse_session_info_from_yaml():
    """Tests that SessionInfo can correctly parse a YAML file."""
    test_file = get_test_file_path("active_sessions.yml")

    session_info = sessinfo.SessionInfo()
    success = session_info.parse_YAML_file(test_file)

    assert success is True
    assert len(session_info.sessions) == 2

    session1 = session_info.sessions[0]
    assert session1.name == "Training Session #1"
    assert session1.sess_id == "1"
    assert session1.user_id == "john_doe"

def test_add_and_remove_session():
    """Tests adding and removing a session."""
    session_info = sessinfo.SessionInfo()
    assert len(session_info.sessions) == 0

    # Add a session
    session_info.add_session(
        session_name="New Session",
        cyber_range_id="10",
        user_id="test_user",
        crt_time="Some Time",
        ttype="Test Type",
        scenarios=["Test Scenario"],
        levels=["Test Level"],
        language="en",
        count="1",
        activity_id="999"
    )
    assert len(session_info.sessions) == 1
    assert session_info.sessions[0].sess_id == "10"

    # Remove the session
    removed = session_info.remove_session(cyber_range_id="10", user_id="test_user")
    assert removed is True
    assert len(session_info.sessions) == 0

def test_write_yaml_file(tmp_path):
    """
    Tests that write_YAML_file correctly writes YAML data, not JSON.
    """
    # Create a session info object with one session
    session_info = sessinfo.SessionInfo()
    session_info.add_session(
        session_name="Write Test",
        cyber_range_id="w1",
        user_id="writer",
        crt_time="Write Time",
        ttype="Write Type",
        scenarios=["Write Scenario"],
        levels=["Write Level"],
        language="en",
        count="1",
        activity_id="w99"
    )

    # Write it to a temporary file
    temp_file = tmp_path / "output.yml"
    success = session_info.write_YAML_file(str(temp_file))

    assert success is True
    assert temp_file.exists()

    # Read the file back and verify its content and format
    with open(temp_file, "r") as f:
        content = f.read()
        # A simple check to distinguish YAML from JSON: valid YAML can start with '- ',
        # whereas our JSON representation starts with '[{'.
        assert content.strip().startswith("- sessions:")

    # Verify by loading it as YAML
    with open(temp_file, "r") as f:
        data = yaml.safe_load(f)

    assert isinstance(data, list)
    assert "sessions" in data[0]
    assert len(data[0]["sessions"]) == 1
    assert data[0]["sessions"][0]["name"] == "Write Test"
