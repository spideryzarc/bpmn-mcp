import os
import xml.etree.ElementTree as ET
from pathlib import Path
import pytest
from bpmn_mcp.server import create_bpmn_diagram, add_bpmn_sequence, list_bpmn_elements, get_sequence_flow_id

BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

def get_bounds(root, elem_id):
    shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{elem_id}']")
    assert shape is not None, f"BPMNShape for '{elem_id}' not found"
    b = shape.find(f"{{{DC_NS}}}Bounds")
    assert b is not None, f"Bounds missing on shape '{elem_id}'"
    return {k: int(float(b.get(k))) for k in ("x", "y", "width", "height")}

def test_add_bpmn_sequence_linear():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "linear_test.bpmn")
    
    # 1. Create diagram
    res_create = create_bpmn_diagram("Process_Linear", "Linear Test Process", bpmn_path)
    assert "Created basic BPMN diagram" in res_create
    assert os.path.exists(bpmn_path)

    # 2. Add linear sequence with edge labels (edge_name)
    elements = [
        {"id": "Start_1", "type": "startEvent", "name": "Start"},
        {"id": "Task_1", "type": "task", "name": "First Task", "edge_name": "Starts workflow"},
        {"id": "End_1", "type": "endEvent", "name": "End", "edge_name": "Completes workflow"}
    ]
    res_seq = add_bpmn_sequence(bpmn_path, elements)
    assert "Added element 'Start_1'" in res_seq
    assert "Added element 'Task_1'" in res_seq
    assert "Added element 'End_1'" in res_seq
    assert "Connected 'Start_1' to 'Task_1'" in res_seq
    assert "Connected 'Task_1' to 'End_1'" in res_seq

    # 3. Parse and verify XML Structure
    tree = ET.parse(bpmn_path)
    root = tree.getroot()

    # Verify elements exist
    assert root.find(f".//{{{BPMN_NS}}}startEvent[@id='Start_1']") is not None
    assert root.find(f".//{{{BPMN_NS}}}task[@id='Task_1']") is not None
    assert root.find(f".//{{{BPMN_NS}}}endEvent[@id='End_1']") is not None

    # Verify sequence flows & names (labels)
    flow1 = root.find(f".//{{{BPMN_NS}}}sequenceFlow[@id='Flow_Start_1_to_Task_1']")
    assert flow1 is not None
    assert flow1.get("sourceRef") == "Start_1"
    assert flow1.get("targetRef") == "Task_1"
    assert flow1.get("name") == "Starts workflow"

    flow2 = root.find(f".//{{{BPMN_NS}}}sequenceFlow[@id='Flow_Task_1_to_End_1']")
    assert flow2 is not None
    assert flow2.get("sourceRef") == "Task_1"
    assert flow2.get("targetRef") == "End_1"
    assert flow2.get("name") == "Completes workflow"

    # Verify coordinates (linear spacing)
    b_start = get_bounds(root, "Start_1")
    b_task = get_bounds(root, "Task_1")
    b_end = get_bounds(root, "End_1")

    # Start_1 is at (100, 100) with size 36x36
    assert b_start == {"x": 100, "y": 100, "width": 36, "height": 36}

    # Task_1 x is sx + sw + 50 = 100 + 36 + 50 = 186
    # Task_1 y centers with Start_1: sy + sh/2 - th/2 = 100 + 18 - 40 = 78
    assert b_task == {"x": 186, "y": 78, "width": 100, "height": 80}

    # End_1 x is tx + tw + 50 = 186 + 100 + 50 = 336
    # End_1 y centers with Task_1: ty + th/2 - eh/2 = 78 + 40 - 18 = 100
    assert b_end == {"x": 336, "y": 100, "width": 36, "height": 36}


