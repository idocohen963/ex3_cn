from dataclasses import dataclass  # https://docs.python.org/3/library/dataclasses.html
from typing import List, Dict, Optional  # https://docs.python.org/3/library/typing.html
import time  # https://docs.python.org/3/library/time.html , https://www.geeksforgeeks.org/python-time-module/
import threading  # From course material
import logging  # https://docs.python.org/3/library/logging.html

from message_segmentation import Segment


@dataclass
class WindowSegment:
    """
    Represents a segment in the sliding window.

    Attributes:
        sequence_number (int): The sequence number of the segment.
        data (bytes): The data of the segment.
        sent_time (float): The timestamp when the segment was sent.
        original_segment (Optional[Segment]): The original segment associated with this window segment.
        acked (bool): Indicates whether this segment has been acknowledged.

    Example:
        window_segment = WindowSegment(
            sequence_number=1,
            data=b"Hello, World!",
            sent_time=time.time(),
            original_segment=segment,
            acked=False
        )
    """
    sequence_number: int
    data: bytes
    sent_time: float
    original_segment: Optional[Segment] = None  # Store original segment
    acked: bool = False


class SlidingWindow:
    """
    Implements a sliding window mechanism for reliable transmission.

    The sliding window manages the sending, acknowledgment, and retransmission of data segments,
    ensuring proper flow control and error handling.

    Attributes:
        window_size (int): Maximum number of unacknowledged segments allowed in the window.
        timeout_seconds (int): Time (in seconds) to wait for an acknowledgment before retransmission.
        base (int): Sequence number of the first segment in the current window.
        next_seq (int): Next sequence number to be assigned to a new segment.
        segments (Dict[int, WindowSegment]): A dictionary of segments currently in the window.
        timer (Optional[threading.Timer]): Timer for managing retransmission timeouts.
        callback (Optional[Callable[[List[WindowSegment]], None]]): Callback function for retransmission.
    """
    def __init__(self, window_size: int, timeout_seconds: int):
        """
        Initializes the sliding window with the specified size and timeout.

        :param window_size: The maximum number of segments in the window.
        :type window_size: int
        :param timeout_seconds: Timeout duration in seconds for retransmission.
        :type timeout_seconds: int
        """
        if window_size <= 0:
            raise ValueError("Window size must be positive")
        if timeout_seconds <= 0:
            raise ValueError("Timeout must be positive")

        self.window_size = window_size
        self.timeout_seconds = timeout_seconds
        self.base = 0  # Start of the window
        self.next_seq = 0  # Next sequence number to be used
        self.segments: Dict[int, WindowSegment] = {}
        self.timer = None
        self.timer_lock = threading.Lock()
        self.segments_lock = threading.Lock()
        self.callback = None  # Callback for retransmission
        self.is_active = True  # Add active state tracking

    def cleanup(self):
        """Safely clean up resources."""
        with self.timer_lock:
            self.is_active = False
            if self.timer:
                self.timer.cancel()
                self.timer = None
        with self.segments_lock:
            self.segments.clear()

    def set_retransmission_callback(self, callback):
        """
        Sets the callback function to handle retransmissions.

        :param callback: Function to call when retransmission is triggered.
        :type callback: Callable[[List[WindowSegment]], None]
        """
        self.callback = callback

    def start_timer(self):
        """
        Starts the retransmission timer for the oldest unacknowledged segment.
        """
        with self.timer_lock:
            if self.timer is None or not self.timer.is_alive():
                self.timer = threading.Timer(self.timeout_seconds, self._timeout_handler)
                self.timer.daemon = True
                self.timer.start()

    def stop_timer(self):
        """
        Stops the retransmission timer if it is running.
        """
        with self.timer_lock:
            if self.timer:
                self.timer.cancel()
                self.timer = None

    def _timeout_handler(self):
        """
        Handles timeout events by triggering retransmission for unacknowledged segments.

        If a timeout occurs, unacknowledged segments are passed to the retransmission callback,
        and the timer is restarted.
        """
        if not self.is_active:
            return

        # logging.info(f"\nTimeout occurred for window starting at sequence {self.base}")

        unacked_segments = []
        with self.segments_lock:
            current_time = time.time()
            for seq in range(self.base, min(self.base + self.window_size, self.next_seq)):
                segment = self.segments.get(seq)
                if segment and not segment.acked:
                    # Fix 6: Add time-since-last-transmission check
                    if current_time - segment.sent_time >= self.timeout_seconds:
                        unacked_segments.append(segment)
                        segment.sent_time = current_time  # Update sent time

        if self.callback and unacked_segments:
            try:
                self.callback(unacked_segments)
            except Exception as e:
                logging.error(f"Error in retransmission callback: {e}")

        # Restart timer only if there are unacknowledged segments
        with self.segments_lock:
            if any(not s.acked for s in self.segments.values()):
                self.start_timer()

    def can_send(self) -> bool:
        """
        Checks if the window can accept more segments for sending.

        :return: True if the window has room for more segments, False otherwise.
        :rtype: bool
        """
        return self.next_seq < self.base + self.window_size

    def add_segment(self, segment: Segment) -> Optional[WindowSegment]:
        """
        Adds a new segment to the sliding window if space is available.

        :param segment: The `Segment` to add to the window.
        :type segment: Segment
        :return: A `WindowSegment` if the segment was added successfully, None otherwise.
        :rtype: Optional[WindowSegment]
        """
        if not self.can_send():
            return None

        with self.segments_lock:
            window_segment = WindowSegment(
                sequence_number=self.next_seq,
                data=segment.data,
                sent_time=time.time(),
                original_segment=segment  # Store original segment
            )
            self.segments[self.next_seq] = window_segment
            self.next_seq += 1

            # Start timer if this is the first segment in the window
            if self.base == window_segment.sequence_number:
                self.start_timer()

            return window_segment

    def handle_ack(self, ack_number: int):
        """
        Processes an acknowledgment for a specific sequence number.

        Advances the window base and marks segments as acknowledged.

        :param ack_number: The sequence number being acknowledged.
        :type ack_number: int
        """
        logging.info(f"Received ACK M{ack_number}")
        with self.segments_lock:
            if ack_number < self.base or ack_number >= self.next_seq:
                logging.warning(f"Spurious ACK M{ack_number} ignored")
                return

            # Mark all segments up to and including ack_number as acknowledged
            for seq in range(self.base, ack_number + 1):
                if seq in self.segments:
                    self.segments[seq].acked = True

            # Slide window forward
            old_base = self.base
            while self.base <= ack_number:
                if self.base in self.segments and self.segments[self.base].acked:
                    del self.segments[self.base]
                    self.base += 1
                else:
                    break

            # If window moved forward
            if self.base > old_base:
                self.stop_timer()
                # Start new timer if there are unacked segments
                if self.base < self.next_seq:
                    self.start_timer()

    def get_unacked_segments(self) -> List[WindowSegment]:
        """
        Retrieves all unacknowledged segments currently in the window.

        :return: A list of unacknowledged `WindowSegment` objects.
        :rtype: List[WindowSegment]
        """
        with self.segments_lock:
            return [
                segment for segment in self.segments.values()
                if not segment.acked
            ]

    def is_empty(self) -> bool:
        """
        Checks if the sliding window has no unacknowledged segments.

        :return: True if all segments are acknowledged, False otherwise.
        :rtype: bool
        """
        with self.segments_lock:
            return len(self.segments) == 0

    def __str__(self) -> str:
        """
        Returns a string representation of the sliding window state.

        :return: A string showing the sequence numbers and acknowledgment status in the window.
        :rtype: str
        """
        with self.segments_lock:
            segments_status = []
            for seq in range(self.base, self.base + self.window_size):
                if seq in self.segments:
                    segment = self.segments[seq]
                    status = f"SEQ{seq}({'ACK' if segment.acked else 'UNACK'})"
                else:
                    status = f"SEQ{seq}(EMPTY)"
                segments_status.append(status)

            return f"Window[{self.base}:{self.base + self.window_size}] - {' | '.join(segments_status)}"
