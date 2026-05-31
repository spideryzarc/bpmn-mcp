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
    """Builds a comprehensive BPMN diagram that exercises every supported element type:
    - All task variants (task, userTask, serviceTask, scriptTask, manualTask,
      businessRuleTask, sendTask, receiveTask, callActivity, subProcess)
    - All gateway types (parallel, exclusive, inclusive, eventBased, complex)
    - All event categories (start/intermediate throw/intermediate catch/boundary/end)
      with the main event definition subtypes (plain, message, timer, signal,
      error, terminate)
    - Boundary events with attachedToRef
    Then verifies the full tool lifecycle: validation, layout, rename, list, remove.

    Diagram layout (three independent flows):

    Flow A – Main parallel path (y ≈ 80-200)
      Start_Plain → GW_Par_Fork ⇒ Task_User    ⇒ GW_Par_Join
                               ⇒ Task_Send → ICatch_Msg → Task_Receive ⇒ GW_Par_Join
                  → GW_Excl ⇒ Task_Script → End_1
                            ⇒ Task_Manual → IThrow_Sig → End_Msg
      Boundary: Bnd_Timer (on Task_User) → End_Terminate
                Bnd_Error (on Task_Service) → Task_BRule → End_Error

    Flow B – Inclusive gateway path (y ≈ 300-420)
      Start_Msg → Task_Generic → GW_Inc_Fork ⇒ Task_Call        ⇒ GW_Inc_Join → End_Signal
                                             ⇒ Task_Service → IThrow_Msg ⇒ GW_Inc_Join

    Flow C – Event-based + complex gateway path (y ≈ 500-580)
      Start_Timer → GW_Event ⇒ ICatch_Timer → Sub_1 ⇒ GW_Complex → End_2
                             ⇒ ICatch_Signal          ⇒ GW_Complex
    """
    import json as _json

    BPMN_NS   = "http://www.omg.org/spec/BPMN/20100524/MODEL"
    BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
    DC_NS     = "http://www.omg.org/spec/DD/20100524/DC"
    DI_NS     = "http://www.omg.org/spec/DD/20100524/DI"

    def parse(path):
        return ET.parse(path).getroot()

    def get_bounds(root, elem_id):
        shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='{elem_id}']")
        assert shape is not None, f"BPMNShape for '{elem_id}' not found"
        b = shape.find(f"{{{DC_NS}}}Bounds")
        assert b is not None, f"Bounds missing on shape '{elem_id}'"
        return {k: int(b.get(k)) for k in ("x", "y", "width", "height")}

    def get_waypoints(root, flow_id):
        edge = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='{flow_id}']")
        assert edge is not None, f"BPMNEdge for '{flow_id}' not found"
        return [
            {"x": int(w.get("x")), "y": int(w.get("y"))}
            for w in edge.findall(f"{{{DI_NS}}}waypoint")
        ]

    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "complex_test.bpmn")

    # ── 1. Create diagram ────────────────────────────────────────────────────
    assert "Created basic BPMN diagram" in create_bpmn_diagram(
        "Process_AllComponents", "All BPMN Components Showcase", bpmn_path
    )

    # ── 2. Add every element type ────────────────────────────────────────────

    # Start events – plain / message / timer
    edit_bpmn_diagram(bpmn_path, "add", "startEvent", "Start_Plain",  "Start")
    edit_bpmn_diagram(bpmn_path, "add", "startEvent", "Start_Msg",    "Message Start",  event_definition="message")
    edit_bpmn_diagram(bpmn_path, "add", "startEvent", "Start_Timer",  "Timer Start",    event_definition="timer")

    # All task variants
    edit_bpmn_diagram(bpmn_path, "add", "task",             "Task_Generic", "Generic Task")
    edit_bpmn_diagram(bpmn_path, "add", "userTask",         "Task_User",    "Approve Request")
    edit_bpmn_diagram(bpmn_path, "add", "serviceTask",      "Task_Service", "Call External API")
    edit_bpmn_diagram(bpmn_path, "add", "scriptTask",       "Task_Script",  "Transform Data")
    edit_bpmn_diagram(bpmn_path, "add", "manualTask",       "Task_Manual",  "Manual Review")
    edit_bpmn_diagram(bpmn_path, "add", "businessRuleTask", "Task_BRule",   "Evaluate Rules")
    edit_bpmn_diagram(bpmn_path, "add", "sendTask",         "Task_Send",    "Send Notification")
    edit_bpmn_diagram(bpmn_path, "add", "receiveTask",      "Task_Receive", "Receive Callback")
    edit_bpmn_diagram(bpmn_path, "add", "callActivity",     "Task_Call",    "Call Sub-Process")
    edit_bpmn_diagram(bpmn_path, "add", "subProcess",       "Sub_1",        "Embedded Sub-Process")

    # All gateway types
    edit_bpmn_diagram(bpmn_path, "add", "parallelGateway",   "GW_Par_Fork",  "Fork")
    edit_bpmn_diagram(bpmn_path, "add", "parallelGateway",   "GW_Par_Join",  "Join")
    edit_bpmn_diagram(bpmn_path, "add", "exclusiveGateway",  "GW_Excl",      "Route")
    edit_bpmn_diagram(bpmn_path, "add", "inclusiveGateway",  "GW_Inc_Fork",  "Inclusive Fork")
    edit_bpmn_diagram(bpmn_path, "add", "inclusiveGateway",  "GW_Inc_Join",  "Inclusive Join")
    edit_bpmn_diagram(bpmn_path, "add", "eventBasedGateway", "GW_Event",     "Event-Based")
    edit_bpmn_diagram(bpmn_path, "add", "complexGateway",    "GW_Complex",   "Complex")

    # Intermediate throw events
    edit_bpmn_diagram(bpmn_path, "add", "intermediateThrowEvent", "IThrow_Sig", "Throw Signal",  event_definition="signal")
    edit_bpmn_diagram(bpmn_path, "add", "intermediateThrowEvent", "IThrow_Msg", "Throw Message", event_definition="message")

    # Intermediate catch events
    edit_bpmn_diagram(bpmn_path, "add", "intermediateCatchEvent", "ICatch_Msg",    "Catch Message", event_definition="message")
    edit_bpmn_diagram(bpmn_path, "add", "intermediateCatchEvent", "ICatch_Timer",  "Wait Timer",    event_definition="timer")
    edit_bpmn_diagram(bpmn_path, "add", "intermediateCatchEvent", "ICatch_Signal", "Catch Signal",  event_definition="signal")

    # Boundary events (attached_to_ref required)
    edit_bpmn_diagram(bpmn_path, "add", "boundaryEvent", "Bnd_Timer",
                      element_name="Timeout",  event_definition="timer",
                      attached_to_ref="Task_User")
    edit_bpmn_diagram(bpmn_path, "add", "boundaryEvent", "Bnd_Error",
                      element_name="On Error", event_definition="error",
                      attached_to_ref="Task_Service")

    # End events – plain / error / terminate / signal / message
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_1",         "End")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_Error",     "Error End",    event_definition="error")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_Terminate", "Terminate",    event_definition="terminate")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_Signal",    "Signal End",   event_definition="signal")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_Msg",       "Message End",  event_definition="message")
    edit_bpmn_diagram(bpmn_path, "add", "endEvent", "End_2",         "End (alt)")

    # ── 3. Sequence flows ─────────────────────────────────────────────────────
    flows = [
        # Flow A: main parallel path
        ("FA_1",  "Start_Plain",    "GW_Par_Fork"),
        ("FA_2",  "GW_Par_Fork",    "Task_User"),
        ("FA_3",  "GW_Par_Fork",    "Task_Send"),
        ("FA_4",  "Task_User",      "GW_Par_Join"),
        ("FA_5",  "Task_Send",      "ICatch_Msg"),
        ("FA_6",  "ICatch_Msg",     "Task_Receive"),
        ("FA_7",  "Task_Receive",   "GW_Par_Join"),
        ("FA_8",  "GW_Par_Join",    "GW_Excl"),
        ("FA_9",  "GW_Excl",        "Task_Script"),
        ("FA_10", "GW_Excl",        "Task_Manual"),
        ("FA_11", "Task_Script",    "End_1"),
        ("FA_12", "Task_Manual",    "IThrow_Sig"),
        ("FA_13", "IThrow_Sig",     "End_Msg"),
        # Boundary escalation paths
        ("FB_1",  "Bnd_Timer",      "End_Terminate"),
        ("FB_2",  "Bnd_Error",      "Task_BRule"),
        ("FB_3",  "Task_BRule",     "End_Error"),
        # Flow B: message start + inclusive gateway
        ("FC_1",  "Start_Msg",      "Task_Generic"),
        ("FC_2",  "Task_Generic",   "GW_Inc_Fork"),
        ("FC_3",  "GW_Inc_Fork",    "Task_Call"),
        ("FC_4",  "GW_Inc_Fork",    "Task_Service"),
        ("FC_5",  "Task_Call",      "GW_Inc_Join"),
        ("FC_6",  "Task_Service",   "IThrow_Msg"),
        ("FC_7",  "IThrow_Msg",     "GW_Inc_Join"),
        ("FC_8",  "GW_Inc_Join",    "End_Signal"),
        # Flow C: timer start + event-based + complex gateway
        ("FD_1",  "Start_Timer",    "GW_Event"),
        ("FD_2",  "GW_Event",       "ICatch_Timer"),
        ("FD_3",  "GW_Event",       "ICatch_Signal"),
        ("FD_4",  "ICatch_Timer",   "Sub_1"),
        ("FD_5",  "ICatch_Signal",  "GW_Complex"),
        ("FD_6",  "Sub_1",          "GW_Complex"),
        ("FD_7",  "GW_Complex",     "End_2"),
    ]
    for fid, src, tgt in flows:
        res = edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", fid, source_ref=src, target_ref=tgt)
        assert "Added sequenceFlow" in res, f"Failed adding flow {fid}: {res}"

    # ── 4. Validation must pass ────────────────────────────────────────────────
    assert "Basic validation passed." in validate_bpmn_diagram(bpmn_path)

    # ── 5. Verify key XML structures ──────────────────────────────────────────
    root = parse(bpmn_path)

    # Start event definitions
    assert root.find(f".//{{{BPMN_NS}}}startEvent[@id='Start_Msg']/{{{BPMN_NS}}}messageEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}startEvent[@id='Start_Timer']/{{{BPMN_NS}}}timerEventDefinition") is not None

    # Intermediate events
    assert root.find(f".//{{{BPMN_NS}}}intermediateThrowEvent[@id='IThrow_Sig']/{{{BPMN_NS}}}signalEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}intermediateThrowEvent[@id='IThrow_Msg']/{{{BPMN_NS}}}messageEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}intermediateCatchEvent[@id='ICatch_Msg']/{{{BPMN_NS}}}messageEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}intermediateCatchEvent[@id='ICatch_Timer']/{{{BPMN_NS}}}timerEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}intermediateCatchEvent[@id='ICatch_Signal']/{{{BPMN_NS}}}signalEventDefinition") is not None

    # End event definitions
    assert root.find(f".//{{{BPMN_NS}}}endEvent[@id='End_Error']/{{{BPMN_NS}}}errorEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}endEvent[@id='End_Terminate']/{{{BPMN_NS}}}terminateEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}endEvent[@id='End_Signal']/{{{BPMN_NS}}}signalEventDefinition") is not None
    assert root.find(f".//{{{BPMN_NS}}}endEvent[@id='End_Msg']/{{{BPMN_NS}}}messageEventDefinition") is not None

    # Boundary events: attachedToRef + child definition
    bnd_timer_elem = root.find(f".//{{{BPMN_NS}}}boundaryEvent[@id='Bnd_Timer']")
    assert bnd_timer_elem is not None
    assert bnd_timer_elem.get("attachedToRef") == "Task_User"
    assert bnd_timer_elem.find(f"{{{BPMN_NS}}}timerEventDefinition") is not None

    bnd_error_elem = root.find(f".//{{{BPMN_NS}}}boundaryEvent[@id='Bnd_Error']")
    assert bnd_error_elem is not None
    assert bnd_error_elem.get("attachedToRef") == "Task_Service"
    assert bnd_error_elem.find(f"{{{BPMN_NS}}}errorEventDefinition") is not None

    # ── 6. Layout shapes (all three flow rows) ────────────────────────────────
    layout = {
        # Flow A: top row
        "Start_Plain":   (80,  100,  36,  36),
        "GW_Par_Fork":   (200,  93,  50,  50),
        "Task_User":     (310,  40, 100,  80),
        "Task_Send":     (310, 160, 100,  80),
        "ICatch_Msg":    (460, 173,  36,  36),
        "Task_Receive":  (540, 160, 100,  80),
        "GW_Par_Join":   (700,  93,  50,  50),
        "GW_Excl":       (820,  93,  50,  50),
        "Task_Script":   (930,  40, 100,  80),
        "Task_Manual":   (930, 160, 100,  80),
        "IThrow_Sig":    (1090, 173,  36,  36),
        "End_1":         (1090,  52,  36,  36),
        "End_Msg":       (1190, 173,  36,  36),
        # Boundary escalation paths
        "Bnd_Timer":     (342, 102,  36,  36),
        "End_Terminate": (342, 200,  36,  36),
        "Bnd_Error":     (462, 222,  36,  36),
        "Task_BRule":    (560, 210, 100,  80),
        "End_Error":     (720, 228,  36,  36),
        # Flow B: middle row
        "Start_Msg":     (80,  310,  36,  36),
        "Task_Generic":  (180, 290, 100,  80),
        "GW_Inc_Fork":   (340, 303,  50,  50),
        "Task_Call":     (450, 260, 100,  80),
        "Task_Service":  (450, 370, 100,  80),
        "IThrow_Msg":    (610, 383,  36,  36),
        "GW_Inc_Join":   (710, 303,  50,  50),
        "End_Signal":    (830, 310,  36,  36),
        # Flow C: bottom row
        "Start_Timer":   (80,  510,  36,  36),
        "GW_Event":      (200, 503,  50,  50),
        "ICatch_Timer":  (310, 470,  36,  36),
        "ICatch_Signal": (310, 550,  36,  36),
        "Sub_1":         (410, 450, 120,  80),
        "GW_Complex":    (600, 503,  50,  50),
        "End_2":         (720, 510,  36,  36),
    }
    for eid, (x, y, w, h) in layout.items():
        res = update_shape_bounds(bpmn_path, eid, x=x, y=y, width=w, height=h)
        assert "Updated bounds" in res, f"update_shape_bounds failed for {eid}: {res}"

    # Verify a representative cross-section of persisted bounds
    root = parse(bpmn_path)
    for eid in ("Start_Plain", "GW_Par_Fork", "Task_User", "Bnd_Timer",
                "GW_Inc_Fork", "Sub_1", "GW_Complex"):
        b = get_bounds(root, eid)
        x, y, w, h = layout[eid]
        assert b == {"x": x, "y": y, "width": w, "height": h}, f"Wrong bounds for {eid}: {b}"

    # ── 7. Layout all edges and verify persisted waypoints ────────────────────
    def route_flow(source_id, target_id):
        sx, sy, sw, sh = layout[source_id]
        tx, ty, tw, th = layout[target_id]

        s_center_x = sx + sw / 2
        s_center_y = sy + sh / 2
        t_center_x = tx + tw / 2
        t_center_y = ty + th / 2

        dx = t_center_x - s_center_x
        dy = t_center_y - s_center_y

        # If elements are almost vertically aligned, route top/bottom.
        if abs(dx) < 60:
            if dy >= 0:
                start = {"x": int(s_center_x), "y": int(sy + sh)}
                end = {"x": int(t_center_x), "y": int(ty)}
            else:
                start = {"x": int(s_center_x), "y": int(sy)}
                end = {"x": int(t_center_x), "y": int(ty + th)}

            if abs(start["x"] - end["x"]) <= 10:
                return [start, end]

            mid_y = (start["y"] + end["y"]) // 2
            return [
                start,
                {"x": start["x"], "y": mid_y},
                {"x": end["x"], "y": mid_y},
                end,
            ]

        # Otherwise, route left/right with an optional elbow.
        if dx >= 0:
            start = {"x": int(sx + sw), "y": int(s_center_y)}
            end = {"x": int(tx), "y": int(t_center_y)}
        else:
            start = {"x": int(sx), "y": int(s_center_y)}
            end = {"x": int(tx + tw), "y": int(t_center_y)}

        if abs(start["y"] - end["y"]) <= 20:
            return [start, end]

        mid_x = (start["x"] + end["x"]) // 2
        return [
            start,
            {"x": mid_x, "y": start["y"]},
            {"x": mid_x, "y": end["y"]},
            end,
        ]

    all_edges = {fid: route_flow(src, tgt) for fid, src, tgt in flows}
    for fid, wps in all_edges.items():
        res = update_edge_waypoints(bpmn_path, fid, wps)
        assert "Updated waypoints" in res, f"update_edge_waypoints failed for {fid}: {res}"

    root = parse(bpmn_path)
    for fid, expected_wps in all_edges.items():
        actual = get_waypoints(root, fid)
        assert actual == expected_wps, f"Wrong waypoints for {fid}: {actual}"
        for wp in actual:
            assert 0 <= wp["x"] <= 1400, f"Waypoint x out of range on {fid}: {wp}"
            assert 0 <= wp["y"] <= 700, f"Waypoint y out of range on {fid}: {wp}"

    # ── 8. Rename an element and verify XML ───────────────────────────────────
    res = update_bpmn_element(bpmn_path, "Task_User", name="Review & Approve")
    assert "Updated element" in res
    root = parse(bpmn_path)
    assert root.find(f".//{{{BPMN_NS}}}userTask[@id='Task_User']").get("name") == "Review & Approve"

    # ── 9. list_bpmn_elements: full structural assertions ─────────────────────
    elements = _json.loads(list_bpmn_elements(bpmn_path))
    by_id = {e["id"]: e for e in elements}

    # Every task type
    for eid, expected_type in [
        ("Task_Generic", "task"),
        ("Task_User",    "userTask"),
        ("Task_Service", "serviceTask"),
        ("Task_Script",  "scriptTask"),
        ("Task_Manual",  "manualTask"),
        ("Task_BRule",   "businessRuleTask"),
        ("Task_Send",    "sendTask"),
        ("Task_Receive", "receiveTask"),
        ("Task_Call",    "callActivity"),
        ("Sub_1",        "subProcess"),
    ]:
        assert eid in by_id,                                f"{eid} missing from list"
        assert by_id[eid]["type"] == expected_type,         f"Wrong type for {eid}"

    # Every gateway type
    for eid, expected_type in [
        ("GW_Par_Fork",  "parallelGateway"),
        ("GW_Par_Join",  "parallelGateway"),
        ("GW_Excl",      "exclusiveGateway"),
        ("GW_Inc_Fork",  "inclusiveGateway"),
        ("GW_Inc_Join",  "inclusiveGateway"),
        ("GW_Event",     "eventBasedGateway"),
        ("GW_Complex",   "complexGateway"),
    ]:
        assert by_id[eid]["type"] == expected_type, f"Wrong type for {eid}"

    # Event definitions on all event types
    for eid, expected_def in [
        ("Start_Msg",    "message"),
        ("Start_Timer",  "timer"),
        ("IThrow_Sig",   "signal"),
        ("IThrow_Msg",   "message"),
        ("ICatch_Msg",   "message"),
        ("ICatch_Timer", "timer"),
        ("ICatch_Signal","signal"),
        ("Bnd_Timer",    "timer"),
        ("Bnd_Error",    "error"),
        ("End_Error",    "error"),
        ("End_Terminate","terminate"),
        ("End_Signal",   "signal"),
        ("End_Msg",      "message"),
    ]:
        assert by_id[eid].get("event_definition") == expected_def, \
            f"Wrong event_definition for {eid}: {by_id[eid]}"

    # Plain events have no event_definition key
    for eid in ("Start_Plain", "End_1", "End_2"):
        assert "event_definition" not in by_id[eid], f"Unexpected event_definition on {eid}"

    # Sequence flow refs
    assert by_id["FA_5"]["sourceRef"] == "Task_Send"    and by_id["FA_5"]["targetRef"] == "ICatch_Msg"
    assert by_id["FB_2"]["sourceRef"] == "Bnd_Error"    and by_id["FB_2"]["targetRef"] == "Task_BRule"
    assert by_id["FD_6"]["sourceRef"] == "Sub_1"        and by_id["FD_6"]["targetRef"] == "GW_Complex"

    # ── 10. Error-case rejection ───────────────────────────────────────────────
    # Duplicate ID
    assert "Error" in edit_bpmn_diagram(bpmn_path, "add", "task", "Task_User", "Dup")
    # sequenceFlow without refs
    assert "source_ref" in edit_bpmn_diagram(bpmn_path, "add", "sequenceFlow", "Bad_F").lower()
    # event_definition on a non-event
    assert "event_definition" in edit_bpmn_diagram(bpmn_path, "add", "task", "T_Bad",
                                                    event_definition="error")
    # attached_to_ref on a non-boundary
    assert "attached_to_ref" in edit_bpmn_diagram(bpmn_path, "add", "task", "T_Bad2",
                                                   attached_to_ref="Task_User")
    # attached_to_ref pointing to a non-existent element
    assert "Error" in edit_bpmn_diagram(bpmn_path, "add", "boundaryEvent", "Bad_Bnd",
                                        event_definition="timer",
                                        attached_to_ref="NonExistent")
    # Invalid action
    assert "Error" in edit_bpmn_diagram(bpmn_path, "update", "task", "Task_User")

    # ── 11. Remove element and verify ─────────────────────────────────────────
    res = edit_bpmn_diagram(bpmn_path, "remove", "task", "Task_Generic")
    assert "Removed element" in res
    root = parse(bpmn_path)
    assert root.find(f".//{{{BPMN_NS}}}task[@id='Task_Generic']") is None

    # Remove again must fail gracefully
    assert "Error" in edit_bpmn_diagram(bpmn_path, "remove", "task", "Task_Generic")

    # Clean up dangling flows that referenced the removed element
    edit_bpmn_diagram(bpmn_path, "remove", "sequenceFlow", "FC_1")
    edit_bpmn_diagram(bpmn_path, "remove", "sequenceFlow", "FC_2")

    # ── 12. Final validation still passes ────────────────────────────────────
    assert "Basic validation passed." in validate_bpmn_diagram(bpmn_path)


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


