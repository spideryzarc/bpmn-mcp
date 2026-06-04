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
    parent_ref: str | None = None,
    documentation: str | None = None,
) -> str:
    """Edits an existing BPMN diagram by adding or removing a single element.

    action: 'add' or 'remove'.

    element_type: BPMN element type to add. Supported values:
      Flow nodes   — 'startEvent', 'endEvent', 'intermediateThrowEvent',
        'intermediateCatchEvent', 'boundaryEvent', 'task', 'userTask',
        'serviceTask', 'scriptTask', 'manualTask', 'sendTask', 'receiveTask',
        'businessRuleTask', 'callActivity', 'subProcess',
        'exclusiveGateway', 'inclusiveGateway', 'parallelGateway',
        'eventBasedGateway', 'complexGateway'.
      Connections  — 'sequenceFlow', 'association', 'dataInputAssociation',
        'dataOutputAssociation', 'messageFlow'.
      Collaboration — 'participant' (Pool), 'lane' (swim-lane inside a Pool).
      Data          — 'dataObjectReference', 'dataStoreReference'.
      Annotation    — 'textAnnotation'.

    POOL AND LANE ARCHITECTURE — how swimlanes work in BPMN 2.0:
      Always create in this order:
        1. Pool:  element_type='participant', element_id='Pool_1', element_name='My Pool'
        2. Lanes: element_type='lane', element_id='Lane_A', element_name='Sales',
                  parent_ref='Pool_1'   ← parent_ref must be the Pool ID
        3. Elements inside a lane: element_type='task', element_id='Task_1',
                  element_name='Review Order', parent_ref='Lane_A'
                  ← parent_ref is the Lane ID
      BPMN 2.0 rule: flow elements are always XML children of the <process>,
      NOT of the <lane>. The lane lists which elements belong to it via
      <flowNodeRef> children. This tool adds the <flowNodeRef> automatically
      when parent_ref points to a lane ID.

    element_id: Unique ID for the new element. Must not already exist.
    element_name: Display label shown in the diagram. For 'textAnnotation',
      this sets the annotation text content.

    source_ref / target_ref: Required for 'sequenceFlow', 'association',
      'dataInputAssociation', 'dataOutputAssociation', and 'messageFlow'.

    event_definition: Semantic subtype for event elements. Accepted values:
      'error', 'message', 'signal', 'terminate', 'timer', 'escalation',
      'compensation', 'conditional', 'link', 'cancel'.
      Only valid when element_type is an event type. Adds the corresponding
      child element (e.g. <bpmn:errorEventDefinition>) inside the event node.

    attached_to_ref: Required for 'boundaryEvent'. The ID of the task or
      sub-process the boundary event attaches to.

    parent_ref: The ID of the parent container:
      - For 'lane'      → must be a participant (Pool) ID.
      - For flow nodes  → can be a subProcess ID, participant ID, or lane ID.
        When a lane ID is given, the element is placed in the lane's parent
        process and a <flowNodeRef> is added to the lane automatically.
      - Omit to place the element in the default (first) process.

    documentation: Optional free-text description added as a <documentation>
      child element.
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
        if root.find(f".//*[@id='{element_id}']") is not None:
            return f"Error: Element with id '{element_id}' already exists."

        # Determine parent container
        parent_elem = None
        lane_ref_id = None  # Set when parent_ref points to a lane
        if parent_ref:
            parent_elem = root.find(f".//*[@id='{parent_ref}']")
            if parent_elem is None:
                return (
                    f"Error: Parent '{parent_ref}' not found. "
                    f"Call list_bpmn_elements to see available containers "
                    f"(participants, subProcesses, lanes)."
                )

            # Participant (Pool) → redirect to its linked process
            if parent_elem.tag.endswith("}participant"):
                proc_ref = parent_elem.get("processRef")
                if not proc_ref:
                    proc_ref = f"Process_{parent_ref}"
                    parent_elem.set("processRef", proc_ref)
                linked_proc = root.find(f".//{{{BPMN_NS}}}process[@id='{proc_ref}']")
                if linked_proc is None:
                    linked_proc = ET.Element(f"{{{BPMN_NS}}}process", {"id": proc_ref, "isExecutable": "true"})
                    root.append(linked_proc)
                parent_elem = linked_proc

            # Lane → element goes into the lane's parent process;
            # a <flowNodeRef> will be registered in the lane after creation.
            elif parent_elem.tag.endswith("}lane"):
                lane_ref_id = parent_ref
                lane_process = None
                for proc in root.findall(f".//{{{BPMN_NS}}}process"):
                    if proc.find(f".//{{{BPMN_NS}}}lane[@id='{parent_ref}']") is not None:
                        lane_process = proc
                        break
                if lane_process is None:
                    return (
                        f"Error: Could not find the process containing lane '{parent_ref}'. "
                        f"Call list_bpmn_elements to inspect the diagram structure."
                    )
                parent_elem = lane_process
        else:
            parent_elem = process

        attribs = {"id": element_id}
        if element_name and element_type != "textAnnotation":
            attribs["name"] = element_name
        
        if element_type in ("sequenceFlow", "association"):
            if not source_ref or not target_ref:
                return f"Error: source_ref and target_ref are required for {element_type}."
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

        # Validate attached_to_ref usage
        if attached_to_ref is not None:
            if element_type not in ("boundaryEvent", "dataObjectReference", "dataStoreReference"):
                return "Error: attached_to_ref is only valid for boundaryEvent, dataObjectReference, or dataStoreReference elements."
            # Verify the target element exists
            if root.find(f".//*[@id='{attached_to_ref}']") is None:
                return f"Error: attached_to_ref '{attached_to_ref}' not found."
            # Only boundaryEvent sets the attachedToRef XML attribute
            if element_type == "boundaryEvent":
                attribs["attachedToRef"] = attached_to_ref

        # Place the flow in the same parent as source_ref if not specified
        if element_type in ("sequenceFlow", "association"):
            flow_parent = parent_elem
            if not parent_ref and source_ref:
                for sub in root.findall(f".//{{{BPMN_NS}}}subProcess"):
                    if sub.find(f".//*[@id='{source_ref}']") is not None:
                        flow_parent = sub
                        break
            new_elem = ET.SubElement(flow_parent, f"{{{BPMN_NS}}}{element_type}", attribs)
            
        elif element_type == "dataInputAssociation":
            if not source_ref or not target_ref:
                return "Error: source_ref and target_ref are required for dataInputAssociation."
            assoc_parent = root.find(f".//*[@id='{target_ref}']")
            if assoc_parent is None:
                return f"Error: target_ref task '{target_ref}' not found for dataInputAssociation."
            new_elem = ET.SubElement(assoc_parent, f"{{{BPMN_NS}}}dataInputAssociation", attribs)
            ET.SubElement(new_elem, f"{{{BPMN_NS}}}sourceRef").text = source_ref
            
        elif element_type == "dataOutputAssociation":
            if not source_ref or not target_ref:
                return "Error: source_ref and target_ref are required for dataOutputAssociation."
            assoc_parent = root.find(f".//*[@id='{source_ref}']")
            if assoc_parent is None:
                return f"Error: source_ref task '{source_ref}' not found for dataOutputAssociation."
            new_elem = ET.SubElement(assoc_parent, f"{{{BPMN_NS}}}dataOutputAssociation", attribs)
            ET.SubElement(new_elem, f"{{{BPMN_NS}}}targetRef").text = target_ref
            
        elif element_type == "messageFlow":
            if not source_ref or not target_ref:
                return "Error: source_ref and target_ref are required for messageFlow."
            collaboration = root.find(f".//{{{BPMN_NS}}}collaboration")
            if collaboration is None:
                return "Error: Collaboration must exist before adding a messageFlow."
            attribs["sourceRef"] = source_ref
            attribs["targetRef"] = target_ref
            new_elem = ET.SubElement(collaboration, f"{{{BPMN_NS}}}messageFlow", attribs)
            
        elif element_type == "participant":
            collaboration = root.find(f".//{{{BPMN_NS}}}collaboration")
            if collaboration is None:
                collaboration = ET.Element(f"{{{BPMN_NS}}}collaboration", {"id": "Collaboration_1"})
                root.insert(0, collaboration)
                plane = root.find(f".//{{{BPMNDI_NS}}}BPMNPlane")
                if plane is not None:
                    plane.set("bpmnElement", "Collaboration_1")
            
            proc_ref = f"Process_{element_id}"
            
            existing_processes = root.findall(f".//{{{BPMN_NS}}}process")
            if len(existing_processes) == 1 and not collaboration.findall(f".//{{{BPMN_NS}}}participant"):
                linked_proc = existing_processes[0]
                proc_ref = linked_proc.get("id")
                if element_name:
                    linked_proc.set("name", element_name)
            else:
                linked_proc = root.find(f".//{{{BPMN_NS}}}process[@id='{proc_ref}']")
                if linked_proc is None:
                    linked_proc = ET.Element(f"{{{BPMN_NS}}}process", {"id": proc_ref, "isExecutable": "true"})
                    if element_name:
                        linked_proc.set("name", element_name)
                    root.append(linked_proc)
            
            attribs["processRef"] = proc_ref
            new_elem = ET.SubElement(collaboration, f"{{{BPMN_NS}}}participant", attribs)

        elif element_type == "lane":
            # Lanes live inside a <laneSet> within the process.
            # parent_elem was already redirected to the correct process above (via participant parent_ref).
            lane_set = parent_elem.find(f"{{{BPMN_NS}}}laneSet")
            if lane_set is None:
                lane_set_id = f"LaneSet_{parent_elem.get('id', 'default')}"
                lane_set = ET.Element(f"{{{BPMN_NS}}}laneSet", {"id": lane_set_id})
                parent_elem.insert(0, lane_set)
            new_elem = ET.SubElement(lane_set, f"{{{BPMN_NS}}}lane", attribs)

        else:
            if element_type == "dataObjectReference":
                logical_id = f"DataObject_{element_id}"
                ET.SubElement(parent_elem, f"{{{BPMN_NS}}}dataObject", {"id": logical_id})
                attribs["dataObjectRef"] = logical_id
                
            elif element_type == "dataStoreReference":
                logical_id = f"DataStore_{element_id}"
                ET.SubElement(root, f"{{{BPMN_NS}}}dataStore", {"id": logical_id, "name": element_name or ""})
                attribs["dataStoreRef"] = logical_id
                
            new_elem = ET.SubElement(parent_elem, f"{{{BPMN_NS}}}{element_type}", attribs)

        # Handle textAnnotation text node
        if element_type == "textAnnotation":
            text_elem = ET.SubElement(new_elem, f"{{{BPMN_NS}}}text")
            text_elem.text = element_name or ""

        # Handle documentation element
        if documentation is not None:
            doc_elem = ET.SubElement(new_elem, f"{{{BPMN_NS}}}documentation")
            doc_elem.text = documentation

        # Add the semantic subtype child node (e.g. <bpmn:errorEventDefinition>)
        if event_definition is not None:
            def_tag = _EVENT_DEFINITION_MAP[event_definition]
            def_id = f"{element_id}_def"
            ET.SubElement(new_elem, f"{{{BPMN_NS}}}{def_tag}", {"id": def_id})

        # Register the new element as a member of its lane via <flowNodeRef>.
        # This is the correct BPMN 2.0 way to associate a flow node with a lane.
        if lane_ref_id and element_type not in (
            "sequenceFlow", "association", "dataInputAssociation",
            "dataOutputAssociation", "messageFlow", "lane",
        ):
            _lane_elem = root.find(f".//{{{BPMN_NS}}}lane[@id='{lane_ref_id}']")
            if _lane_elem is not None:
                _fnr = ET.SubElement(_lane_elem, f"{{{BPMN_NS}}}flowNodeRef")
                _fnr.text = element_id

        # Add DI information for visualizers
        plane = root.find(f".//{{{BPMNDI_NS}}}BPMNPlane")
        if plane is not None:
            if element_type in ("sequenceFlow", "association", "dataInputAssociation", "dataOutputAssociation", "messageFlow"):
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
                    if element_type in ("dataInputAssociation", "dataOutputAssociation", "messageFlow"):
                        # If source is above target, exit bottom of source and enter top of target
                        if sy < ty:
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(sx + sw/2)), "y": str(int(sy + sh))})
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(tx + tw/2)), "y": str(int(ty))})
                        else:
                            # Exit top of source and enter bottom of target
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(sx + sw/2)), "y": str(int(sy))})
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(tx + tw/2)), "y": str(int(ty + th))})
                    else:
                        # Connect from right edge of source to left edge of target
                        s_center_y = int(sy + sh/2)
                        t_center_y = int(ty + th/2)
                        if tx > (sx + sw) and abs(s_center_y - t_center_y) > 5:
                            x_mid = int((sx + sw + tx) / 2)
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(sx + sw)), "y": str(s_center_y)})
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(x_mid), "y": str(s_center_y)})
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(x_mid), "y": str(t_center_y)})
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(tx)), "y": str(t_center_y)})
                        else:
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(sx + sw)), "y": str(s_center_y)})
                            ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(int(tx)), "y": str(t_center_y)})
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
                
                if element_type == "subProcess":
                    shape_attribs["isExpanded"] = "true"
                elif element_type in ("participant", "lane"):
                    shape_attribs["isHorizontal"] = "true"

                shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", shape_attribs)
                shapes = plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape")
                
                x_pos = None
                if element_type == "subProcess":
                    width = "250"
                    height = "150"
                    y_pos = "70"
                elif element_type == "textAnnotation":
                    width = "100"
                    height = "80"
                    y_pos = "100"
                elif element_type == "dataObjectReference":
                    width = "36"
                    height = "50"
                    y_pos = "100"
                elif element_type == "dataStoreReference":
                    width = "50"
                    height = "50"
                    y_pos = "100"
                elif element_type == "participant":
                    width = "600"
                    height = "250"
                    x_pos = 100
                    # Count existing participants
                    existing_participants_di = []
                    for sh in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                        elem_ref = sh.get("bpmnElement")
                        if elem_ref and elem_ref != element_id:
                            collab = root.find(f".//{{{BPMN_NS}}}collaboration")
                            if collab is not None:
                                part = collab.find(f".//{{{BPMN_NS}}}participant[@id='{elem_ref}']")
                                if part is not None:
                                    existing_participants_di.append(sh)
                    y_pos = str(100 + len(existing_participants_di) * 300)
                elif element_type == "lane":
                    # Auto-position lane inside its participant pool.
                    # parent_ref is the participant ID (the original argument value).
                    width = "570"
                    height = "150"
                    x_pos = 130
                    y_pos = "100"
                    if parent_ref:
                        _part_shape_di = None
                        for _s in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                            if _s.get("bpmnElement") == parent_ref:
                                _part_shape_di = _s
                                break
                        if _part_shape_di is not None:
                            _pb = _part_shape_di.find(f"{{{DC_NS}}}Bounds")
                            if _pb is not None:
                                _px = float(_pb.get("x", 100))
                                _py = float(_pb.get("y", 100))
                                _pw = float(_pb.get("width", 600))
                                # Lane starts after the 30px pool-name header
                                x_pos = int(_px + 30)
                                width = str(int(_pw - 30))
                                # Stack new lane below existing lanes
                                _part_el = root.find(f".//{{{BPMN_NS}}}participant[@id='{parent_ref}']")
                                _proc_id = _part_el.get("processRef") if _part_el is not None else None
                                lane_bottom = _py
                                if _proc_id:
                                    _proc_el = root.find(f".//{{{BPMN_NS}}}process[@id='{_proc_id}']")
                                    if _proc_el is not None:
                                        _lset = _proc_el.find(f"{{{BPMN_NS}}}laneSet")
                                        if _lset is not None:
                                            for _xl in _lset.findall(f"{{{BPMN_NS}}}lane"):
                                                if _xl.get("id") == element_id:
                                                    continue
                                                _xl_s = None
                                                for _s2 in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                                                    if _s2.get("bpmnElement") == _xl.get("id"):
                                                        _xl_s = _s2
                                                        break
                                                if _xl_s is not None:
                                                    _xlb = _xl_s.find(f"{{{DC_NS}}}Bounds")
                                                    if _xlb is not None:
                                                        _bottom = float(_xlb.get("y", _py)) + float(_xlb.get("height", 150))
                                                        lane_bottom = max(lane_bottom, _bottom)
                                y_pos = str(int(lane_bottom))
                else:
                    if "Gateway" in element_type:
                        width = "50"
                        height = "50"
                        y_pos = "93"
                    elif "Event" in element_type:
                        width = "36"
                        height = "36"
                        y_pos = "100"
                    else:
                        width = "100"
                        height = "80"
                        y_pos = "78"
                
                # Default position
                if x_pos is None:
                    x_pos = 100 + (len(shapes) - 1) * 150
                
                # If we have parent_ref, adjust visual position to be inside the parent.
                # Skip for 'lane' — its position was already computed in the lane size block.
                if parent_ref and element_type != "lane":
                    p_shape = plane.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{parent_ref}']")
                    if p_shape is not None:
                        collab = root.find(f".//{{{BPMN_NS}}}collaboration")
                        is_part = False
                        if collab is not None:
                            is_part = collab.find(f".//{{{BPMN_NS}}}participant[@id='{parent_ref}']") is not None
                        # True when parent_ref was a lane (lane_ref_id tracks this)
                        is_lane_parent = (lane_ref_id is not None)

                        pb = p_shape.find(f"{{{DC_NS}}}Bounds")
                        if pb is not None:
                            px, py, pw, ph = float(pb.get("x")), float(pb.get("y")), float(pb.get("width")), float(pb.get("height"))
                            if is_part:
                                shapes_in_pool = 0
                                for other_sh in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                                    ob = other_sh.find(f"{{{DC_NS}}}Bounds")
                                    if ob is not None:
                                        ox = float(ob.get("x", 0))
                                        oy = float(ob.get("y", 0))
                                        if (px <= ox <= px + pw) and (py <= oy <= py + ph) and (other_sh.get("bpmnElement") != element_id) and (other_sh.get("bpmnElement") != parent_ref):
                                            shapes_in_pool += 1
                                x_pos = int(px + 80 + (shapes_in_pool * 150))
                                y_pos = str(int(py + (ph / 2) - (float(height) / 2)))
                            elif is_lane_parent:
                                # Count elements already registered in this lane
                                shapes_in_lane = 0
                                _lane_node = root.find(f".//{{{BPMN_NS}}}lane[@id='{lane_ref_id}']")
                                if _lane_node is not None:
                                    for _fnr in _lane_node.findall(f"{{{BPMN_NS}}}flowNodeRef"):
                                        if _fnr.text and _fnr.text != element_id:
                                            shapes_in_lane += 1
                                x_pos = int(px + 50 + (shapes_in_lane * 150))
                                y_pos = str(int(py + (ph / 2) - (float(height) / 2)))
                            else:
                                x_pos = int(px + 20)
                                y_pos = str(int(py + (ph / 2) - (float(height) / 2)))
                # If we have attached_to_ref for data elements, position them centered horizontally below the referenced element
                elif attached_to_ref and element_type in ("dataObjectReference", "dataStoreReference"):
                    p_shape = plane.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{attached_to_ref}']")
                    if p_shape is not None:
                        pb = p_shape.find(f"{{{DC_NS}}}Bounds")
                        if pb is not None:
                            px, py, pw, ph = float(pb.get("x")), float(pb.get("y")), float(pb.get("width")), float(pb.get("height"))
                            x_pos = int(px + (pw / 2) - (float(width) / 2))
                            y_pos = str(int(py + ph + 80))

                # Check and resolve collisions with already positioned elements
                existing_bounds = []
                for other_shape in plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                    other_ref = other_shape.get("bpmnElement")
                    if not other_ref or other_ref == element_id:
                        continue
                    # Containers like participants (pools) and subProcesses should not cause collisions for nested elements
                    other_elem = root.find(f".//*[@id='{other_ref}']")
                    if other_elem is not None:
                        other_type = other_elem.tag.replace(f"{{{BPMN_NS}}}", "")
                        if other_type in ("participant", "subProcess", "lane"):
                            continue
                    b = other_shape.find(f"{{{DC_NS}}}Bounds")
                    if b is not None:
                        existing_bounds.append((
                            float(b.get("x", 0)),
                            float(b.get("y", 0)),
                            float(b.get("width", 0)),
                            float(b.get("height", 0))
                        ))
                
                curr_x = float(x_pos)
                curr_y = float(y_pos)
                curr_w = float(width)
                curr_h = float(height)
                
                collision_resolved = False
                while not collision_resolved:
                    collision_found = False
                    for (ox, oy, ow, oh) in existing_bounds:
                        if (curr_x < ox + ow) and (ox < curr_x + curr_w) and (curr_y < oy + oh) and (oy < curr_y + curr_h):
                            curr_x = ox + ow + 50.0
                            collision_found = True
                            break
                    if not collision_found:
                        collision_resolved = True
                
                x_pos = str(int(curr_x))
                y_pos = str(int(curr_y))

                ET.SubElement(shape, f"{{{DC_NS}}}Bounds", {
                    "x": str(x_pos), "y": str(y_pos), "width": width, "height": height
                })

        msg = f"Added {element_type} with id '{element_id}'."

    elif action == "remove":
        # Find parent and element
        parent_elem = None
        elem_to_remove = None
        for parent in root.findall(".//"):
            for child in parent:
                if child.get("id") == element_id:
                    parent_elem = parent
                    elem_to_remove = child
                    break
            if elem_to_remove is not None:
                break
        
        if elem_to_remove is None or parent_elem is None:
            return f"Error: Element with id '{element_id}' not found."
        
        parent_elem.remove(elem_to_remove)
        msg = f"Removed element with id '{element_id}'."
    else:
        return f"Error: Invalid action '{action}'. Must be 'add' or 'remove'."

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return msg

@mcp.tool()
def validate_bpmn_diagram(file_path: str) -> str:
    """Performs basic validation on the BPMN XML structure, including multiple processes, collaborations, sequence flows, and message flows."""
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
    
    processes = root.findall(f".//{{{BPMN_NS}}}process")
    if not processes:
        return "Validation Error: No process found."

    issues = []
    
    # Check sequence flows, associations and data associations across all processes
    flows = []
    associations = []
    data_inputs = []
    data_outputs = []
    
    for proc in processes:
        flows.extend(proc.findall(f".//{{{BPMN_NS}}}sequenceFlow"))
        associations.extend(proc.findall(f".//{{{BPMN_NS}}}association"))
        data_inputs.extend(proc.findall(f".//{{{BPMN_NS}}}dataInputAssociation"))
        data_outputs.extend(proc.findall(f".//{{{BPMN_NS}}}dataOutputAssociation"))

    # Also validate message flows inside collaboration
    message_flows = []
    collab = root.find(f".//{{{BPMN_NS}}}collaboration")
    if collab is not None:
        message_flows = collab.findall(f".//{{{BPMN_NS}}}messageFlow")

    # Collect IDs from all elements across all processes and collaborations
    all_elements = set()
    for elem in root.findall(".//*[@id]"):
        tag_name = elem.tag.replace(f"{{{BPMN_NS}}}", "")
        if tag_name not in ("sequenceFlow", "association", "dataInputAssociation", "dataOutputAssociation", "messageFlow"):
            all_elements.add(elem.get("id"))
    
    for connection in list(flows) + list(associations):
        source = connection.get("sourceRef")
        target = connection.get("targetRef")
        cid = connection.get("id")
        tag_name = connection.tag.replace(f"{{{BPMN_NS}}}", "")
        if not source or not target:
            issues.append(f"{tag_name} {cid} missing sourceRef or targetRef.")
        if source and source not in all_elements:
            issues.append(f"{tag_name} {cid} references unknown sourceRef '{source}'.")
        if target and target not in all_elements:
            issues.append(f"{tag_name} {cid} references unknown targetRef '{target}'.")

    for connection in list(data_inputs) + list(data_outputs):
        cid = connection.get("id")
        tag_name = connection.tag.replace(f"{{{BPMN_NS}}}", "")
        
        # Find parent task ID:
        parent_id = None
        for parent in root.findall(".//"):
            if connection in parent:
                parent_id = parent.get("id")
                break
        
        source_node = connection.find(f"{{{BPMN_NS}}}sourceRef")
        target_node = connection.find(f"{{{BPMN_NS}}}targetRef")
        
        source = source_node.text if source_node is not None else (parent_id if tag_name == "dataOutputAssociation" else None)
        target = target_node.text if target_node is not None else (parent_id if tag_name == "dataInputAssociation" else None)
        
        if not source or not target:
            issues.append(f"{tag_name} {cid} missing sourceRef or targetRef mapping.")
        if source and source not in all_elements:
            issues.append(f"{tag_name} {cid} references unknown sourceRef '{source}'.")
        if target and target not in all_elements:
            issues.append(f"{tag_name} {cid} references unknown targetRef '{target}'.")

    for connection in message_flows:
        source = connection.get("sourceRef")
        target = connection.get("targetRef")
        cid = connection.get("id")
        if not source or not target:
            issues.append(f"messageFlow {cid} missing sourceRef or targetRef.")
        if source and source not in all_elements:
            issues.append(f"messageFlow {cid} references unknown sourceRef '{source}'.")
        if target and target not in all_elements:
            issues.append(f"messageFlow {cid} references unknown targetRef '{target}'.")

    if issues:
        return "Validation failed with issues:\n" + "\n".join(issues)
    
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
def batch_update_visuals(
    file_path: str,
    shapes: list[dict] | None = None,
    edges: list[dict] | None = None
) -> str:
    """Updates visual coordinates (bounds and waypoints) for multiple shapes and edges in a single batch.
    shapes: List of dicts, e.g., [{"id": "Task_1", "x": 100, "y": 200, "width": 100, "height": 80}]
    edges: List of dicts, e.g., [{"id": "Flow_1", "waypoints": [{"x": 100, "y": 100}, {"x": 200, "y": 100}]}]
    """
    path = _resolve_path(file_path)
    if not path.exists():
        return f"Error: File {path} does not exist."
    try:
        tree = ET.parse(path)
        root = tree.getroot()
    except Exception as e:
        return f"Error parsing XML: {e}"

    shapes_updated = 0
    edges_updated = 0

    if shapes:
        for s_data in shapes:
            el_id = s_data.get("id")
            if not el_id:
                continue
            x = s_data.get("x")
            y = s_data.get("y")
            w = s_data.get("width")
            h = s_data.get("height")
            if x is None or y is None or w is None or h is None:
                continue
            
            shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{el_id}']")
            if shape is None:
                for s in root.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                    if s.get("bpmnElement") == el_id:
                        shape = s
                        break
            if shape is not None:
                bounds = shape.find(f"{{{DC_NS}}}Bounds")
                if bounds is None:
                    bounds = ET.SubElement(shape, f"{{{DC_NS}}}Bounds")
                bounds.set("x", str(x))
                bounds.set("y", str(y))
                bounds.set("width", str(w))
                bounds.set("height", str(h))
                shapes_updated += 1

    if edges:
        for e_data in edges:
            el_id = e_data.get("id")
            wps = e_data.get("waypoints")
            if not el_id or wps is None:
                continue
            
            edge = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='{el_id}']")
            if edge is None:
                for e in root.findall(f".//{{{BPMNDI_NS}}}BPMNEdge"):
                    if e.get("bpmnElement") == el_id:
                        edge = e
                        break
            if edge is not None:
                existing = edge.findall(f"{{{DI_NS}}}waypoint")
                for wp in existing:
                    edge.remove(wp)
                for wp in wps:
                    ET.SubElement(edge, f"{{{DI_NS}}}waypoint", {"x": str(wp["x"]), "y": str(wp["y"])})
                edges_updated += 1

    tree.write(path, encoding="utf-8", xml_declaration=True)
    return f"Batch update complete: {shapes_updated} shapes and {edges_updated} edges successfully updated visually."

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

    elements = []
    
    # Iterate over collaboration elements (participants and message flows)
    collab = root.find(f".//{{{BPMN_NS}}}collaboration")
    if collab is not None:
        for elem in collab:
            tag = elem.tag
            elem_type = tag.replace(f"{{{BPMN_NS}}}", "") if tag.startswith(f"{{{BPMN_NS}}}") else tag
            if elem_type in ("participant", "messageFlow"):
                elem_data = {
                    "id": elem.get("id"),
                    "type": elem_type,
                    "name": elem.get("name")
                }
                if elem_type == "participant":
                    elem_data["processRef"] = elem.get("processRef")
                elif elem_type == "messageFlow":
                    elem_data["sourceRef"] = elem.get("sourceRef")
                    elem_data["targetRef"] = elem.get("targetRef")
                elements.append(elem_data)

    # Iterate over all processes
    processes = root.findall(f".//{{{BPMN_NS}}}process")
    for process in processes:
        for elem in process.iter():
            if elem == process:
                continue
            tag = elem.tag
            if tag.startswith(f"{{{BPMN_NS}}}"):
                elem_type = tag.replace(f"{{{BPMN_NS}}}", "")
            else:
                elem_type = tag
                
            # Exclude internal/structural child elements from the flat list
            if elem_type in (
                "definitions", "text", "documentation", "waypoint", "Bounds",
                "incoming", "outgoing", "dataObject", "sourceRef", "targetRef",
                "laneSet", "flowNodeRef",
            ) or elem_type.endswith("EventDefinition"):
                continue

            elem_data = {
                "id": elem.get("id"),
                "type": elem_type,
                "name": elem.get("name")
            }
            
            # If it's a textAnnotation, the name/content resides in <bpmn:text>
            if elem_type == "textAnnotation":
                text_elem = elem.find(f"{{{BPMN_NS}}}text")
                elem_data["name"] = text_elem.text if text_elem is not None else ""

            # For lanes, expose which element IDs belong to this lane
            if elem_type == "lane":
                elem_data["flowNodeRefs"] = [
                    r.text for r in elem.findall(f"{{{BPMN_NS}}}flowNodeRef") if r.text
                ]

            # Extract documentation if present
            doc_elem = elem.find(f"{{{BPMN_NS}}}documentation")
            if doc_elem is not None:
                elem_data["documentation"] = doc_elem.text
            
            # Add connection specific fields
            if elem_type in ("sequenceFlow", "association"):
                elem_data["sourceRef"] = elem.get("sourceRef")
                elem_data["targetRef"] = elem.get("targetRef")
            elif elem_type in ("dataInputAssociation", "dataOutputAssociation"):
                # Find parent task ID:
                parent_id = None
                for parent in process.iter():
                    if elem in parent:
                        parent_id = parent.get("id")
                        break
                
                source_node = elem.find(f"{{{BPMN_NS}}}sourceRef")
                target_node = elem.find(f"{{{BPMN_NS}}}targetRef")
                
                elem_data["sourceRef"] = source_node.text if source_node is not None else (parent_id if elem_type == "dataOutputAssociation" else None)
                elem_data["targetRef"] = target_node.text if target_node is not None else (parent_id if elem_type == "dataInputAssociation" else None)

            # Expose event definition subtype, e.g. "error", "message", "signal"
            if elem_type in _EVENT_TYPES:
                _def_tag_to_key = {v: k for k, v in _EVENT_DEFINITION_MAP.items()}
                for child in elem:
                    child_local = child.tag.replace(f"{{{BPMN_NS}}}", "")
                    if child_local in _def_tag_to_key:
                        elem_data["event_definition"] = _def_tag_to_key[child_local]
                        break

            elements.append(elem_data)

    # Resolve visual coordinates (DI bounds, waypoints, and labels) for all elements
    for elem_data in elements:
        el_id = elem_data.get("id")
        if not el_id:
            continue
        
        # Check if it is a Shape in DI
        shape_di = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{el_id}']")
        if shape_di is None:
            # Fallback to loop if xpath fails
            for s in root.findall(f".//{{{BPMNDI_NS}}}BPMNShape"):
                if s.get("bpmnElement") == el_id:
                    shape_di = s
                    break
        
        if shape_di is not None:
            bounds = shape_di.find(f"{{{DC_NS}}}Bounds")
            if bounds is not None:
                elem_data["x"] = int(float(bounds.get("x", 0)))
                elem_data["y"] = int(float(bounds.get("y", 0)))
                elem_data["width"] = int(float(bounds.get("width", 0)))
                elem_data["height"] = int(float(bounds.get("height", 0)))
            
            # Check for label bounds
            label = shape_di.find(f"{{{BPMNDI_NS}}}BPMNLabel")
            if label is not None:
                l_bounds = label.find(f"{{{DC_NS}}}Bounds")
                if l_bounds is not None:
                    elem_data["label_x"] = int(float(l_bounds.get("x", 0)))
                    elem_data["label_y"] = int(float(l_bounds.get("y", 0)))
                    elem_data["label_width"] = int(float(l_bounds.get("width", 0)))
                    elem_data["label_height"] = int(float(l_bounds.get("height", 0)))
        else:
            # Check if it is an Edge/Flow in DI
            edge_di = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='{el_id}']")
            if edge_di is None:
                for e in root.findall(f".//{{{BPMNDI_NS}}}BPMNEdge"):
                    if e.get("bpmnElement") == el_id:
                        edge_di = e
                        break
            
            if edge_di is not None:
                waypoints = []
                for wp in edge_di.findall(f"{{{DI_NS}}}waypoint"):
                    waypoints.append({
                        "x": int(float(wp.get("x", 0))),
                        "y": int(float(wp.get("y", 0)))
                    })
                if waypoints:
                    elem_data["waypoints"] = waypoints
                
                # Check for label bounds
                label = edge_di.find(f"{{{BPMNDI_NS}}}BPMNLabel")
                if label is not None:
                    l_bounds = label.find(f"{{{DC_NS}}}Bounds")
                    if l_bounds is not None:
                        elem_data["label_x"] = int(float(l_bounds.get("x", 0)))
                        elem_data["label_y"] = int(float(l_bounds.get("y", 0)))
                        elem_data["label_width"] = int(float(l_bounds.get("width", 0)))
                        elem_data["label_height"] = int(float(l_bounds.get("height", 0)))
        
    return json.dumps(elements, indent=2)

@mcp.tool()
def update_bpmn_element(
    file_path: str,
    element_id: str,
    name: str | None = None,
    documentation: str | None = None,
) -> str:
    """Updates properties of an existing BPMN element.
    Currently supports updating the 'name' attribute (or text content for textAnnotation)
    and the 'documentation' element.
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
    if process is None:
        return "Error: No process found in BPMN XML."

    elem_to_update = None
    for elem in process.iter():
        if elem.get("id") == element_id:
            elem_to_update = elem
            break
            
    if elem_to_update is None:
        return f"Error: Element with id '{element_id}' not found in process."
        
    updates = []
    if name is not None:
        tag = elem_to_update.tag
        elem_type = tag.replace(f"{{{BPMN_NS}}}", "") if tag.startswith(f"{{{BPMN_NS}}}") else tag
        if elem_type == "textAnnotation":
            text_elem = elem_to_update.find(f"{{{BPMN_NS}}}text")
            if text_elem is None:
                text_elem = ET.SubElement(elem_to_update, f"{{{BPMN_NS}}}text")
            text_elem.text = name
            updates.append(f"text='{name}'")
        else:
            elem_to_update.set("name", name)
            updates.append(f"name='{name}'")

    if documentation is not None:
        doc_elem = elem_to_update.find(f"{{{BPMN_NS}}}documentation")
        if doc_elem is None:
            doc_elem = ET.Element(f"{{{BPMN_NS}}}documentation")
            elem_to_update.insert(0, doc_elem)
        doc_elem.text = documentation
        updates.append(f"documentation='{documentation}'")
        
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
      - 'parent_ref' (str): The ID of the parent container (e.g., a subProcess) to place the element inside.
      - 'lane_ref' (str): The ID of an existing lane to register this element in.
        The element is added to the lane's parent process and a <flowNodeRef> is
        appended to the lane. Lanes must be created first with
        edit_bpmn_diagram(element_type='lane', ...).

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
                tag = existing_el.tag
                elem_type = tag.replace(f"{{{BPMN_NS}}}", "") if tag.startswith(f"{{{BPMN_NS}}}") else tag
                if elem_type == "textAnnotation":
                    text_elem = existing_el.find(f"{{{BPMN_NS}}}text")
                    if text_elem is None:
                        text_elem = ET.SubElement(existing_el, f"{{{BPMN_NS}}}text")
                    text_elem.text = elem_data["name"]
                else:
                    existing_el.set("name", elem_data["name"])
            if "documentation" in elem_data:
                doc_elem = existing_el.find(f"{{{BPMN_NS}}}documentation")
                if doc_elem is None:
                    doc_elem = ET.Element(f"{{{BPMN_NS}}}documentation")
                    existing_el.insert(0, doc_elem)
                doc_elem.text = elem_data["documentation"]
            msg_log.append(f"Updated existing element '{el_id}'.")
        else:
            # Determine parent container
            parent_ref = elem_data.get("parent_ref")
            parent_elem = process
            if parent_ref:
                parent_elem = process.find(f".//*[@id='{parent_ref}']")
                if parent_elem is None:
                    return f"Error: Parent element '{parent_ref}' not found in process."

            # Create new element
            attribs = {"id": el_id}
            if "name" in elem_data and el_type != "textAnnotation":
                attribs["name"] = elem_data["name"]

            new_elem = ET.SubElement(parent_elem, f"{{{BPMN_NS}}}{el_type}", attribs)
            
            if el_type == "textAnnotation":
                text_elem = ET.SubElement(new_elem, f"{{{BPMN_NS}}}text")
                text_elem.text = elem_data.get("name", "")

            if "documentation" in elem_data:
                doc_elem = ET.SubElement(new_elem, f"{{{BPMN_NS}}}documentation")
                doc_elem.text = elem_data["documentation"]
            
            ev_def = elem_data.get("event_definition")
            if ev_def and ev_def in _EVENT_DEFINITION_MAP:
                def_tag = _EVENT_DEFINITION_MAP[ev_def]
                ET.SubElement(new_elem, f"{{{BPMN_NS}}}{def_tag}", {"id": f"{el_id}_def"})

            shape_attribs = {"id": f"{el_id}_di", "bpmnElement": el_id}
            if ev_def and el_type in ("intermediateThrowEvent", "intermediateCatchEvent", "boundaryEvent"):
                shape_attribs["isMarkerVisible"] = "true"
            
            if el_type == "subProcess":
                shape_attribs["isExpanded"] = "true"

            shape = ET.SubElement(plane, f"{{{BPMNDI_NS}}}BPMNShape", shape_attribs)
            
            # Layout logic
            if el_type == "subProcess":
                width = 250.0
                height = 150.0
            elif el_type == "textAnnotation":
                width = 100.0
                height = 80.0
            else:
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
            elif parent_ref:
                p_bounds = get_bounds(parent_ref)
                if p_bounds:
                    px, py, pw, ph = p_bounds
                    x_pos = px + 20.0
                    y_pos = py + (ph / 2.0) - (height / 2.0)
            else:
                # No source, put at the end
                shapes = plane.findall(f".//{{{BPMNDI_NS}}}BPMNShape")
                x_pos = 100.0 + (max(len(shapes) - 1, 0)) * 150.0
                if el_type == "subProcess":
                    y_pos = 70.0
                
            ET.SubElement(shape, f"{{{DC_NS}}}Bounds", {
                "x": str(int(x_pos)), "y": str(int(y_pos)), "width": str(int(width)), "height": str(int(height))
            })
            msg_log.append(f"Added element '{el_id}' at ({int(x_pos)}, {int(y_pos)}).")

        # Register element in its lane if lane_ref is specified
        _lane_ref = elem_data.get("lane_ref")
        if _lane_ref and el_type not in ("sequenceFlow", "association"):
            _lane_el = None
            for _proc in root.findall(f".//{{{BPMN_NS}}}process"):
                _found = _proc.find(f".//{{{BPMN_NS}}}lane[@id='{_lane_ref}']")
                if _found is not None:
                    _lane_el = _found
                    break
            if _lane_el is None:
                return (
                    f"Error: Lane '{_lane_ref}' not found. "
                    f"Create it first with edit_bpmn_diagram(element_type='lane', ...)."
                )
            _existing_refs = [r.text for r in _lane_el.findall(f"{{{BPMN_NS}}}flowNodeRef")]
            if el_id not in _existing_refs:
                _fnr = ET.SubElement(_lane_el, f"{{{BPMN_NS}}}flowNodeRef")
                _fnr.text = el_id

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
                
                # Determine parent container for the sequenceFlow
                flow_parent = process
                for sub in process.findall(f".//{{{BPMN_NS}}}subProcess"):
                    if sub.find(f".//*[@id='{el_id}']") is not None:
                        flow_parent = sub
                        break
                    
                ET.SubElement(flow_parent, f"{{{BPMN_NS}}}sequenceFlow", flow_attribs)
                
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
    return "\n".join(msg_log)

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

