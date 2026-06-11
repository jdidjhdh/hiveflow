"""HiveFlow - Multi-Modal Processing

Provides unified interface for:
- Image: Analysis, OCR, generation, embedding
- Audio: Speech-to-Text (STT), Text-to-Speech (TTS), transcription
- Video: Frame extraction, summarization, scene detection

Integrates with LLM clients and can be used as MCP tools.
"""

import base64
import hashlib
import io
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ======================== Multi-Modal Types ========================


class MediaType(str, Enum):
    """Supported media types."""

    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"


@dataclass
class MediaContent:
    """A piece of media content."""

    media_type: MediaType
    data: str | bytes  # File path or raw bytes
    mime_type: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_base64(self) -> str:
        """Convert to base64 string."""
        if isinstance(self.data, bytes):
            return base64.b64encode(self.data).decode()
        with open(self.data, "rb") as f:
            return base64.b64encode(f.read()).decode()

    def to_data_url(self) -> str:
        """Convert to data URL."""
        b64 = self.to_base64()
        return f"data:{self.mime_type};base64,{b64}"


@dataclass
class ImageAnalysisResult:
    """Result of image analysis."""

    description: str
    labels: list[str] = field(default_factory=list)
    objects: list[str] = field(default_factory=list)
    text: str = ""  # OCR result
    confidence: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class AudioTranscriptResult:
    """Result of audio transcription."""

    text: str
    language: str = ""
    duration_seconds: float = 0.0
    words: list[dict[str, Any]] = field(default_factory=list)  # Word-level timestamps
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VideoSummaryResult:
    """Result of video summarization."""

    summary: str
    key_frames: list[int] = field(default_factory=list)  # Frame indices
    scenes: list[dict[str, Any]] = field(default_factory=list)
    duration_seconds: float = 0.0
    fps: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImageGenerationResult:
    """Result of image generation."""

    image_data: bytes | None = None
    image_url: str = ""
    prompt: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


# ======================== Image Processor ========================


class ImageProcessor(ABC):
    """Abstract base class for image processing."""

    @abstractmethod
    async def analyze(self, image: MediaContent, prompt: str = "") -> ImageAnalysisResult: ...

    @abstractmethod
    async def ocr(self, image: MediaContent) -> str: ...

    @abstractmethod
    async def generate(self, prompt: str, size: str = "1024x1024") -> ImageGenerationResult: ...

    @abstractmethod
    async def embed(self, image: MediaContent) -> list[float]: ...


