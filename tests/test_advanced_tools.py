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
