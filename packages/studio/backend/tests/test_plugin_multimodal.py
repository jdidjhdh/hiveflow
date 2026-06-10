"""HiveFlow - Plugin Marketplace and Multi-Modal Tests"""
import asyncio
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from hiveflow import (
    PluginMarketplace, PluginSpec, PluginCategory,
    MultiModalPipeline, MockImageProcessor, MockAudioProcessor, MockVideoProcessor,
    MediaContent, MediaType,
    MCPPluginManager,
)


# ======================== Plugin Marketplace Tests ========================

def test_marketplace_list_plugins():
    marketplace = PluginMarketplace()
    plugins = marketplace.list_plugins()
    assert len(plugins) >= 10  # At least 10 built-in plugins


def test_marketplace_filter_by_category():
    marketplace = PluginMarketplace()
    data_plugins = marketplace.list_plugins(category=PluginCategory.DATA)
    assert len(data_plugins) >= 2  # filesystem, database
    assert all(p.category == PluginCategory.DATA for p in data_plugins)

    dev_plugins = marketplace.list_plugins(category=PluginCategory.DEVELOPMENT)
    assert len(dev_plugins) >= 2  # code-executor, git


def test_marketplace_search():
    marketplace = PluginMarketplace()
    results = marketplace.search_plugins("file")
    assert len(results) >= 1
    assert any("file" in p.name.lower() or "file" in " ".join(p.tags).lower() for p in results)


def test_marketplace_get_plugin():
    marketplace = PluginMarketplace()
    plugin = marketplace.get_plugin("filesystem")
    assert plugin is not None
    assert plugin.name == "Filesystem Server"
    assert len(plugin.tools) >= 5


def test_marketplace_get_nonexistent_plugin():
    marketplace = PluginMarketplace()
    plugin = marketplace.get_plugin("nonexistent")
    assert plugin is None


def test_marketplace_get_categories():
    marketplace = PluginMarketplace()
    categories = marketplace.get_categories()
    assert PluginCategory.DATA in categories
    assert PluginCategory.TOOLS in categories
    assert categories[PluginCategory.DATA] >= 2


def test_marketplace_stats():
    marketplace = PluginMarketplace()
    stats = marketplace.get_stats()
    assert stats["total_plugins"] >= 10
    assert "categories" in stats
    assert stats["built_in"] >= 10


def test_marketplace_add_custom_plugin():
    marketplace = PluginMarketplace()
    initial_count = len(marketplace.list_plugins())

    custom = PluginSpec(
        plugin_id="custom_tool",
        name="Custom Tool",
        description="A custom plugin",
        category=PluginCategory.CUSTOM,
        command="echo",
        args=["hello"],
        icon="🔧",
        tags=["custom"],
        is_built_in=False,
    )
    marketplace.add_plugin(custom)

    plugins = marketplace.list_plugins()
    assert len(plugins) == initial_count + 1


def test_marketplace_remove_custom_plugin():
    marketplace = PluginMarketplace()
    custom = PluginSpec(
        plugin_id="temp_plugin",
        name="Temp",
        description="Temp plugin",
        category=PluginCategory.CUSTOM,
        is_built_in=False,
    )
    marketplace.add_plugin(custom)
    assert marketplace.remove_plugin("temp_plugin")

    # Can't remove built-in
    assert not marketplace.remove_plugin("filesystem")


@pytest.mark.asyncio
async def test_marketplace_install_plugin():
    marketplace = PluginMarketplace()
    mgr = MCPPluginManager()

    result = await marketplace.install_plugin("filesystem", mgr)
    assert result

    # Verify plugin was registered
    plugins = await mgr.list_plugins()
    assert any(p.plugin_id == "filesystem" for p in plugins)


@pytest.mark.asyncio
async def test_marketplace_install_nonexistent():
    marketplace = PluginMarketplace()
    mgr = MCPPluginManager()

    result = await marketplace.install_plugin("nonexistent", mgr)
    assert not result


def test_marketplace_plugin_spec_to_dict():
    marketplace = PluginMarketplace()
    plugin = marketplace.get_plugin("filesystem")
    d = plugin.to_dict()
    assert d["plugin_id"] == "filesystem"
    assert d["name"] == "Filesystem Server"
    assert "tools" in d
    assert len(d["tools"]) >= 5