def test_event_definition_end_error():
    """An endEvent with event_definition='error' must contain an errorEventDefinition child."""
    import json
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "event_def_test.bpmn")

    create_bpmn_diagram("Process_EvDef", "Event Def Process", bpmn_path)
    edit_bpmn_diagram(bpmn_path, "add", "startEvent", "Start_1", "Start")
    res = edit_bpmn_diagram(
        bpmn_path, "add", "endEvent", "End_Error",
        element_name="Error End", event_definition="error"
    )
    assert "Added endEvent" in res

    tree = ET.parse(bpmn_path)
    root = tree.getroot()
    BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
    end_event = root.find(f".//{{{BPMN_NS}}}endEvent[@id='End_Error']")
    assert end_event is not None, "endEvent node not found"
    error_def = end_event.find(f"{{{BPMN_NS}}}errorEventDefinition")
    assert error_def is not None, "errorEventDefinition child missing"
    assert error_def.get("id") == "End_Error_def"

    # list_bpmn_elements must report the subtype
    elements = json.loads(list_bpmn_elements(bpmn_path))
    end_data = next(e for e in elements if e["id"] == "End_Error")
    assert end_data["event_definition"] == "error"


def test_event_definition_intermediate_message():
    """An intermediateCatchEvent with event_definition='message' must set isMarkerVisible on its shape."""
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "event_def_intermediate_test.bpmn")

    create_bpmn_diagram("Process_Msg", "Message Process", bpmn_path)
    res = edit_bpmn_diagram(
        bpmn_path, "add", "intermediateCatchEvent", "Catch_Msg",
        element_name="Receive Message", event_definition="message"
    )
    assert "Added intermediateCatchEvent" in res

    tree = ET.parse(bpmn_path)
    root = tree.getroot()
    BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
    BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"

    catch_event = root.find(f".//{{{BPMN_NS}}}intermediateCatchEvent[@id='Catch_Msg']")
    assert catch_event is not None
    msg_def = catch_event.find(f"{{{BPMN_NS}}}messageEventDefinition")
    assert msg_def is not None, "messageEventDefinition child missing"

    shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Catch_Msg']")
    assert shape is not None
    assert shape.get("isMarkerVisible") == "true"


