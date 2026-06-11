"""HiveFlow - Plugin Marketplace

Provides a curated collection of pre-built MCP plugins for common use cases.
Each plugin is a ready-to-use MCP server configuration with metadata.

Includes:
- Filesystem: File read/write/search
- Web Search: Web scraping and search engine integration
- Database: SQL database query and schema exploration
- Code Execution: Python/JavaScript code sandbox
- Git: Repository operations
- Email: Email send/receive
- Calendar: Calendar management
- API Client: REST API integration
"""

import logging
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class PluginCategory(str, Enum):
    """Plugin categories."""

    DATA = "data"  # Data sources (DB, file, API)
    TOOLS = "tools"  # Utility tools (code, search, email)
    COMMUNICATION = "communication"  # Email, calendar, messaging
    DEVELOPMENT = "development"  # Git, CI/CD, code tools
    AI = "ai"  # AI services
    CUSTOM = "custom"


@dataclass
class PluginSpec:
    """A complete plugin specification for the marketplace."""

    plugin_id: str
    name: str
    description: str
    category: PluginCategory
    version: str = "1.0.0"
    author: str = "HiveFlow"
    transport: str = "stdio"
    command: str = ""
    args: list[str] = field(default_factory=list)
    env_keys: list[str] = field(default_factory=list)  # Required env vars
    tools: list[dict[str, str]] = field(default_factory=list)  # Tool descriptions
    icon: str = ""  # Emoji or icon
    tags: list[str] = field(default_factory=list)
    documentation: str = ""
    rating: float = 0.0
    downloads: int = 0
    is_built_in: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "plugin_id": self.plugin_id,
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "version": self.version,
            "author": self.author,
            "transport": self.transport,
            "command": self.command,
            "args": self.args,
            "env_keys": self.env_keys,
            "tools": self.tools,
            "icon": self.icon,
            "tags": self.tags,
            "documentation": self.documentation,
            "rating": self.rating,
            "downloads": self.downloads,
            "is_built_in": self.is_built_in,
        }


