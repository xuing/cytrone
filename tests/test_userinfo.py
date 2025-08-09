import os
from src.cytrone import userinfo

def test_parse_user_info_from_yaml():
    """
    Tests that UserInfo can correctly parse a YAML file.
    """
    # Get the path to the test data file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    test_file = os.path.join(current_dir, "data", "users.yml")

    # Create a UserInfo instance and parse the file
    user_info = userinfo.UserInfo()
    success = user_info.parse_YAML_file(test_file)

    # Assert that parsing was successful
    assert success is True

    # Assert that the correct number of users were loaded
    assert len(user_info.users) == 2

    # Assert details of the first user
    john = user_info.get_user("john_doe")
    assert john is not None
    assert john.name == "John Doe"
    assert john.id == "john_doe"
    assert john.password is not None
    assert john.host_mgmt_addr == "192.168.1.10"
    assert john.host_virbr_addr == "192.168.122.1"
    assert john.host_account == "johndoe"

    # Assert details of the second user
    jane = user_info.get_user("jane_smith")
    assert jane is not None
    assert jane.name == "Jane Smith"
    assert jane.id == "jane_smith"
    assert jane.host_account == "janesmith"

def test_user_replace_variables():
    """
    Tests the variable replacement in a template string.
    """
    user = userinfo.User(
        name="Test User",
        id="test_user",
        host_mgmt_addr="10.0.0.1",
        host_virbr_addr="192.168.122.1",
        host_account="test"
    )

    template = "mgmt: {{ host_mgmt_addr }}, virbr: {{ host_virbr_addr }}, range: {{ clone_range_id }}, inst: {{ clone_instance_number }}"

    result = user.replace_variables(template, "range42", 5)

    expected = "mgmt: 10.0.0.1, virbr: 192.168.122.1, range: range42, inst: 5"

    assert result == expected