def test_event_definition_invalid_type_rejected():
    """event_definition on a non-event element must return an error string."""
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "event_def_invalid_test.bpmn")

    create_bpmn_diagram("Process_Bad", "Bad Process", bpmn_path)
    res = edit_bpmn_diagram(
        bpmn_path, "add", "task", "Task_1",
        element_name="Task", event_definition="error"
    )
    assert "Error" in res and "event_definition" in res


def test_event_definition_unknown_value_rejected():
    """An unknown event_definition value must return an error string."""
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "event_def_unknown_test.bpmn")

    create_bpmn_diagram("Process_Unk", "Unknown Process", bpmn_path)
    res = edit_bpmn_diagram(
        bpmn_path, "add", "endEvent", "End_1",
        event_definition="banana"
    )
    assert "Error" in res and "banana" in res


def test_comments_and_annotations():
    """Tests the full lifecycle of comments, text annotations, associations, and documentation."""
    import json
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "comments_test.bpmn")

    # 1. Create diagram
    create_bpmn_diagram("Process_Comments", "Comments Process", bpmn_path)

    # 2. Add task with documentation
    res_task = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="userTask",
        element_id="Task_Approval",
        element_name="Approve Invoice",
        documentation="Invoice must be reviewed by the finance manager."
    )
    assert "Added userTask" in res_task

    # 3. Add textAnnotation
    res_annot = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="textAnnotation",
        element_id="Note_Finance",
        element_name="Check the tax ID carefully!"
    )
    assert "Added textAnnotation" in res_annot

    # 4. Add association connecting them
    res_assoc = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="association",
        element_id="Assoc_1",
        source_ref="Note_Finance",
        target_ref="Task_Approval"
    )
    assert "Added association" in res_assoc

    # 5. Validate the diagram
    res_val = validate_bpmn_diagram(bpmn_path)
    assert "Basic validation passed." in res_val

    # 6. List elements and assert fields
    elements = json.loads(list_bpmn_elements(bpmn_path))
    by_id = {e["id"]: e for e in elements}

    assert "Task_Approval" in by_id
    assert by_id["Task_Approval"]["documentation"] == "Invoice must be reviewed by the finance manager."

    assert "Note_Finance" in by_id
    assert by_id["Note_Finance"]["type"] == "textAnnotation"
    assert by_id["Note_Finance"]["name"] == "Check the tax ID carefully!"

    assert "Assoc_1" in by_id
    assert by_id["Assoc_1"]["type"] == "association"
    assert by_id["Assoc_1"]["sourceRef"] == "Note_Finance"
    assert by_id["Assoc_1"]["targetRef"] == "Task_Approval"

    # 7. Update documentation and textAnnotation
    res_up_doc = update_bpmn_element(
        bpmn_path,
        element_id="Task_Approval",
        documentation="Invoice must be reviewed by the finance senior manager."
    )
    assert "Updated element" in res_up_doc
    assert "documentation=" in res_up_doc

    res_up_annot = update_bpmn_element(
        bpmn_path,
        element_id="Note_Finance",
        name="Check the tax ID and amount carefully!"
    )
    assert "Updated element" in res_up_annot
    assert "text=" in res_up_annot

    # 8. List again and assert updated fields
    elements_updated = json.loads(list_bpmn_elements(bpmn_path))
    by_id_up = {e["id"]: e for e in elements_updated}

    assert by_id_up["Task_Approval"]["documentation"] == "Invoice must be reviewed by the finance senior manager."
    assert by_id_up["Note_Finance"]["name"] == "Check the tax ID and amount carefully!"