class OpenAIImageProcessor(ImageProcessor):
    """Image processing using OpenAI's vision and image APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        vision_model: str = "gpt-4o",
        image_model: str = "dall-e-3",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.vision_model = vision_model
        self.image_model = image_model
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai>=1.0.0 is required for OpenAIImageProcessor")
        return self._client

    async def analyze(self, image: MediaContent, prompt: str = "") -> ImageAnalysisResult:
        """Analyze image content using GPT-4o vision."""
        client = self._get_client()
        data_url = image.to_data_url()
        user_prompt = prompt or "Describe this image in detail. What do you see?"

        response = await client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            max_tokens=1024,
        )

        description = response.choices[0].message.content or ""
        return ImageAnalysisResult(
            description=description,
            confidence=0.9,
            metadata={
                "model": self.vision_model,
                "usage": response.usage.model_dump() if response.usage else {},
            },
        )

    async def ocr(self, image: MediaContent) -> str:
        """Extract text from image using vision model."""
        return (
            await self.analyze(
                image,
                "Extract all text from this image. Return only the text, nothing else.",
            )
        ).description

    async def generate(self, prompt: str, size: str = "1024x1024") -> ImageGenerationResult:
        """Generate image from text prompt using DALL-E."""
        client = self._get_client()
        response = await client.images.generate(
            model=self.image_model,
            prompt=prompt,
            size=size,
            n=1,
            response_format="b64_json",
        )

        image_data = base64.b64decode(response.data[0].b64_json)
        return ImageGenerationResult(
            image_data=image_data,
            prompt=prompt,
            metadata={
                "model": self.image_model,
                "size": size,
                "revised_prompt": response.data[0].revised_prompt,
            },
        )

    async def embed(self, image: MediaContent) -> list[float]:
        """Generate image embedding (simulated for now)."""
        # OpenAI doesn't have a dedicated image embedding API yet
        # Use vision model to describe image, then embed the description
        analysis = await self.analyze(image, "Describe in 3 words")
        # In production, you'd use CLIP or similar
        return [hash(c) % 1000 / 1000.0 for c in analysis.description[:128]]


class MockImageProcessor(ImageProcessor):
    """Mock image processor for testing."""

    def __init__(self):
        self._mock_descriptions: dict[str, str] = {}

    def set_mock_description(self, image_hash: str, description: str):
        self._mock_descriptions[image_hash] = description

    def _hash_image(self, image: MediaContent) -> str:
        if isinstance(image.data, bytes):
            return hashlib.md5(image.data).hexdigest()[:8]
        return hashlib.md5(image.data.encode()).hexdigest()[:8]

    async def analyze(self, image: MediaContent, prompt: str = "") -> ImageAnalysisResult:
        img_hash = self._hash_image(image)
        description = self._mock_descriptions.get(img_hash, "A test image with various objects")
        return ImageAnalysisResult(
            description=description,
            labels=["test", "image"],
            confidence=0.95,
            metadata={"mock": True},
        )

    async def ocr(self, image: MediaContent) -> str:
        return "Sample OCR text extracted from image"

    async def generate(self, prompt: str, size: str = "1024x1024") -> ImageGenerationResult:
        return ImageGenerationResult(
            image_data=b"\x89PNG\r\n\x1a\n" + b"\x00" * 100,  # Fake PNG header
            prompt=prompt,
            metadata={"mock": True, "size": size},
        )

    async def embed(self, image: MediaContent) -> list[float]:
        return [0.1] * 128


# ======================== Audio Processor ========================


class AudioProcessor(ABC):
    """Abstract base class for audio processing."""

    @abstractmethod
    async def transcribe(self, audio: MediaContent, language: str = "") -> AudioTranscriptResult: ...

    @abstractmethod
    async def translate(self, audio: MediaContent, target_language: str = "en") -> AudioTranscriptResult: ...

    @abstractmethod
    async def text_to_speech(self, text: str, voice: str = "") -> bytes: ...


class OpenAIAudioProcessor(AudioProcessor):
    """Audio processing using OpenAI's Whisper and TTS APIs."""

    def __init__(
        self,
        api_key: str | None = None,
        stt_model: str = "whisper-1",
        tts_model: str = "tts-1",
        tts_voice: str = "alloy",
    ):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY", "")
        self.stt_model = stt_model
        self.tts_model = tts_model
        self.tts_voice = tts_voice
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI

                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("openai>=1.0.0 is required for OpenAIAudioProcessor")
        return self._client

    async def transcribe(self, audio: MediaContent, language: str = "") -> AudioTranscriptResult:
        """Transcribe audio to text using Whisper."""
        client = self._get_client()

        # Prepare audio file
        if isinstance(audio.data, bytes):
            audio_file = io.BytesIO(audio.data)
            audio_file.name = "audio.wav"
        else:
            audio_file = open(audio.data, "rb")

        kwargs: dict[str, Any] = {
            "model": self.stt_model,
            "file": audio_file,
            "response_format": "verbose_json",
        }
        if language:
            kwargs["language"] = language

        response = await client.audio.transcriptions.create(**kwargs)

        return AudioTranscriptResult(
            text=response.text,
            language=language or response.language or "",
            duration_seconds=response.duration if hasattr(response, "duration") else 0,
            metadata={"model": self.stt_model},
        )

    async def translate(self, audio: MediaContent, target_language: str = "en") -> AudioTranscriptResult:
        """Translate audio to text in target language."""
        client = self._get_client()

        if isinstance(audio.data, bytes):
            audio_file = io.BytesIO(audio.data)
            audio_file.name = "audio.wav"
        else:
            audio_file = open(audio.data, "rb")

        response = await client.audio.translations.create(
            model=self.stt_model,
            file=audio_file,
        )

        return AudioTranscriptResult(
            text=response.text,
            language=target_language,
            metadata={"model": self.stt_model, "translated": True},
        )

    async def text_to_speech(self, text: str, voice: str = "") -> bytes:
        """Convert text to speech."""
        client = self._get_client()
        response = await client.audio.speech.create(
            model=self.tts_model,
            voice=voice or self.tts_voice,
            input=text,
        )
        return response.content


