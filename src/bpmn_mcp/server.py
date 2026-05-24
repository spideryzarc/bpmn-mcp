from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("BPMN Tools")

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

ET.register_namespace("bpmn", BPMN_NS)
ET.register_namespace("bpmndi", BPMNDI_NS)
ET.register_namespace("dc", DC_NS)
ET.register_namespace("di", DI_NS)

def _resolve_path(file_path: str) -> Path:
    return Path(file_path).expanduser().resolve()

@mcp.tool()
def create_bpmn_diagram(process_id: str, process_name: str, file_path: str) -> str:
    """Creates a basic BPMN 2.0 XML skeleton with a process and saves it to file_path."""
    root = ET.Element(f"{{{BPMN_NS}}}definitions", {
        "id": "Definitions_1",
        "targetNamespace": "http://bpmn.io/schema/bpmn",
        "exporter": "BPMN MCP"
    })
    
    process = ET.SubElement(root, f"{{{BPMN_NS}}}process", {
        "id": process_id,
        "name": process_name,
        "isExecutable": "true"
    })
    
    # Create the DI element
    diagram = ET.SubElement(root, f"{{{BPMNDI_NS}}}BPMNDiagram", {"id": "BPMNDiagram_1"})
    plane = ET.SubElement(diagram, f"{{{BPMNDI_NS}}}BPMNPlane", {
        "id": "BPMNPlane_1",
        "bpmnElement": process_id
    })
    
    tree = ET.ElementTree(root)
    path = _resolve_path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return f"Created basic BPMN diagram at {path}"

@mcp.tool()
def edit_bpmn_diagram(
    file_path: str,
    action: str,
    element_type: str,
    element_id: str,
    element_name: str | None = None,
    source_ref: str | None = None,
    target_ref: str | None = None
) -> str:
    """Edits an existing BPMN diagram.
    action: 'add' or 'remove'
    element_type: e.g., 'startEvent', 'endEvent', 'task', 'userTask', 'exclusiveGateway', 'sequenceFlow'
    element_id: Unique ID for the element.
    element_name: Display name.
    source_ref/target_ref: Required if element_type is 'sequenceFlow'.
    """
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    # Find the first process
    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        return "Error: No process found in BPMN XML."

    if action == "add":
        if process.find(f".//*[@id='{element_id}']") is not None:
            return f"Error: Element with id '{element_id}' already exists."

        attribs = {"id": element_id}
        if element_name:
            attribs["name"] = element_name
        
        if element_type == "sequenceFlow":
            if not source_ref or not target_ref:
                return "Error: source_ref and target_ref are required for sequenceFlow."
            attribs["sourceRef"] = source_ref
            attribs["targetRef"] = target_ref
            
        ET.SubElement(process, f"{{{BPMN_NS}}}{element_type}", attribs)
        
        # Add DI information for visualizers
        plane = root.find(f".//{{{BPMNDI_NS}}}BPMNPlane")
        if plane is not None:
            if element_type == "sequenceFlow":
                edge = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge", {
                    "id": f"{element_id}_di",
                    "bpmnElement": element_id
                })
                
                # Find source and target bounds to draw the line correctly
                def get_bounds(plane, ref_id):
                    for shape in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                        if shape.get("bpmnElement") == ref_id:
                            b = shape.find(f"{{{DC_NS}}}Bounds")
                            if b is not None:
                                return float(b.get("x", 0)), float(b.get("y", 0)), float(b.get("width", 0)), float(b.get("height", 0))
                    return None
                
                s_bounds = get_bounds(plane, source_ref)
                t_bounds = get_bounds(plane, target_ref)
                
                if s_bounds and t_bounds:
                    sx, sy, sw, sh = s_bounds
                    tx, ty, tw, th = t_bounds
                    # Connect from right edge of source to left edge of target
                    ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(sx + sw)), "y": str(int(sy + sh/2))})
                    ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(tx)), "y": str(int(ty + th/2))})
                else:
                    ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": "150", "y": "118"})
                    ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": "250", "y": "118"})
            else:
                shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", {
                    "id": f"{element_id}_di",
                    "bpmnElement": element_id
                })
                shapes = plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape")
                x_pos = 100 + (len(shapes) - 1) * 150
                
                width = "36" if "Event" in element_type else "100"
                height = "36" if "Event" in element_type else "80"
                y_pos = "100" if "Event" in element_type else "78" # align centers roughly
                
                ET.SubElement(shape, f"{{{DC_NS}}}Bounds", {
                    "x": str(x_pos), "y": y_pos, "width": width, "height": height
                })

        msg = f"Added {element_type} with id '{element_id}'."

    elif action == "remove":
        # Find and remove
        elem_to_remove = None
        for elem in process:
            if elem.get("id") == element_id:
                elem_to_remove = elem
                break
        
        if elem_to_remove is None:
            return f"Error: Element with id '{element_id}' not found in process."
        
        process.remove(elem_to_remove)
        msg = f"Removed element with id '{element_id}'."
    else:
        return f"Error: Invalid action '{action}'. Must be 'add' or 'remove'."

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return msg

