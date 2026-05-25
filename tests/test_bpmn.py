import os
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path
from bpmn_mcp.server import (
    create_bpmn_diagram,
    edit_bpmn_diagram,
    validate_bpmn_diagram,
    update_shape_bounds,
    update_edge_waypoints,
    update_label_bounds,
    list_bpmn_elements,
    update_bpmn_element
)

def test_bpmn_lifecycle():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "test.bpmn")
        # 1. Create Diagram
    res_create = create_bpmn_diagram("Process_1", "Test Process", bpmn_path)
    assert "Created basic BPMN diagram" in res_create
    assert os.path.exists(bpmn_path)
    
    # 2. Validate empty diagram
    res_val1 = validate_bpmn_diagram(bpmn_path)
    assert "Basic validation passed." in res_val1
    
    # 3. Add Start Event
    res_edit1 = edit_bpmn_diagram(
        file_path=bpmn_path,
        action="add",
        element_type="startEvent",
        element_id="StartEvent_1",
        element_name="Start"
    )
    assert "Added startEvent" in res_edit1
    
    # 4. Add End Event
    res_edit2 = edit_bpmn_diagram(
        file_path=bpmn_path,
        action="add",
        element_type="endEvent",
        element_id="EndEvent_1",
        element_name="End"
    )
    assert "Added endEvent" in res_edit2
    
    # 5. Add Sequence Flow
    res_edit3 = edit_bpmn_diagram(
        file_path=bpmn_path,
        action="add",
        element_type="sequenceFlow",
        element_id="Flow_1",
        source_ref="StartEvent_1",
        target_ref="EndEvent_1"
    )
    assert "Added sequenceFlow" in res_edit3
    
    # 6. Validate modified diagram
    res_val2 = validate_bpmn_diagram(bpmn_path)
    assert "Basic validation passed." in res_val2
    
    # 7. List elements (JSON)
    res_list = list_bpmn_elements(bpmn_path)
    assert "StartEvent_1" in res_list
    assert "EndEvent_1" in res_list
    assert "Flow_1" in res_list

    # 8. Update element
    res_update = update_bpmn_element(bpmn_path, "StartEvent_1", name="New Start Name")
    assert "Updated element" in res_update
    assert "name='New Start Name'" in res_update

    res_list_updated = list_bpmn_elements(bpmn_path)
    assert "New Start Name" in res_list_updated

def test_complex_bpmn_lifecycle():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "complex_test.bpmn")
    
    # Create Diagram
    create_bpmn_diagram("Complex_Process", "Complex Process", bpmn_path)
    
    # Add Nodes
    edit_bpmn_diagram(bpmn_path, "add", "startEvent", "Start_1", "Start")
    edit_bpmn_diagram(bpmn_path, "add", "exclusiveGateway", "Gateway_1", "Decision")
    edit_bpmn_diagram(bpmn_path, "add", "task", "Task_A", "Path A")
    edit_bpmn_diagram(bpmn_path, "add", "task", "Task_B", "Path B")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_1", "End")
    
    # Add Flows
    edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", "Flow_S_G", source_ref="Start_1", target_ref="Gateway_1")
    edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", "Flow_G_A", source_ref="Gateway_1", target_ref="Task_A")
    edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", "Flow_G_B", source_ref="Gateway_1", target_ref="Task_B")
    edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", "Flow_A_E", source_ref="Task_A", target_ref="End_1")
    edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", "Flow_B_E", source_ref="Task_B", target_ref="End_1")
    
    # Validate
    res_val = validate_bpmn_diagram(bpmn_path)
    assert "Basic validation passed." in res_val
    
    # Use the tools to layout the diagram beautifully (proving the LLM tools work)
    # Start: center (118, 118)
    update_shape_bounds(bpmn_path, "Start_1", x=100, y=100, width=36, height=36)
    
    # Gateway: center (225, 118). Top is (225, 93). Bottom is (225, 143). Right is (250, 118).
    update_shape_bounds(bpmn_path, "Gateway_1", x=200, y=93, width=50, height=50)
    
    # Task A (Top branch)
    update_shape_bounds(bpmn_path, "Task_A", x=350, y=40, width=100, height=80)
    
    # Task B (Bottom branch)
    update_shape_bounds(bpmn_path, "Task_B", x=350, y=180, width=100, height=80)
    
    # End Event: center (568, 118) to align horizontally with Start/Gateway
    update_shape_bounds(bpmn_path, "End_1", x=550, y=100, width=36, height=36)
    
    # Layout Edges with orthogonal waypoints
    # Start to Gateway
    update_edge_waypoints(bpmn_path, "Flow_S_G", [{"x": 136, "y": 118}, {"x": 200, "y": 118}])
    
    # Gateway to Task A (up then right)
    update_edge_waypoints(bpmn_path, "Flow_G_A", [{"x": 225, "y": 93}, {"x": 225, "y": 80}, {"x": 350, "y": 80}])
    
    # Gateway to Task B (down then right)
    update_edge_waypoints(bpmn_path, "Flow_G_B", [{"x": 225, "y": 143}, {"x": 225, "y": 220}, {"x": 350, "y": 220}])
    
    # Task A to End (right then down)
    update_edge_waypoints(bpmn_path, "Flow_A_E", [{"x": 450, "y": 80}, {"x": 500, "y": 80}, {"x": 500, "y": 118}, {"x": 550, "y": 118}])
    
    # Task B to End (right then up)
    update_edge_waypoints(bpmn_path, "Flow_B_E", [{"x": 450, "y": 220}, {"x": 500, "y": 220}, {"x": 500, "y": 118}, {"x": 550, "y": 118}])
    
    # List elements (JSON) and check
    res_list = list_bpmn_elements(bpmn_path)
    assert "exclusiveGateway" in res_list
    assert "Gateway_1" in res_list
    assert "Flow_B_E" in res_list

