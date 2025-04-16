import json  # https://docs.python.org/3/library/json.html , https://realpython.com/python-json/
import logging  # https://docs.python.org/3/library/logging.html
import socket  # From course material
from threading import Lock, Thread  # https://docs.python.org/3/library/threading.html , Course material
from typing import Dict  # https://docs.python.org/3/library/typing.html

from config_manager import ConfigManager
from message_segmentation import MessageSegmenter, Segment


class ReliableServer:
    """
    Implements a reliable server for handling segmented message transmissions.

    The server supports receiving and acknowledging segments, reassembling messages, and
    managing connections with clients. It uses a `MessageSegmenter` for message segmentation
    and reassembly, and a configuration manager to define server parameters.

    Attributes:
        host (str): The server's host address.
        port (int): The port on which the server listens.
        config (ConfigManager): Configuration manager containing server settings.
        socket (Optional[socket.socket]): The server's main socket.
        is_running (bool): Indicates whether the server is running.
        active_connections (set): A set of active client connections.
        segments_lock (Lock): Lock for synchronizing access to `received_segments`.
        received_segments (Dict[str, Dict[int, Segment]]): Stores received segments by message ID.
        highest_contiguous_seq (Dict[str, int]): Tracks the highest contiguous sequence number per message.
        segmenter (MessageSegmenter): Handles segmentation and reassembly of messages.
    """
    def __init__(self, host: str, port: int, config: ConfigManager):
        """
        Initializes the server.

        :param host: The host address to bind the server.
        :type host: str
        :param port: The port to bind the server.
        :type port: int
        :param config: Configuration manager containing server settings.
        :type config: ConfigManager
        """
        self.host = host
        self.port = port
        self.config = config
        self.socket = None
        self.is_running = False
        self.active_connections = set()
        self.segments_lock = Lock()
        self.received_segments: Dict[str, Dict[int, Segment]] = {}  # message_id -> {seq_num -> segment}
        self.highest_contiguous_seq: Dict[str, int] = {}  # message_id -> seq_num
        self.segmenter = MessageSegmenter(config.maximum_msg_size)

    def shutdown(self):
        """
        Shuts down the server.

        Closes all active client connections and the server socket.
        """
        logging.info("Initiating server shutdown...")
        self.is_running = False

        # Close client connections with timeout
        for client_socket in list(self.active_connections):
            try:
                if client_socket:
                    client_socket.shutdown(socket.SHUT_RDWR)
                    client_socket.close()
            except Exception as e:
                logging.error(f"Error closing client connection: {e}")
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                logging.error(f"Error closing server socket: {e}")
        self.active_connections.clear()

        # Close server socket
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                logging.error(f"Error closing server socket: {e}")

    def initialize_socket(self):
        """
        Creates, configures, and binds the server's socket.

        :raises Exception: If the socket fails to initialize or bind.
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(10)
            logging.info(f"Server initialized on {self.host}:{self.port}, mode set to 'LISTEN'")
        except Exception as e:
            logging.error(f"Failed to initialize server: {e}")
            raise

    def handle_max_size_request(self, client: socket.socket) -> bool:
        """
        Handles a client's request for the maximum message size.

        Responds with the maximum message size defined in the server configuration.

        :param client: The client socket from which the request was received.
        :type client: socket.socket
        :return: True if the request was handled successfully, False otherwise.
        :rtype: bool
        """
        try:
            logging.info("Waiting for max size request...")
            request = client.recv(1024).decode('utf-8').strip()
            logging.info(f"Received request: {request}")

            if not request or request != "REQUEST_MAX_SIZE":
                error_message = json.dumps({"STATUS": "ERROR", "MESSAGE": "Invalid request"})
                client.sendall(error_message.encode('utf-8'))
                logging.error("Invalid max size request received")
                return False

            response = json.dumps({
                "MAX_SIZE": self.config.maximum_msg_size,
                "STATUS": "OK"
            })
            logging.info(f"Sending response: {response}")
            client.sendall(response.encode('utf-8'))
            logging.info(f"Sent max message size: {self.config.maximum_msg_size}")
            return True

        except Exception as e:
            logging.error(f"Error handling max size request: {e}")
            return False

    def send_acknowledgment(self, client: socket.socket, message_id: str):
        """
        Sends an acknowledgment for the highest contiguous sequence received for a message.

        :param client: The client socket to which the acknowledgment will be sent.
        :type client: socket.socket
        :param message_id: The ID of the message being acknowledged.
        :type message_id: str
        """
        try:
            ack_message = json.dumps({
                "STATUS": "OK",
                "ACK": self.highest_contiguous_seq[message_id],
            })
            ack_data = ack_message.encode('utf-8')
            total_sent = 0
            while total_sent < len(ack_data):
                sent = client.send(ack_data[total_sent:])
                if sent == 0:
                    raise RuntimeError("Socket connection broken")
                total_sent += sent
        except Exception as e:
            logging.error(f"Error sending acknowledgment: {e}")
            raise  # Propagate error to handle connection failure

    def update_contiguous_sequence(self, message_id: str):
        """
         Updates the highest contiguous sequence number for a message.

         This ensures that the server tracks the next expected segment sequence
         for the message being processed.

         :param message_id: The ID of the message being updated.
         :type message_id: str
         :return: The updated highest contiguous sequence number.
         :rtype: int
         """
        with self.segments_lock:
            current = self.highest_contiguous_seq[message_id]
            segments = self.received_segments[message_id]

            logging.info(f"Updating sequence for {message_id}, starting from {current}")
            logging.info(f"Available segments: {sorted(segments.keys())}")

            # Since we know the first message starts at 0, and we start at -1
            if current == -1 and 0 in segments:
                current = 0
                logging.info("Updated initial sequence to 0")

            # Check for continuous sequence after current
            while (current + 1) in segments:
                current += 1
                logging.info(f"Incremented to {current}")

            self.highest_contiguous_seq[message_id] = current
            logging.info(f"Final sequence number: {current}")
            return current  # Return the updated sequence number

    def handle_client_connection(self, client: socket.socket, addr):
        """
        Handles the lifecycle of a client connection.

        Manages the reception and acknowledgment of message segments, as well
        as reassembly of complete messages.

        :param client: The client socket for the connection.
        :type client: socket.socket
        :param addr: The address of the connected client.
        :type addr: tuple
        """
        self.active_connections.add(client)
        logging.info(f"New connection from {addr}")

        # Track received segments for duplicate detection
        message_history = {}  # Dict for track message IDs and their segments
        completed_messages = set()

        try:
            if not self.handle_max_size_request(client):
                return

            while True:
                try:
                    if not client.fileno():
                        break
                    data = client.recv(self.config.maximum_msg_size + 1024)
                    if not data:
                        logging.info("Client closed connection (no data)")
                        break

                    segment = self.segmenter.deserialize_segment(data)
                    if not segment:
                        continue

                    message_id = segment.message_id
                    seq_num = segment.sequence_number

                    # Check for duplicates before any processing
                    if message_id in completed_messages:
                        logging.warning(
                            f"Duplicate packet detected and discarded - Message: {message_id}, Sequence: M{seq_num}")
                        # Still send ACK for the highest contiguous sequence we've seen to prevent retransmit
                        ack_message = json.dumps({
                            "STATUS": "OK",
                            "ACK": f"M{segment.total_segments - 1}"  # Send final ACK
                        })
                        client.sendall(ack_message.encode('utf-8'))
                        continue

                    if message_id not in message_history:
                        message_history[message_id] = set()

                    # Check for duplicates in ongoing messages
                    if seq_num in message_history[message_id]:
                        logging.warning(
                            f"Duplicate packet detected and discarded - Message: {message_id}, Sequence: M{seq_num}")
                        # Still send ACK for the highest contiguous sequence we've seen to prevent retransmit
                        current_seq = self.highest_contiguous_seq.get(message_id, -1)
                        ack_message = json.dumps({
                            "STATUS": "OK",
                            "ACK": f"M{current_seq}"
                        })
                        client.sendall(ack_message.encode('utf-8'))
                        continue

                    # Record this segment as received
                    message_history[message_id].add(seq_num)
                    logging.info(f"Processing new segment M{seq_num} of message {message_id}")

                    with self.segments_lock:
                        # Initialize if new message
                        if message_id not in self.received_segments:
                            self.received_segments[message_id] = {}
                            self.highest_contiguous_seq[message_id] = -1
                            logging.info(f"Initialized new message {message_id}")

                        # Store the segment
                        self.received_segments[message_id][seq_num] = segment
                        logging.info(f"Stored segment M{seq_num}")

                        # Update sequence - check for contiguous segments
                        current_seq = self.highest_contiguous_seq[message_id]
                        while current_seq + 1 in self.received_segments[message_id]:
                            current_seq += 1

                        self.highest_contiguous_seq[message_id] = current_seq
                        logging.info(f"Updated sequence to M{current_seq}")

                        # Send acknowledgment
                        ack_message = json.dumps({
                            "STATUS": "OK",
                            "ACK": f"M{current_seq}"
                        })
                        logging.info(f"Sending ACK message: {ack_message}")
                        client.sendall(ack_message.encode('utf-8'))
                        logging.info(f"ACK sent successfully")

                        # If this was the last segment and we've received everything
                        if segment.is_last and current_seq == segment.total_segments - 1:
                            message = self.segmenter.reassemble_message(
                                list(self.received_segments[message_id].values())
                            )
                            logging.info(f"Received complete message: {message}")

                            completed_messages.add(message_id)

                            # Clean up this message's tracking
                            del self.received_segments[message_id]
                            del self.highest_contiguous_seq[message_id]
                            logging.info("Waiting for next message...")

                except ConnectionResetError:
                    logging.warning(f"Client forcibly closed connection: {addr}")
                    break
                except socket.timeout:
                    logging.warning(f"Client disconnected due to timeout: {addr}")
                    break
                except Exception as e:
                    logging.error(f"Error processing data: {e}", exc_info=True)
                    break

        finally:
            if client in self.active_connections:
                self.active_connections.remove(client)
            try:
                client.close()
                logging.info(f"Connection from {addr} closed")
            except Exception as e:
                logging.error(f"Error closing client connection: {e}")

    def run(self):
        """
        Starts the server and listens for client connections.

        The server handles incoming connections, processes client requests, and ensures
        reliable message transmission. Gracefully shuts down on receiving a termination signal.
        """
        self.initialize_socket()
        self.is_running = True

        while self.is_running:
            try:
                self.socket.settimeout(1.0)  # Add timeout to allow checking is_running
                try:
                    client, addr = self.socket.accept()
                    Thread(target=self.handle_client_connection, args=(client, addr)).start()
                except socket.timeout:
                    continue  # Check is_running condition
                except Exception as e:
                    logging.error(f"Error accepting connection: {e}")

            except KeyboardInterrupt:
                logging.info("Received shutdown signal")
                break

        self.shutdown()

        if self.socket:
            self.socket.close()

    def __del__(self):
        self.shutdown()
