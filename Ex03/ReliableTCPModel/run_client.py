from config_manager import ConfigManager
from reliable_client import ReliableClient
import logging  # https://docs.python.org/3/library/logging.html
import time  # https://docs.python.org/3/library/time.html
import random  # https://www.w3schools.com/python/module_random.asp , Intro to Computation Course - Year I Semester I
import string  # https://docs.python.org/3/library/string.html , Intro to Computation Course - Year I Semester I


def get_test_parameters():
    """Prompt user for test parameters"""
    params = {}
    try:
        print("\nEnter test parameters:")
        params['msg_count'] = int(input("Number of messages to send: "))
        params['min_size'] = int(input("Minimum message size (bytes): "))
        params['max_size'] = int(input("Maximum message size (bytes): "))
        params['interval'] = float(input("Interval between messages (seconds): "))

        if params['msg_count'] <= 0:
            raise ValueError("Message count must be positive")
        if params['min_size'] <= 0 or params['max_size'] <= 0:
            raise ValueError("Message sizes must be positive")
        if params['min_size'] > params['max_size']:
            raise ValueError("Minimum size cannot be greater than maximum size")
        if params['interval'] < 0:
            raise ValueError("Interval cannot be negative")

        return params
    except ValueError as e:
        print(f"Invalid input: {e}")
        return None


def generate_random_message(min_size: int, max_size: int) -> str:
    """Generates a random message of specified size range"""
    size = random.randint(min_size, max_size)
    return ''.join(random.choices(string.ascii_letters + string.digits, k=size))


def run_basic_test(client: ReliableClient, params: dict) -> bool:
    """Runs basic test with fixed-size messages at regular intervals"""
    print("\nRunning basic test scenario...")
    success_count = 0

    for i in range(params['msg_count']):
        message = generate_random_message(params['min_size'], params['min_size'])
        print(f"\nSending message {i + 1}/{params['msg_count']} (size: {len(message)} bytes)")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if client.send_message(message):
                    success_count += 1
                    print("Message sent successfully")
                    break
                else:
                    if attempt < max_attempts - 1:
                        print(f"Retrying message... (attempt {attempt + 2}/{max_attempts})")
                        time.sleep(params['interval'])
                    else:
                        print("Failed to send message after all attempts")
            except Exception as e:
                print(f"Error sending message: {e}")
                if attempt < max_attempts - 1:
                    print(f"Retrying message... (attempt {attempt + 2}/{max_attempts})")
                    time.sleep(params['interval'])
                else:
                    print("Failed to send message after all attempts")

        time.sleep(params['interval'])

    print(f"\nTest completed. Success rate: {success_count}/{params['msg_count']}")
    return success_count == params['msg_count']


def run_stress_test(client: ReliableClient, params: dict) -> bool:
    """Runs stress test with large messages and minimal intervals"""
    print("\nRunning stress test scenario...")
    success_count = 0

    for i in range(params['msg_count']):
        message = generate_random_message(params['max_size'], params['max_size'])
        print(f"\nSending message {i + 1}/{params['msg_count']} (size: {len(message)} bytes)")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if client.send_message(message):
                    success_count += 1
                    print("Message sent successfully")
                    break
                else:
                    if attempt < max_attempts - 1:
                        print(f"Retrying message... (attempt {attempt + 2}/{max_attempts})")
                        time.sleep(0.5)
                    else:
                        print("Failed to send message after all attempts")
            except Exception as e:
                print(f"Error sending message: {e}")
                if attempt < max_attempts - 1:
                    print(f"Retrying message... (attempt {attempt + 2}/{max_attempts})")
                    time.sleep(0.5)
                else:
                    print("Failed to send message after all attempts")

        time.sleep(0.1)

    print(f"\nTest completed. Success rate: {success_count}/{params['msg_count']}")
    return success_count == params['msg_count']


def run_random_test(client: ReliableClient, params: dict) -> bool:
    """Runs random test with varying message sizes and intervals"""
    print("\nRunning random test scenario...")
    success_count = 0

    for i in range(params['msg_count']):
        size = random.randint(params['min_size'], params['max_size'])
        message = generate_random_message(size, size)
        interval = random.uniform(0.1, params['interval'] * 2)

        print(f"\nSending message {i + 1}/{params['msg_count']}")
        print(f"Size: {len(message)} bytes")
        print(f"Waiting interval: {interval:.2f}s")

        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                if client.send_message(message):
                    success_count += 1
                    print("Message sent successfully")
                    break
                else:
                    if attempt < max_attempts - 1:
                        print(f"Retrying message... (attempt {attempt + 2}/{max_attempts})")
                        time.sleep(interval)
                    else:
                        print("Failed to send message after all attempts")
            except Exception as e:
                print(f"Error sending message: {e}")
                if attempt < max_attempts - 1:
                    print(f"Retrying message... (attempt {attempt + 2}/{max_attempts})")
                    time.sleep(interval)
                else:
                    print("Failed to send message after all attempts")

        time.sleep(interval)

    print(f"\nTest completed. Success rate: {success_count}/{params['msg_count']}")
    return success_count == params['msg_count']