class MockAudioProcessor(AudioProcessor):
    """Mock audio processor for testing."""

    async def transcribe(self, audio: MediaContent, language: str = "") -> AudioTranscriptResult:
        return AudioTranscriptResult(
            text="This is a mock transcription of the audio content.",
            language=language or "en",
            duration_seconds=5.0,
            metadata={"mock": True},
        )

    async def translate(self, audio: MediaContent, target_language: str = "en") -> AudioTranscriptResult:
        return AudioTranscriptResult(
            text="This is a mock translation.",
            language=target_language,
            metadata={"mock": True},
        )

    async def text_to_speech(self, text: str, voice: str = "") -> bytes:
        return b"mock audio data"


# ======================== Video Processor ========================


class VideoProcessor(ABC):
    """Abstract base class for video processing."""

    @abstractmethod
    async def extract_frames(self, video: MediaContent, max_frames: int = 10) -> list[bytes]: ...

    async def summarize(
        self, video: MediaContent, image_processor: ImageProcessor | None = None
    ) -> VideoSummaryResult: ...


class OpenAIVideoProcessor(VideoProcessor):
    """Video processing using frame extraction + vision analysis."""

    def __init__(self):
        pass

    async def extract_frames(self, video: MediaContent, max_frames: int = 10) -> list[bytes]:
        """Extract key frames from video."""
        import importlib.util

        if importlib.util.find_spec("cv2") is not None:
            return self._extract_frames_opencv(video, max_frames)
        if importlib.util.find_spec("moviepy") is not None:
            return self._extract_frames_moviepy(video, max_frames)
        raise ImportError("opencv-python or moviepy is required for video processing")

    def _extract_frames_opencv(self, video: MediaContent, max_frames: int) -> list[bytes]:
        """Extract frames using OpenCV."""
        import cv2

        if isinstance(video.data, bytes):
            # Write to temp file
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                f.write(video.data)
                video_path = f.name
        else:
            video_path = video.data

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps = cap.get(cv2.CAP_PROP_FPS)

        frames = []
        # Sample evenly
        step = max(1, total_frames // max_frames)
        for i in range(0, total_frames, step):
            cap.set(cv2.CAP_PROP_POS_FRAMES, i)
            ret, frame = cap.read()
            if ret:
                _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                frames.append(buffer.tobytes())
            if len(frames) >= max_frames:
                break

        cap.release()
        video.metadata["fps"] = fps
        video.metadata["total_frames"] = total_frames
        return frames

    def _extract_frames_moviepy(self, video: MediaContent, max_frames: int) -> list[bytes]:
        """Extract frames using moviepy."""
        import io

        from moviepy import VideoFileClip

        if isinstance(video.data, bytes):
            import tempfile

            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
                f.write(video.data)
                video_path = f.name
        else:
            video_path = video.data

        clip = VideoFileClip(video_path)
        duration = clip.duration
        frames = []

        # Sample evenly
        step = duration / max_frames
        for t in [i * step for i in range(max_frames)]:
            if t < duration:
                frame = clip.get_frame(t)
                from PIL import Image

                img = Image.fromarray(frame)
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=80)
                frames.append(buf.getvalue())

        clip.close()
        return frames

    async def summarize(self, video: MediaContent, image_processor: ImageProcessor | None = None) -> VideoSummaryResult:
        """Summarize video by analyzing key frames."""
        if image_processor is None:
            image_processor = MockImageProcessor()

        frames = await self.extract_frames(video, max_frames=10)
        if not frames:
            return VideoSummaryResult(summary="No frames extracted", duration_seconds=0)

        # Analyze each frame
        descriptions = []
        for frame_data in frames:
            media = MediaContent(
                media_type=MediaType.IMAGE,
                data=frame_data,
                mime_type="image/jpeg",
            )
            analysis = await image_processor.analyze(media, "Describe what you see in this video frame.")
            descriptions.append(analysis.description)

        # Combine descriptions into summary
        summary = "Video summary: " + " | ".join(descriptions[:5])

        return VideoSummaryResult(
            summary=summary,
            key_frames=list(range(len(frames))),
            duration_seconds=video.metadata.get("duration", 0),
            fps=video.metadata.get("fps", 0),
            metadata={"frames_analyzed": len(descriptions)},
        )


class MockVideoProcessor(VideoProcessor):
    """Mock video processor for testing."""

    async def extract_frames(self, video: MediaContent, max_frames: int = 10) -> list[bytes]:
        return [b"fake_frame_" + str(i).encode() for i in range(min(max_frames, 3))]

    async def summarize(self, video: MediaContent, image_processor: ImageProcessor | None = None) -> VideoSummaryResult:
        return VideoSummaryResult(
            summary="Mock video summary: The video shows various scenes with different content.",
            key_frames=[0, 1, 2],
            duration_seconds=30.0,
            fps=30.0,
            metadata={"mock": True},
        )


