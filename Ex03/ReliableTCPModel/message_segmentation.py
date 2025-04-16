from dataclasses import dataclass  # https://docs.python.org/3/library/dataclasses.html
from typing import List, Optional  # https://docs.python.org/3/library/typing.html
import hashlib  # https://docs.python.org/3/library/hashlib.html
import json  # https://docs.python.org/3/library/json.html , https://realpython.com/python-json/
import logging  # https://docs.python.org/3/library/logging.html
import math  # https://docs.python.org/3/library/math.html


@dataclass
class Segment:
    """
    Represents a single message segment with associated metadata.

    Attributes:
        sequence_number (int): The sequence number of the segment in the message.
        data (bytes): The actual data of the segment.
        checksum (str): SHA-256 checksum of the segment's data for integrity verification.
        total_segments (int): Total number of segments in the original message.
        message_id (str): Unique identifier for the message.
        is_last (bool): Indicates if this is the last segment of the message.
        original_length (int): The original length of the full message in bytes.

    Example:
        segment = Segment(
            sequence_number=0,
            data=b"Hello, World!",
            checksum="abc123...",
            total_segments=1,
            message_id="1-abcd1234",
            is_last=True,
            original_length=13
        )
    """
    sequence_number: int
    data: bytes
    checksum: str
    total_segments: int
    message_id: str
    is_last: bool
    original_length: int