class PluginMarketplace:
    """
    Marketplace of pre-built MCP plugins.

    Usage:
        marketplace = PluginMarketplace()

        # List all plugins
        plugins = marketplace.list_plugins()

        # Search plugins
        plugins = marketplace.search_plugins("file")

        # Get plugin by ID
        plugin = marketplace.get_plugin("filesystem")

        # Install plugin to MCPPluginManager
        await marketplace.install_plugin("filesystem", plugin_manager)
    """

    def __init__(self):
        self._plugins: dict[str, PluginSpec] = {}
        self._register_built_in_plugins()

    def list_plugins(self, category: PluginCategory | None = None) -> list[PluginSpec]:
        """List all available plugins, optionally filtered by category."""
        plugins = list(self._plugins.values())
        if category:
            plugins = [p for p in plugins if p.category == category]
        return sorted(plugins, key=lambda p: p.downloads, reverse=True)

    def get_plugin(self, plugin_id: str) -> PluginSpec | None:
        """Get a plugin by ID."""
        return self._plugins.get(plugin_id)

    def search_plugins(self, query: str) -> list[PluginSpec]:
        """Search plugins by name, description, tags, or tools."""
        query_lower = query.lower()
        results = []
        for plugin in self._plugins.values():
            if (
                query_lower in plugin.name.lower()
                or query_lower in plugin.description.lower()
                or any(query_lower in tag.lower() for tag in plugin.tags)
                or any(query_lower in t.get("name", "").lower() for t in plugin.tools)
            ):
                results.append(plugin)
        return results

    async def install_plugin(self, plugin_id: str, plugin_manager, **overrides) -> bool:
        """Install a plugin to an MCPPluginManager instance."""
        spec = self._plugins.get(plugin_id)
        if not spec:
            return False

        # Allow overrides for command, args, env
        cmd = overrides.get("command", spec.command)
        args = overrides.get("args", spec.args)
        env = {}
        for key in spec.env_keys:
            val = overrides.get(key, os.environ.get(key, ""))
            if val:
                env[key] = val

        await plugin_manager.register_plugin(
            plugin_id=spec.plugin_id,
            name=spec.name,
            description=spec.description,
            transport=spec.transport,
            command=cmd,
            args=args,
            env=env,
        )
        logger.info(f"Plugin installed from marketplace: {plugin_id}")
        return True

    def get_categories(self) -> dict[PluginCategory, int]:
        """Get all available categories with plugin counts."""
        counts: dict[PluginCategory, int] = {}
        for plugin in self._plugins.values():
            counts[plugin.category] = counts.get(plugin.category, 0) + 1
        return counts

    def get_stats(self) -> dict[str, Any]:
        """Get marketplace statistics."""
        return {
            "total_plugins": len(self._plugins),
            "categories": {c.value: n for c, n in self.get_categories().items()},
            "built_in": sum(1 for p in self._plugins.values() if p.is_built_in),
            "total_downloads": sum(p.downloads for p in self._plugins.values()),
        }

    def add_plugin(self, spec: PluginSpec):
        """Add a custom plugin to the marketplace."""
        self._plugins[spec.plugin_id] = spec
        logger.info(f"Custom plugin added: {spec.plugin_id}")

    def remove_plugin(self, plugin_id: str) -> bool:
        """Remove a custom plugin from the marketplace."""
        if plugin_id in self._plugins:
            spec = self._plugins[plugin_id]
            if spec.is_built_in:
                return False  # Can't remove built-in plugins
            del self._plugins[plugin_id]
            return True
        return False

    def _register_built_in_plugins(self):
        """Register all built-in plugins."""
        plugins = [
            # 1. Filesystem Plugin
            PluginSpec(
                plugin_id="filesystem",
                name="Filesystem Server",
                description="Read, write, and search files on the local filesystem. Supports directory listing, file content reading, and file operations.",
                category=PluginCategory.DATA,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-filesystem"],
                env_keys=[],
                tools=[
                    {"name": "read_file", "description": "Read the contents of a file"},
                    {"name": "write_file", "description": "Write content to a file"},
                    {"name": "list_directory", "description": "List files in a directory"},
                    {"name": "search_files", "description": "Search for files by pattern"},
                    {"name": "move_file", "description": "Move or rename a file"},
                    {"name": "delete_file", "description": "Delete a file"},
                ],
                icon="📁",
                tags=["file", "filesystem", "io", "storage"],
                documentation="https://github.com/modelcontextprotocol/servers/tree/main/src/filesystem",
                downloads=15000,
            ),
            # 2. Web Search Plugin
            PluginSpec(
                plugin_id="web-search",
                name="Web Search Server",
                description="Search the web and extract page content. Integrates with Brave Search or DuckDuckGo for web search results.",
                category=PluginCategory.TOOLS,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-brave-search"],
                env_keys=["BRAVE_API_KEY"],
                tools=[
                    {"name": "web_search", "description": "Search the web using Brave Search"},
                    {"name": "fetch_page", "description": "Fetch and extract content from a URL"},
                    {"name": "extract_links", "description": "Extract links from a page"},
                ],
                icon="🔍",
                tags=["search", "web", "scrape", "browser"],
                documentation="https://github.com/modelcontextprotocol/servers/tree/main/src/brave-search",
                downloads=12000,
            ),
            # 3. Database Plugin
            PluginSpec(
                plugin_id="database",
                name="Database Server",
                description="Query SQL databases (PostgreSQL, MySQL, SQLite). Supports schema exploration, query execution, and result formatting.",
                category=PluginCategory.DATA,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-postgres"],
                env_keys=["DATABASE_URL"],
                tools=[
                    {"name": "query", "description": "Execute a SQL query"},
                    {"name": "list_tables", "description": "List all tables in the database"},
                    {"name": "describe_table", "description": "Get schema of a table"},
                    {"name": "explain_query", "description": "EXPLAIN a SQL query"},
                ],
                icon="🗄️",
                tags=["database", "sql", "postgres", "mysql", "sqlite"],
                documentation="https://github.com/modelcontextprotocol/servers/tree/main/src/postgres",
                downloads=8000,
            ),
            # 4. Code Execution Plugin
            PluginSpec(
                plugin_id="code-executor",
                name="Code Executor Server",
                description="Execute Python and JavaScript code in a sandboxed environment. Returns output, errors, and execution time.",
                category=PluginCategory.DEVELOPMENT,
                command="python",
                args=["-m", "hiveflow.mcp_code_server"],
                env_keys=[],
                tools=[
                    {"name": "execute_python", "description": "Execute Python code"},
                    {"name": "execute_javascript", "description": "Execute JavaScript code"},
                    {"name": "install_package", "description": "Install a Python package"},
                    {"name": "list_packages", "description": "List installed packages"},
                ],
                icon="💻",
                tags=["code", "python", "javascript", "execute", "sandbox"],
                documentation="Execute code in a secure sandbox",
                downloads=6000,
            ),
            # 5. Git Plugin
            PluginSpec(
                plugin_id="git",
                name="Git Server",
                description="Git repository operations including status, diff, commit, branch management, and log viewing.",
                category=PluginCategory.DEVELOPMENT,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-git"],
                env_keys=[],
                tools=[
                    {"name": "git_status", "description": "Show repository status"},
                    {"name": "git_diff", "description": "Show changes between commits"},
                    {"name": "git_log", "description": "Show commit history"},
                    {"name": "git_branch", "description": "List and manage branches"},
                    {"name": "git_commit", "description": "Create a commit"},
                ],
                icon="🔀",
                tags=["git", "version-control", "repository", "commit"],
                documentation="https://github.com/modelcontextprotocol/servers/tree/main/src/git",
                downloads=5000,
            ),
            # 6. Email Plugin
            PluginSpec(
                plugin_id="email",
                name="Email Server",
                description="Send and receive emails via IMAP/SMTP. Supports composing, searching, and organizing emails.",
                category=PluginCategory.COMMUNICATION,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-email"],
                env_keys=["IMAP_HOST", "IMAP_PORT", "SMTP_HOST", "SMTP_PORT", "EMAIL_USER", "EMAIL_PASSWORD"],
                tools=[
                    {"name": "send_email", "description": "Send an email"},
                    {"name": "list_emails", "description": "List emails in inbox"},
                    {"name": "read_email", "description": "Read an email content"},
                    {"name": "search_emails", "description": "Search emails by criteria"},
                ],
                icon="📧",
                tags=["email", "imap", "smtp", "communication"],
                documentation="Send and receive emails",
                downloads=3000,
            ),
            # 7. Calendar Plugin
            PluginSpec(
                plugin_id="calendar",
                name="Calendar Server",
                description="Calendar management via Google Calendar API. Supports creating events, listing schedules, and managing invitations.",
                category=PluginCategory.COMMUNICATION,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-google-calendar"],
                env_keys=["GOOGLE_CALENDAR_CREDENTIALS"],
                tools=[
                    {"name": "list_events", "description": "List calendar events"},
                    {"name": "create_event", "description": "Create a calendar event"},
                    {"name": "update_event", "description": "Update an existing event"},
                    {"name": "delete_event", "description": "Delete a calendar event"},
                ],
                icon="📅",
                tags=["calendar", "google", "schedule", "events"],
                documentation="Google Calendar integration",
                downloads=2500,
            ),
            # 8. REST API Client Plugin
            PluginSpec(
                plugin_id="api-client",
                name="API Client Server",
                description="Make HTTP requests to any REST API. Supports GET/POST/PUT/DELETE with authentication headers.",
                category=PluginCategory.TOOLS,
                command="npx",
                args=["-y", "@modelcontextprotocol/server-fetch"],
                env_keys=[],
                tools=[
                    {"name": "fetch", "description": "Make an HTTP request"},
                    {"name": "get", "description": "HTTP GET request"},
                    {"name": "post", "description": "HTTP POST request"},
                    {"name": "put", "description": "HTTP PUT request"},
                    {"name": "delete", "description": "HTTP DELETE request"},
                ],
                icon="🌐",
                tags=["api", "http", "rest", "fetch", "request"],
                documentation="Make HTTP requests",
                downloads=7000,
            ),
            # 9. Knowledge Base / RAG Plugin (HiveFlow native)
            PluginSpec(
                plugin_id="hiveflow-rag",
                name="HiveFlow Knowledge Base",
                description="Native HiveFlow RAG integration. Query knowledge bases, add documents, and manage collections through MCP.",
                category=PluginCategory.AI,
                command="python",
                args=["-m", "hiveflow.mcp_rag_server"],
                env_keys=["HIVEFLOW_KB_PATH"],
                tools=[
                    {"name": "query_kb", "description": "Query a knowledge base"},
                    {"name": "search_kb", "description": "Search without answer generation"},
                    {"name": "add_document", "description": "Add a document to KB"},
                    {"name": "list_documents", "description": "List documents in KB"},
                    {"name": "remove_document", "description": "Remove a document from KB"},
                    {"name": "create_kb", "description": "Create a new knowledge base"},
                ],
                icon="🧠",
                tags=["rag", "knowledge-base", "vector", "search", "hiveflow"],
                documentation="HiveFlow RAG via MCP",
                downloads=1000,
                is_built_in=True,
            ),
            # 10. Multi-Modal Plugin (HiveFlow native)
            PluginSpec(
                plugin_id="hiveflow-multimodal",
                name="HiveFlow Multi-Modal",
                description="Native HiveFlow multi-modal processing. Image analysis, audio transcription, video summarization through MCP.",
                category=PluginCategory.AI,
                command="python",
                args=["-m", "hiveflow.mcp_multimodal_server"],
                env_keys=["OPENAI_API_KEY"],
                tools=[
                    {"name": "analyze_image", "description": "Analyze an image with AI"},
                    {"name": "extract_text", "description": "OCR text from image"},
                    {"name": "transcribe_audio", "description": "Transcribe audio to text"},
                    {"name": "generate_image", "description": "Generate an image from text"},
                    {"name": "summarize_video", "description": "Summarize video content"},
                ],
                icon="🎨",
                tags=["multimodal", "image", "audio", "video", "ocr", "hiveflow"],
                documentation="HiveFlow Multi-Modal via MCP",
                downloads=500,
                is_built_in=True,
            ),
        ]

        for plugin in plugins:
            self._plugins[plugin.plugin_id] = plugin