# ======================== MultiModal Pipeline ========================


class MultiModalPipeline:
    """
    Unified multi-modal processing pipeline.

    Usage:
        pipeline = MultiModalPipeline(
            image_processor=OpenAIImageProcessor(),
            audio_processor=OpenAIAudioProcessor(),
            video_processor=OpenAIVideoProcessor(),
        )

        # Image analysis
        result = await pipeline.analyze_image(MediaContent(
            media_type=MediaType.IMAGE,
            data="path/to/image.jpg",
        ))

        # Audio transcription
        result = await pipeline.transcribe_audio(MediaContent(
            media_type=MediaType.AUDIO,
            data="path/to/audio.wav",
        ))

        # Video summary
        result = await pipeline.summarize_video(MediaContent(
            media_type=MediaType.VIDEO,
            data="path/to/video.mp4",
        ))
    """

    def __init__(
        self,
        image_processor: ImageProcessor | None = None,
        audio_processor: AudioProcessor | None = None,
        video_processor: VideoProcessor | None = None,
    ):
        self.image_processor = image_processor or MockImageProcessor()
        self.audio_processor = audio_processor or MockAudioProcessor()
        self.video_processor = video_processor or MockVideoProcessor()

    async def analyze_image(self, image: MediaContent, prompt: str = "") -> ImageAnalysisResult:
        """Analyze image content."""
        return await self.image_processor.analyze(image, prompt)

    async def extract_text_from_image(self, image: MediaContent) -> str:
        """OCR text from image."""
        return await self.image_processor.ocr(image)

    async def generate_image(self, prompt: str, size: str = "1024x1024") -> ImageGenerationResult:
        """Generate image from text."""
        return await self.image_processor.generate(prompt, size)

    async def transcribe_audio(self, audio: MediaContent, language: str = "") -> AudioTranscriptResult:
        """Transcribe audio to text."""
        return await self.audio_processor.transcribe(audio, language)

    async def translate_audio(self, audio: MediaContent, target_language: str = "en") -> AudioTranscriptResult:
        """Translate audio to text."""
        return await self.audio_processor.translate(audio, target_language)

    async def text_to_speech(self, text: str, voice: str = "") -> bytes:
        """Convert text to speech."""
        return await self.audio_processor.text_to_speech(text, voice)

    async def summarize_video(self, video: MediaContent) -> VideoSummaryResult:
        """Summarize video content."""
        return await self.video_processor.summarize(video, self.image_processor)

    async def extract_video_frames(self, video: MediaContent, max_frames: int = 10) -> list[bytes]:
        """Extract frames from video."""
        return await self.video_processor.extract_frames(video, max_frames)

    # Integration with RAG: Add image content to knowledge base
    async def add_image_to_kb(self, kb_manager, kb_id: str, image: MediaContent, chunker=None):
        """Analyze image and add the description to a knowledge base."""
        from .rag import Document, DocumentType

        analysis = await self.analyze_image(image)
        content = f"Image Analysis: {analysis.description}"
        if analysis.text:
            content += f"\nOCR Text: {analysis.text}"

        doc = Document(
            doc_id=Document.compute_doc_id(content, "image"),
            content=content,
            doc_type=DocumentType.TEXT,
            metadata={
                "media_type": "image",
                "labels": analysis.labels,
                "objects": analysis.objects,
                "confidence": analysis.confidence,
                **image.metadata,
            },
        )
        return await kb_manager.add_document(kb_id, doc, chunker)

    async def add_audio_to_kb(self, kb_manager, kb_id: str, audio: MediaContent, language: str = "", chunker=None):
        """Transcribe audio and add to knowledge base."""
        from .rag import Document, DocumentType

        transcript = await self.transcribe_audio(audio, language)
        doc = Document(
            doc_id=Document.compute_doc_id(transcript.text, "audio"),
            content=transcript.text,
            doc_type=DocumentType.TEXT,
            metadata={
                "media_type": "audio",
                "language": transcript.language,
                "duration_seconds": transcript.duration_seconds,
                **audio.metadata,
            },
        )
        return await kb_manager.add_document(kb_id, doc, chunker)
