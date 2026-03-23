# Plugins & Skills

Plugins and skills extend JARVIS with new tools — from web search to custom API integrations.

**Prerequisites:**
- JARVIS running and logged in (see [Getting Started](./getting-started.md))

---

## Concepts

| Term | What it is |
|------|-----------|
| **Plugin** | A local Python package loaded at startup from the file system |
| **Skill** | An installable package pulled from the Skill Market or a custom URL |
| **MCP server** | An external process exposing tools via the Model Context Protocol (stdio or HTTP) |

Skills are the primary way to add capabilities at runtime without restarting JARVIS.

---

## Install from the Skill Market

1. Navigate to **Plugins** → **Browse Market**.
2. Browse or search the catalog.
3. Click **Install (Personal)** to install for your account only, or **Install (System-wide)** (admin only) to make it available to all users.
4. After installation the card shows a green **Installed** badge.

---

## Install from a URL

Private or unlisted skills, `npx`-based MCP servers, and GitHub repositories can be installed directly:

1. From the **Plugins** page, click **Install from URL** in the page header.
   _Alternatively, from the Skill Market header, click **+ Install from URL**._
2. Paste the package URL or `npx` command.
3. Choose **Personal** or **System-wide** scope.
4. Click **Install**.

**Example — install an npx MCP server:**
```
npx -y @modelcontextprotocol/server-filesystem /home/user/docs
```

---

## Configure a Plugin

Some plugins require API keys or other settings:

1. Go to **Plugins** and find the plugin card.
2. Click **Configure**.
3. Enter key/value pairs. Toggle **Encrypt** for secrets (stored with Fernet encryption).
4. Click **Add** for each entry.

---

## Enable / Disable Tools

Each plugin exposes one or more tools. Individual tools can be toggled in the plugin configuration panel.

---

## Uninstall

1. Go to **Plugins** → **My Installed Plugins** (or **System Installed Plugins** for admins).
2. Click **Uninstall** next to the plugin.
3. Confirm the dialog.

The plugin is removed from the database; no restart is required for market-installed skills.

---

## Reload Locally-Loaded Plugins

File-system plugins (Python packages in the `plugins/` directory) are loaded at startup. After adding or modifying a plugin file:

1. Go to **Plugins**.
2. Click **Reload Plugins**.

This triggers a hot-reload without a full Docker restart.
