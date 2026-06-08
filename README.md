# BPMN MCP Server

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/)
[![Model Context Protocol](https://img.shields.io/badge/MCP-1.0.0-orange.svg)](https://modelcontextprotocol.io)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen.svg)](https://github.com/spideryzarc/bpmn-mcp)

A Model Context Protocol (MCP) server that provides structured tools for AI assistants and developers to create, edit, validate, and lay out BPMN 2.0 XML diagrams (`.bpmn`) programmatically. 

This server abstracts the complexities of raw XML manipulation (including namespaces and DI coordinate mapping), enabling agents to work with BPMN models using simple, high-level JSON payloads.

---

## 🚀 Key Capabilities

- **Semantic Diagram Mutation**: Add or remove tasks, gateways, intermediate/boundary events, data objects, annotations, and sequence flows.
- **Intelligent Auto-Layout**: Automatically compute shape boundaries, calculate vertical offsets for sibling branches to prevent collisions, and route orthogonal sequence flow lines (elbows).
- **Swimlanes & Collaboration**: Support for pools (`participants`) and `lanes` with automatic node references to match BPMN 2.0 standards.
- **Multi-Pool Collaboration**: Connect separate organizations or processes with `messageFlow` elements.
- **AI-Friendly Inspection**: Query the complete diagram structure as a flat JSON array, allowing LLMs to understand the current state in a single call.
- **Structural Validation**: Validate element references, loopback targets, start/end node availability, and connection consistency.

---

## 📦 Getting Started

### Prerequisites

- **Python**: Version 3.10 or higher.
- **uv**: We recommend using [uv](https://github.com/astral-sh/uv) for fast package and project management.

### Installation

Install and synchronize dependencies:

```bash
uv sync
```

For development and test dependencies:

```bash
uv sync --dev
```

### Running the Server

Start the MCP server using:

```bash
uv run bpmn-mcp
```

Or run it via Python's module syntax:

```bash
uv run python -m bpmn_mcp.main
```

---

## 🔌 Editor & Client Integration

You can run this server directly from the GitHub repository without cloning it locally by using `uvx`.

### Claude Desktop

Add the following configuration to your `claude_desktop_config.json` (typically located in `%APPDATA%\Claude` on Windows or `~/Library/Application Support/Claude` on macOS):

```json
{
  "mcpServers": {
    "bpmn-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/spideryzarc/bpmn-mcp.git",
        "bpmn-mcp"
      ]
    }
  }
}
```

### VS Code (Cline / Roo Code / Roo Clinic)

Add this configuration to your local client settings file:

```json
{
  "mcpServers": {
    "bpmn-mcp": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/spideryzarc/bpmn-mcp.git",
        "bpmn-mcp"
      ]
    }
  }
}
```

---

## 🛠️ MCP Tools Reference

The server exposes 11 core tools designed to cover the entire lifecycle of BPMN diagramming.

| Tool Name | Key Parameters | Description |
| :--- | :--- | :--- |
| `create_bpmn_diagram` | `process_id`, `process_name`, `file_path` | Initializes a new BPMN file containing a base process and a DI plane. |
| `add_bpmn_sequence` | `file_path`, `elements` | **[Best Practice]** Appends a list of consecutive elements, auto-wires sequence flows, and applies layout collision routing. |
| `edit_bpmn_diagram` | `file_path`, `element_type`, `element_id`, `source_ref`, `target_ref`, etc. | Adds or removes individual elements. Used for pools, lanes, gateways, boundary events, annotations, and flows. |
| `list_bpmn_elements` | `file_path` | Returns a simplified flat JSON array representing all process elements, positions, and references. |
| `validate_bpmn_diagram` | `file_path` | Performs structural validation, ensuring flow references exist and connection rules are obeyed. |
| `update_bpmn_element` | `file_path`, `element_id`, `name`, `documentation` | Renames an element or updates its text documentation node. |
| `update_shape_bounds` | `file_path`, `element_id`, `x`, `y`, `width`, `height` | Manually updates the position and size of a shape's DI representation. |
| `update_edge_waypoints`| `file_path`, `element_id`, `waypoints` | Replaces the DI waypoint coordinate pairs (x, y) of a flow line (edge). |
| `update_label_bounds` | `file_path`, `element_id`, `x`, `y`, `width`, `height` | Positions or sizes the text label of a shape or sequence flow edge. |
| `batch_update_visuals` | `file_path`, `shapes`, `edges` | Visual optimization helper: updates multiple shapes and edges in a single request. |
| `get_sequence_flow_id` | `file_path`, `source_ref`, `target_ref` | Looks up the sequence flow ID connecting two elements. |

---

## 🌊 Advanced Workflows & BPMN Concepts

### 1. Swimlane (Pool & Lane) Workflow

In BPMN 2.0, flow nodes are process children, whereas lanes reference these nodes via `<flowNodeRef>`. The server handles this automatically.

**Step-by-Step Swimlane Creation:**

1. **Create the Pool (`participant`)**:
   ```json
   {
     "tool": "edit_bpmn_diagram",
     "arguments": {
       "file_path": "order_process.bpmn",
       "element_type": "participant",
       "element_id": "Pool_Warehouse",
       "element_name": "Warehouse Department"
     }
   }
   ```
2. **Create Lanes inside the Pool** (by matching `parent_ref` to the Pool ID):
   ```json
   {
     "tool": "edit_bpmn_diagram",
     "arguments": {
       "file_path": "order_process.bpmn",
       "element_type": "lane",
       "element_id": "Lane_Packing",
       "element_name": "Packing Crew",
       "parent_ref": "Pool_Warehouse"
     }
   }
   ```
3. **Place Flow Elements inside a Lane** (by matching `parent_ref` to the Lane ID):
   ```json
   {
     "tool": "edit_bpmn_diagram",
     "arguments": {
       "file_path": "order_process.bpmn",
       "element_type": "task",
       "element_id": "Task_PackBox",
       "element_name": "Pack Order Box",
       "parent_ref": "Lane_Packing"
     }
   }
   ```

---

### 2. Multi-Pool Collaboration (Message Flows)

To model interactions between different processes or systems, use `messageFlow` to bridge elements across pools.

```json
{
  "tool": "edit_bpmn_diagram",
  "arguments": {
    "file_path": "collaboration.bpmn",
    "element_type": "messageFlow",
    "element_id": "MF_Customer_to_Seller",
    "element_name": "Submit Order",
    "source_ref": "Task_SubmitOrder_InPoolA",
    "target_ref": "StartEvent_Received_InPoolB"
  }
}
```

---

### 3. Layout Engine Rules

The auto-layout engine implements three main routing rules:
* **Horizontal Flow**: Sequence flows generally exit the right side of a shape and enter the left side of the next.
* **Sibling Branch Offset**: When multiple paths branch off a single element (e.g., from an exclusive gateway), the engine calculates the coordinates of sibling shapes sequentially to prevent them from rendering directly on top of each other.
* **Loopback Routing (Elbows)**: If a sequence flow routes backward (target x is less than source x), the engine exits the bottom of the source element, runs underneath, and enters the bottom of the target element, avoiding overlapping process paths.

---

## 🧪 Development & Testing

Run the test suite using pytest to ensure XML writing, DI coordinate mapping, and validations work as expected:

```bash
uv run pytest -v
```

### Project Structure

```text
.
├── pyproject.toml
├── README.md
├── src/
│   └── bpmn_mcp/
│       ├── __init__.py
│       ├── main.py        # CLI Entrypoint
│       └── server.py      # Core Server & MCP Tools Implementation
├── test_outputs/          # Output directory for generated test files
└── tests/                 # Unit tests verifying BPMN features
    ├── test_bpmn.py
    └── test_sequence.py
```

---

## 📜 Philosophy

> *"The plans of the diligent lead to profit as surely as haste leads to poverty."* — Proverbs 21:5
> 
> *"But all things should be done decently and in order."* — 1 Corinthians 14:40

---

## 📄 License

This project is licensed under the MIT License. See [LICENSE](LICENSE) or details in `pyproject.toml` for more information.