def select_client_mode():
    """Prompt user to select client mode"""
    while True:
        print("\nSelect client mode:")
        print("1. Normal mode")
        print("2. Test mode")

        choice = input("\nEnter your choice (1-2): ").strip()

        if choice == "1":
            return "normal", None
        elif choice == "2":
            print("\nSelect test scenario:")
            print("1. Basic (fixed-size messages)")
            print("2. Stress (large messages)")
            print("3. Random (varying sizes)")

            scenario = input("\nEnter your choice (1-3): ").strip()
            if scenario in ["1", "2", "3"]:
                scenarios = {
                    "1": "basic",
                    "2": "stress",
                    "3": "random"
                }
                params = get_test_parameters()
                if params:
                    return "test", (scenarios[scenario], params)

        print("Invalid choice. Please try again.")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    config = ConfigManager()
    client = None

    try:
        print("Welcome to the Reliable Transfer Client!")
        print("---------------------------------------")

        mode, test_config = select_client_mode()

        if mode == "test":
            # Use default configuration for testing
            config_path = ConfigManager.get_default_client_config_path()
            if not config_path:
                return
            config.load_from_file(config_path)
            print("\nLoaded default configuration for testing")
        else:
            # Handle regular configuration
            while True:
                try:
                    if not _handle_configuration_input(config):
                        return
                    break
                except Exception as e:
                    print(f"\nConfiguration error: {e}")
                    if not _should_retry():
                        return

        print("\nCurrent Configuration:")
        print(config.client_config_str())

        # Connect to server
        max_connection_attempts = 3
        for attempt in range(max_connection_attempts):
            try:
                print(f"\nConnecting to server (attempt {attempt + 1}/{max_connection_attempts})...")
                client = ReliableClient('127.0.0.1', 5000, config)

                if client.connect():
                    print("Connected to server successfully!")
                    break
                else:
                    print("Failed to connect to server.")
                    if attempt < max_connection_attempts - 1:
                        print("Retrying...")
                        continue
                    return

            except ConnectionRefusedError:
                print("Server appears to be offline.")
                if attempt < max_connection_attempts - 1:
                    print("Retrying...")
                    continue
                return
            except Exception as e:
                print(f"Connection error: {e}")
                return

        # Handle test mode or regular operation
        if mode == "test":
            scenario, params = test_config
            if scenario == 'basic':
                run_basic_test(client, params)
            elif scenario == 'stress':
                run_stress_test(client, params)
            elif scenario == 'random':
                run_random_test(client, params)
        else:
            # Regular operation mode
            while True:
                try:
                    print("\nOptions:")
                    print("1. Send a message")
                    print("2. Send message from configuration")
                    print("3. Exit")

                    choice = input("\nEnter your choice (1-3): ").strip()

                    if choice == '1':
                        if not _handle_message_send(client):
                            continue
                        print("Message sent successfully.")
                    elif choice == '2':
                        if not _handle_configured_message_send(client, config):
                            continue
                        print("Message sent successfully.")
                    elif choice == '3':
                        print("\nExiting...")
                        break
                    else:
                        print("\nInvalid choice. Please try again.")

                except ConnectionError:
                    print("\nLost connection to server.")
                    break
                except Exception as e:
                    print(f"\nError during operation: {e}")
                    if not _should_retry():
                        break

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if client:
            try:
                client.close()
                print("\nConnection closed.")
            except Exception as e:
                print(f"\nError during cleanup: {e}")


def _handle_configuration_input(config: ConfigManager) -> bool:
    """Handle configuration loading from file or user input."""
    choice = input("Load configuration from (F)ile or (U)ser input? ").strip().lower()

    if choice == 'f':
        return _handle_file_configuration(config)
    elif choice == 'u':
        return _handle_user_configuration(config)
    else:
        print("Invalid choice. Please enter 'F' for file or 'U' for user input.")
        return False


def _handle_file_configuration(config: ConfigManager) -> bool:
    """Handle loading configuration from file."""
    choice = input("Load (D)efault configuration or custom (P)ath? ").strip().lower()

    try:
        if choice == 'd':
            path = ConfigManager.get_default_client_config_path()
            if not path:
                return False
        elif choice == 'p':
            path = input("Enter configuration file path: ").strip()
        else:
            print("Invalid choice.")
            return False

        config.load_from_file(path)
        print("\nLoaded configuration successfully!")
        return True

    except Exception as e:
        print(f"Error loading configuration: {e}")
        return False


def _handle_user_configuration(config: ConfigManager) -> bool:
    """Handle loading configuration through user input."""
    try:
        config.load_from_user_input()
        print("\nConfiguration saved successfully!")
        return True
    except ValueError as e:
        print(f"\nInvalid input: {e}")
        return False
    except Exception as e:
        print(f"\nError during configuration: {e}")
        return False


def _handle_message_send(client: ReliableClient) -> bool:
    """Handle sending a custom message."""
    message = input("\nEnter your message: ").strip()
    if not message:
        print("Message cannot be empty.")
        return False

    print("\nSending message...")
    return client.send_message(message)


def _handle_configured_message_send(client: ReliableClient, config: ConfigManager) -> bool:
    """Handle sending the configured message."""
    if not config.message:
        print("No message configured.")
        return False

    print("\nSending configured message...")
    return client.send_message(config.message)


def _should_retry() -> bool:
    """Ask user if they want to retry after an error."""
    return input("Would you like to try again? (y/n) ").strip().lower() == 'y'


if __name__ == "__main__":
    main()
