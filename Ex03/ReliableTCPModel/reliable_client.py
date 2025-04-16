import hashlib  # https://docs.python.org/3/library/hashlib.html
import time

from message_segmentation import MessageSegmenter
from sliding_window import SlidingWindow
import socket  # From course material
import json  # https://docs.python.org/3/library/json.html , https://realpython.com/python-json/
import logging  # https://docs.python.org/3/library/logging.html
from typing import Optional  # https://docs.python.org/3/library/typing.html
from config_manager import ConfigManager


class ReliableClient:
    """
    Implements a reliable client for sending segmented messages to a server.

    The client establishes a connection with the server, negotiates the maximum message size,
    and uses a sliding window protocol for reliable message transmission with acknowledgment
    and retransmission handling.

    Attributes:
        host (str): The server's host address.
        port (int): The server's port.
        config (ConfigManager): Configuration manager containing client settings.
        socket (Optional[socket.socket]): The client's socket for communication.
        server_max_size (Optional[int]): Maximum message size supported by the server.
        segmenter (Optional[MessageSegmenter]): Handles message segmentation.
        sliding_window (Optional[SlidingWindow]): Manages the sliding window protocol.
    """
    def __init__(self, host: str, port: int, config: ConfigManager):
        """
        Initializes the ReliableClient.

        :param host: The server's host address.
        :type host: str
        :param port: The server's port.
        :type port: int
        :param config: Configuration manager containing client settings.
        :type config: ConfigManager
        """
        self.host = host
        self.port = port
        self.config = config
        self.socket: Optional[socket.socket] = None
        self.server_max_size: Optional[int] = None
        self.segmenter: Optional[MessageSegmenter] = None
        self.sliding_window: Optional[SlidingWindow] = None

    def connect(self) -> bool:
        """
        Establishes a connection to the server and initializes components.

        :return: True if the connection and initialization are successful, False otherwise.
        :rtype: bool
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(30)  # Add connection timeout
            self.socket.connect((self.host, self.port))

            if not self._request_max_size():
                self.close()
                return False

            try:
                self.segmenter = MessageSegmenter(self.server_max_size)
                self.sliding_window = SlidingWindow(
                    window_size=self.config.window_size,
                    timeout_seconds=self.config.timeout
                )
                self.sliding_window.set_retransmission_callback(self._handle_retransmission)

                # Reset timeout to normal after connection is established
                self.socket.settimeout(self.config.timeout)
                return True
            except Exception as e:
                logging.error(f"Failed to initialize components: {e}")
                self.close()
                return False

        except Exception as e:
            logging.error(f"Connection failed: {e}", exc_info=True)
            if self.socket:
                self.close()
            return False

    def _request_max_size(self) -> bool:
        """
        Requests the maximum message size supported by the server.

        :return: True if the request is successful, False otherwise.
        :rtype: bool
        """
        try:
            # Send request
            logging.info("Sending max size request to server")
            self.socket.sendall("REQUEST_MAX_SIZE".encode('utf-8'))

            # Receive response with retry
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    logging.info("Waiting for server response...")
                    response = self.socket.recv(1024).decode('utf-8')
                    logging.info(f"Received response: {response}")

                    response_data = json.loads(response)
                    if response_data.get('STATUS') == 'OK':
                        self.server_max_size = response_data.get('MAX_SIZE')
                        return True
                    else:
                        logging.error(f"Server returned invalid status: {response_data.get('STATUS')}")
                        return False

                except socket.timeout:
                    if attempt < max_retries - 1:
                        logging.warning(f"Timeout on attempt {attempt + 1}, retrying...")
                        continue
                    logging.error("Max retries exceeded for max size request")
                    return False

        except Exception as e:
            logging.error(f"Error requesting maximum message size: {e}")
            return False

    def _handle_retransmission(self, segments):
        """
        Handles retransmission of segments upon timeout.

        Called by the sliding window protocol to resend unacknowledged segments.

        :param segments: A list of `WindowSegment` objects to retransmit.
        :type segments: List[WindowSegment]
        """
        backoff = 0.5
        for window_segment in segments:
            try:
                if window_segment.original_segment:
                    serialized = self.segmenter.serialize_segment(window_segment.original_segment)
                    self.socket.sendall(serialized)
                    logging.info(f"Retransmitted segment {window_segment.sequence_number}")
            except Exception as e:
                logging.error(f"Error retransmitting segment: {e}")
            finally:
                backoff = min(backoff * 2, self.config.timeout)  # Exponential backoff
                time.sleep(backoff)

    @staticmethod
    def _calculate_checksum(data: bytes) -> str:
        """
        Computes the SHA-256 checksum for the given data.

        :param data: The data for which to compute the checksum.
        :type data: bytes
        :return: The hexadecimal checksum string.
        :rtype: str
        """
        return hashlib.sha256(data).hexdigest()

    def send_message(self, message: str) -> bool:
        """
        Sends a message to the server using segmentation and sliding window protocol.

        Segments the message, transmits segments, and handles acknowledgments
        and retransmissions as necessary.

        :param message: The message to be sent.
        :type message: str
        :return: True if the message is sent successfully, False otherwise.
        :rtype: bool
        """
        if not all([self.socket, self.server_max_size, self.segmenter, self.sliding_window]):
            logging.error("Client not properly initialized")
            return False

        try:
            # Reset sliding window for new message
            self.sliding_window = SlidingWindow(
                window_size=self.config.window_size,
                timeout_seconds=self.config.timeout
            )
            self.sliding_window.set_retransmission_callback(self._handle_retransmission)

            # Segment the message
            segments = self.segmenter.segment_message(message)
            max_retries = 5
            retry_count = 0
            total_timeout = time.time() + (self.config.timeout * 3)  # Overall timeout

            while (segments or not self.sliding_window.is_empty()) and time.time() < total_timeout:
                if retry_count >= max_retries:
                    logging.error("Max retries exceeded for message")
                    return False

                # Send new segments if window has space
                while segments and self.sliding_window.can_send():
                    segment = segments.pop(0)
                    window_segment = self.sliding_window.add_segment(segment)
                    if window_segment:
                        serialized = self.segmenter.serialize_segment(segment)
                        self.socket.sendall(serialized)
                        logging.info(f"Sent segment M{segment.sequence_number}")

                # Wait for acknowledgment
                ack_timeout = min(0.5, (total_timeout - time.time()) / 2)
                if ack_timeout <= 0:
                    break

                try:
                    self.socket.settimeout(ack_timeout)
                    ack_data = self.socket.recv(1024).decode('utf-8')
                    try:
                        ack = json.loads(ack_data)
                        if ack.get('STATUS') == 'OK':
                            ack_num = int(ack.get('ACK').replace('M', ''))
                            self.sliding_window.handle_ack(ack_num)
                            retry_count = 0  # Reset retry count on successful ACK
                            if not segments and self.sliding_window.is_empty():
                                return True
                    except json.JSONDecodeError:
                        logging.warning("Received malformed ACK")
                        continue

                except socket.timeout:
                    retry_count += 1
                    # Exponential backoff for retries
                    backoff = min(0.1 * (2 ** retry_count), 1.0)
                    logging.warning(f"Timeout waiting for ACK (retry {retry_count}/{max_retries})")
                    time.sleep(backoff)
                    continue
                except Exception as e:
                    logging.error(f"Error receiving acknowledgment: {e}")
                    retry_count += 1
                    continue

            if time.time() >= total_timeout:
                logging.error("Total timeout exceeded for message")
                return False

            return not segments and self.sliding_window.is_empty()

        except Exception as e:
            logging.error(f"Error in send_message: {e}", exc_info=True)
            return False

    def sendall(self, data):
        """Wrapper for socket's sendall method (used for mock in testing)."""
        if self.socket:
            self.socket.sendall(data)

    def close(self):
        """
        Closes the connection to the server.

        Ensures the socket is properly closed to release resources.
        """
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
                self.socket.close()
            except Exception as e:
                logging.error(f"Error during socket cleanup: {e}")
            finally:
                self.socket = None

    def __del__(self):
        self.close()