def test_add_bpmn_sequence_branching_and_smart_layout():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "branching_test.bpmn")
    create_bpmn_diagram("Process_Branching", "Branching Process", bpmn_path)

    # 1. Add linear sequence to gateway
    add_bpmn_sequence(bpmn_path, [
        {"id": "Start_1", "type": "startEvent", "name": "Start"},
        {"id": "Gateway_1", "type": "exclusiveGateway", "name": "Decision"}
    ])

    # 2. Add Branch 1 with label
    res_b1 = add_bpmn_sequence(bpmn_path, [
        {"id": "Task_B1", "type": "task", "name": "Branch 1", "source_ref": "Gateway_1", "edge_name": "Yes"},
        {"id": "End_1", "type": "endEvent", "name": "End 1"}
    ])
    assert "Added element 'Task_B1'" in res_b1
    assert "Connected 'Gateway_1' to 'Task_B1'" in res_b1

    # 3. Add Branch 2 with label
    res_b2 = add_bpmn_sequence(bpmn_path, [
        {"id": "Task_B2", "type": "task", "name": "Branch 2", "source_ref": "Gateway_1", "edge_name": "No"},
        {"id": "End_2", "type": "endEvent", "name": "End 2"}
    ])
    assert "Added element 'Task_B2'" in res_b2
    assert "Connected 'Gateway_1' to 'Task_B2'" in res_b2

    # 4. Parse and verify Y coordinates and edge labels
    tree = ET.parse(bpmn_path)
    root = tree.getroot()

    b_gw = get_bounds(root, "Gateway_1")
    b_b1 = get_bounds(root, "Task_B1")
    b_b2 = get_bounds(root, "Task_B2")

    # Gateway_1 bounds: sx=186, sy=78, sw=100, sh=80
    assert b_gw == {"x": 186, "y": 78, "width": 100, "height": 80}

    # Task_B1 (Branch 1): centers with Gateway_1
    # x = 186 + 100 + 50 = 336
    # y = sy + sh/2 - th/2 = 78 + 40 - 40 = 78
    assert b_b1 == {"x": 336, "y": 78, "width": 100, "height": 80}

    # Task_B2 (Branch 2): sibling Task_B1 exists (bottom = y + h = 78 + 80 = 158)
    # x = 336
    # y = 158 + 20 = 178
    assert b_b2 == {"x": 336, "y": 178, "width": 100, "height": 80}

    # Verify edge names (labels)
    flow_b1 = root.find(f".//{{{BPMN_NS}}}sequenceFlow[@id='Flow_Gateway_1_to_Task_B1']")
    assert flow_b1 is not None
    assert flow_b1.get("name") == "Yes"

    flow_b2 = root.find(f".//{{{BPMN_NS}}}sequenceFlow[@id='Flow_Gateway_1_to_Task_B2']")
    assert flow_b2 is not None
    assert flow_b2.get("name") == "No"

    # Verify End_2 centers with Task_B2
    # x = 336 + 100 + 50 = 486
    # y = ty + th/2 - eh/2 = 178 + 40 - 18 = 200
    b_end2 = get_bounds(root, "End_2")
    assert b_end2 == {"x": 486, "y": 200, "width": 36, "height": 36}


