> "The plans of the diligent lead to profit as surely as haste leads to poverty." — Proverbs 21:5 | "But all things should be done decently and in order." — 1 Corinthians 14:40

# BPMN MCP Server

This project provides an MCP (Model Context Protocol) server that exposes tools for creating, editing, validating, and laying out BPMN 2.0 XML diagrams (`.bpmn`).

## Setup

Requires Python 3.10+

```bash
uv sync
```

Install development dependencies for running tests:

```bash
uv sync --dev
```

## Usage

You can run the server directly or integrate it via your MCP client.

```bash
uv run bpmn-mcp
```

Alternative entry point:

```bash
uv run python -m bpmn_mcp.main
```

### Remote Usage (Without Cloning)

You can run this server directly from the GitHub repository without cloning it locally by using `uvx`.

#### Antigravity IDE
Add the following to your Antigravity IDE MCP configuration (e.g., `.gemini/mcp.json`):
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

#### VS Code
Add the identical configuration to your VS Code MCP settings file (e.g., `cline_mcp_settings.json` or Claude Desktop config):
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

## Features

- **Create**: Generate a BPMN skeleton with `definitions`, one `process`, and DI (`BPMNDiagram`/`BPMNPlane`).
- **Edit Structure**: Add or remove individual BPMN elements and update element names.
- **Auto-Layout Sequence**: Dynamically generate entire process branches (`sequenceFlows`) with orthogonal auto-routing (smart elbows for branches and loops).
- **Validate**: Run structural validation for BPMN root/process presence and `sequenceFlow` references.
- **Layout**: Reposition shapes, update sequence flow waypoints, and reposition labels for shapes/edges.
- **Inspect**: List process elements as JSON for agent-friendly state inspection.

## Tool Reference

- `create_bpmn_diagram`: Create a new BPMN file with base process and DI.
- `add_bpmn_sequence`: **[BEST PRACTICE]** Adds a sequence of elements, automatically generating sequence flows and applying orthogonal Y-axis layout routing.
- `edit_bpmn_diagram`: Add or remove individual BPMN elements.
- `validate_bpmn_diagram`: Validate core BPMN XML structure and sequence flow references.
- `update_shape_bounds`: Set x/y/width/height of a shape in BPMN DI.
- `update_edge_waypoints`: Replace edge waypoints for sequence flow routing.
- `update_label_bounds`: Set x/y/width/height for label text bounds (shape or edge).
- `list_bpmn_elements`: Return process elements as formatted JSON.
- `update_bpmn_element`: Update element properties (currently `name`).
- `get_sequence_flow_id`: Returns the ID of a sequence flow connecting two specific elements.

## Tech Stack

- Python 3.10+
- FastMCP / MCP server runtime
- `xml.etree.ElementTree` for BPMN XML and BPMN-DI manipulation
- `pytest` for tests
- `uv` for dependency and environment management

## Project Structure

```text
.
├── pyproject.toml
├── README.md
├── src/
│   └── bpmn_mcp/
│       ├── __init__.py
│       ├── main.py
│       └── server.py
├── test_outputs/
│   ├── complex_sequence_auto.bpmn
│   ├── complex_test.bpmn
│   ├── loop_test.bpmn
│   ├── linear_test.bpmn
│   └── ... (other generated BPMN tests)
└── tests/
    ├── test_bpmn.py
    └── test_sequence.py
```

## Example Usage

Typical tool sequence used by an MCP client:

1. `create_bpmn_diagram` to initialize a file.
2. `add_bpmn_sequence` to add tasks/events/gateways and automatically handle geometric placement and connections.
3. `update_shape_bounds`, `update_edge_waypoints`, and `update_label_bounds` to fine-tune layout manually if necessary.
4. `validate_bpmn_diagram` to verify references.
5. `list_bpmn_elements` to inspect current process state.

Example call payload:

```json
{
  "tool": "add_bpmn_sequence",
  "arguments": {
    "file_path": "test_outputs/test.bpmn",
    "elements": [
        {"id": "Start", "type": "startEvent", "name": "Start"},
        {"id": "Task1", "type": "task", "name": "Do Work"}
    ]
  }
}
```

## Testing

```bash
uv run pytest -v
```
