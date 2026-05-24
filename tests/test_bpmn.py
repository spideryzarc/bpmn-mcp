import os
import tempfile
from pathlib import Path
from bpmn_mcp.server import (
    create_bpmn_diagram,
    edit_bpmn_diagram,
    validate_bpmn_diagram,
    export_bpmn_diagram
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
    
    # 7. Export diagram
    res_export = export_bpmn_diagram(bpmn_path)
    assert "StartEvent_1" in res_export
    assert "EndEvent_1" in res_export
    assert "Flow_1" in res_export
    assert "definitions" in res_export

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
    
    # Export and check elements
    res_export = export_bpmn_diagram(bpmn_path)
    assert "exclusiveGateway" in res_export
    assert "Gateway_1" in res_export
    assert "Flow_B_E" in res_export
