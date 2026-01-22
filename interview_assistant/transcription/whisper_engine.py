"""Whisper model management for transcription."""

import os
from pathlib import Path
from typing import Optional, List, Tuple
from dataclasses import dataclass

import numpy as np


@dataclass
class TranscriptionSegment:
    """A transcription segment."""
    text: str
    start: float
    end: float
    confidence: float = 1.0


@dataclass
class TranscriptionResult:
    """Result of transcription."""
    text: str
    segments: List[TranscriptionSegment]
    language: str
    duration: float


class WhisperEngine:
    """
    Whisper model wrapper for speech-to-text transcription.

    Uses faster-whisper for efficient inference.
    """

    MODELS = ["tiny", "base", "small", "medium", "large-v2", "large-v3"]

    def __init__(
        self,
        model_size: str = "base",
        device: str = "auto",
        compute_type: str = "auto",
        language: str = "en",
    ):
        """
        Initialize Whisper engine.

        Args:
            model_size: Model size (tiny, base, small, medium, large-v2, large-v3)
            device: Device to use (auto, cpu, cuda)
            compute_type: Compute type (auto, int8, float16, float32)
            language: Language code for transcription
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language

        self._model = None
        self._model_path: Optional[Path] = None

    def _resolve_device(self) -> Tuple[str, str]:
        """Resolve device and compute type."""
        device = self.device
        compute_type = self.compute_type

        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except ImportError:
                device = "cpu"

        if compute_type == "auto":
            if device == "cuda":
                compute_type = "float16"
            else:
                compute_type = "int8"

        return device, compute_type

    def load_model(self) -> bool:
        """
        Load the Whisper model.

        Returns:
            True if model loaded successfully
        """
        if self._model is not None:
            return True

        try:
            from faster_whisper import WhisperModel

            device, compute_type = self._resolve_device()

            print(f"Loading Whisper {self.model_size} on {device} ({compute_type})...")

            self._model = WhisperModel(
                self.model_size,
                device=device,
                compute_type=compute_type,
            )

            print("Whisper model loaded successfully")
            return True

        except ImportError:
            print("faster-whisper not installed. Install with: pip install faster-whisper")
            return False
        except Exception as e:
            print(f"Error loading Whisper model: {e}")
            return False

    def transcribe(
        self,
        audio: np.ndarray,
        sample_rate: int = 16000,
        language: Optional[str] = None,
    ) -> Optional[TranscriptionResult]:
        """
        Transcribe audio.

        Args:
            audio: Audio samples (int16 or float32)
            sample_rate: Sample rate of audio
            language: Language code (None for auto-detect)

        Returns:
            TranscriptionResult or None on error
        """
        if not self.load_model():
            return None

        try:
            # Normalize audio to float32
            if audio.dtype == np.int16:
                audio = audio.astype(np.float32) / 32768.0
            elif audio.dtype != np.float32:
                audio = audio.astype(np.float32)

            # Resample if needed (Whisper expects 16kHz)
            if sample_rate != 16000:
                # Simple resampling - for production use librosa or scipy
                ratio = 16000 / sample_rate
                new_length = int(len(audio) * ratio)
                indices = np.linspace(0, len(audio) - 1, new_length)
                audio = np.interp(indices, np.arange(len(audio)), audio)

            # Transcribe
            segments, info = self._model.transcribe(
                audio,
                language=language or self.language,
                vad_filter=True,
                vad_parameters=dict(
                    min_silence_duration_ms=500,
                    speech_pad_ms=200,
                ),
            )

            # Convert segments
            result_segments = []
            full_text = []

            for segment in segments:
                result_segments.append(TranscriptionSegment(
                    text=segment.text.strip(),
                    start=segment.start,
                    end=segment.end,
                    confidence=segment.avg_logprob if hasattr(segment, 'avg_logprob') else 1.0,
                ))
                full_text.append(segment.text.strip())

            return TranscriptionResult(
                text=" ".join(full_text),
                segments=result_segments,
                language=info.language if info else self.language,
                duration=info.duration if info else len(audio) / 16000,
            )

        except Exception as e:
            print(f"Transcription error: {e}")
            return None

    def is_loaded(self) -> bool:
        """Check if model is loaded."""
        return self._model is not None

    def unload_model(self) -> None:
        """Unload the model to free memory."""
        self._model = None

    @classmethod
    def download_model(cls, model_size: str = "base") -> bool:
        """
        Download Whisper model.

        Args:
            model_size: Model size to download

        Returns:
            True if download successful
        """
        try:
            from faster_whisper import WhisperModel

            print(f"Downloading Whisper {model_size} model...")
            # This will trigger download
            model = WhisperModel(model_size, device="cpu", compute_type="int8")
            del model
            print("Model downloaded successfully")
            return True

        except Exception as e:
            print(f"Error downloading model: {e}")
            return False

    @classmethod
    def get_available_models(cls) -> List[str]:
        """Get list of available model sizes."""
        return cls.MODELS.copy()