def test_marketplace_built_in_plugins():
    marketplace = PluginMarketplace()
    built_in = [p for p in marketplace.list_plugins() if p.is_built_in]

    # Verify key plugins exist
    plugin_ids = {p.plugin_id for p in built_in}
    assert "filesystem" in plugin_ids
    assert "web-search" in plugin_ids
    assert "database" in plugin_ids
    assert "code-executor" in plugin_ids
    assert "git" in plugin_ids
    assert "email" in plugin_ids
    assert "calendar" in plugin_ids
    assert "api-client" in plugin_ids
    assert "hiveflow-rag" in plugin_ids
    assert "hiveflow-multimodal" in plugin_ids


# ======================== Multi-Modal: Image Tests ========================

@pytest.mark.asyncio
async def test_mock_image_analyze():
    processor = MockImageProcessor()
    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"fake_image_data",
        mime_type="image/png",
    )
    result = await processor.analyze(image, "What is this?")
    assert result.description
    assert result.confidence > 0
    assert result.metadata.get("mock") is True


@pytest.mark.asyncio
async def test_mock_image_ocr():
    processor = MockImageProcessor()
    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"fake_image_data",
        mime_type="image/png",
    )
    text = await processor.ocr(image)
    assert text
    assert len(text) > 0


@pytest.mark.asyncio
async def test_mock_image_generate():
    processor = MockImageProcessor()
    result = await processor.generate("A cat sitting on a mat", size="512x512")
    assert result.image_data is not None
    assert result.prompt == "A cat sitting on a mat"
    assert result.metadata.get("mock") is True


@pytest.mark.asyncio
async def test_mock_image_embed():
    processor = MockImageProcessor()
    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"fake_image_data",
        mime_type="image/png",
    )
    embedding = await processor.embed(image)
    assert len(embedding) == 128


@pytest.mark.asyncio
async def test_mock_image_custom_description():
    processor = MockImageProcessor()
    processor.set_mock_description("abc12345", "A beautiful sunset over the ocean")

    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"test_hash_data",  # Will hash to something
        mime_type="image/png",
    )
    # Get the actual hash
    img_hash = processor._hash_image(image)
    processor.set_mock_description(img_hash, "Custom description for this image")

    result = await processor.analyze(image)
    assert result.description == "Custom description for this image"


# ======================== Multi-Modal: Audio Tests ========================

@pytest.mark.asyncio
async def test_mock_audio_transcribe():
    processor = MockAudioProcessor()
    audio = MediaContent(
        media_type=MediaType.AUDIO,
        data=b"fake_audio_data",
        mime_type="audio/wav",
    )
    result = await processor.transcribe(audio, language="en")
    assert result.text
    assert result.language == "en"
    assert result.duration_seconds > 0


@pytest.mark.asyncio
async def test_mock_audio_translate():
    processor = MockAudioProcessor()
    audio = MediaContent(
        media_type=MediaType.AUDIO,
        data=b"fake_audio_data",
        mime_type="audio/wav",
    )
    result = await processor.translate(audio, target_language="fr")
    assert result.text
    assert result.language == "fr"


@pytest.mark.asyncio
async def test_mock_audio_tts():
    processor = MockAudioProcessor()
    audio_bytes = await processor.text_to_speech("Hello world", voice="alloy")
    assert audio_bytes == b"mock audio data"


# ======================== Multi-Modal: Video Tests ========================

@pytest.mark.asyncio
async def test_mock_video_extract_frames():
    processor = MockVideoProcessor()
    video = MediaContent(
        media_type=MediaType.VIDEO,
        data=b"fake_video_data",
        mime_type="video/mp4",
    )
    frames = await processor.extract_frames(video, max_frames=5)
    assert len(frames) == 3  # Mock returns 3 frames


@pytest.mark.asyncio
async def test_mock_video_summarize():
    processor = MockVideoProcessor()
    video = MediaContent(
        media_type=MediaType.VIDEO,
        data=b"fake_video_data",
        mime_type="video/mp4",
    )
    result = await processor.summarize(video)
    assert result.summary
    assert len(result.key_frames) == 3
    assert result.duration_seconds == 30.0


# ======================== Multi-Modal Pipeline Tests ========================

@pytest.mark.asyncio
async def test_multimodal_pipeline_analyze_image():
    pipeline = MultiModalPipeline(
        image_processor=MockImageProcessor(),
        audio_processor=MockAudioProcessor(),
        video_processor=MockVideoProcessor(),
    )
    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"test_image",
        mime_type="image/png",
    )
    result = await pipeline.analyze_image(image, "Describe this")
    assert result.description


