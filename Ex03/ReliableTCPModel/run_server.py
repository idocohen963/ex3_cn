from Testing.network_simulator import NetworkSimulator
from config_manager import ConfigManager
from reliable_server import ReliableServer
import logging  # https://docs.python.org/3/library/logging.html
import threading  # https://docs.python.org/3/library/threading.html , Course material


def select_server_mode():
    """Prompt user to select server mode"""
    while True:
        print("\nSelect server mode:")
        print("1. Normal mode")
        print("2. Network simulation mode")

        choice = input("\nEnter your choice (1-2): ").strip()

        if choice == "1":
            return "normal", None
        elif choice == "2":
            conditions = get_network_conditions()
            if conditions:
                return "simulation", conditions
        else:
            print("Invalid choice. Please try again.")


def get_network_conditions():
    """Prompt user for network simulation conditions"""
    conditions = {}
    try:
        print("\nEnter network simulation conditions (0.0-1.0 for rates):")
        conditions['packet_loss'] = float(input("Packet loss rate: "))
        conditions['ack_loss'] = float(input("ACK loss rate: "))
        conditions['min_delay'] = float(input("Minimum delay (seconds): "))
        conditions['max_delay'] = float(input("Maximum delay (seconds): "))
        conditions['duplication'] = float(input("Packet duplication rate: "))
        conditions['reordering'] = float(input("Packet reordering rate: "))

        for key, value in conditions.items():
            if key.endswith('rate') and (value < 0 or value > 1):
                raise ValueError(f"{key} must be between 0 and 1")
            if key.endswith('delay') and value < 0:
                raise ValueError(f"{key} cannot be negative")

        return conditions
    except ValueError as e:
        print(f"Invalid input: {e}")
        return None


def main():
    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(levelname)s: %(message)s',
        datefmt='%H:%M:%S'
    )

    config = ConfigManager()
    server = None
    simulator = None

    try:
        print("Welcome to the Reliable Transfer Server!")
        print("---------------------------------------")

        while True:
            try:
                if not _handle_configuration_input(config):
                    return
                break
            except Exception as e:
                print(f"\nConfiguration error: {e}")
                if not _should_retry():
                    return

        print("\nServer Configuration:")
        print(config.server_config_str())

        mode, conditions = select_server_mode()

        try:
            print("\nInitializing server...")

            if mode == "simulation":
                # Start the actual server on a different port
                server = ReliableServer('127.0.0.1', 5001, config)

                simulator = NetworkSimulator(listen_port=5000, target_port=5001)
                simulator.set_conditions(**conditions)

                # Start simulator in a separate thread
                simulator_thread = threading.Thread(target=simulator.start)
                simulator_thread.daemon = True
                simulator_thread.start()

                print("\nNetwork Simulator active with conditions:")
                for key, value in conditions.items():
                    print(f"{key}: {value}")
            else:
                server = ReliableServer('127.0.0.1', 5000, config)

            print("\nServer starting...")
            print("Press CTRL + C to shutdown the server")
            print("------------------------------------")

            server.run()

        except OSError as e:
            print(f"\nNetwork error: {e}")
            print("Please check if the port is available and try again.")
        except Exception as e:
            print(f"\nServer initialization error: {e}")

    except KeyboardInterrupt:
        print("\nServer shutdown requested.")
    except Exception as e:
        print(f"\nAn error occurred: {e}")
    finally:
        if simulator:
            simulator.stop()
        if server:
            try:
                server.shutdown()
                print("\nServer shutdown complete.")
            except Exception as e:
                print(f"\nError during server shutdown: {e}")


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
            path = ConfigManager.get_default_server_config_path()
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


def _should_retry() -> bool:
    """Ask user if they want to retry after an error."""
    return input("Would you like to try again? (y/n) ").strip().lower() == 'y'


if __name__ == "__main__":
    main()
