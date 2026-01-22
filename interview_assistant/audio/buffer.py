"""Thread-safe audio ring buffer for streaming."""

import threading
from collections import deque
from typing import Optional

import numpy as np


class AudioRingBuffer:
    """
    Thread-safe ring buffer for audio streaming.

    Stores audio samples in a circular buffer with automatic
    overflow handling.
    """

    def __init__(self, capacity_seconds: float = 30.0, sample_rate: int = 16000):
        """
        Initialize the audio buffer.

        Args:
            capacity_seconds: Maximum audio duration to store
            sample_rate: Audio sample rate in Hz
        """
        self.sample_rate = sample_rate
        self.capacity = int(capacity_seconds * sample_rate)
        self._buffer: deque = deque(maxlen=self.capacity)
        self._lock = threading.Lock()

    def write(self, data: bytes) -> None:
        """
        Write audio data to the buffer.

        Args:
            data: Raw audio bytes (int16 format)
        """
        samples = np.frombuffer(data, dtype=np.int16)
        with self._lock:
            self._buffer.extend(samples)

    def write_array(self, samples: np.ndarray) -> None:
        """
        Write numpy array to the buffer.

        Args:
            samples: Audio samples as numpy array
        """
        with self._lock:
            self._buffer.extend(samples.astype(np.int16))

    def read(self, num_samples: int) -> np.ndarray:
        """
        Read and remove samples from the buffer.

        Args:
            num_samples: Number of samples to read

        Returns:
            Audio samples as numpy array
        """
        with self._lock:
            samples = []
            for _ in range(min(num_samples, len(self._buffer))):
                samples.append(self._buffer.popleft())
            return np.array(samples, dtype=np.int16)

    def peek(self, num_samples: Optional[int] = None) -> np.ndarray:
        """
        Read samples without removing them.

        Args:
            num_samples: Number of samples to read (None for all)

        Returns:
            Audio samples as numpy array
        """
        with self._lock:
            if num_samples is None:
                return np.array(list(self._buffer), dtype=np.int16)
            samples = list(self._buffer)[:num_samples]
            return np.array(samples, dtype=np.int16)

    def clear(self) -> None:
        """Clear all samples from the buffer."""
        with self._lock:
            self._buffer.clear()

    def __len__(self) -> int:
        """Get current number of samples in buffer."""
        with self._lock:
            return len(self._buffer)

    @property
    def duration_seconds(self) -> float:
        """Get current duration of audio in buffer."""
        return len(self) / self.sample_rate

    @property
    def is_empty(self) -> bool:
        """Check if buffer is empty."""
        return len(self) == 0

    @property
    def is_full(self) -> bool:
        """Check if buffer is at capacity."""
        return len(self) >= self.capacity