@pytest.mark.asyncio
async def test_multimodal_pipeline_extract_text():
    pipeline = MultiModalPipeline()
    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"test_image",
        mime_type="image/png",
    )
    text = await pipeline.extract_text_from_image(image)
    assert text


@pytest.mark.asyncio
async def test_multimodal_pipeline_generate_image():
    pipeline = MultiModalPipeline()
    result = await pipeline.generate_image("A sunset over mountains", size="1024x1024")
    assert result.image_data is not None
    assert result.prompt == "A sunset over mountains"


@pytest.mark.asyncio
async def test_multimodal_pipeline_transcribe_audio():
    pipeline = MultiModalPipeline()
    audio = MediaContent(
        media_type=MediaType.AUDIO,
        data=b"test_audio",
        mime_type="audio/wav",
    )
    result = await pipeline.transcribe_audio(audio)
    assert result.text


@pytest.mark.asyncio
async def test_multimodal_pipeline_translate_audio():
    pipeline = MultiModalPipeline()
    audio = MediaContent(
        media_type=MediaType.AUDIO,
        data=b"test_audio",
        mime_type="audio/wav",
    )
    result = await pipeline.translate_audio(audio, target_language="ja")
    assert result.language == "ja"


@pytest.mark.asyncio
async def test_multimodal_pipeline_tts():
    pipeline = MultiModalPipeline()
    audio_bytes = await pipeline.text_to_speech("Hello")
    assert audio_bytes == b"mock audio data"


@pytest.mark.asyncio
async def test_multimodal_pipeline_summarize_video():
    pipeline = MultiModalPipeline()
    video = MediaContent(
        media_type=MediaType.VIDEO,
        data=b"test_video",
        mime_type="video/mp4",
    )
    result = await pipeline.summarize_video(video)
    assert result.summary


@pytest.mark.asyncio
async def test_multimodal_pipeline_extract_video_frames():
    pipeline = MultiModalPipeline()
    video = MediaContent(
        media_type=MediaType.VIDEO,
        data=b"test_video",
        mime_type="video/mp4",
    )
    frames = await pipeline.extract_video_frames(video, max_frames=5)
    assert len(frames) > 0


# ======================== Multi-Modal + RAG Integration ========================

@pytest.mark.asyncio
async def test_multimodal_add_image_to_kb():
    from hiveflow import KnowledgeBaseManager

    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_image", "Image KB")

    pipeline = MultiModalPipeline()
    image = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"test_image_for_kb",
        mime_type="image/png",
        metadata={"source": "test.png"},
    )

    ids = await pipeline.add_image_to_kb(mgr, "kb_image", image)
    assert len(ids) >= 1

    kb = (await mgr.list_kbs())[0]
    assert kb.doc_count == 1


@pytest.mark.asyncio
async def test_multimodal_add_audio_to_kb():
    from hiveflow import KnowledgeBaseManager

    mgr = KnowledgeBaseManager()
    await mgr.create_kb("kb_audio", "Audio KB")

    pipeline = MultiModalPipeline()
    audio = MediaContent(
        media_type=MediaType.AUDIO,
        data=b"test_audio_for_kb",
        mime_type="audio/wav",
        metadata={"source": "test.wav"},
    )

    ids = await pipeline.add_audio_to_kb(mgr, "kb_audio", audio)
    assert len(ids) >= 1

    kb = (await mgr.list_kbs())[0]
    assert kb.doc_count == 1


# ======================== MediaContent Tests ========================

def test_media_content_to_base64_bytes():
    content = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"hello",
        mime_type="image/png",
    )
    b64 = content.to_base64()
    assert b64 == "aGVsbG8="


def test_media_content_data_url():
    content = MediaContent(
        media_type=MediaType.IMAGE,
        data=b"hello",
        mime_type="image/png",
    )
    url = content.to_data_url()
    assert url.startswith("data:image/png;base64,")
    assert "aGVsbG8=" in url


def test_media_content_metadata():
    content = MediaContent(
        media_type=MediaType.VIDEO,
        data=b"video_data",
        mime_type="video/mp4",
        metadata={"duration": 120, "resolution": "1920x1080"},
    )
    assert content.metadata["duration"] == 120
    assert content.metadata["resolution"] == "1920x1080"
