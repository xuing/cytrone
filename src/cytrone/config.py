"""
Handles loading and accessing application configuration from config.yml.
"""
import yaml
from pathlib import Path
from typing import Any, Dict

# The config file is expected to be in the project root directory.
# This path navigates up from src/cytrone/ to the root.
CONFIG_FILE_PATH = Path(__file__).parent.parent.parent / "config.yml"

_config: Dict[str, Any] = {}


def load_config(path: Path = CONFIG_FILE_PATH) -> None:
    """
    Loads the YAML configuration file from the given path.

    Args:
        path: The path to the configuration file.

    Raises:
        FileNotFoundError: If the configuration file cannot be found.
        yaml.YAMLError: If there is an error parsing the configuration file.
    """
    global _config
    try:
        with open(path, "r") as f:
            _config = yaml.safe_load(f)
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found at {path}")
        raise
    except yaml.YAMLError as e:
        print(f"ERROR: Error parsing YAML configuration file: {e}")
        raise


def get_config() -> Dict[str, Any]:
    """
    Returns the entire configuration dictionary.

    Loads the configuration from the file if it hasn't been loaded yet.
    """
    if not _config:
        load_config()
    return _config


def get_section_config(section: str) -> Dict[str, Any]:
    """
    Returns a specific section from the configuration.

    Args:
        section: The name of the configuration section to retrieve.
    """
    return get_config().get(section, {})
