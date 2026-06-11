"""
HiveFlow - 13: Plugin Development

This example demonstrates the built-in plugin marketplace.

Usage:
    python 13_plugin_development.py
"""
import asyncio
from hiveflow import PluginMarketplace, MCPPluginManager


async def main():
    print("=== Plugin Development Example ===\n")

    marketplace = PluginMarketplace()
    plugins = marketplace.list_plugins()
    print(f"Built-in plugins available: {len(plugins)}")
    for plugin in plugins[:5]:
        print(f"  - {plugin.name} ({plugin.category.value}): {plugin.description[:50]}...")

    search_results = marketplace.search_plugins("file")
    print(f"\nSearch 'file': {len(search_results)} matches")

    filesystem = marketplace.get_plugin("filesystem")
    if filesystem:
        print(f"\nFilesystem plugin tools: {[t['name'] for t in filesystem.tools]}")

    plugin_manager = MCPPluginManager()
    if filesystem:
        installed = await marketplace.install_plugin("filesystem", plugin_manager)
        print(f"Installed filesystem plugin: {installed}")

    categories = marketplace.get_categories()
    print(f"\nCategories: {list(categories.keys())}")


if __name__ == "__main__":
    asyncio.run(main())
