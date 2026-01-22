"""Voice Activity Detection for audio processing."""

from typing import Optional, Tuple
import numpy as np


class SimpleVAD:
    """
    Simple Voice Activity Detection based on energy levels.

    For production, consider using silero-vad or webrtcvad.
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        frame_duration_ms: int = 30,
        energy_threshold: float = 0.01,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
    ):
        """
        Initialize VAD.

        Args:
            sample_rate: Audio sample rate
            frame_duration_ms: Duration of each frame in ms
            energy_threshold: Minimum energy to consider as speech
            min_speech_duration_ms: Minimum speech duration to trigger
            min_silence_duration_ms: Minimum silence to end speech
        """
        self.sample_rate = sample_rate
        self.frame_samples = int(sample_rate * frame_duration_ms / 1000)
        self.energy_threshold = energy_threshold
        self.min_speech_frames = int(min_speech_duration_ms / frame_duration_ms)
        self.min_silence_frames = int(min_silence_duration_ms / frame_duration_ms)

        # State
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        self._speech_start_sample = 0
        self._total_samples = 0

    def process_frame(self, audio: np.ndarray) -> Tuple[bool, bool]:
        """
        Process an audio frame.

        Args:
            audio: Audio samples (int16 or float32)

        Returns:
            Tuple of (is_speech, speech_ended)
        """
        # Normalize to float
        if audio.dtype == np.int16:
            audio = audio.astype(np.float32) / 32768.0

        # Calculate energy (RMS)
        energy = np.sqrt(np.mean(audio ** 2))

        is_speech_frame = energy > self.energy_threshold
        speech_ended = False

        if is_speech_frame:
            self._speech_frames += 1
            self._silence_frames = 0

            if not self._is_speaking and self._speech_frames >= self.min_speech_frames:
                self._is_speaking = True
                self._speech_start_sample = self._total_samples - (self._speech_frames * self.frame_samples)
        else:
            self._silence_frames += 1

            if self._is_speaking and self._silence_frames >= self.min_silence_frames:
                self._is_speaking = False
                self._speech_frames = 0
                speech_ended = True

        self._total_samples += len(audio)

        return self._is_speaking, speech_ended

    def is_speech(self, audio: np.ndarray) -> bool:
        """
        Check if audio contains speech.

        Args:
            audio: Audio samples

        Returns:
            True if speech detected
        """
        is_speaking, _ = self.process_frame(audio)
        return is_speaking

    def reset(self) -> None:
        """Reset VAD state."""
        self._speech_frames = 0
        self._silence_frames = 0
        self._is_speaking = False
        self._speech_start_sample = 0
        self._total_samples = 0

    @property
    def is_speaking(self) -> bool:
        """Check if currently in speech segment."""
        return self._is_speaking


class SileroVAD:
    """
    Voice Activity Detection using Silero VAD model.

    More accurate than simple energy-based VAD.
    Requires: pip install silero-vad torch
    """

    def __init__(
        self,
        sample_rate: int = 16000,
        threshold: float = 0.5,
        min_speech_duration_ms: int = 250,
        min_silence_duration_ms: int = 500,
    ):
        """
        Initialize Silero VAD.

        Args:
            sample_rate: Audio sample rate (8000 or 16000)
            threshold: Speech probability threshold
            min_speech_duration_ms: Minimum speech duration
            min_silence_duration_ms: Minimum silence to end speech
        """
        self.sample_rate = sample_rate
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.min_silence_duration_ms = min_silence_duration_ms

        self._model = None
        self._is_speaking = False
        self._speech_start_time = 0
        self._silence_start_time = 0

    def _load_model(self):
        """Lazy load the Silero VAD model."""
        if self._model is None:
            try:
                import torch
                model, utils = torch.hub.load(
                    repo_or_dir='snakers4/silero-vad',
                    model='silero_vad',
                    force_reload=False,
                    onnx=False
                )
                self._model = model
                self._get_speech_timestamps = utils[0]
            except ImportError:
                print("Silero VAD not available. Install with: pip install silero-vad torch")
                self._model = None

    def process_audio(self, audio: np.ndarray) -> Tuple[bool, bool]:
        """
        Process audio and detect speech.

        Args:
            audio: Audio samples (int16 or float32)

        Returns:
            Tuple of (is_speech, speech_ended)
        """
        self._load_model()

        if self._model is None:
            # Fallback to simple VAD
            return SimpleVAD().process_frame(audio)

        try:
            import torch

            # Normalize to float32
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0

            # Run model
            tensor = torch.from_numpy(audio)
            speech_prob = self._model(tensor, self.sample_rate).item()

            is_speech = speech_prob > self.threshold
            speech_ended = False

            current_time_ms = len(audio) / self.sample_rate * 1000

            if is_speech:
                self._silence_start_time = 0
                if not self._is_speaking:
                    self._speech_start_time += current_time_ms
                    if self._speech_start_time >= self.min_speech_duration_ms:
                        self._is_speaking = True
            else:
                self._speech_start_time = 0
                if self._is_speaking:
                    self._silence_start_time += current_time_ms
                    if self._silence_start_time >= self.min_silence_duration_ms:
                        self._is_speaking = False
                        speech_ended = True

            return self._is_speaking, speech_ended

        except Exception as e:
            print(f"Silero VAD error: {e}")
            return False, False

    def is_speech(self, audio: np.ndarray) -> bool:
        """Check if audio contains speech."""
        is_speaking, _ = self.process_audio(audio)
        return is_speaking

    def reset(self) -> None:
        """Reset VAD state."""
        self._is_speaking = False
        self._speech_start_time = 0
        self._silence_start_time = 0

    @property
    def is_speaking(self) -> bool:
        """Check if currently in speech segment."""
        return self._is_speaking


def get_vad(use_silero: bool = True, **kwargs) -> SimpleVAD:
    """
    Get a VAD instance.

    Args:
        use_silero: Try to use Silero VAD if available
        **kwargs: Additional arguments for VAD

    Returns:
        VAD instance
    """
    if use_silero:
        try:
            import torch
            return SileroVAD(**kwargs)
        except ImportError:
            pass

    return SimpleVAD(**kwargs)
