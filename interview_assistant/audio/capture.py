"""System audio capture using PipeWire/PulseAudio."""

import subprocess
import threading
from typing import Callable, Optional

import numpy as np
import sounddevice as sd

from interview_assistant.core.events import Event, get_event_bus
from .buffer import AudioRingBuffer
from .devices import AudioDeviceManager, AudioDevice


class SystemAudioCapture:
    """
    Captures system audio from PipeWire/PulseAudio monitor sources.

    This allows capturing audio from video conferencing apps
    like Google Meet, Zoom, etc.
    """

    def __init__(
        self,
        device: Optional[str] = None,
        sample_rate: int = 16000,
        channels: int = 1,
        buffer_seconds: float = 30.0,
    ):
        """
        Initialize audio capture.

        Args:
            device: Audio device name or ID. None for auto-detect monitor.
            sample_rate: Sample rate in Hz (16000 for Whisper)
            channels: Number of audio channels (1 for mono)
            buffer_seconds: Size of the ring buffer in seconds
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self.buffer = AudioRingBuffer(buffer_seconds, sample_rate)

        self._device_manager = AudioDeviceManager()
        self._device = self._resolve_device(device)

        self._stream: Optional[sd.InputStream] = None
        self._process: Optional[subprocess.Popen] = None
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._use_parecord = False

        self._event_bus = get_event_bus()
        self._on_audio_chunk: Optional[Callable[[np.ndarray], None]] = None

        # Audio level tracking
        self._current_level: float = 0.0

    def _resolve_device(self, device: Optional[str]) -> Optional[AudioDevice]:
        """Resolve device name to AudioDevice object."""
        if device is None or device == "auto":
            # Try to get a PipeWire monitor device first (for system audio)
            monitor = self._device_manager.get_default_pipewire_monitor()
            if monitor:
                return monitor
            # Fall back to sounddevice monitor
            monitor = self._device_manager.get_default_monitor()
            if monitor:
                return monitor
            # Fall back to default input
            return self._device_manager.get_default_input()

        # Try by ID first
        dev = self._device_manager.get_device_by_id(device)
        if dev:
            return dev

        # Try by name
        return self._device_manager.get_device_by_name(device)

    def _audio_callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Callback for sounddevice audio stream."""
        if status:
            print(f"Audio callback status: {status}")

        # Convert to mono if needed
        if len(indata.shape) > 1 and indata.shape[1] > 1:
            audio = np.mean(indata, axis=1)
        elif len(indata.shape) > 1:
            audio = indata[:, 0]
        else:
            audio = indata

        self._process_audio(audio)

    def _process_audio(self, audio: np.ndarray) -> None:
        """Process audio data from any source."""
        # Convert to int16
        if audio.dtype == np.float32 or audio.dtype == np.float64:
            audio_int16 = (audio * 32767).astype(np.int16)
        elif audio.dtype == np.int16:
            audio_int16 = audio
        else:
            audio_int16 = audio.astype(np.int16)

        # Write to buffer
        self.buffer.write_array(audio_int16)

        # Calculate audio level (RMS)
        audio_float = audio_int16.astype(np.float32) / 32767.0
        rms = np.sqrt(np.mean(audio_float ** 2))
        self._current_level = min(1.0, rms * 10)  # Normalize to 0-1

        # Emit events
        self._event_bus.emit(Event.AUDIO_CHUNK, audio_int16, on_main_thread=False)
        self._event_bus.emit(Event.AUDIO_LEVEL, self._current_level)

        # Call custom callback if set
        if self._on_audio_chunk:
            self._on_audio_chunk(audio_int16)

    def _parecord_thread(self, source_name: str) -> None:
        """Thread to read audio from parecord subprocess."""
        try:
            # Use parecord to capture from the monitor source
            cmd = [
                "parecord",
                "--device", source_name,
                "--rate", str(self.sample_rate),
                "--channels", "1",
                "--format", "s16le",
                "--raw",
            ]

            self._process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
            )

            device_display = "Bluetooth" if "bluez" in source_name else source_name.split(".")[-2] if "." in source_name else source_name
            print(f"Capturing system audio from: {device_display}")

            # Read audio data in chunks
            chunk_size = 1024 * 2  # 1024 samples * 2 bytes per sample (int16)

            while self._running and self._process and self._process.poll() is None:
                data = self._process.stdout.read(chunk_size)
                if not data:
                    break

                # Convert bytes to numpy array
                audio = np.frombuffer(data, dtype=np.int16)
                self._process_audio(audio)

        except Exception as e:
            print(f"Error in parecord thread: {e}")
        finally:
            if self._process:
                self._process.terminate()
                self._process = None

    def start(self) -> bool:
        """
        Start audio capture.

        Returns:
            True if capture started successfully
        """
        if self._running:
            return True

        # Refresh device selection to get currently active audio output
        self._device = self._resolve_device(None)

        # Determine if we should use parecord (for PipeWire monitor sources)
        if self._device and not self._device.id.isdigit():
            # This is a PipeWire/PulseAudio source name, use parecord
            return self._start_parecord()
        else:
            # Use sounddevice for numeric device IDs
            return self._start_sounddevice()

    def _start_parecord(self) -> bool:
        """Start capture using parecord for PipeWire/PulseAudio sources."""
        try:
            source_name = self._device.id if self._device else None
            if not source_name:
                print("No device specified for parecord")
                return False

            self._running = True
            self._use_parecord = True
            self._thread = threading.Thread(
                target=self._parecord_thread,
                args=(source_name,),
                daemon=True,
            )
            self._thread.start()

            self._event_bus.emit(Event.RECORDING_STARTED)
            return True

        except Exception as e:
            print(f"Error starting parecord capture: {e}")
            self._running = False
            return False

    def _start_sounddevice(self) -> bool:
        """Start capture using sounddevice."""
        try:
            device_id = None
            if self._device:
                try:
                    device_id = int(self._device.id)
                except ValueError:
                    print(f"Warning: Device '{self._device.id}' is not a numeric ID, using default")
                    device_id = None

            # Query device to get supported channels
            if device_id is not None:
                try:
                    dev_info = sd.query_devices(device_id)
                    max_channels = dev_info.get('max_input_channels', 1)
                    channels = min(self.channels, max_channels) if max_channels > 0 else self.channels
                except Exception:
                    channels = self.channels
            else:
                channels = self.channels

            self._stream = sd.InputStream(
                device=device_id,
                channels=channels,
                samplerate=self.sample_rate,
                callback=self._audio_callback,
                blocksize=1024,
                dtype=np.float32,
            )
            self._stream.start()
            self._running = True
            self._use_parecord = False

            print(f"Audio capture started on device: {device_id or 'default'}")
            self._event_bus.emit(Event.RECORDING_STARTED)
            return True

        except Exception as e:
            print(f"Error starting audio capture: {e}")
            self._running = False
            return False

    def stop(self) -> None:
        """Stop audio capture."""
        self._running = False

        if self._process:
            try:
                self._process.terminate()
                self._process.wait(timeout=2)
            except Exception as e:
                print(f"Error stopping parecord: {e}")
            self._process = None

        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                print(f"Error stopping audio stream: {e}")
            self._stream = None

        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None

        self._event_bus.emit(Event.RECORDING_STOPPED)

    def get_audio(self, seconds: Optional[float] = None) -> np.ndarray:
        """
        Get audio from the buffer.

        Args:
            seconds: Duration of audio to get. None for all.

        Returns:
            Audio samples as numpy array
        """
        if seconds is None:
            return self.buffer.peek()

        num_samples = int(seconds * self.sample_rate)
        return self.buffer.peek(num_samples)

    def clear_buffer(self) -> None:
        """Clear the audio buffer."""
        self.buffer.clear()

    def set_audio_callback(self, callback: Callable[[np.ndarray], None]) -> None:
        """Set a callback to receive audio chunks."""
        self._on_audio_chunk = callback

    def change_device(self, device: str) -> bool:
        """
        Change the audio capture device.

        Args:
            device: New device name or ID

        Returns:
            True if device changed successfully
        """
        was_running = self._running

        if was_running:
            self.stop()

        self._device = self._resolve_device(device)

        if was_running:
            return self.start()

        return True

    @property
    def is_running(self) -> bool:
        """Check if capture is running."""
        return self._running

    @property
    def current_level(self) -> float:
        """Get current audio level (0-1)."""
        return self._current_level

    @property
    def device_name(self) -> str:
        """Get current device name."""
        if self._device:
            return self._device.display_name
        return "No device"

    @property
    def available_devices(self) -> list:
        """Get list of available monitor devices."""
        return self._device_manager.get_monitor_devices()

    def refresh_devices(self) -> list:
        """Refresh and get available devices."""
        self._device_manager.refresh_devices()
        return self.available_devices
