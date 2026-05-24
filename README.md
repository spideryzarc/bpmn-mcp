# BPMN MCP Server

This is an MCP (Model Context Protocol) server designed to provide an AI assistant with the capability to create, edit, validate, and export BPMN 2.0 XML diagrams (`.bpmn`).

## Setup

Requires Python 3.10+

```bash
uv sync
```

## Usage

You can run the server directly or integrate it via your MCP client.

```bash
uv run bpmn-mcp
```

## Features

- **Create**: Generate a basic `.bpmn` file structure with definitions and a process.
- **Edit**: Add nodes (tasks, events, gateways) and connect them via sequence flows.
- **Validate**: Perform basic checks on the XML structure to ensure it's a valid BPMN definition.
- **Export**: Retrieve the raw XML representation or save it to a file.
