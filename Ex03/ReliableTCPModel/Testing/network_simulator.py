import json  # https://docs.python.org/3/library/json.html , https://www.w3schools.com/python/python_json.asp
import random  # https://www.w3schools.com/python/module_random.asp , Intro to Computation Course - Year I Semester I
import socket  # Course material
import threading  # https://docs.python.org/3/library/threading.html , Course material
import queue  # https://docs.python.org/3/library/queue.html , Data Structures Course - Year I Semester II
import time  # https://docs.python.org/3/library/time.html
import logging  # https://docs.python.org/3/library/logging.html
from typing import Optional, List, Tuple


class NetworkConditions:
    """Configuration class for network simulation conditions"""

    def __init__(self):
        self.packet_loss_rate = 0.0  # Probability of dropping a packet
        self.ack_loss_rate = 0.0  # Probability of dropping an ACK
        self.delay_range = (0, 0)  # Random delay range in seconds (min, max)
        self.duplication_rate = 0.0  # Probability of duplicating a packet
        self.reordering_rate = 0.0  # Probability of reordering packets
        self.reordering_delay = 0.5  # Delay for reordered packets


class NetworkSimulator:
    """
    Simulates various network conditions for testing TCP reliability mechanisms.
    Acts as a proxy between client and server.
    """

    def __init__(self, listen_port: int, target_port: int):
        self.listen_port = listen_port
        self.target_port = target_port
        self.conditions = NetworkConditions()
        self.socket = None
        self.is_running = False
        self.client_connections = set()
        self.packet_queue = queue.Queue()
        self.active_connections = {}

    def start(self):
        """Starts the network simulator"""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind(('127.0.0.1', self.listen_port))
        self.socket.listen(5)
        self.is_running = True

        # Start packet processing thread
        threading.Thread(target=self._process_packet_queue, daemon=True).start()

        while self.is_running:
            try:
                client_sock, addr = self.socket.accept()
                self.client_connections.add(client_sock)
                threading.Thread(target=self._handle_connection,
                                 args=(client_sock,), daemon=True).start()
            except Exception as e:
                logging.error(f"Error accepting connection: {e}")

    def stop(self):
        """Stops the network simulator"""
        self.is_running = False
        # Clean up all active connections
        for conn_id in list(self.active_connections.keys()):
            self._cleanup_connection(conn_id)
        if self.socket:
            try:
                self.socket.close()
            except:
                pass

    @staticmethod
    def _should_process_special(data: bytes) -> bool:
        """Check if this is a special packet that should bypass normal simulation"""
        try:
            decoded = data.decode('utf-8').strip()
            return (decoded == "REQUEST_MAX_SIZE" or
                   '"MAX_SIZE":' in decoded)  # Max size response
        except:
            return False

    def _should_drop_packet(self, is_ack: bool) -> bool:
        """Determines if a packet should be dropped based on configured rates"""
        rate = self.conditions.ack_loss_rate if is_ack else self.conditions.packet_loss_rate
        return random.random() < rate

    def _handle_connection(self, client_socket: socket.socket):
        """Handles a client connection by forwarding data through the simulator"""
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        conn_id = id(client_socket)  # Unique identifier for this connection

        try:
            server_socket.connect(('127.0.0.1', self.target_port))
            self.active_connections[conn_id] = (client_socket, server_socket)

            def forward(source: socket.socket, destination: socket.socket, is_client_to_server: bool):
                try:
                    while conn_id in self.active_connections:
                        try:
                            data = source.recv(65536)
                            if not data:
                                break

                            if self._should_process_special(data):
                                logging.info("Processing handshake packet directly")
                                destination.sendall(data)
                                continue

                            # Try to parse data to determine if it's an ACK
                            try:
                                parsed = json.loads(data.decode('utf-8'))
                                is_ack = 'ACK' in parsed and parsed.get('STATUS') == 'OK'
                            except:
                                is_ack = False

                            # Use appropriate drop rate based on packet type
                            if is_ack:
                                drop_rate = self.conditions.ack_loss_rate
                            else:
                                drop_rate = self.conditions.packet_loss_rate

                            if random.random() < drop_rate:
                                logging.info(f"Dropping {'ACK' if is_ack else 'data packet'}")
                                continue

                            # Handle packet duplication
                            packets = [(data, 0)]
                            if not is_ack and random.random() < self.conditions.duplication_rate:
                                logging.info("Duplicating packet")
                                packets.append((data, 0.05))

                            # Process each packet
                            for packet, additional_delay in packets:
                                base_delay = random.uniform(
                                    self.conditions.delay_range[0],
                                    self.conditions.delay_range[1]
                                )
                                delay = base_delay + additional_delay

                                # Add reordering delay if applicable (only for data packets)
                                if (not is_ack and
                                        random.random() < self.conditions.reordering_rate):
                                    delay += self.conditions.reordering_delay
                                    logging.info("Reordering packet")

                                # Queue the packet for sending
                                self.packet_queue.put((destination, data, delay, conn_id))

                        except socket.timeout:
                            continue
                        except Exception as e:
                            logging.error(f"Error processing packet: {e}")
                            continue

                except Exception as e:
                    logging.error(f"Error in forwarding: {e}")
                finally:
                    try:
                        source.close()
                        destination.close()
                    except:
                        pass

            client_socket.settimeout(5)  # 5 second timeout
            server_socket.settimeout(5)  # 5 second timeout

            # Start forwarding threads
            client_to_server = threading.Thread(
                target=forward,
                args=(client_socket, server_socket, True)
            )
            server_to_client = threading.Thread(
                target=forward,
                args=(server_socket, client_socket, False)
            )

            client_to_server.daemon = True
            server_to_client.daemon = True

            client_to_server.start()
            server_to_client.start()

            # Wait for threads
            while client_to_server.is_alive() and server_to_client.is_alive():
                time.sleep(0.1)

        except Exception as e:
            logging.error(f"Error setting up connection: {e}")
        finally:
            self._cleanup_connection(conn_id)

    def _cleanup_connection(self, conn_id: int):
        """Clean up a connection and its resources"""
        if conn_id in self.active_connections:
            client_socket, server_socket = self.active_connections[conn_id]
            try:
                client_socket.close()
            except:
                pass
            try:
                server_socket.close()
            except:
                pass
            del self.active_connections[conn_id]

    def _process_packet_queue(self):
        """Processes queued packets with their designated delays"""
        while self.is_running:
            try:
                destination, data, delay, conn_id = self.packet_queue.get(timeout=1)
                # Check if connection is still active
                if conn_id not in self.active_connections:
                    continue

                if delay > 0:
                    time.sleep(delay)

                # Double-check connection is still active after delay
                if conn_id in self.active_connections:
                    try:
                        if destination.fileno() != -1:  # Check if socket is still valid
                            destination.sendall(data)
                    except:
                        # Remove connection if it's no longer valid
                        if conn_id in self.active_connections:
                            del self.active_connections[conn_id]

            except queue.Empty:
                continue
            except Exception as e:
                if "not a socket" not in str(e):  # Ignore expected socket cleanup errors
                    logging.error(f"Error processing packet: {e}")

    def set_conditions(self,
                       packet_loss: float = 0.0,
                       ack_loss: float = 0.0,
                       min_delay: float = 0.0,
                       max_delay: float = 0.0,
                       duplication: float = 0.0,
                       reordering: float = 0.0):
        """Sets the network conditions for simulation"""
        self.conditions.packet_loss_rate = packet_loss
        self.conditions.ack_loss_rate = ack_loss
        self.conditions.delay_range = (min_delay, max_delay)
        self.conditions.duplication_rate = duplication
        self.conditions.reordering_rate = reordering
