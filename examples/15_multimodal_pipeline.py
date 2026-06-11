"""
HiveFlow - 15: Multimodal Pipeline

This example demonstrates image/audio/video processing capabilities.

Usage:
    python 15_multimodal_pipeline.py
"""
import asyncio
from hiveflow import (
    MultiModalPipeline,
    MockImageProcessor,
    MockAudioProcessor,
    MockVideoProcessor,
    MediaContent,
    MediaType,
)


async def main():
    print("=== Multimodal Pipeline Example ===\n")

    pipeline = MultiModalPipeline(
        image_processor=MockImageProcessor(),
        audio_processor=MockAudioProcessor(),
        video_processor=MockVideoProcessor(),
    )

    image = MediaContent(media_type=MediaType.IMAGE, data=b"fake_image_bytes", mime_type="image/jpeg")
    image_result = await pipeline.analyze_image(image)
    print("Image analysis:")
    print(f"  Description: {image_result.description}")
    print(f"  Labels: {image_result.labels}")
    print(f"  Confidence: {image_result.confidence:.2f}")

    audio = MediaContent(media_type=MediaType.AUDIO, data=b"fake_audio_bytes", mime_type="audio/wav")
    audio_result = await pipeline.transcribe_audio(audio)
    print("\nAudio transcript:")
    print(f"  Text: {audio_result.text}")
    print(f"  Language: {audio_result.language or 'en'}")

    video = MediaContent(media_type=MediaType.VIDEO, data=b"fake_video_bytes", mime_type="video/mp4")
    video_result = await pipeline.summarize_video(video)
    print("\nVideo summary:")
    print(f"  Summary: {video_result.summary}")
    print(f"  Key frames: {len(video_result.key_frames)}")
    print(f"  Scenes: {len(video_result.scenes)}")


if __name__ == "__main__":
    asyncio.run(main())
