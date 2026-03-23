# Plugin SDK

Write a Python plugin to add custom tools to JARVIS.

**Prerequisites:**
- Python 3.11+
- JARVIS running locally (see [Getting Started](../user-guide/getting-started.md))

---

## Directory Structure

```
my_plugin/
├── __init__.py    # Exports the plugin class
└── plugin.py      # Plugin implementation
```

---

## Minimal Example

```python
# my_plugin/plugin.py
from langchain_core.tools import tool

from app.plugins.sdk import JarvisPlugin, JarvisPluginManifest, PluginCategory
from app.plugins.api import PluginAPI


class GreetPlugin(JarvisPlugin):
    manifest = JarvisPluginManifest(
        plugin_id="greet",
        name="Greet",
        version="1.0.0",
        description="Returns a greeting for the given name.",
        category=PluginCategory.TOOL,
        author="you@example.com",
    )

    async def on_load(self, api: PluginAPI) -> None:
        prefix = api.get_config("GREET_PREFIX") or "Hello"

        @tool
        def greet(name: str) -> str:
            """Return a greeting for the given name."""
            return f"{prefix}, {name}!"

        api.register_tool(greet)
```

```python
# my_plugin/__init__.py
from .plugin import GreetPlugin

plugin = GreetPlugin()
```

---

## SDK API Reference

### `JarvisPlugin` (abstract base class)

Subclass this and set a class-level `manifest`.

| Method / property | Description |
|-------------------|-------------|
| `manifest` | Class attribute — a `JarvisPluginManifest` instance |
| `async on_load(api)` | **Required.** Called once when the plugin is activated. Register tools here. |
| `async on_unload()` | Optional. Called on app shutdown for cleanup. |
| `plugin_id` | Property — returns `manifest.plugin_id` |

### `JarvisPluginManifest` fields

| Field | Type | Description |
|-------|------|-------------|
| `plugin_id` | `str` | Unique slug (e.g. `"my-plugin"`) |
| `name` | `str` | Human-readable name |
| `version` | `str` | Semver string (default `"0.1.0"`) |
| `description` | `str` | Brief purpose |
| `category` | `PluginCategory` | One of: `TOOL`, `CHANNEL`, `RAG`, `AUTOMATION`, `UI`, `SYSTEM` |
| `requires` | `list[str]` | IDs of dependency plugins |
| `config_schema` | `dict` | JSON Schema for plugin config (optional) |

### `PluginAPI` methods

| Method | Description |
|--------|-------------|
| `api.register_tool(tool)` | Register a LangChain `BaseTool` contributed by this plugin |
| `api.register_channel(adapter)` | Register a channel adapter (Slack, Discord, etc.) |
| `api.get_config(key, default=None)` | Read a value from environment variables |

### `SimpleSkillPlugin`

For the common case of registering all public methods as tools automatically:

```python
from app.plugins.sdk import SimpleSkillPlugin, JarvisPluginManifest


class MathPlugin(SimpleSkillPlugin):
    manifest = JarvisPluginManifest(
        plugin_id="math",
        name="Math",
        description="Basic math operations.",
    )

    def add(self, a: float, b: float) -> str:
        """Add two numbers."""
        return str(a + b)

    def multiply(self, a: float, b: float) -> str:
        """Multiply two numbers."""
        return str(a * b)
```

Each method becomes a tool named `{plugin_id}_{method_name}` with the docstring as description.

---

## Installing a Local Plugin

1. Copy your plugin directory to `backend/plugins/my_plugin/`.
2. In JARVIS, go to **Plugins** → **Reload Plugins**.
3. The plugin appears in the list and its tools are available to the agent.

---

## Publishing to a Registry

A registry is a JSON file served over HTTPS listing available skills:

```json
[
  {
    "id": "greet",
    "name": "Greet",
    "version": "1.0.0",
    "description": "Returns a greeting for the given name.",
    "author": "you@example.com",
    "type": "python_plugin",
    "install_url": "https://your-host.com/plugins/greet.zip",
    "scope": ["personal", "system"]
  }
]
```

Point JARVIS to your registry by setting `SKILL_REGISTRY_URL=https://your-host.com/registry.json` in `.env`.