def test_add_bpmn_sequence_upsert_and_loop():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "loop_test.bpmn")
    create_bpmn_diagram("Process_Loop", "Loop Process", bpmn_path)

    # 1. Create a linear path
    add_bpmn_sequence(bpmn_path, [
        {"id": "Start_1", "type": "startEvent", "name": "Start"},
        {"id": "Task_1", "type": "task", "name": "Main Task"},
        {"id": "Gateway_1", "type": "exclusiveGateway", "name": "Decision"}
    ])

    # 2. Add branch 1
    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_B1", "type": "task", "name": "Branch 1", "source_ref": "Gateway_1"}
    ])

    # 3. Create a loop: Branch 2 from Gateway_1 back to Task_1 (which already exists)
    res_loop = add_bpmn_sequence(bpmn_path, [
        {"id": "Task_B2", "type": "task", "name": "Branch 2 (Loop)", "source_ref": "Gateway_1", "edge_name": "Retry"},
        {"id": "Task_1", "type": "task", "name": "Main Task (Updated)", "edge_name": "Back to start"}  # Refers to existing ID!
    ])

    assert "Updated existing element 'Task_1'" in res_loop
    assert "Connected 'Task_B2' to 'Task_1'" in res_loop

    # Verify XML
    tree = ET.parse(bpmn_path)
    root = tree.getroot()

    # Check there is ONLY ONE Task_1 element
    tasks = root.findall(f".//{{{BPMN_NS}}}task[@id='Task_1']")
    assert len(tasks) == 1
    assert tasks[0].get("name") == "Main Task (Updated)"

    # Check BPMN plane has only one BPMNShape for Task_1
    shapes = root.findall(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Task_1']")
    assert len(shapes) == 1

    # Check connection from Task_B2 to Task_1 exists and has label
    loop_flow = root.find(f".//{{{BPMN_NS}}}sequenceFlow[@sourceRef='Task_B2'][@targetRef='Task_1']")
    assert loop_flow is not None
    assert loop_flow.get("id") == "Flow_Task_B2_to_Task_1"
    assert loop_flow.get("name") == "Back to start"

    # Check connection from Gateway_1 to Task_B2 has label "Retry"
    branch_flow = root.find(f".//{{{BPMN_NS}}}sequenceFlow[@sourceRef='Gateway_1'][@targetRef='Task_B2']")
    assert branch_flow is not None
    assert branch_flow.get("name") == "Retry"


def test_add_bpmn_sequence_error_handling(tmp_path):
    # Non-existent file
    bpmn_path = str(tmp_path / "non_existent.bpmn")
    res = add_bpmn_sequence(bpmn_path, [{"id": "Start_1", "type": "startEvent"}])
    assert "does not exist" in res

    # Invalid XML file
    invalid_path = tmp_path / "invalid.bpmn"
    invalid_path.write_text("invalid xml contents")
    res = add_bpmn_sequence(str(invalid_path), [{"id": "Start_1", "type": "startEvent"}])
    assert "Error parsing XML" in res

    # Missing process or plane
    bad_xml_path = tmp_path / "bad_structure.bpmn"
    bad_xml_path.write_text("<definitions></definitions>")
    res = add_bpmn_sequence(str(bad_xml_path), [{"id": "Start_1", "type": "startEvent"}])
    assert "No process or plane found" in res

    # Missing elements parameters
    ok_path = str(tmp_path / "ok.bpmn")
    create_bpmn_diagram("Process_Ok", "Ok Process", ok_path)
    
    # Missing id or type
    res = add_bpmn_sequence(ok_path, [
        {"id": "Start_1"}, # missing type
        {"type": "startEvent"} # missing id
    ])
    assert "Skipping element at index 0 due to missing id or type." in res
    assert "Skipping element at index 1 due to missing id or type." in res


def test_get_sequence_flow_id(tmp_path):
    bpmn_path = str(tmp_path / "flow_id_test.bpmn")
    create_bpmn_diagram("Process_FlowId", "Flow ID Process", bpmn_path)

    add_bpmn_sequence(bpmn_path, [
        {"id": "Start_1", "type": "startEvent"},
        {"id": "Task_1", "type": "task"},
        {"id": "Gateway_1", "type": "exclusiveGateway"}
    ])

    # Correct retrieval
    assert get_sequence_flow_id(bpmn_path, "Start_1", "Task_1") == "Flow_Start_1_to_Task_1"
    assert get_sequence_flow_id(bpmn_path, "Task_1", "Gateway_1") == "Flow_Task_1_to_Gateway_1"
    
    # Missing retrieval
    res_miss = get_sequence_flow_id(bpmn_path, "Start_1", "Gateway_1")
    assert "Error: No sequence flow found from 'Start_1' to 'Gateway_1'." in res_miss
    
    # File errors
    res_file = get_sequence_flow_id(str(tmp_path / "nope.bpmn"), "A", "B")
    assert "does not exist" in res_file


def test_complex_bpmn_sequence_auto_layout():
    """
    Re-implements the layout of test_complex_bpmn_lifecycle using the
    new add_bpmn_sequence tool to test automatic layout and flow generation.
    """
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "complex_sequence_auto.bpmn")
    
    create_bpmn_diagram("Process_Complex_Auto", "Complex Auto Layout", bpmn_path)

    # Flow A - Main parallel path
    add_bpmn_sequence(bpmn_path, [
        {"id": "Start_Plain", "type": "startEvent", "name": "Start"},
        {"id": "GW_Par_Fork", "type": "parallelGateway", "name": "Fork"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_User", "type": "userTask", "name": "Approve Request", "source_ref": "GW_Par_Fork"},
        {"id": "GW_Par_Join", "type": "parallelGateway", "name": "Join"},
        {"id": "GW_Excl", "type": "exclusiveGateway", "name": "Route"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_Send", "type": "sendTask", "name": "Send Notification", "source_ref": "GW_Par_Fork"},
        {"id": "ICatch_Msg", "type": "intermediateCatchEvent", "name": "Catch Message", "event_definition": "message"},
        {"id": "Task_Receive", "type": "receiveTask", "name": "Receive Callback"},
        {"id": "GW_Par_Join", "type": "parallelGateway"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_Script", "type": "scriptTask", "name": "Transform Data", "source_ref": "GW_Excl"},
        {"id": "End_1", "type": "endEvent", "name": "End"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_Manual", "type": "manualTask", "name": "Manual Review", "source_ref": "GW_Excl"},
        {"id": "IThrow_Sig", "type": "intermediateThrowEvent", "name": "Throw Signal", "event_definition": "signal"},
        {"id": "End_Msg", "type": "endEvent", "name": "Message End", "event_definition": "message"}
    ])

    # Flow B - Inclusive path
    add_bpmn_sequence(bpmn_path, [
        {"id": "Start_Msg", "type": "startEvent", "name": "Message Start", "event_definition": "message"},
        {"id": "Task_Generic", "type": "task", "name": "Generic Task"},
        {"id": "GW_Inc_Fork", "type": "inclusiveGateway", "name": "Inclusive Fork"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_Call", "type": "callActivity", "name": "Call Sub-Process", "source_ref": "GW_Inc_Fork"},
        {"id": "GW_Inc_Join", "type": "inclusiveGateway", "name": "Inclusive Join"},
        {"id": "End_Signal", "type": "endEvent", "name": "Signal End", "event_definition": "signal"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "Task_Service", "type": "serviceTask", "name": "Call External API", "source_ref": "GW_Inc_Fork"},
        {"id": "IThrow_Msg", "type": "intermediateThrowEvent", "name": "Throw Message", "event_definition": "message"},
        {"id": "GW_Inc_Join", "type": "inclusiveGateway"}
    ])

    # Flow C - Event-based + complex gateway
    add_bpmn_sequence(bpmn_path, [
        {"id": "Start_Timer", "type": "startEvent", "name": "Timer Start", "event_definition": "timer"},
        {"id": "GW_Event", "type": "eventBasedGateway", "name": "Event-Based"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "ICatch_Timer", "type": "intermediateCatchEvent", "name": "Wait Timer", "event_definition": "timer", "source_ref": "GW_Event"},
        {"id": "Sub_1", "type": "subProcess", "name": "Embedded Sub-Process"},
        {"id": "GW_Complex", "type": "complexGateway", "name": "Complex"},
        {"id": "End_2", "type": "endEvent", "name": "End (alt)"}
    ])

    add_bpmn_sequence(bpmn_path, [
        {"id": "ICatch_Signal", "type": "intermediateCatchEvent", "name": "Catch Signal", "event_definition": "signal", "source_ref": "GW_Event"},
        {"id": "GW_Complex", "type": "complexGateway"}
    ])

    # Verify elements were added
    elements = list_bpmn_elements(bpmn_path)
    assert "Start_Plain" in elements
    assert "Task_User" in elements
    assert "GW_Inc_Fork" in elements
    assert "Sub_1" in elements