def test_update_label_bounds_for_shape_and_edge():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "labels_test.bpmn")

    create_bpmn_diagram("Label_Process", "Label Process", bpmn_path)
    edit_bpmn_diagram(bpmn_path, "add", "task", "Task_1", "Task")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_1", "End")
    edit_bpmn_diagram(
        bpmn_path,
        "add",
        "sequenceFlow",
        "Flow_1",
        source_ref="Task_1",
        target_ref="End_1"
    )

    shape_result = update_label_bounds(bpmn_path, "Task_1", x=120, y=40, width=100, height=20)
    edge_result = update_label_bounds(bpmn_path, "Flow_1", x=250, y=95, width=70, height=18)

    assert "Updated label bounds for 'Task_1'" in shape_result
    assert "Updated label bounds for 'Flow_1'" in edge_result

    tree = ET.parse(bpmn_path)
    root = tree.getroot()
    ns = {
        "bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI",
        "dc": "http://www.omg.org/spec/DD/20100524/DC"
    }

    task_shape = root.find(".//bpmndi:BPMNShape[@bpmnElement='Task_1']", ns)
    assert task_shape is not None
    task_label_bounds = task_shape.find("bpmndi:BPMNLabel/dc:Bounds", ns)
    assert task_label_bounds is not None
    assert task_label_bounds.get("x") == "120"
    assert task_label_bounds.get("y") == "40"
    assert task_label_bounds.get("width") == "100"
    assert task_label_bounds.get("height") == "20"

    flow_edge = root.find(".//bpmndi:BPMNEdge[@bpmnElement='Flow_1']", ns)
    assert flow_edge is not None
    flow_label_bounds = flow_edge.find("bpmndi:BPMNLabel/dc:Bounds", ns)
    assert flow_label_bounds is not None
    assert flow_label_bounds.get("x") == "250"
    assert flow_label_bounds.get("y") == "95"
    assert flow_label_bounds.get("width") == "70"
    assert flow_label_bounds.get("height") == "18"


def test_validate_bpmn_with_nested_subprocess_is_valid():
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = output_dir / "subprocess_complete_valid.bpmn"

    bpmn_xml = """<?xml version="1.0" encoding="UTF-8"?>
<bpmn:definitions xmlns:bpmn="http://www.omg.org/spec/BPMN/20100524/MODEL"
                                    xmlns:bpmndi="http://www.omg.org/spec/BPMN/20100524/DI"
                                    xmlns:dc="http://www.omg.org/spec/DD/20100524/DC"
                                    xmlns:di="http://www.omg.org/spec/DD/20100524/DI"
                                    id="Defs_Subprocess"
                                    targetNamespace="http://bpmn.io/schema/bpmn">
    <bpmn:process id="Process_Subprocess" name="Process With SubProcess" isExecutable="true">
        <bpmn:startEvent id="Start_Main" name="Start" />
        <bpmn:subProcess id="Sub_1" name="Approval Subprocess">
            <bpmn:startEvent id="Start_Sub" name="Sub Start" />
            <bpmn:task id="Task_Sub" name="Review" />
            <bpmn:endEvent id="End_Sub" name="Sub End" />
            <bpmn:sequenceFlow id="Flow_Sub_1" sourceRef="Start_Sub" targetRef="Task_Sub" />
            <bpmn:sequenceFlow id="Flow_Sub_2" sourceRef="Task_Sub" targetRef="End_Sub" />
        </bpmn:subProcess>
        <bpmn:endEvent id="End_Main" name="End" />
        <bpmn:sequenceFlow id="Flow_Main_1" sourceRef="Start_Main" targetRef="Sub_1" />
        <bpmn:sequenceFlow id="Flow_Main_2" sourceRef="Sub_1" targetRef="End_Main" />
    </bpmn:process>
    <bpmndi:BPMNDiagram id="BPMNDiagram_1">
        <bpmndi:BPMNPlane id="BPMNPlane_1" bpmnElement="Process_Subprocess">
            <bpmndi:BPMNShape id="Start_Main_di" bpmnElement="Start_Main">
                <dc:Bounds x="100" y="130" width="36" height="36" />
            </bpmndi:BPMNShape>
            <bpmndi:BPMNShape id="Sub_1_di" bpmnElement="Sub_1" isExpanded="true">
                <dc:Bounds x="180" y="70" width="280" height="180" />
            </bpmndi:BPMNShape>
            <bpmndi:BPMNShape id="End_Main_di" bpmnElement="End_Main">
                <dc:Bounds x="520" y="130" width="36" height="36" />
            </bpmndi:BPMNShape>
            <bpmndi:BPMNEdge id="Flow_Main_1_di" bpmnElement="Flow_Main_1">
                <di:waypoint x="136" y="148" />
                <di:waypoint x="180" y="148" />
            </bpmndi:BPMNEdge>
            <bpmndi:BPMNEdge id="Flow_Main_2_di" bpmnElement="Flow_Main_2">
                <di:waypoint x="460" y="148" />
                <di:waypoint x="520" y="148" />
            </bpmndi:BPMNEdge>
        </bpmndi:BPMNPlane>
    </bpmndi:BPMNDiagram>
</bpmn:definitions>
"""

    bpmn_path.write_text(bpmn_xml, encoding="utf-8")

    res_val = validate_bpmn_diagram(str(bpmn_path))
    assert "Basic validation passed." in res_val
