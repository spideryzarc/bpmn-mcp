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

## Features

- **Create**: Generate a BPMN skeleton with `definitions`, one `process`, and DI (`BPMNDiagram`/`BPMNPlane`).
- **Edit Structure**: Add or remove BPMN elements (including `sequenceFlow`) and update element names.
- **Validate**: Run structural validation for BPMN root/process presence and `sequenceFlow` references.
- **Layout**: Reposition shapes, update sequence flow waypoints, and reposition labels for shapes/edges.
- **Inspect**: List process elements as JSON for agent-friendly state inspection.

## Tool Reference

- `create_bpmn_diagram`: Create a new BPMN file with base process and DI.
- `edit_bpmn_diagram`: Add or remove BPMN elements.
- `validate_bpmn_diagram`: Validate core BPMN XML structure and sequence flow references.
- `update_shape_bounds`: Set x/y/width/height of a shape in BPMN DI.
- `update_edge_waypoints`: Replace edge waypoints for sequence flow routing.
- `update_label_bounds`: Set x/y/width/height for label text bounds (shape or edge).
- `list_bpmn_elements`: Return process elements as formatted JSON.
- `update_bpmn_element`: Update element properties (currently `name`).

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
│   ├── complex_test.bpmn
│   ├── labels_test.bpmn
│   └── test.bpmn
└── tests/
    └── test_bpmn.py
```

## Example Usage

Typical tool sequence used by an MCP client:

1. `create_bpmn_diagram` to initialize a file.
2. `edit_bpmn_diagram` to add tasks/events/flows.
3. `update_shape_bounds`, `update_edge_waypoints`, and `update_label_bounds` to organize layout.
4. `validate_bpmn_diagram` to verify references.
5. `list_bpmn_elements` to inspect current process state.

Example call payload:

```json
{
  "tool": "update_label_bounds",
  "arguments": {
    "file_path": "test_outputs/test.bpmn",
    "element_id": "Flow_1",
    "x": 250,
    "y": 95,
    "width": 70,
    "height": 18
  }
}
```

## Testing

```bash
uv run pytest -q
```
