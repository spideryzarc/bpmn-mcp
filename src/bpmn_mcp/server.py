from __future__ import annotations

import json
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

_EVENT_DEFINITION_MAP: dict[str, str] = {
    "error": "errorEventDefinition",
    "message": "messageEventDefinition",
    "signal": "signalEventDefinition",
    "terminate": "terminateEventDefinition",
    "timer": "timerEventDefinition",
    "escalation": "escalationEventDefinition",
    "compensation": "compensateEventDefinition",
    "conditional": "conditionalEventDefinition",
    "link": "linkEventDefinition",
    "cancel": "cancelEventDefinition",
}

_EVENT_TYPES = {
    "startEvent", "endEvent",
    "intermediateThrowEvent", "intermediateCatchEvent",
    "boundaryEvent",
}

@mcp.tool()
def edit_bpmn_diagram(
    file_path: str,
    action: str,
    element_type: str,
    element_id: str,
    element_name: str | None = None,
    source_ref: str | None = None,
    target_ref: str | None = None,
    event_definition: str | None = None,
    attached_to_ref: str | None = None,
) -> str:
    """Edits an existing BPMN diagram.
    action: 'add' or 'remove'
    element_type: e.g., 'startEvent', 'endEvent', 'task', 'userTask', 'exclusiveGateway', 'sequenceFlow'
    element_id: Unique ID for the element.
    element_name: Display name.
    source_ref/target_ref: Required if element_type is 'sequenceFlow'.
    event_definition: Optional semantic subtype for events. Accepted values:
        'error', 'message', 'signal', 'terminate', 'timer',
        'escalation', 'compensation', 'conditional', 'link', 'cancel'.
        When provided, the corresponding child definition element
        (e.g. <bpmn:errorEventDefinition>) is added inside the event node.
    attached_to_ref: Required for 'boundaryEvent'. The ID of the task or
        sub-process the boundary event is attached to. Sets the
        'attachedToRef' attribute in the BPMN model.
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

        # Validate event_definition usage
        if event_definition is not None:
            if element_type not in _EVENT_TYPES:
                return (
                    f"Error: event_definition is only valid for event elements "
                    f"({', '.join(sorted(_EVENT_TYPES))}), got '{element_type}'."
                )
            if event_definition not in _EVENT_DEFINITION_MAP:
                valid = ", ".join(sorted(_EVENT_DEFINITION_MAP))
                return f"Error: Unknown event_definition '{event_definition}'. Valid values: {valid}."

        # Validate attached_to_ref (boundaryEvent only)
        if attached_to_ref is not None:
            if element_type != "boundaryEvent":
                return "Error: attached_to_ref is only valid for boundaryEvent elements."
            # Verify the target element exists
            if process.find(f".//*[@id='{attached_to_ref}']") is None:
                return f"Error: attached_to_ref '{attached_to_ref}' not found in process."
            attribs["attachedToRef"] = attached_to_ref

        new_elem = ET.SubElement(process, f"{{{BPMN_NS}}}{element_type}", attribs)

        # Add the semantic subtype child node (e.g. <bpmn:errorEventDefinition>)
        if event_definition is not None:
            def_tag = _EVENT_DEFINITION_MAP[event_definition]
            def_id = f"{element_id}_def"
            ET.SubElement(new_elem, f"{{{BPMN_NS}}}{def_tag}", {"id": def_id})

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
                shape_attribs: dict[str, str] = {
                    "id": f"{element_id}_di",
                    "bpmnElement": element_id,
                }
                # bpmn.io needs isMarkerVisible="true" to render the subtype
                # marker on intermediate events that carry a definition.
                if event_definition is not None and element_type in (
                    "intermediateThrowEvent", "intermediateCatchEvent", "boundaryEvent"
                ):
                    shape_attribs["isMarkerVisible"] = "true"

                shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", shape_attribs)
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
    
    # Check sequence flows, including flows inside nested containers like subProcess.
    flows = process.findall(f".//{{{BPMN_NS}}}sequenceFlow")

    # Collect IDs from all nested BPMN elements so sourceRef/targetRef can point
    # to valid nodes declared inside subProcess and other nested structures.
    all_elements = {
        elem.get("id")
        for elem in process.findall(".//*[@id]")
        if elem.tag != f"{{{BPMN_NS}}}sequenceFlow"
    }
    
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

@mcp.tool()
def update_label_bounds(file_path: str, element_id: str, x: int, y: int, width: int, height: int) -> str:
    """Updates the visual boundaries (coordinates and size) of an element label."""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    di_element = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{element_id}']")
    if di_element is None:
        di_element = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='{element_id}']")

    if di_element is None:
        # Fallback to loop if xpath fails due to namespaces
        for shape in root.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
            if shape.get("bpmnElement") == element_id:
                di_element = shape
                break

    if di_element is None:
        for edge in root.findall(f".//{{{BPMNDI_NS}}}BPMNEdge"):
            if edge.get("bpmnElement") == element_id:
                di_element = edge
                break

    if di_element is None:
        return f"Error: DI element for '{element_id}' not found."

    label = di_element.find(f"{{{BPMNDI_NS}}}BPMNLabel")
    if label is None:
        label = ET.SubElement(di_element, f"{{{BPMNDI_NS}}}BPMNLabel")

    bounds = label.find(f"{{{DC_NS}}}Bounds")
    if bounds is None:
        bounds = ET.SubElement(label, f"{{{DC_NS}}}Bounds")

    bounds.set("x", str(x))
    bounds.set("y", str(y))
    bounds.set("width", str(width))
    bounds.set("height", str(height))

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return f"Updated label bounds for '{element_id}': x={x}, y={y}, w={width}, h={height}."

@mcp.tool()
def list_bpmn_elements(file_path: str) -> str:
    """Returns a JSON string listing all elements in the BPMN diagram and their properties."""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        return "Error: No process found in BPMN XML."

    elements = []
    # Iterate over all children of the process
    for elem in process:
        # Strip the namespace from the tag to get the type
        tag = elem.tag
        if tag.startswith(f"{{{BPMN_NS}}}"):
            elem_type = tag.replace(f"{{{BPMN_NS}}}", "")
        else:
            elem_type = tag
            
        elem_data = {
            "id": elem.get("id"),
            "type": elem_type,
            "name": elem.get("name")
        }
        
        # Add sequenceFlow specific fields
        if elem_type == "sequenceFlow":
            elem_data["sourceRef"] = elem.get("sourceRef")
            elem_data["targetRef"] = elem.get("targetRef")

        # Expose event definition subtype, e.g. "error", "message", "signal"
        if elem_type in _EVENT_TYPES:
            _def_tag_to_key = {v: k for k, v in _EVENT_DEFINITION_MAP.items()}
            for child in elem:
                child_local = child.tag.replace(f"{{{BPMN_NS}}}", "")
                if child_local in _def_tag_to_key:
                    elem_data["event_definition"] = _def_tag_to_key[child_local]
                    break

        elements.append(elem_data)
        
    return json.dumps(elements, indent=2)

@mcp.tool()
def update_bpmn_element(file_path: str, element_id: str, name: str | None = None) -> str:
    """Updates properties of an existing BPMN element. Currently supports updating the 'name' attribute."""
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    process = root.find(f".//{{{BPMN_NS}}}process")
    if process is None:
        return "Error: No process found in BPMN XML."

    elem_to_update = None
    for elem in process:
        if elem.get("id") == element_id:
            elem_to_update = elem
            break
            
    if elem_to_update is None:
        return f"Error: Element with id '{element_id}' not found in process."
        
    updates = []
    if name is not None:
        elem_to_update.set("name", name)
        updates.append(f"name='{name}'")
        
    if not updates:
        return "No updates provided."

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return f"Updated element '{element_id}': {', '.join(updates)}."

@mcp.tool()
def add_bpmn_sequence(file_path: str, elements: list[dict]) -> str:
    """Adds a sequence of BPMN elements connected by sequence flows.
    'elements' is a list of dicts.
    
    Required fields per dict:
      - 'id' (str): Unique identifier for the element.
      - 'type' (str): The BPMN type (e.g. 'task', 'startEvent', 'exclusiveGateway').
      
    Optional fields per dict:
      - 'name' (str): The display name/label for the shape.
      - 'source_ref' (str): Anchors the sequence to an existing element ID.
      - 'edge_name' (str): The display name/label for the incoming sequence flow (edge).
      - 'event_definition' (str): e.g., 'message', 'timer', 'error' (for events).
      
    Sequence flows (edges) between consecutive elements in the list are created automatically.
    Automatically calculates layout Y based on sibling branches, preventing overlap.
    Updates existing elements without duplicating.
    """
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    process = root.find(f".//{{{BPMN_NS}}}process")
    plane = root.find(f".//{{{BPMNDI_NS}}}BPMNPlane")
    if process is None or plane is None:
        return "Error: No process or plane found in BPMN XML."

    def get_bounds(ref_id):
        for shape in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
            if shape.get("bpmnElement") == ref_id:
                b = shape.find(f"{{{DC_NS}}}Bounds")
                if b is not None:
                    return float(b.get("x", 0)), float(b.get("y", 0)), float(b.get("width", 0)), float(b.get("height", 0))
        return None

    msg_log = []
    prev_id = None
    
    for i, elem_data in enumerate(elements):
        el_id = elem_data.get("id")
        el_type = elem_data.get("type")
        if not el_id or not el_type:
            msg_log.append(f"Skipping element at index {i} due to missing id or type.")
            continue

        # Check if exists
        existing_el = process.find(f".//*[@id='{el_id}']")
        if existing_el is not None:
            # Upsert attributes
            if "name" in elem_data:
                existing_el.set("name", elem_data["name"])
            msg_log.append(f"Updated existing element '{el_id}'.")
        else:
            # Create new element
            attribs = {"id": el_id}
            if "name" in elem_data:
                attribs["name"] = elem_data["name"]

            new_elem = ET.SubElement(process, f"{{{BPMN_NS}}}{el_type}", attribs)
            
            ev_def = elem_data.get("event_definition")
            if ev_def and ev_def in _EVENT_DEFINITION_MAP:
                def_tag = _EVENT_DEFINITION_MAP[ev_def]
                ET.SubElement(new_elem, f"{{{BPMN_NS}}}{def_tag}", {"id": f"{el_id}_def"})

            shape_attribs = {"id": f"{el_id}_di", "bpmnElement": el_id}
            if ev_def and el_type in ("intermediateThrowEvent", "intermediateCatchEvent", "boundaryEvent"):
                shape_attribs["isMarkerVisible"] = "true"
            
            shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", shape_attribs)
            
            # Layout logic
            width = 36.0 if "Event" in el_type else 100.0
            height = 36.0 if "Event" in el_type else 80.0
            
            # Determine source for layout
            layout_source_id = prev_id if i > 0 else elem_data.get("source_ref")
            
            x_pos = 100.0
            y_pos = 100.0 if "Event" in el_type else 78.0
            
            if layout_source_id:
                s_bounds = get_bounds(layout_source_id)
                if s_bounds:
                    sx, sy, sw, sh = s_bounds
                    x_pos = sx + sw + 50.0
                    
                    # Check siblings
                    sibling_ids = [flow.get("targetRef") for flow in process.findall(f".//{{{BPMN_NS}}}sequenceFlow") if flow.get("sourceRef") == layout_source_id]
                    # Filter out self
                    sibling_ids = [sid for sid in sibling_ids if sid and sid != el_id]
                    
                    max_bottom = None
                    for sid in sibling_ids:
                        sb = get_bounds(sid)
                        if sb:
                            bottom = sb[1] + sb[3]
                            if max_bottom is None or bottom > max_bottom:
                                max_bottom = bottom
                    
                    if max_bottom is not None:
                        y_pos = max_bottom + 20.0
                    else:
                        y_pos = sy + (sh / 2.0) - (height / 2.0)
            else:
                # No source, put at the end
                shapes = plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape")
                x_pos = 100.0 + (max(len(shapes) - 1, 0)) * 150.0
                
            ET.SubElement(shape, f"{{{DC_NS}}}Bounds", {
                "x": str(int(x_pos)), "y": str(int(y_pos)), "width": str(int(width)), "height": str(int(height))
            })
            msg_log.append(f"Added element '{el_id}' at ({int(x_pos)}, {int(y_pos)}).")

        # Auto-connect
        # If there's a prev_id (from previous loop iteration), connect prev_id -> el_id
        # If it's the first element and has a source_ref, connect source_ref -> el_id
        conn_source = prev_id if (i > 0 and prev_id) else (elem_data.get("source_ref") if i == 0 else None)
        
        if conn_source:
            # Check if flow exists
            flow_exists = False
            for flow in process.findall(f".//{{{BPMN_NS}}}sequenceFlow"):
                if flow.get("sourceRef") == conn_source and flow.get("targetRef") == el_id:
                    flow_exists = True
                    break
            
            if not flow_exists:
                flow_id = f"Flow_{conn_source}_to_{el_id}"
                flow_attribs = {"id": flow_id, "sourceRef": conn_source, "targetRef": el_id}
                if "edge_name" in elem_data:
                    flow_attribs["name"] = elem_data["edge_name"]
                    
                ET.SubElement(process, f"{{{BPMN_NS}}}sequenceFlow", flow_attribs)
                
                edge = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNEdge", {
                    "id": f"{flow_id}_di", "bpmnElement": flow_id
                })
                
                s_b = get_bounds(conn_source)
                t_b = get_bounds(el_id)
                if s_b and t_b:
                    sx, sy, sw, sh = s_b
                    tx, ty, tw, th = t_b
                    s_center_x = sx + sw/2
                    s_center_y = sy + sh/2
                    t_center_x = tx + tw/2
                    t_center_y = ty + th/2
                    
                    if t_center_x < s_center_x:
                        # X varies negatively (e.g. Loop) -> Exit bottom, enter bottom
                        start_x = int(s_center_x)
                        start_y = int(sy + sh)
                        end_x = int(t_center_x)
                        end_y = int(ty + th)
                        
                        mid_y = int(max(start_y, end_y) + 30)
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(start_x), "y": str(start_y)})
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(start_x), "y": str(mid_y)})
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(end_x), "y": str(mid_y)})
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(end_x), "y": str(end_y)})
                        
                    elif abs(t_center_y - s_center_y) > 2:
                        # Y varies (Branching up or down)
                        if t_center_y > s_center_y:
                            # Target is below -> Exit bottom, enter left
                            start_x = int(s_center_x)
                            start_y = int(sy + sh)
                        else:
                            # Target is above -> Exit top, enter left
                            start_x = int(s_center_x)
                            start_y = int(sy)
                            
                        end_x = int(tx)
                        end_y = int(t_center_y)
                        
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(start_x), "y": str(start_y)})
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(start_x), "y": str(end_y)})
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(end_x), "y": str(end_y)})
                        
                    else:
                        # Horizontal -> Exit right, enter left
                        start_x = int(sx + sw)
                        start_y = int(s_center_y)
                        end_x = int(tx)
                        end_y = int(t_center_y)
                        
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(start_x), "y": str(start_y)})
                        ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(end_x), "y": str(end_y)})
                msg_log.append(f"Connected '{conn_source}' to '{el_id}'.")
                
        prev_id = el_id
        
    tree.write(path, encoding="utf-8", xml_declaration=True)
    return "\\n".join(msg_log)

@mcp.tool()
def get_sequence_flow_id(file_path: str, source_ref: str, target_ref: str) -> str:
    """Returns the ID of the sequence flow (edge) connecting source_ref to target_ref.
    Useful when you need the ID of an automatically created edge to update its waypoints or labels.
    """
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    for flow in root.findall(f".//{{{BPMN_NS}}}sequenceFlow"):
        if flow.get("sourceRef") == source_ref and flow.get("targetRef") == target_ref:
            flow_id = flow.get("id")
            if flow_id:
                return flow_id
                
    return f"Error: No sequence flow found from '{source_ref}' to '{target_ref}'."

@mcp.resource("manifesto://info")
def get_manifesto() -> str:
    """Returns the MCP server manifesto explaining capabilities and suggested extensions."""
    return """# BPMN MCP Server

**Purpose**: Provides structured tools to read, create, modify, and visually layout BPMN 2.0 XML diagrams (`.bpmn`) without manual XML parsing.

## Best Practices
1. **State Inspection**: Always use `list_bpmn_elements` to inspect the diagram state instead of reading the raw XML file.
2. **Diagram Creation**: Prioritize using `add_bpmn_sequence` for diagram creation and branching. It automatically handles sequenceFlow connections and geometric Y-axis layouts.
"""
