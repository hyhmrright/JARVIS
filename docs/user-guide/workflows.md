# Workflow Studio

Workflow Studio is a visual editor for building multi-step automation pipelines.

**Prerequisites:**
- JARVIS running and logged in (see [Getting Started](./getting-started.md))

---

## Open Workflow Studio

Click **Workflows** in the left sidebar. The canvas loads with an empty graph.

---

## Create a Workflow

1. Click **New Workflow**.
2. Give it a name.
3. The canvas shows a default **Start** node.

---

## Add Nodes

1. Click **+ Add Node** (or right-click the canvas).
2. Choose a node type:
   - **LLM** — call the configured language model
   - **Tool** — invoke an installed plugin tool
   - **HTTP** — make an outbound HTTP request
   - **Transform** — apply a JavaScript expression to the data
3. Configure the node's parameters in the right panel.

---

## Connect Nodes

Drag from an output port to an input port to create an edge. Data flows along edges as JSON objects.

---

## Run / Test

1. Click **Run** in the toolbar.
2. Provide test input in the **Input** panel on the left.
3. Watch execution progress — each node highlights green (success) or red (error).
4. Click any executed node to inspect its input and output.

---

## Save and Trigger from Chat

1. Click **Save**.
2. In a chat conversation, type `/run <workflow-name>` to trigger the workflow inline.
3. The workflow result is streamed back as a chat message.

Workflows can also be triggered on a schedule via the **Proactive Monitoring** page (cron syntax).