@mcp.tool()
def validate_bpmn_diagram(file_path: str) -> str:
    """Performs basic validation on the BPMN XML structure."""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Invalid XML: {e}"

    if not root.tag.endswith("definitions"):
        return "Validation Error: Root element is not 'definitions'."
    
    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        return "Validation Error: No process found."

    issues = []
    
    # Check sequence flows
    flows = process.findall(f".//{{{BPMN_NS}}}sequenceFlow")
    all_elements = {elem.get("id") for elem in process if elem.get("id")}
    
    for flow in flows:
        source = flow.get("sourceRef")
        target = flow.get("targetRef")
        fid = flow.get("id")
        if not source or not target:
            issues.append(f"Flow {fid} missing sourceRef or targetRef.")
        if source and source not in all_elements:
            issues.append(f"Flow {fid} references unknown sourceRef '{source}'.")
        if target and target not in all_elements:
            issues.append(f"Flow {fid} references unknown targetRef '{target}'.")

    if issues:
        return "Validation failed with issues:\\n" + "\\n".join(issues)
    
    return "Basic validation passed."

@mcp.tool()
def export_bpmn_diagram(file_path: str) -> str:
    """Returns the BPMN diagram XML content as a string."""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    
    try:
        content = path.read_text(encoding="utf-8")
        return content
    except Exception as e:
        return f"Error reading file: {e}"

@mcp.tool()
def update_shape_bounds(file_path: str, element_id: str, x: int, y: int, width: int, height: int) -> str:
    """Updates the visual boundaries (coordinates and size) of a BPMN shape."""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{element_id}']")
    if shape is None:
        # Fallback to loop if xpath fails due to namespaces
        for s in root.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
            if s.get("bpmnElement") == element_id:
                shape = s
                break

    if shape is None:
        return f"Error: BPMNShape for element '{element_id}' not found."

    bounds = shape.find(f"{{{DC_NS}}}Bounds")
    if bounds is None:
        bounds = ET.SubElement(shape, f"{{{DC_NS}}}Bounds")
    
    bounds.set("x", str(x))
    bounds.set("y", str(y))
    bounds.set("width", str(width))
    bounds.set("height", str(height))

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return f"Updated bounds for '{element_id}': x={x}, y={y}, w={width}, h={height}."

@mcp.tool()
def update_edge_waypoints(file_path: str, element_id: str, waypoints: list[dict[str, int]]) -> str:
    """Updates the waypoints (x, y coordinate pairs) of a BPMN edge (sequence flow).
    waypoints should be a list of dicts: [{"x": 100, "y": 100}, {"x": 200, "y": 200}]
    """
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    edge = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='{element_id}']")
    if edge is None:
        for e in root.findall(f".//{{{BPMNDI_NS}}}BPMNEdge"):
            if e.get("bpmnElement") == element_id:
                edge = e
                break

    if edge is None:
        return f"Error: BPMNEdge for element '{element_id}' not found."

    # Remove existing waypoints
    existing = edge.findall(f"{{{DI_NS}}}waypoint")
    for wp in existing:
        edge.remove(wp)

    # Add new waypoints
    for wp in waypoints:
        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(wp["x"]), "y": str(wp["y"])})

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return f"Updated waypoints for edge '{element_id}' with {len(waypoints)} points."
