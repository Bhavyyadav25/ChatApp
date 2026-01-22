"""Audio device enumeration and management."""

import subprocess
from dataclasses import dataclass
from typing import List, Optional

import sounddevice as sd


@dataclass
class AudioDevice:
    """Represents an audio device."""
    id: str
    name: str
    is_input: bool
    is_output: bool
    is_monitor: bool
    sample_rate: int
    channels: int
    is_running: bool = False  # True if device is currently active

    @property
    def display_name(self) -> str:
        """Get display name for UI."""
        suffix = ""
        if self.is_monitor and "System Audio" not in self.name:
            suffix = " (Monitor)"
        return f"{self.name}{suffix}"


class AudioDeviceManager:
    """
    Manages audio device enumeration and selection.

    Supports both PulseAudio and PipeWire.
    """

    def __init__(self):
        self._devices: List[AudioDevice] = []
        self._selected_device: Optional[AudioDevice] = None
        self.refresh_devices()

    def refresh_devices(self) -> List[AudioDevice]:
        """Refresh the list of available audio devices."""
        self._devices = []

        # Get devices from sounddevice (works with PulseAudio/PipeWire)
        try:
            devices = sd.query_devices()
            for i, dev in enumerate(devices):
                is_input = dev.get("max_input_channels", 0) > 0
                is_output = dev.get("max_output_channels", 0) > 0
                name = dev.get("name", f"Device {i}")

                # Check if it's a monitor source
                is_monitor = ".monitor" in name.lower() or "monitor of" in name.lower()

                device = AudioDevice(
                    id=str(i),
                    name=name,
                    is_input=is_input,
                    is_output=is_output,
                    is_monitor=is_monitor,
                    sample_rate=int(dev.get("default_samplerate", 44100)),
                    channels=dev.get("max_input_channels", 0) or dev.get("max_output_channels", 0),
                )
                self._devices.append(device)
        except Exception as e:
            print(f"Error querying sounddevice: {e}")

        # Also try to get monitor sources via pactl
        self._add_monitor_sources()

        return self._devices

    def _add_monitor_sources(self) -> None:
        """Add monitor sources from PulseAudio/PipeWire."""
        try:
            result = subprocess.run(
                ["pactl", "list", "sources", "short"],
                capture_output=True,
                text=True,
                timeout=5,
            )

            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    if not line:
                        continue
                    parts = line.split("\t")
                    if len(parts) >= 2:
                        source_id = parts[0]
                        source_name = parts[1]
                        # Check state (RUNNING, SUSPENDED, etc.)
                        state = parts[-1] if len(parts) > 2 else "UNKNOWN"

                        # Check if already in list
                        if any(d.id == source_name for d in self._devices):
                            continue

                        is_monitor = ".monitor" in source_name

                        # Create friendly display name
                        display_name = source_name
                        if "bluez" in source_name:
                            display_name = "Bluetooth Audio"
                            if is_monitor:
                                display_name += " (System Audio)"
                        elif "Speaker" in source_name:
                            display_name = "Speakers (System Audio)"
                        elif "HDMI" in source_name:
                            display_name = f"HDMI (System Audio)"

                        device = AudioDevice(
                            id=source_name,
                            name=display_name,
                            is_input=True,
                            is_output=False,
                            is_monitor=is_monitor,
                            sample_rate=16000,
                            channels=1,
                            is_running=(state == "RUNNING"),
                        )
                        self._devices.append(device)
        except Exception as e:
            print(f"Error getting pactl sources: {e}")

    def get_input_devices(self) -> List[AudioDevice]:
        """Get all input devices."""
        return [d for d in self._devices if d.is_input]

    def get_monitor_devices(self) -> List[AudioDevice]:
        """Get all monitor sources (for capturing system audio)."""
        return [d for d in self._devices if d.is_monitor]

    def get_default_pipewire_monitor(self) -> Optional[AudioDevice]:
        """Get the best PipeWire/PulseAudio monitor source for system audio."""
        # Refresh to get current state (RUNNING vs SUSPENDED)
        self.refresh_devices()

        # Get all PipeWire monitor sources (non-numeric IDs)
        monitors = [d for d in self._devices if d.is_monitor and not d.id.isdigit()]

        if not monitors:
            return None

        # Prefer RUNNING monitors (currently active audio output)
        running = [m for m in monitors if m.is_running]
        if running:
            # Prefer bluetooth if available (common for headphones)
            for m in running:
                if "bluez" in m.id:
                    return m
            return running[0]

        # Fall back to speaker monitor
        for m in monitors:
            if "Speaker" in m.id or "speaker" in m.id:
                return m

        # Fall back to any monitor
        return monitors[0]

    def get_default_monitor(self) -> Optional[AudioDevice]:
        """Get the default monitor source for system audio capture."""
        # Only return monitors from sounddevice (not pactl) since pactl names
        # don't work with sounddevice directly
        monitors = [d for d in self._devices if d.is_monitor and d.id.isdigit()]
        if monitors:
            # Prefer the default sink monitor
            for m in monitors:
                if "default" in m.name.lower() or "@default" in m.name.lower():
                    return m
            return monitors[0]
        return None

    def get_default_input(self) -> Optional[AudioDevice]:
        """Get the default input device."""
        # Prefer 'default' or 'pipewire' device
        for d in self._devices:
            if d.is_input and d.id.isdigit():
                if "default" in d.name.lower():
                    return d
        for d in self._devices:
            if d.is_input and d.id.isdigit():
                if "pipewire" in d.name.lower():
                    return d
        # Fall back to any input device with numeric ID
        inputs = [d for d in self._devices if d.is_input and d.id.isdigit()]
        if inputs:
            return inputs[0]
        return None

    def get_device_by_id(self, device_id: str) -> Optional[AudioDevice]:
        """Get device by ID."""
        for d in self._devices:
            if d.id == device_id:
                return d
        return None

    def get_device_by_name(self, name: str) -> Optional[AudioDevice]:
        """Get device by name."""
        for d in self._devices:
            if d.name == name:
                return d
        return None

    def select_device(self, device: AudioDevice) -> None:
        """Select a device for capture."""
        self._selected_device = device

    @property
    def selected_device(self) -> Optional[AudioDevice]:
        """Get the currently selected device."""
        return self._selected_device

    @property
    def all_devices(self) -> List[AudioDevice]:
        """Get all devices."""
        return self._devices.copy()
