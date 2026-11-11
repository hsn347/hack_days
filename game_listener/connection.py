import socket
import logging
from typing import Callable, Optional


class GameConnection:
    """Thin TCP transport layer (connect, send, receive, listen, close)."""

    def __init__(self, host: str, port: int, timeout: float = 15.0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock: Optional[socket.socket] = None
        self.connected = False

    def _require_socket(self) -> socket.socket:
        if not self.connected or self.sock is None:
            raise ConnectionError("Not connected")
        return self.sock

    def connect(self) -> None:
        """Open a TCP connection to (host, port)."""
        if self.connected:
            return

        logging.info(f"Connecting to {self.host}:{self.port}")

        sock = socket.socket(
            socket.AF_INET,
            socket.SOCK_STREAM
        )

        sock.settimeout(self.timeout)

        try:
            sock.connect((self.host, self.port))
            self.sock = sock
            self.connected = True
            logging.info("TCP connection established")
        except Exception:
            sock.close()
            raise

    def send(self, data: bytes) -> None:
        """Send all raw bytes over the active TCP socket."""
        sock = self._require_socket()
        try:
            sock.sendall(data)
        except OSError:
            self.close()
            raise

    def receive(self, size: int = 4096) -> bytes:
        """Read up to `size` bytes from the TCP receive buffer."""
        sock = self._require_socket()
        return sock.recv(size)

    def listen(self, on_data: Optional[Callable[[bytes], None]] = None) -> None:
        """Continuously read incoming byte chunks until server closes or errors."""
        self._require_socket()
        logging.info("Listening for incoming data...")

        try:
            while self.connected:
                try:
                    data = self.receive(4096)

                    if not data:
                        logging.warning("Server closed connection")
                        break

                    logging.info(
                        f"Received {len(data)} bytes: {data.hex()}"
                    )

                    if on_data is not None:
                        on_data(data)

                except socket.timeout:
                    # Timeout only means no bytes arrived in this window; pipe stays open.
                    continue

                except OSError as error:
                    logging.error(f"Socket error: {error}")
                    break
        finally:
            self.close()

    def close(self) -> None:
        """Close the socket safely and reset connection state."""
        was_active = self.connected or self.sock is not None
        self.connected = False

        if self.sock is not None:
            try:
                self.sock.close()
            finally:
                self.sock = None

        if was_active:
            logging.info("Connection closed")