## Purpose
Provides structured tools to read, create, modify, and visually lay out BPMN 2.0 XML
diagrams (`.bpmn`) without manual XML parsing.

## Available Tools
| Tool | What it does |
|------|--------------|
| `create_bpmn_diagram` | Creates an empty BPMN file with a default process |
| `edit_bpmn_diagram` | Adds or removes a single element (task, event, gateway, lane, pool, …) |
| `add_bpmn_sequence` | Adds a list of elements and auto-connects them with sequence flows |
| `list_bpmn_elements` | Returns all elements with IDs, types, names, bounds, and lane membership |
| `validate_bpmn_diagram` | Validates sequence/message flows and element references |
| `update_bpmn_element` | Renames an element or updates its documentation |
| `update_shape_bounds` | Moves/resizes a single shape |
| `update_edge_waypoints` | Repositions the waypoints of a sequence flow edge |
| `update_label_bounds` | Repositions the label of a shape or edge |
| `batch_update_visuals` | Updates bounds/waypoints for many elements in one call |
| `get_sequence_flow_id` | Looks up the auto-generated ID of a sequence flow edge |

## Best Practices
1. **Inspect first** — call `list_bpmn_elements` to understand the current structure
   before editing. Never read the raw XML file.
2. **Prefer `add_bpmn_sequence`** for building linear flows and branches — it
   auto-creates sequenceFlows and prevents shape overlap with Y-axis layout.
