## Authors

All credits and copyrights go to:

1. - **Name:** Aladdin Abu Hegly (עלאא אלדין אבו חגלה).
   - **ID:** 322231580.
2. - **Name:** Ido Cohen (עידו כהן).
   - **ID:** 322541327.

---

## Words for examiners on the structure of the project:

- Any inline code or codeblocks found to be grayed out/turned into a comment are mostly for debugging and checking edge
  cases and functionality, you may ignore them.
- The knowledge source for different components implemented in the project's classes are usually located at the top
  of the class itself next to the imports. This is in order to show you that we have used external sources legally and
  appropriately, as is allowed in the requirements of this task, so please take that into consideration when grading
  this assignment.
- The code for the batch (`.bat`) scripts for automating the running task for the client and server separately
  have been written with the help of ChatGPT. These scripts are outside the scope of the project's requirements and
  therefore should not be taken into consideration when grading, they are simply made for the purpose of ease of use.

  The prompt is as follows:

> "is it possible to create scripts that run my client and server separately through a batch file
> without having to manually navigate the terminal to the directory and typing the running commands?"

It is important to note that these scripts only work on Windows. If you want to run the client and server through Unix
systems, you should navigate to the directory of the project using the terminal/shell, and run the `run_server` and
`run_client` command scripts separately. Example usage through Powershell:

```Powershell
PS C:\Users\<user>\<path to project root>\Ex03\ReliableTCPModel> py -3 run_server.py
```

- Additionally, we have used ChatGPT to help add explanations for the Segmentation process and the Sliding Window Protocol written in this Readme file (read below).
  - Prompt used for segmentation process explanation:

> Add a brief explanation in Markdown format for segmentation.

- Prompt used for sliding window protocol explanation:

> Please add an explanation for the sliding window protocol in Markdown format.

- The entire exchange process, including images of the client and server sides of the terminal, and images of the packet
  and data exchange, and the entire TCP connection routines between the server and the client has been documented in a PDF
  document compressed in a ZIP file along with the Wireshark `.pcapng` file and the Python code files for this project.
- The project supports testing different network conditions and edge cases such as:
  - Frequent retransmissions.
  - High rates of ACK drops.
  - High rates of packet drops.
  - Network delays.
  - Arrival of incorrect sequence of segments (out-of-order arrival).

These tests can be run simply by running the server and client scripts as you usually would, and selecting the appropriate options, "Network Simulation mode" for the server side, and "Test mode" for the client side. The testing is highly flexible and configurable, allowing the user to input different parameters, such as probabilities of packet and/or ack dropping, intentional inserted time delay values and other parameters to test a multitude of edge cases.

- Note on `default_client_config.txt` and `default_server_config.txt`

  - `default_client_config.txt`:

    - `maximum_msg_size`: Set to 256 as default value, client gets actual parameter by requesting from server.
    - `window_size`: Set to 1 as default value, client has no use for parameter.
  - `default_server_config.txt`:

    - `message`: Set to "None" as default value, server has no use for parameter.
    - `timeout`: Set to 1 as default value, server has no use for parameter.

---

# Segmentation

## Overview

**Segmentation** is the process of dividing large messages into smaller chunks (called segments) to facilitate reliable and efficient transmission over a network. This is especially important for networks like TCP/IP, where message sizes may need to conform to specific limits (e.g., Maximum Transmission Unit or MTU).

---

## Why Segmentation is Needed

1. **Size Constraints**: Many networks impose size limits on packets, and segmentation ensures that large messages can be split to fit within these limits.
2. **Reliability**: Smaller segments are easier to manage, retransmit, and reassemble in case of errors or packet loss.
3. **Efficient Transmission**: Breaking down messages allows the system to use bandwidth more effectively and avoid delays caused by excessively large data packets.

---

## How Segmentation Works

