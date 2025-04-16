import logging  # https://docs.python.org/3/library/logging.html
import os  # https://docs.python.org/3/library/os.html
from typing import Optional, Dict, Any

project_root = os.path.dirname(os.path.abspath(__file__))

config_path_server = os.path.join(project_root, "..", "config_files", "default_server_config.txt")
config_path_client = os.path.join(project_root, "..", "config_files", "default_client_config.txt")


# noinspection PyShadowingNames
class ConfigManager:
    """
    A helper class to manage configuration for our Reliable Data Transfer implementation.
    Handles loading and validation of configuration parameters from both user input
    and configuration files.
    """
    def __init__(self):
        self.message: Optional[str] = None
        self.maximum_msg_size: Optional[int] = None
        self.window_size: Optional[int] = None
        self.timeout: Optional[int] = None
        self._config_loaded = False

        # Network config with defaults
        self.host = '127.0.0.1'
        self.port = 5000

        self.CONSTRAINTS = {
            'maximum_msg_size': {'min': 256, 'max': 65536},
            'window_size': {'min': 1, 'max': 100},
            'timeout': {'min': 1, 'max': 120}
        }

    def validate_config(self):
        """
        Validates the configuration parameters.
        Raises ValueError if any parameter is invalid.
        """
        if not self.message:
            raise ValueError("Message cannot be empty")

        errors = []
        for param, value in {
            'maximum_msg_size': self.maximum_msg_size,
            'window_size': self.window_size,
            'timeout': self.timeout
        }.items():
            if not isinstance(value, int):
                errors.append(f"{param} must be an integer")
            elif value < self.CONSTRAINTS[param]['min']:
                errors.append(
                    f"{param} must be at least {self.CONSTRAINTS[param]['min']}"
                )
            elif value > self.CONSTRAINTS[param]['max']:
                errors.append(
                    f"{param} cannot exceed {self.CONSTRAINTS[param]['max']}"
                )

        if errors:
            raise ValueError("\n".join(errors))

    def load_from_user_input(self):
        """
        Prompts the user to enter values for the configuration parameters.
        Validates input and reprompts on invalid input.
        """
        while True:
            try:
                print("\nEnter configuration values:")
                print("-" * 30)

                self.message = input("Message to send: ").strip()
                if not self.message:
                    print("Message cannot be empty. Please try again.")
                    continue

                for param in ['maximum_msg_size', 'window_size', 'timeout']:
                    constraints = self.CONSTRAINTS[param]
                    while True:
                        try:
                            value = input(
                                f"{param} ({constraints['min']}-{constraints['max']}): "
                            )
                            value = int(value)
                            if constraints['min'] <= value <= constraints['max']:
                                setattr(self, param, value)
                                break
                            print(
                                f"Value must be between {constraints['min']} "
                                f"and {constraints['max']}"
                            )
                        except ValueError:
                            print("Please enter a valid number")

                self.validate_config()
                self._config_loaded = True
                break

            except ValueError as e:
                print(f"Invalid input: {str(e)}")
                retry = input("Would you like to try again? (y/n): ").lower()
                if retry != 'y':
                    raise ValueError("Configuration aborted by user")

    # def export_config(self, file_path: str) -> None:
    #     """Export current configuration to a file."""
    #     if not self._config_loaded:
    #         raise RuntimeError("No configuration to export")
    #
    #     try:
    #         with open(file_path, 'w', encoding='utf-8') as f:
    #             f.write(f'message: "{self.message}"\n')
    #             f.write(f'maximum_msg_size: {self.maximum_msg_size}\n')
    #             f.write(f'window_size: {self.window_size}\n')
    #             f.write(f'timeout: {self.timeout}\n')
    #     except Exception as e:
    #         raise RuntimeError(f"Failed to export configuration: {str(e)}")
    #
    # def reset_config(self) -> None:
    #     """Reset configuration to initial state."""
    #     self.message = None
    #     self.maximum_msg_size = None
    #     self.window_size = None
    #     self.timeout = None
    #     self._config_loaded = False

    def load_from_file(self, file_path):
        """
        Reads the configuration parameters from a text file.

        :param file_path: Path to the configuration file.
        :raises: FileNotFoundError if file doesn't exist
        :raises: ValueError if file format is invalid
        """
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"Configuration file not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()

            # Initialize parameters dictionary
            params: Dict[str, Any] = {
                'message': None,
                'maximum_msg_size': None,
                'window_size': None,
                'timeout': None
            }

            # Parse file content
            for line_num, line in enumerate(content.split('\n'), 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue

                try:
                    key, value = [part.strip() for part in line.split(':', 1)]
                except ValueError:
                    logging.warning(f"Skipping invalid line {line_num}: {line}")
                    continue

                if key in params:
                    # Handle string vs integer values
                    if key == 'message':
                        params[key] = value.strip('"')
                    else:
                        try:
                            params[key] = int(value)
                        except ValueError:
                            raise ValueError(
                                f"Invalid value for {key} on line {line_num}: {value}"
                            )
                else:
                    logging.warning(f"Unknown parameter on line {line_num}: {key}")

            # Check for missing parameters
            missing = [k for k, v in params.items() if v is None]
            if missing:
                raise ValueError(
                    f"Missing required parameters: {', '.join(missing)}"
                )

            self.message = params['message']
            self.maximum_msg_size = params['maximum_msg_size']
            self.window_size = params['window_size']
            self.timeout = params['timeout']

            self.validate_config()
            self._config_loaded = True

        except Exception as e:
            self._config_loaded = False
            raise ValueError(f"Error loading configuration: {str(e)}") from e

    def is_config_loaded(self):
        """Returns whether configuration has been successfully loaded."""
        return self._config_loaded

    @staticmethod
    def get_default_client_config_path():
        try:

            if not os.path.exists(config_path_client):
                raise FileNotFoundError(f"Config file not found at {config_path_client}")

            return config_path_client
        except Exception as e:
            print(f"Error finding config file: {e}")
            return None

    @staticmethod
    def get_default_server_config_path():
        try:

            if not os.path.exists(config_path_server):
                raise FileNotFoundError(f"Config file not found at {config_path_server}")

            return config_path_server
        except Exception as e:
            print(f"Error finding config file: {e}")
            return None

    # def __str__(self):
    #     """Returns a string representation of the current configuration."""
    #     if not self._config_loaded:
    #         return "Configuration not loaded"
    #
    #     msg_bytes = len(self.message.encode('utf-8'))
    #     num_segments = (msg_bytes + self.maximum_msg_size - 1) // self.maximum_msg_size
    #
    #     return (
    #         f"Message: {self.message}\n"
    #         f"Message Size: {msg_bytes} bytes\n"
    #         f"Maximum Message Size: {self.maximum_msg_size} bytes\n"
    #         f"Number of Segments: {num_segments}\n"
    #         f"Window Size: {self.window_size}\n"
    #         f"Timeout: {self.timeout} seconds"
    #     )

    def client_config_str(self):
        """Returns a string representation of the client side configuration."""
        if not self._config_loaded:
            return "Configuration not loaded"

        return (
            f"   - MSG : {self.message}\n"
            f"   - TIMEOUT : {self.timeout} seconds"
        )

    def server_config_str(self):
        """Returns a string representation of the server side configuration."""
        if not self._config_loaded:
            return "Configuration not loaded"

        msg_bytes = len(self.message.encode('utf-8'))
        num_segments = (msg_bytes + self.maximum_msg_size - 1) // self.maximum_msg_size

        return (
            f"   - MSG_SIZE : {msg_bytes} bytes\n"
            f"   - MAX_MSG_SIZE : {self.maximum_msg_size} bytes\n"
            f"   - NUM_OF_SEG : {num_segments}\n"
            f"   - WNDW_SIZE: {self.window_size}\n"
        )