def test_data_objects_and_stores():
    """Tests the full lifecycle of dataObjectReference, dataStoreReference, and associations."""
    import json
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "data_elements_test.bpmn")

    # 1. Create diagram
    create_bpmn_diagram("Process_Data", "Data Process", bpmn_path)

    # 2. Add a task
    edit_bpmn_diagram(bpmn_path, "add", "userTask", "Task_Process", "Process Invoice")

    # 3. Add dataObjectReference attached to the task (should be positioned below)
    res_do = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="dataObjectReference",
        element_id="Invoice_Doc",
        element_name="Invoice Document",
        attached_to_ref="Task_Process"
    )
    assert "Added dataObjectReference" in res_do

    # 4. Add dataStoreReference attached to the task (should be positioned below)
    res_ds = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="dataStoreReference",
        element_id="Invoice_DB",
        element_name="Invoice Database",
        attached_to_ref="Task_Process"
    )
    assert "Added dataStoreReference" in res_ds

    # 5. Add dataInputAssociation (DB -> Task)
    res_in = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="dataInputAssociation",
        element_id="Input_Assoc",
        source_ref="Invoice_DB",
        target_ref="Task_Process"
    )
    assert "Added dataInputAssociation" in res_in

    # 6. Add dataOutputAssociation (Task -> Doc)
    res_out = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="dataOutputAssociation",
        element_id="Output_Assoc",
        source_ref="Task_Process",
        target_ref="Invoice_Doc"
    )
    assert "Added dataOutputAssociation" in res_out

    # 7. Validate diagram
    res_val = validate_bpmn_diagram(bpmn_path)
    assert "Basic validation passed." in res_val

    # 8. Verify DI Bounds and structure
    tree = ET.parse(bpmn_path)
    root = tree.getroot()
    BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
    BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
    DC_NS = "http://www.omg.org/spec/DD/20100524/DC"

    # XML Logical Assertions
    assert root.find(f".//{{{BPMN_NS}}}dataObject[@id='DataObject_Invoice_Doc']") is not None
    assert root.find(f".//{{{BPMN_NS}}}dataStore[@id='DataStore_Invoice_DB']") is not None
    
    # DI Dimension and Position Assertions (Invoice_Doc width=36, height=50 centered under Task_Process width=100, height=80 at x=100, y=78)
    do_shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Invoice_Doc']")
    assert do_shape is not None
    do_bounds = do_shape.find(f"{{{DC_NS}}}Bounds")
    assert do_bounds.get("width") == "36"
    assert do_bounds.get("height") == "50"
    assert do_bounds.get("x") == "132"
    assert do_bounds.get("y") == "238"

    # Invoice_DB width=50, height=50 centered under Task_Process at x=100, y=78, shifted right to x=218 to avoid collision with Invoice_Doc
    ds_shape = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Invoice_DB']")
    assert ds_shape is not None
    ds_bounds = ds_shape.find(f"{{{DC_NS}}}Bounds")
    assert ds_bounds.get("width") == "50"
    assert ds_bounds.get("height") == "50"
    assert ds_bounds.get("x") == "218"
    assert ds_bounds.get("y") == "238"

    # DI Edge Waypoint Assertions
    di_ns = {"bpmndi": "http://www.omg.org/spec/BPMN/20100524/DI", "di": "http://www.omg.org/spec/DD/20100524/DI"}
    
    input_edge = root.find(".//bpmndi:BPMNEdge[@bpmnElement='Input_Assoc']", di_ns)
    assert input_edge is not None
    wps_input = input_edge.findall("di:waypoint", di_ns)
    assert len(wps_input) == 2
    assert wps_input[0].get("x") == "243" and wps_input[0].get("y") == "238" # DB Top (shifted right)
    assert wps_input[1].get("x") == "150" and wps_input[1].get("y") == "158" # Task Bottom

    output_edge = root.find(".//bpmndi:BPMNEdge[@bpmnElement='Output_Assoc']", di_ns)
    assert output_edge is not None
    wps_output = output_edge.findall("di:waypoint", di_ns)
    assert len(wps_output) == 2
    assert wps_output[0].get("x") == "150" and wps_output[0].get("y") == "158" # Task Bottom
    assert wps_output[1].get("x") == "150" and wps_output[1].get("y") == "238" # Doc Top

    # 9. List elements and assert fields
    elements = json.loads(list_bpmn_elements(bpmn_path))
    by_id = {e["id"]: e for e in elements}

    assert "Invoice_Doc" in by_id
    assert by_id["Invoice_Doc"]["type"] == "dataObjectReference"
    assert by_id["Invoice_Doc"]["name"] == "Invoice Document"

    assert "Invoice_DB" in by_id
    assert by_id["Invoice_DB"]["type"] == "dataStoreReference"
    assert by_id["Invoice_DB"]["name"] == "Invoice Database"

    assert "Input_Assoc" in by_id
    assert by_id["Input_Assoc"]["type"] == "dataInputAssociation"
    assert by_id["Input_Assoc"]["sourceRef"] == "Invoice_DB"
    assert by_id["Input_Assoc"]["targetRef"] == "Task_Process"

    assert "Output_Assoc" in by_id
    assert by_id["Output_Assoc"]["type"] == "dataOutputAssociation"
    assert by_id["Output_Assoc"]["sourceRef"] == "Task_Process"
    assert by_id["Output_Assoc"]["targetRef"] == "Invoice_Doc"