1. **Splitting the Message**:

   - The original message is divided into segments based on size constraints (e.g., the network's maximum segment size).
   - Each segment is encoded in a format that ensures it respects encoding boundaries (e.g., UTF-8).
2. **Adding Metadata**:

   - Each segment is assigned metadata such as:
     - Sequence number
     - Checksum for integrity verification
     - Total number of segments
     - A unique message identifier
3. **Transmission**:

   - Segments are sent sequentially or in parallel, depending on the protocol used.
4. **Reassembly**:

   - The receiver reassembles the segments using sequence numbers and metadata to reconstruct the original message.

---

## Benefits of Segmentation

- **Scalability**: Enables transmission of large messages over constrained networks.
- **Error Handling**: Retransmission of only lost or corrupted segments instead of the entire message.
- **Protocol Support**: Widely used in protocols like TCP, where segmentation is integral to its operation.

---

## Example

Suppose a message "Hello, this is a test message!" is too large to send in a single packet:

1. Segmentation breaks it into smaller chunks:

   - Segment 1: "Hello, this is"
   - Segment 2: " a test mes"
   - Segment 3: "sage!"
2. Metadata is added to each segment:

   - Sequence Number: 1, 2, 3
   - Message ID: "MSG123"
3. Segments are sent to the receiver, which reassembles them in order.

---

## Applications

- **TCP/IP Communication**: Segmentation is fundamental in protocols like TCP for reliable data transfer.
- **Streaming Services**: Large media files are segmented for efficient transmission and playback.

---

## Summary

Segmentation is a critical process in networking that enables large messages to be transmitted effectively and reliably. It ensures compliance with size constraints, facilitates error recovery, and supports the reassembly of messages at the destination.

# Sliding Window Protocol

## Overview

The **Sliding Window Protocol** is a method used in reliable data transmission to control the flow of data between a sender and a receiver. It is widely employed in networking protocols such as **TCP** to ensure efficient and reliable communication, even in the presence of packet loss, delays, or errors.

---

## Key Concepts

### 1. **Window Size**

- The "window" is a fixed-size range of sequence numbers that the sender can send without waiting for acknowledgments.
- The size of the window determines the maximum number of unacknowledged packets that can be in transit at any given time.

### 2. **Acknowledgments (ACKs)**

- The receiver sends acknowledgments back to the sender for each successfully received packet.
- ACKs are used to slide the window forward, allowing the sender to transmit more packets.

### 3. **Sequence Numbers**

- Each packet is assigned a unique sequence number.
- The sequence number ensures packets are delivered and reassembled in the correct order.

### 4. **Sliding Mechanism**

- As the sender receives acknowledgments for packets within the current window, the window "slides" forward to accommodate new packets.

---

## How It Works

### Sender Side

1. The sender maintains a **window** of unacknowledged packets.
2. It transmits packets up to the size of the window.
3. If an acknowledgment is received for a packet, the sender slides the window forward and transmits the next packet in sequence.
4. If a timeout occurs (no acknowledgment received), the sender retransmits the unacknowledged packet(s).

### Receiver Side

1. The receiver maintains a buffer for incoming packets.
2. It checks the sequence number of each received packet:
   - If the packet is within the expected range, it is stored, and an acknowledgment is sent.
   - If the packet is outside the range (e.g., duplicate or out of order), it is discarded, and no acknowledgment is sent.
3. Once all packets up to the highest expected sequence number are received, the receiver sends a cumulative acknowledgment.

---

## Example

### Parameters:

- **Window Size**: 4 packets
- **Sequence Numbers**: 0, 1, 2, 3, 4, 5, 6, 7...

### Transmission:

1. Sender sends packets 0, 1, 2, 3 (window size = 4).
2. Receiver acknowledges packet 0 (`ACK 0`), and the sender slides the window to send packet 4.
3. Receiver acknowledges packet 1 (`ACK 1`), and the sender slides the window further to send packet 5.
4. If packet 2 is lost:
   - Receiver does not send acknowledgment for packet 2.
   - Sender retransmits packet 2 after a timeout.

---

## Advantages

- **Efficiency**: Allows multiple packets to be in transit simultaneously, maximizing bandwidth utilization.
- **Error Recovery**: Retransmission ensures reliable delivery even in the presence of packet loss.
- **Flow Control**: Adapts to the receiver's capacity by adjusting the window size dynamically.

---

## Challenges

- **Timeout Handling**: Requires careful configuration of timeout values to balance between responsiveness and unnecessary retransmissions.
- **Buffer Management**: Both sender and receiver must manage buffers efficiently to avoid packet loss or delays.

---

# Task Log: Reliable TCP Communication Project

## 1. **Message Segmentation**

**Description**: Implement functionality to segment large messages into smaller chunks suitable for network transmission and reassemble them at the receiver.

- [X]  Create the `Segment` data structure with metadata fields.
- [X]  Implement `MessageSegmenter` for:
  - [X]  Segmenting messages into UTF-8 safe chunks.
  - [X]  Generating checksums for data integrity.
  - [X]  Serializing and deserializing segments.
  - [X]  Reassembling segments into the original message.
- [ ]  Add unit tests for segmentation and reassembly.

## 2. **Sliding Window Protocol**

**Description**: Implement the sliding window mechanism for reliable and efficient segment transmission with retransmission support.

- [X]  Define `WindowSegment` data structure with retransmission metadata.
- [X]  Create `SlidingWindow` class for:
  - [X]  Maintaining a window of active unacknowledged segments.
  - [X]  Handling acknowledgments and updating window state.
  - [X]  Retransmitting unacknowledged segments on timeout.
  - [X]  Exposing methods to check available window space.
- [X]  Add retransmission callback for timeout handling.
- [X]  Integrate with threading for timer-based retransmission.
- [X]  Implement exponential backoff for retransmissions.
- [X]  Write integration tests for window behavior under varying network conditions.

---

## 3. **Reliable Server**

**Description**: Develop a server that handles multiple clients, processes segmented messages, and sends acknowledgments.

- [X]  Create the `ReliableServer` class with:
  - [X]  Methods for client connection handling (`handle_client_connection`).
  - [X]  Acknowledgment logic and contiguous sequence tracking.
  - [X]  Reassembling complete messages.
  - [X]  Server shutdown process.
- [X]  Implement server socket initialization and listening.
- [X]  Add support for handling client connection errors.
- [X]  Optimize memory usage for segment storage in `received_segments`.

---

## 4. **Reliable Client**

**Description**: Develop a client that connects to the server, sends segmented messages, and manages acknowledgments.

- [X]  Create the `ReliableClient` class with:
  - [X]  Connection establishment and maximum size negotiation.
  - [X]  Message segmentation and sliding window-based transmission.
  - [X]  Handling retransmissions with sliding window protocol.
  - [X]  Sending and receiving acknowledgments.
- [X]  Implement message timeout handling on the client side.
- [X]  Add client connection recovery mechanisms.
- [X]  Write end-to-end tests for client-server interactions.

---

## 5. **Configuration Management**

**Description**: Develop a centralized configuration manager to handle server and client settings.

- [X]  Define `ConfigManager` class for:
  - [X]  Managing parameters like `maximum_msg_size`, `window_size`, `timeout`, etc.
  - [ ]  Loading configurations from a JSON/YAML file.
  - [X]  Adding validation for configuration parameters.

---

## 6. **Logging and Debugging**

**Description**: Integrate logging for debugging and monitoring application behavior.

- [X]  Add logging to key components (server, client, sliding window, etc.).
- [X]  Configure logging levels (INFO, DEBUG, ERROR) dynamically via configuration.
- [ ]  Integrate log rotation for server logs.

---

## 7. **Testing and Validation**

**Description**: Write comprehensive tests to validate each component's behavior under various conditions.

- [X]  Unit tests for `MessageSegmenter`.
- [X]  Unit tests for `SlidingWindow`.
- [X]  Integration tests for client-server communication.
- [X]  Stress tests for handling large messages and high throughput.
- [X]  Tests for handling packet loss and retransmission.

---

## 8. **Documentation**

**Description**: Document the project for developers and end-users.

- [X]  Write docstrings for all classes and methods.
- [X]  Create a Markdown README with:

  - [X]  Project overview and setup instructions.
  - [X]  Explanation of the sliding window protocol.
- [ ]  Add a troubleshooting guide for common issues.

---
