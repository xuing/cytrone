# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## High-level Code Architecture

CyTrONE is an integrated cybersecurity training framework. It consists of a central management component and several helper modules that work together to provide a complete training solution.

The main components are:

- **CyTrONE (main)**: The core framework that integrates all other modules. Its source code is located in the `code/` directory. It uses a database of training content (in `database/`) and helper scripts (in `scripts/`) to manage the training lifecycle.

- **CyLMS (`cylms/`)**: A set of tools to support cybersecurity training on a Learning Management System (LMS), specifically Moodle. It handles the conversion of training content from YAML format to SCORM packages and manages their upload/removal from the LMS.

- **CyRIS (`cyris/`)**: A cyber range instantiation system responsible for creating and managing the virtual training environments. It uses YAML descriptions to automate the setup of virtual machines, networks, and necessary tools for the training exercises.

- **CyPROM (`cyprom/`)**: A scenario progression management module used to introduce dynamic elements into the training. It follows a "Trigger-Action-Branching" model to adapt the scenario based on trainee actions, allowing for more realistic and interactive training like real-time attack simulations.

The general workflow is as follows:
1. An instructor provides training requirements.
2. CyTrONE uses CyLMS to upload training materials to the LMS.
3. CyTrONE uses CyRIS to create the corresponding virtual cyber range environment.
4. CyPROM can be used to manage the progression of dynamic scenarios within the created cyber range.
5. Trainees access the training content via the LMS and perform exercises in the cyber range.

## Common Commands

The primary way to interact with the CyTrONE framework is through the shell scripts located in the `scripts/` directory. A configuration file `scripts/CONFIG` (based on the `scripts/CONFIG.dist` template) must be created first.

### Framework Lifecycle Management

- **Start CyTrONE framework:**
  ```bash
  ./scripts/start_cytrone.sh
  ```

- **Stop CyTrONE framework:**
  ```bash
  ./scripts/stop_cytrone.sh
  ```

### Training Session Management

- **Create a new training session:**
  This script typically presents a menu of pre-configured training options.
  ```bash
  ./scripts/create_training.sh
  ```

- **End a training session:**
  Requires the session ID as an argument.
  ```bash
  # Example for session ID 1
  ./scripts/end_training.sh 1
  ```

- **Get information about active sessions:**
  ```bash
  ./scripts/get_sessions.sh
  ```

- **Retrieve access information for a cyber range:**
  ```bash
  ./scripts/get_notification.sh
  ```

### Component-Specific Commands

While CyTrONE orchestrates the main workflow, individual components can be used standalone.

- **CyLMS:**
  - Convert YAML content and add to LMS:
    ```bash
    ./cylms/cylms.py --convert-content training_example.yml --config-file config_file --add-to-lms 1
    ```
  - Remove an activity from LMS:
    ```bash
    ./cylms/cylms.py --config-file config_file --remove-from-lms 1,ID
    ```

- **CyPROM:**
  - Run with default settings:
    ```bash
    ./cyprom/cyprom.py
    ```
  - Requires `pip install -r cyprom/requirements.txt` for dependencies.

- **CyRIS:**
  - Create a cyber range:
    ```bash
    ./cyris/main/cyris.py ./cyris/examples/basic.yml ./cyris/CONFIG
    ```
  - Destroy a cyber range:
    ```bash
    ./cyris/main/range_cleanup.sh 123 ./cyris/CONFIG
    ```