def test_collaborations_pools_and_messages():
    """Tests the full lifecycle of BPMN collaborations, pools, and message flows:
    - Create a diagram
    - Add participant pools (Participant_A, Participant_B)
    - Add tasks to respective pools using parent_ref (Task_A, Task_B)
    - Add a message flow connecting the tasks (MessageFlow_1)
    - Validate the collaboration diagram
    - Assert that correct waypoints are generated for the vertical message flow routing
    - Verify elements in list_bpmn_elements output
    """
    import json
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "collaboration_test.bpmn")

    # 1. Create diagram
    res_create = create_bpmn_diagram("Process_Main", "Main Process", bpmn_path)
    assert "Created basic BPMN diagram" in res_create

    # 2. Add Participant_A
    res_pA = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="participant",
        element_id="Participant_A",
        element_name="Participant A"
    )
    assert "Added participant" in res_pA

    # 3. Add Participant_B
    res_pB = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="participant",
        element_id="Participant_B",
        element_name="Participant B"
    )
    assert "Added participant" in res_pB

    # 4. Add Task_A (under Participant_A)
    res_tA = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="task",
        element_id="Task_A",
        element_name="Task A",
        parent_ref="Participant_A"
    )
    assert "Added task" in res_tA

    # 5. Add Task_B (under Participant_B)
    res_tB = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="task",
        element_id="Task_B",
        element_name="Task B",
        parent_ref="Participant_B"
    )
    assert "Added task" in res_tB

    # 6. Add MessageFlow_1
    res_mf = edit_bpmn_diagram(
        bpmn_path,
        action="add",
        element_type="messageFlow",
        element_id="MessageFlow_1",
        element_name="Message Flow 1",
        source_ref="Task_A",
        target_ref="Task_B"
    )
    assert "Added messageFlow" in res_mf

    # 7. Validate the collaboration diagram
    res_val = validate_bpmn_diagram(bpmn_path)
    assert "Basic validation passed." in res_val

    # 8. Verify XML structure
    tree = ET.parse(bpmn_path)
    root = tree.getroot()

    BPMN_NS = "http://www.omg.org/spec/BPMN/20100524/MODEL"
    BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
    DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
    DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

    # Verify Collaboration root elements
    collaboration = root.find(f".//{{{BPMN_NS}}}collaboration")
    assert collaboration is not None
    assert collaboration.get("id") == "Collaboration_1"

    # Verify that participants point to their respective processes
    part_A = collaboration.find(f"{{{BPMN_NS}}}participant[@id='Participant_A']")
    part_B = collaboration.find(f"{{{BPMN_NS}}}participant[@id='Participant_B']")
    assert part_A is not None and part_B is not None
    
    proc_A_id = part_A.get("processRef")
    proc_B_id = part_B.get("processRef")
    assert proc_A_id is not None
    assert proc_B_id is not None

    # Check processes existence in definitions
    proc_A = root.find(f"{{{BPMN_NS}}}process[@id='{proc_A_id}']")
    proc_B = root.find(f"{{{BPMN_NS}}}process[@id='{proc_B_id}']")
    assert proc_A is not None and proc_B is not None

    # Verify tasks are placed inside the correct processes
    assert proc_A.find(f"{{{BPMN_NS}}}task[@id='Task_A']") is not None
    assert proc_B.find(f"{{{BPMN_NS}}}task[@id='Task_B']") is not None

    # Verify Message Flow is inside Collaboration
    assert collaboration.find(f"{{{BPMN_NS}}}messageFlow[@id='MessageFlow_1']") is not None

    # 9. Verify DI Shape Bounds
    # Participant_A should be stacked at y=100
    shape_pA = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Participant_A']")
    assert shape_pA is not None
    bounds_pA = shape_pA.find(f"{{{DC_NS}}}Bounds")
    assert bounds_pA.get("x") == "100"
    assert bounds_pA.get("y") == "100"
    assert bounds_pA.get("width") == "600"
    assert bounds_pA.get("height") == "250"

    # Participant_B should be stacked at y=400
    shape_pB = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Participant_B']")
    assert shape_pB is not None
    bounds_pB = shape_pB.find(f"{{{DC_NS}}}Bounds")
    assert bounds_pB.get("x") == "100"
    assert bounds_pB.get("y") == "400"
    assert bounds_pB.get("width") == "600"
    assert bounds_pB.get("height") == "250"

    # Task_A (width=100, height=80) centered in Participant_A (x=100, y=100, w=600, h=250)
    # shapes_in_pool = 0 => x_pos = 100 + 80 = 180, y_pos = 100 + 125 - 40 = 185
    shape_tA = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Task_A']")
    assert shape_tA is not None
    bounds_tA = shape_tA.find(f"{{{DC_NS}}}Bounds")
    assert bounds_tA.get("x") == "180"
    assert bounds_tA.get("y") == "185"
    assert bounds_tA.get("width") == "100"
    assert bounds_tA.get("height") == "80"

    # Task_B (width=100, height=80) centered in Participant_B (x=100, y=400, w=600, h=250)
    # shapes_in_pool = 0 => x_pos = 100 + 80 = 180, y_pos = 400 + 125 - 40 = 485
    shape_tB = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Task_B']")
    assert shape_tB is not None
    bounds_tB = shape_tB.find(f"{{{DC_NS}}}Bounds")
    assert bounds_tB.get("x") == "180"
    assert bounds_tB.get("y") == "485"
    assert bounds_tB.get("width") == "100"
    assert bounds_tB.get("height") == "80"

    # 10. Verify DI Edge Message Flow Waypoints
    # Since Task_A (y=185, h=80, bottom=265) is above Task_B (y=485, top=485),
    # the messageFlow connects Task_A Bottom (180+50=230, 265) to Task_B Top (180+50=230, 485)
    edge_mf = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='MessageFlow_1']")
    assert edge_mf is not None
    wps = edge_mf.findall(f"{{{DI_NS}}}waypoint")
    assert len(wps) == 2
    assert wps[0].get("x") == "230" and wps[0].get("y") == "265"
    assert wps[1].get("x") == "230" and wps[1].get("y") == "485"

    # 11. Verify list_bpmn_elements output
    elements = json.loads(list_bpmn_elements(bpmn_path))
    by_id = {e["id"]: e for e in elements}

    assert "Participant_A" in by_id
    assert by_id["Participant_A"]["type"] == "participant"
    assert by_id["Participant_A"]["name"] == "Participant A"
    assert by_id["Participant_A"]["processRef"] == proc_A_id

    assert "Participant_B" in by_id
    assert by_id["Participant_B"]["type"] == "participant"
    assert by_id["Participant_B"]["name"] == "Participant B"
    assert by_id["Participant_B"]["processRef"] == proc_B_id

    assert "Task_A" in by_id
    assert by_id["Task_A"]["type"] == "task"
    assert by_id["Task_A"]["name"] == "Task A"

    assert "Task_B" in by_id
    assert by_id["Task_B"]["type"] == "task"
    assert by_id["Task_B"]["name"] == "Task B"

    assert "MessageFlow_1" in by_id
    assert by_id["MessageFlow_1"]["type"] == "messageFlow"
    assert by_id["MessageFlow_1"]["name"] == "Message Flow 1"
    assert by_id["MessageFlow_1"]["sourceRef"] == "Task_A"
    assert by_id["MessageFlow_1"]["targetRef"] == "Task_B"


