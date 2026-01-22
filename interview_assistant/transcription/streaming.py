"""Real-time streaming transcription."""

import asyncio
import threading
from typing import Callable, Optional, List
from collections import deque
from dataclasses import dataclass

import numpy as np

from interview_assistant.core.events import Event, get_event_bus
from interview_assistant.audio.vad import SimpleVAD, get_vad
from interview_assistant.audio.buffer import AudioRingBuffer
from .whisper_engine import WhisperEngine, TranscriptionResult


@dataclass
class StreamingConfig:
    """Configuration for streaming transcription."""
    model_size: str = "base"
    language: str = "en"
    device: str = "auto"
    min_audio_length: float = 1.0  # seconds
    max_audio_length: float = 30.0  # seconds
    silence_threshold: float = 0.8  # seconds of silence to trigger transcription
    use_vad: bool = True


class StreamingTranscriber:
    """
    Real-time streaming transcription using Whisper.

    Processes audio chunks and emits transcription events
    when speech segments are detected.
    """

    def __init__(self, config: Optional[StreamingConfig] = None):
        """
        Initialize streaming transcriber.

        Args:
            config: Transcription configuration
        """
        self.config = config or StreamingConfig()

        self._engine = WhisperEngine(
            model_size=self.config.model_size,
            device=self.config.device,
            language=self.config.language,
        )

        self._vad = get_vad(use_silero=self.config.use_vad)
        self._audio_buffer: List[np.ndarray] = []
        self._silence_duration = 0.0
        self._sample_rate = 16000

        self._event_bus = get_event_bus()
        self._running = False
        self._lock = threading.Lock()

        # Callbacks
        self._on_partial: Optional[Callable[[str], None]] = None
        self._on_complete: Optional[Callable[[str], None]] = None

    def start(self) -> bool:
        """
        Start the transcriber.

        Returns:
            True if started successfully
        """
        if not self._engine.load_model():
            return False

        self._running = True
        self._audio_buffer = []
        self._silence_duration = 0.0
        self._vad.reset()

        return True

    def stop(self) -> None:
        """Stop the transcriber."""
        self._running = False

        # Process any remaining audio
        if self._audio_buffer:
            self._process_buffer()

    def process_audio(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """
        Process an audio chunk.

        Args:
            audio: Audio samples (int16)
            sample_rate: Sample rate of audio

        Returns:
            Transcription text if completed, None otherwise
        """
        if not self._running:
            return None

        self._sample_rate = sample_rate

        # Check VAD
        is_speech, speech_ended = self._vad.process_frame(audio)

        with self._lock:
            if is_speech:
                self._audio_buffer.append(audio)
                self._silence_duration = 0.0

                # Emit partial transcription event
                self._event_bus.emit(Event.TRANSCRIPTION_STARTED)

            else:
                chunk_duration = len(audio) / sample_rate
                self._silence_duration += chunk_duration

            # Check if we should transcribe
            buffer_duration = self._get_buffer_duration()

            should_transcribe = (
                (speech_ended and buffer_duration >= self.config.min_audio_length) or
                (self._silence_duration >= self.config.silence_threshold and buffer_duration >= self.config.min_audio_length) or
                (buffer_duration >= self.config.max_audio_length)
            )

            if should_transcribe and self._audio_buffer:
                return self._process_buffer()

        return None

    def _get_buffer_duration(self) -> float:
        """Get duration of audio in buffer."""
        total_samples = sum(len(chunk) for chunk in self._audio_buffer)
        return total_samples / self._sample_rate

    def _process_buffer(self) -> Optional[str]:
        """Process the audio buffer and return transcription."""
        if not self._audio_buffer:
            return None

        # Concatenate audio
        audio = np.concatenate(self._audio_buffer)
        self._audio_buffer = []
        self._silence_duration = 0.0
        self._vad.reset()

        # Transcribe
        result = self._engine.transcribe(audio, self._sample_rate)

        if result and result.text.strip():
            text = result.text.strip()

            # Emit event
            self._event_bus.emit(Event.TRANSCRIPTION_COMPLETE, text)

            # Call callback
            if self._on_complete:
                self._on_complete(text)

            return text

        return None

    async def process_audio_async(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """
        Process audio chunk asynchronously.

        Args:
            audio: Audio samples
            sample_rate: Sample rate

        Returns:
            Transcription text if completed
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            self.process_audio,
            audio,
            sample_rate,
        )

    def transcribe_file(self, audio: np.ndarray, sample_rate: int = 16000) -> Optional[str]:
        """
        Transcribe a complete audio file/buffer.

        Args:
            audio: Audio samples
            sample_rate: Sample rate

        Returns:
            Transcription text
        """
        if not self._engine.load_model():
            return None

        result = self._engine.transcribe(audio, sample_rate)
        return result.text if result else None

    def set_on_partial(self, callback: Callable[[str], None]) -> None:
        """Set callback for partial transcriptions."""
        self._on_partial = callback

    def set_on_complete(self, callback: Callable[[str], None]) -> None:
        """Set callback for complete transcriptions."""
        self._on_complete = callback

    def clear_buffer(self) -> None:
        """Clear the audio buffer."""
        with self._lock:
            self._audio_buffer = []
            self._silence_duration = 0.0
            self._vad.reset()

    @property
    def is_running(self) -> bool:
        """Check if transcriber is running."""
        return self._running

    @property
    def buffer_duration(self) -> float:
        """Get current buffer duration in seconds."""
        with self._lock:
            return self._get_buffer_duration()


class TranscriptionPipeline:
    """
    Complete transcription pipeline that connects
    audio capture to transcription.
    """

    def __init__(
        self,
        config: Optional[StreamingConfig] = None,
        on_transcription: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the pipeline.

        Args:
            config: Transcription configuration
            on_transcription: Callback when transcription is complete
        """
        self.transcriber = StreamingTranscriber(config)
        self._on_transcription = on_transcription
        self._event_bus = get_event_bus()

        # Subscribe to audio events
        self._event_bus.subscribe(Event.AUDIO_CHUNK, self._on_audio_chunk)

    def _on_audio_chunk(self, audio: np.ndarray) -> None:
        """Handle incoming audio chunk."""
        if not self.transcriber.is_running:
            return

        result = self.transcriber.process_audio(audio)

        if result and self._on_transcription:
            self._on_transcription(result)

    def start(self) -> bool:
        """Start the pipeline."""
        return self.transcriber.start()

    def stop(self) -> None:
        """Stop the pipeline."""
        self.transcriber.stop()

    def set_callback(self, callback: Callable[[str], None]) -> None:
        """Set transcription callback."""
        self._on_transcription = callback
        self.transcriber.set_on_complete(callback)