# noinspection PyShadowingNames
class MessageSegmenter:
    """
    Handles message segmentation and reassembly with support for UTF-8 encoding boundaries,
    metadata, and checksums for reliable data transmission.

    Attributes:
        max_data_size (int): Maximum size of the data portion in each segment.
        metadata_overhead (int): Estimated fixed overhead for metadata in each segment.
        message_counter (int): Counter to generate unique message IDs.
    """
    def __init__(self, max_segment_size: int):
        """
        Initializes the MessageSegmenter with a maximum segment size.

        :param max_segment_size: Maximum size (in bytes) of a single segment, including metadata.
        :type max_segment_size: int
        :raises ValueError: If the maximum segment size is invalid or too small.
        """
        if max_segment_size <= 0:
            raise ValueError("Maximum segment size must be positive")

        sample_metadata = {
            'seq': 0,
            'checksum': 'x' * 64,  # SHA-256 hash length
            'total_segments': 999999,
            'message_id': '999999-ffffffff',
            'is_last': True,
            'original_length': 999999999
        }
        self.metadata_overhead = len(json.dumps({'metadata': sample_metadata, 'data': ''}))

        if max_segment_size <= self.metadata_overhead:
            raise ValueError(
                f"Maximum segment size ({max_segment_size}) must be greater than "
                f"metadata overhead ({self.metadata_overhead})"
            )

        self.max_data_size = max_segment_size - self.metadata_overhead
        self.message_counter = 0
        self.max_segment_size = max_segment_size

        logging.info(f"Message Segmenter initialized with the following parameters:\n"
                     f"   - MAX_SEG_SIZE : {max_segment_size}, \n"
                     f"   - HEADER_SIZE : {self.metadata_overhead}, \n"
                     f"   - MAX_DATA_SIZE : {self.max_data_size}. \n")

    def _generate_message_id(self, message: str) -> str:
        """
        Generates a unique identifier for the message.

        Combines an incrementing counter with a hash of the message content to ensure uniqueness.

        :param message: The message for which to generate the ID.
        :type message: str
        :return: A unique message ID string.
        :rtype: str

        Example:
            message_id = self._generate_message_id("Hello, World!")
            print(message_id)  # Example output: "1-abcd1234"
        """
        self.message_counter += 1
        message_hash = hashlib.sha256(
            f"{self.message_counter}{message}".encode('utf-8')
        ).hexdigest()[:16]
        return f"{self.message_counter}-{message_hash}"

    @staticmethod
    def _calculate_checksum(data: bytes) -> str:
        """Calculates SHA-256 checksum of segment data."""
        return hashlib.sha256(data).hexdigest()

    @staticmethod
    def _find_safe_split_point(message_bytes: bytes, target_size: int) -> int:
        """
        Finds a safe position to split UTF-8 encoded bytes without breaking characters.
        """
        if target_size >= len(message_bytes):
            return len(message_bytes)

        if target_size <= 0:
            raise ValueError("Target size must be positive")

        # Quick check for ASCII-only content
        if all(b <= 0x7F for b in message_bytes[:target_size]):
            return target_size

        # Start from target size and move backward
        pos = target_size
        while pos > 0:
            # Check if we're at a UTF-8 character boundary
            if pos < len(message_bytes) and (
                message_bytes[pos] & 0xC0) != 0x80:  # Not a continuation byte
                try:
                    message_bytes[:pos].decode('utf-8')
                    return pos
                except UnicodeDecodeError:
                    pass
            pos -= 1

        raise ValueError("Could not find valid UTF-8 boundary")

    def segment_message(self, message: str) -> List[Segment]:
        """
        Segments a message into chunks respecting UTF-8 boundaries.

        The method divides a UTF-8 encoded message into smaller segments that can be transmitted
        over a network. Each segment contains metadata including a sequence number, checksum, and
        message ID.

        :param message: The input message to be segmented.
        :type message: str
        :raises ValueError: If the input message is empty or invalid.
        :return: A list of `Segment` objects representing the segmented message.
        :rtype: List[Segment]

        Example:
            segments = segment_message("This is a test message")
            print(len(segments))  # Outputs the number of generated segments
        """
        if not message:
            raise ValueError("Message cannot be empty")

        try:
            message_bytes = message.encode('utf-8')
        except UnicodeEncodeError as e:
            raise ValueError(f"Failed to encode message: {e}")

        message_id = self._generate_message_id(message)
        total_length = len(message_bytes)

        if total_length > (2 ** 32 - 1):  # Practical limit check
            raise ValueError("Message too large to segment")

        # Calculate total segments needed
        total_segments = math.ceil(total_length / self.max_data_size)
        bytes_processed = 0

        def segment_generator():
            nonlocal bytes_processed
            sequence_number = 0
            while bytes_processed < total_length:
                remaining_bytes = message_bytes[bytes_processed:]
                target_size = min(self.max_data_size, len(remaining_bytes))

                split_size = self._find_safe_split_point(remaining_bytes, target_size)
                segment_data = remaining_bytes[:split_size]

                is_last = bytes_processed + split_size >= total_length
                yield self._create_segment(
                    segment_data,
                    sequence_number,
                    message_id,
                    total_segments,
                    is_last,
                    total_length
                )
                sequence_number += 1
                bytes_processed += split_size

        return list(segment_generator())

    def _create_segment(self, data: bytes, seq_num: int, msg_id: str,
                        total_segments: int, is_last: bool,
                        original_length: int) -> Segment:
        """Helper method to create segments with validation."""
        if len(data) > self.max_data_size:
            raise ValueError(f"Segment data size ({len(data)}) exceeds maximum ({self.max_data_size})")

        return Segment(
            sequence_number=seq_num,
            data=data,
            checksum=self._calculate_checksum(data),
            total_segments=total_segments,
            message_id=msg_id,
            is_last=is_last,
            original_length=original_length
        )

    def serialize_segment(self, segment: Segment) -> bytes:
        """
        Serializes a segment for transmission.

        Converts a `Segment` object into a JSON-encoded byte stream that can be sent
        over the network.

        :param segment: The `Segment` object to serialize.
        :type segment: Segment
        :return: A JSON-encoded byte stream representing the segment.
        :rtype: bytes

        Example:
            serialized_data = serialize_segment(segment)
            print(serialized_data)  # Outputs the serialized bytes
        """
        metadata = {
            'seq': segment.sequence_number,
            'checksum': segment.checksum,
            'total_segments': segment.total_segments,
            'message_id': segment.message_id,
            'is_last': segment.is_last,
            'original_length': segment.original_length
        }

        try:
            segment_data = segment.data.decode('utf-8')
        except UnicodeDecodeError as e:
            raise ValueError(f"Failed to decode segment data: {e}")

        packet = {
            'metadata': metadata,
            'data': segment_data
        }

        serialized = json.dumps(packet).encode('utf-8')
        if len(serialized) > self.max_segment_size:
            raise ValueError(
                f"Serialized segment size ({len(serialized)}) exceeds "
                f"maximum ({self.max_segment_size})"
            )

        return serialized

    @staticmethod
    def _validate_metadata(metadata: dict) -> bool:
        required_fields = {'seq', 'checksum', 'total_segments', 'message_id', 'is_last', 'original_length'}
        return all(field in metadata for field in required_fields)

    @staticmethod
    def deserialize_segment(data: bytes) -> Optional[Segment]:
        """
        Deserializes received data back into a `Segment` object.

        Parses a JSON-encoded byte stream into a `Segment` object, verifying its
        integrity using the checksum.

        :param data: The received JSON-encoded byte stream.
        :type data: bytes
        :return: A `Segment` object if successful, or None if deserialization fails.
        :rtype: Optional[Segment]

        Example:
            segment = deserialize_segment(received_data)
            if segment:
                print("Segment deserialized successfully")
            else:
                print("Failed to deserialize segment")
        """
        try:
            packet = json.loads(data.decode('utf-8'))

            # Validate packet structure
            if not isinstance(packet, dict) or 'metadata' not in packet or 'data' not in packet:
                logging.error("Invalid packet structure")
                return None

            metadata = packet['metadata']
            if not MessageSegmenter._validate_metadata(metadata):
                logging.error("Missing required metadata fields")
                return None

            # Convert data to bytes and verify checksum
            try:
                segment_data = packet['data'].encode('utf-8')
            except (AttributeError, UnicodeEncodeError) as e:
                logging.error(f"Invalid segment data: {e}")
                return None

            calculated_checksum = hashlib.sha256(segment_data).hexdigest()
            if calculated_checksum != metadata['checksum']:
                logging.warning("Checksum verification failed")
                return None

            return Segment(
                sequence_number=metadata['seq'],
                data=segment_data,
                checksum=metadata['checksum'],
                total_segments=metadata['total_segments'],
                message_id=metadata['message_id'],
                is_last=metadata['is_last'],
                original_length=metadata['original_length']
            )

        except Exception as e:
            logging.error(f"Deserialization error: {e}")
            return None

    @staticmethod
    def reassemble_message(segments: List[Segment]) -> Optional[str]:
        """
        Reassembles the original message from its segments.

        Combines a list of `Segment` objects back into the original UTF-8 string,
        verifying the sequence, integrity, and completeness of the segments.

        :param segments: A list of `Segment` objects to reassemble.
        :type segments: List[Segment]
        :return: The original reassembled message as a string, or None if reassembly fails.
        :rtype: Optional[str]

        Example:
            message = reassemble_message(segments)
            if message:
                print("Message reassembled:", message)
            else:
                print("Failed to reassemble message")
        """
        if not segments:
            return None

        try:
            # Validate segment sequence
            sorted_segments = sorted(segments, key=lambda s: s.sequence_number)
            expected_count = sorted_segments[0].total_segments

            if len(sorted_segments) != expected_count:
                logging.warning(f"Segment count mismatch: expected {expected_count}, got {len(sorted_segments)}")
                sorted_segments = [
                    s for i, s in enumerate(sorted_segments)
                    if i == 0 or sorted_segments[i].sequence_number != sorted_segments[i - 1].sequence_number
                ]

            # Validate sequence continuity
            if any(s.sequence_number != i for i, s in enumerate(sorted_segments)):
                logging.error("Discontinuous segment sequence")
                return None

            # Validate message consistency
            message_id = sorted_segments[0].message_id
            original_length = sorted_segments[0].original_length

            if not all(s.message_id == message_id and
                       s.original_length == original_length for s in sorted_segments):
                logging.error("Inconsistent message metadata")
                return None

            # Validate last segment flag
            if not sorted_segments[-1].is_last:
                logging.error("Missing last segment")
                return None

            # Reassemble and verify
            reassembled = b''.join(segment.data for segment in sorted_segments)
            if len(reassembled) != sorted_segments[0].original_length:
                logging.error("Reassembled length mismatch")
                return None

            return reassembled.decode('utf-8')

        except Exception as e:
            logging.error(f"Reassembly error: {e}")
            return None


# Test
if __name__ == "__main__":
    # UTF-8 Test
    message = "Hello, 世界! This is a test message with UTF-8 characters: 🌟🌍"

    # Create segmenter with small max size to force multiple segments
    segmenter = MessageSegmenter(max_segment_size=40)

    segments = segmenter.segment_message(message)
    print(f"Message split into {len(segments)} segments")

    # Serialization/deserialization
    transmitted_segments = []
    for segment in segments:
        # Transmit
        serialized = segmenter.serialize_segment(segment)
        # Receive and deserialize
        received_segment = MessageSegmenter.deserialize_segment(serialized)
        if received_segment:
            transmitted_segments.append(received_segment)

    # Reassemble message
    reassembled = MessageSegmenter.reassemble_message(transmitted_segments)
    if reassembled:
        print(f"Original message: {message}")
        print(f"Reassembled message: {reassembled}")
        print(f"Successful transmission: {message == reassembled}")
