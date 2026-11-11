"""Packet framing helpers for TCP byte streams."""

from collections import deque
from typing import Any, Callable, Deque, List


def _read_next_item(
    queue: Deque[Any],
    feed_fn: Callable[[bytes], Any],
    receive_fn: Callable[[int], bytes],
    chunk_size: int,
) -> Any:
    """Read raw TCP chunks into `feed_fn` until `queue` yields one complete item."""
    while not queue:
        chunk = receive_fn(chunk_size)
        if not chunk:
            raise ConnectionError("Server closed connection before completing frame")
        feed_fn(chunk)
    return queue.popleft()


class LineFramer:
    """Buffer raw TCP bytes and extract newline-delimited messages (Login Server)."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._lines: Deque[str] = deque()

    def pack(self, text: str) -> bytes:
        """Append the trailing newline delimiter expected by Login Server."""
        return (text + "\n").encode("utf-8")

    def feed(self, chunk: bytes) -> List[str]:
        """Add incoming bytes to the buffer and extract all complete lines."""
        self._buffer.extend(chunk)
        extracted: List[str] = []

        while True:
            newline_idx = self._buffer.find(b"\n")
            if newline_idx == -1:
                break

            raw_line = bytes(self._buffer[:newline_idx])
            del self._buffer[: newline_idx + 1]

            line = raw_line.decode("utf-8", errors="replace").strip()
            self._lines.append(line)
            extracted.append(line)

        return extracted

    def read_line(self, receive_fn: Callable[[int], bytes], chunk_size: int = 4096) -> str:
        """Read from TCP until at least one complete line is buffered, then pop one."""
        return _read_next_item(self._lines, self.feed, receive_fn, chunk_size)


class GateFramer:
    """Buffer raw TCP bytes and extract 2-byte / 5-byte length-prefixed Gate packets."""

    def __init__(self) -> None:
        self._buffer = bytearray()
        self._packets: Deque[bytes] = deque()

    def pack(self, payload: bytes) -> bytes:
        """Prefix payload with a 2-byte big-endian length header (max 65535 bytes)."""
        size = len(payload)
        if size > 65535:
            raise ValueError(f"Gate outgoing packet too large: {size} bytes")
        return size.to_bytes(2, "big") + payload

    def feed(self, chunk: bytes) -> List[bytes]:
        """Add incoming bytes and extract all complete Gate packets."""
        self._buffer.extend(chunk)
        extracted: List[bytes] = []

        while True:
            if len(self._buffer) < 2:
                break

            header_size = 2
            payload_len = int.from_bytes(self._buffer[:2], "big")

            if payload_len == 65535:
                header_size = 5
                if len(self._buffer) < 5:
                    break
                payload_len = int.from_bytes(self._buffer[2:5], "big")

            total_size = header_size + payload_len
            if len(self._buffer) < total_size:
                break

            packet = bytes(self._buffer[header_size:total_size])
            del self._buffer[:total_size]
            self._packets.append(packet)
            extracted.append(packet)

        return extracted

    def read_packet(self, receive_fn: Callable[[int], bytes], chunk_size: int = 4096) -> bytes:
        """Read from TCP until at least one complete Gate packet is buffered, then pop one."""
        return _read_next_item(self._packets, self.feed, receive_fn, chunk_size)