def test_batch_update_visuals():
    from bpmn_mcp.server import batch_update_visuals
    output_dir = Path("test_outputs")
    output_dir.mkdir(exist_ok=True)
    bpmn_path = str(output_dir / "batch_update_test.bpmn")

    create_bpmn_diagram("Batch_Process", "Batch Process", bpmn_path)
    edit_bpmn_diagram(bpmn_path, "add", "task", "Task_1", "Task 1")
    edit_bpmn_diagram(bpmn_path, "add", "task", "Task_2", "Task 2")
    edit_bpmn_diagram(
        bpmn_path,
        "add",
        "sequenceFlow",
        "Flow_1",
        source_ref="Task_1",
        target_ref="Task_2"
    )

    # Apply batch update
    res = batch_update_visuals(
        file_path=bpmn_path,
        shapes=[
            {"id": "Task_1", "x": 150, "y": 80, "width": 100, "height": 80},
            {"id": "Task_2", "x": 350, "y": 80, "width": 100, "height": 80}
        ],
        edges=[
            {"id": "Flow_1", "waypoints": [{"x": 250, "y": 120}, {"x": 350, "y": 120}]}
        ]
    )

    assert "Batch update complete" in res
    assert "2 shapes and 1 edges successfully updated visually." in res

    # Verify visual layout changes
    root = ET.parse(bpmn_path).getroot()
    BPMNDI_NS = "http://www.omg.org/spec/BPMN/20100524/DI"
    DC_NS = "http://www.omg.org/spec/DD/20100524/DC"
    DI_NS = "http://www.omg.org/spec/DD/20100524/DI"

    shape_t1 = root.find(f".//{{{BPMNDI_NS}}}BPMNShape[@bpmnElement='Task_1']")
    bounds_t1 = shape_t1.find(f"{{{DC_NS}}}Bounds")
    assert bounds_t1.get("x") == "150"
    assert bounds_t1.get("y") == "80"

    edge_f1 = root.find(f".//{{{BPMNDI_NS}}}BPMNEdge[@bpmnElement='Flow_1']")
    wps = edge_f1.findall(f"{{{DI_NS}}}waypoint")
    assert len(wps) == 2
    assert wps[0].get("x") == "250"
    assert wps[1].get("x") == "350"