3. **Use `edit_bpmn_diagram`** for single elements: pools, lanes, gateways, boundary
   events, data objects, text annotations, and message flows.

## Pool and Lane (Swimlane) Workflow
Pools and lanes **must be created in order** before placing elements inside them.

```
Step 1 — Create a Pool (participant):
  edit_bpmn_diagram(element_type='participant', element_id='Pool_A',
                    element_name='Order Fulfillment', file_path='...')

Step 2 — Create lanes inside the pool (parent_ref = Pool ID):
  edit_bpmn_diagram(element_type='lane', element_id='Lane_Sales',
                    element_name='Sales', parent_ref='Pool_A', file_path='...')
  edit_bpmn_diagram(element_type='lane', element_id='Lane_Warehouse',
                    element_name='Warehouse', parent_ref='Pool_A', file_path='...')

Step 3 — Add flow elements inside a lane (parent_ref = Lane ID):
  edit_bpmn_diagram(element_type='startEvent', element_id='Start_1',
                    element_name='Order Received', parent_ref='Lane_Sales', file_path='...')
  edit_bpmn_diagram(element_type='task', element_id='Task_Review',
                    element_name='Review Order', parent_ref='Lane_Sales', file_path='...')
  edit_bpmn_diagram(element_type='task', element_id='Task_Pack',
                    element_name='Pack Items', parent_ref='Lane_Warehouse', file_path='...')

Step 4 — Connect elements with sequenceFlows as usual:
  edit_bpmn_diagram(element_type='sequenceFlow', element_id='Flow_1',
                    source_ref='Start_1', target_ref='Task_Review', file_path='...')
```

### Why parent_ref works differently for pools vs lanes
- **Pool (participant) ID** → the element is placed in the pool's linked process.
- **Lane ID** → the element is still placed in the process (BPMN 2.0 rule: flow nodes
  are always process children, not lane children), AND a `<flowNodeRef>` entry is
  automatically added inside the lane to record membership.
  Call `list_bpmn_elements` after adding elements to verify `flowNodeRefs` lists.

## Multi-Pool Collaboration (Message Flows)
```
1. Create Pool A (reuses the default process automatically if it's the first pool):
   edit_bpmn_diagram(element_type='participant', element_id='Pool_A',
                     element_name='Customer', file_path='...')

2. Create Pool B (gets its own new process):
   edit_bpmn_diagram(element_type='participant', element_id='Pool_B',
                     element_name='Supplier', file_path='...')

3. Add elements with parent_ref pointing to the correct pool.

4. Connect across pools with messageFlow (NOT sequenceFlow):
   edit_bpmn_diagram(element_type='messageFlow', element_id='MF_1',
                     source_ref='Task_InPoolA', target_ref='Task_InPoolB', file_path='...')
```
"""
