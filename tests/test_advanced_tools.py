import pytest
from pathlib import Path
from vioraeda_mcp.server import (
    viora_bom_generate,
    viora_schematic_netlist,
    viora_symbol_validate
)

# Use existing files from the environment for realistic testing
SAMPLE_SCH = "/home/jnd/qt_projects/viospice/bjt_amplifier.flxsch"
SAMPLE_SYM = "/home/jnd/ViospiceLib/sym/npn2.viosym"

def test_bom_generate():
    """Verify BOM generation logic by querying a real schematic."""
    if not Path(SAMPLE_SCH).exists():
        pytest.skip("Sample schematic not found in environment")
    
    res = viora_bom_generate(SAMPLE_SCH)
    assert res["ok"] is True
    assert "bom" in res
    assert res["component_count"] > 0
    # Check for common BOM fields
    first_item = res["bom"][0]
    assert "part" in first_item
    assert "quantity" in first_item
    assert "designators" in first_item

def test_schematic_netlist():
    """Verify that we can export a schematic to a SPICE netlist."""
    if not Path(SAMPLE_SCH).exists():
        pytest.skip("Sample schematic not found in environment")
    
    res = viora_schematic_netlist(SAMPLE_SCH, analysis="op")
    assert res["ok"] is True
    assert ".title" in res["stdout"].lower() or ".op" in res["stdout"].lower()

def test_symbol_validate():
    """Verify symbol validation tool."""
    if not Path(SAMPLE_SYM).exists():
        pytest.skip("Sample symbol not found in environment")
    
    res = viora_symbol_validate(SAMPLE_SYM)
    assert res["ok"] is True
    assert "name" in res["data"]
    assert "pinCount" in res["data"]

def test_symbol_from_subckt(tmp_path):
    """Verify conversion of a SPICE subcircuit to a Viora symbol."""
    from vioraeda_mcp.server import viora_symbol_from_subckt
    
    subckt_file = tmp_path / "test.cir"
    subckt_file.write_text(".subckt TEST_NODE A B C\nR1 A B 1k\n.ends", encoding="utf-8")
    
    # Test with explicit out_dir
    out_dir = tmp_path / "syms"
    res = viora_symbol_from_subckt(str(subckt_file), str(out_dir))
    assert res["ok"] is True
    assert res["data"]["count"] >= 1
    assert (out_dir / "test_node.viosym").exists()

def test_symbol_from_subckt_op(tmp_path):
    """Verify conversion of a SPICE subcircuit to a Viora 'op' (triangle) symbol."""
    from vioraeda_mcp.server import viora_symbol_from_subckt
    import json
    
    subckt_file = tmp_path / "opamp.cir"
    subckt_file.write_text(".subckt MY_OP IN- IN+ VCC VEE OUT\n.ends", encoding="utf-8")
    
    out_dir = tmp_path / "syms_op"
    res = viora_symbol_from_subckt(str(subckt_file), str(out_dir), name="MY_OP", type="op")
    assert res["ok"] is True
    assert "image_preview_path" in res
    assert Path(res["image_preview_path"]).exists()
    assert res["image_preview_path"].endswith(".png")
    
    sym_file = out_dir / "my_op.viosym"
    assert sym_file.exists()
    
    # Verify polygon primitive exists (the triangle)
    content = json.loads(sym_file.read_text())
    primitives = content.get("primitives", [])
    assert any(p["type"] == "polygon" for p in primitives)
    assert any(p["type"] == "text" and p["text"] == "+" for p in primitives)
