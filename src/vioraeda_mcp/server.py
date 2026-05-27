import argparse
import json
import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP, Image

# Setup basic logging to stderr
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("vioraeda-mcp")

# Create the MCP server instance
mcp = FastMCP("VioraEDA")

# --- Configuration & Path Resolution ---

def get_viora_executable() -> str:
    """Locate the viora CLI binary across Linux, Windows, and Mac."""
    is_windows = sys.platform == "win32"
    ext = ".exe" if is_windows else ""
    
    # Priority: PATH > ~/.local/bin > known build paths
    exe = shutil.which(f"viora{ext}") or shutil.which(f"viospice{ext}")
    if exe:
        return exe
    
    # Fallback to a common local bin
    home_local_bin = Path.home() / ".local" / "bin" / f"viora{ext}"
    if home_local_bin.exists():
        return str(home_local_bin)
    
    return f"viora{ext}"

def run_viora_command(args: List[str], timeout: int = 120, json_out: bool = False) -> Dict[str, Any]:
    """Execute a viora CLI command."""
    exe = get_viora_executable()
    try:
        proc = subprocess.run(
            [exe] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        
        out = proc.stdout.strip()
        err = proc.stderr.strip()
        data = None
        
        if json_out and out:
            json_start = out.find('{')
            json_end = out.rfind('}')
            if json_start >= 0 and json_end > json_start:
                try:
                    data = json.loads(out[json_start : json_end + 1])
                except json.JSONDecodeError:
                    pass
            else:
                try:
                    data = json.loads(out)
                except json.JSONDecodeError:
                    pass
        
        if proc.returncode == 0:
            return {
                "ok": True,
                "code": proc.returncode,
                "stdout": out,
                "stderr": err,
                "data": data,
            }
        
        return {
            "ok": False,
            "error": f"Command failed (code {proc.returncode}): {err or out}",
            "stdout": out,
            "stderr": err,
            "code": proc.returncode,
            "data": data,
        }
            
    except subprocess.TimeoutExpired:
        return {"ok": False, "error": f"Command timed out after {timeout}s"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# --- GUI Integration (WebSocket Bridge) ---

async def ui_query_async(code: str, host: str = "localhost", port: int = 18790) -> Dict[str, Any]:
    """Execute Python code in the running GUI context via internal vspice bridge."""
    try:
        import vspice.ui
        proxy = vspice.ui.connect(host=host, port=port)
        result = proxy.run_python_code(code)
        return {"ok": True, "output": result.get("output", ""), "is_error": not result.get("ok", False)}
    except ImportError:
        return {"ok": False, "error": "vspice python module not found."}
    except Exception as e:
        return {"ok": False, "error": f"GUI not detected: {e}"}

# --- MCP Tool Definitions: System & Files ---

@mcp.tool()
def viora_status() -> dict:
    """Show VioraEDA engine, CLI, and environment status."""
    exe = get_viora_executable()
    status = {
        "ok": True,
        "viora_executable": exe,
        "python_version": sys.version.split()[0],
    }
    try:
        res = subprocess.run([exe, "--version"], capture_output=True, text=True, timeout=2)
        status["viora_version"] = res.stdout.strip() or res.stderr.strip() or "unknown"
    except Exception:
        status["viora_version"] = "unknown"
    return status

@mcp.tool()
def viora_list_files(path: str = ".") -> dict:
    """List files in the workspace."""
    p = Path(path).resolve()
    try:
        files = []
        for item in p.iterdir():
            files.append({
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
                "size": item.stat().st_size if item.is_file() else 0,
            })
        return {"ok": True, "path": str(p), "files": files}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
def viora_read_file(path: str) -> dict:
    """Read design file content."""
    try:
        p = Path(path).resolve()
        return {"ok": True, "path": str(p), "content": p.read_text(encoding="utf-8")}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
def viora_write_file(path: str, content: str) -> dict:
    """Create or update a design file."""
    try:
        p = Path(path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"ok": True, "path": str(p)}
    except Exception as e:
        return {"ok": False, "error": str(e)}

# --- MCP Tool Definitions: Design & Symbols ---

@mcp.tool()
def viora_symbol_list(path: str = ".") -> dict:
    """Query the symbol library for available components."""
    return run_viora_command(["symbol-list", path, "--json"], json_out=True)

@mcp.tool()
def viora_schematic_query(file: str) -> dict:
    """Analyze a .flxsch schematic to extract components and connectivity."""
    return run_viora_command(["schematic-query", file, "--json"], json_out=True)

@mcp.tool()
def viora_flux_run(file: str = None, code: str = None, t: float = None, inputs: list = None) -> dict:
    """Execute automation logic via FluxScript."""
    if file:
        args = ["flux", "run", file]
    elif code:
        args = ["flux", "eval", code, "--json"]
        if t is not None:
            args.extend(["--time", str(t)])
        if inputs:
            args.extend(["--inputs", ",".join(map(str, inputs))])
    else:
        return {"ok": False, "error": "Missing file or code"}
    return run_viora_command(args, json_out=True)

@mcp.tool()
def viora_get_project_root() -> dict:
    """Return the absolute path of the current workspace root."""
    return {"ok": True, "project_root": str(Path.cwd().resolve())}

@mcp.tool()
def viospice_launch_viewer(file: str, type: str = "plot") -> dict:
    """Launch the standalone Waveform Viewer or Oscilloscope for a .raw file.
    Use type='osc' for a hardware-realistic analog oscilloscope view.
    """
    if sys.platform == "linux" and not os.environ.get("DISPLAY"):
        return {"ok": False, "error": "DISPLAY not set - cannot launch GUI."}
    
    exe = get_viora_executable()
    args = [exe, "view", file, "--type", type]
    try:
        # Start as a detached process
        subprocess.Popen(
            args,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        return {"ok": True, "message": f"Launched {type} viewer for {file}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@mcp.tool()
def viora_schematic_netlist(
    file: str,
    analysis: str = "tran",
    stop: str = "10m",
    step: str = "10u",
    format: str = "spice",
    out: Optional[str] = None
) -> dict:
    """Generate a raw SPICE netlist from a Viora schematic (.flxsch)."""
    args = ["schematic-netlist", file, "--analysis", analysis, "--stop", stop, "--step", step, "--format", format]
    if out:
        args.extend(["--out", out])
    return run_viora_command(args, json_out=(format == "json"))

@mcp.tool()
def viora_symbol_import(input_file: str, out_file: str, name: Optional[str] = None) -> dict:
    """Import external symbols from LTspice (.asy) or KiCad (.kicad_sym)."""
    args = ["symbol-import", input_file, out_file]
    if name:
        args.extend(["--name", name])
    return run_viora_command(args)

@mcp.tool()
def viora_symbol_validate(file: str) -> dict:
    """Check symbol integrity and pin mapping correctness."""
    return run_viora_command(["symbol-validate", file, "--json"], json_out=True)

@mcp.tool()
def viora_symbol_from_subckt(
    file: str, 
    out_dir: Optional[str] = None, 
    name: Optional[str] = None,
    type: str = "ic"
) -> dict:
    """Generate Viora symbols (.viosym) from SPICE .subckt definitions.
    This creates a visual symbol with automatic pin placement and mapping.
    It also returns a path to a temporary image preview of the generated symbol.
    
    Supported types:
    - 'ic': Standard rectangular body with a Pin 1 dot indicator.
    - 'op': Classic triangular Operational Amplifier shape.
    """
    if out_dir is None:
        out_dir = str(Path.home() / "ViospiceLib" / "sym")
    
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    
    args = ["symbol-from-subckt", file, out_dir, "--json", "--symbol-type", type]
    if name:
        args.extend(["--name", name])
    
    res = run_viora_command(args, json_out=True)
    
    # If a specific symbol was requested and generated, provide a visual preview
    if res.get("ok") and name:
        sym_file = Path(out_dir) / f"{name.lower()}.viosym"
        if sym_file.exists():
            # Create a temporary image path
            tmp_fd, tmp_img = tempfile.mkstemp(suffix=".png", prefix=f"viora_sym_{name.lower()}_")
            os.close(tmp_fd)
            
            render_res = run_viora_command(["symbol-render", str(sym_file), tmp_img, "--scale", "4.0"])
            if render_res.get("ok"):
                res["image_preview_path"] = tmp_img
                
    return res

@mcp.tool()
def viora_bom_generate(file: str) -> dict:
    """Generate a Bill of Materials (BOM) from a schematic."""
    res = run_viora_command(["schematic-query", file, "--json"], json_out=True)
    if not res.get("ok"):
        return res
    
    components = res.get("data", {}).get("components", [])
    bom = []
    # Group by part/value
    registry = {}
    for c in components:
        key = (c.get("part", "UNKNOWN"), c.get("value", ""))
        if key not in registry:
            registry[key] = {"part": key[0], "value": key[1], "quantity": 0, "designators": []}
        registry[key]["quantity"] += 1
        registry[key]["designators"].append(c.get("id", "?"))
    
    return {
        "ok": True,
        "schematic": file,
        "component_count": len(components),
        "bom": sorted(list(registry.values()), key=lambda x: x["part"])
    }

# --- MCP Tool Definitions: Simulation ---

@mcp.tool()
def viospice_netlist_run(
    file: Optional[str] = None,
    cir: Optional[str] = None,
    analysis: Optional[str] = None,
    stop: Optional[str] = None,
    step: Optional[str] = None,
    signals: Optional[List[str]] = None,
    robust: bool = False,
    compat: bool = True,
) -> dict:
    """Execute a SPICE/VioSpice simulation."""
    args = ["netlist-run", "--json"]
    temp_file = None
    if cir:
        fd, temp_file = tempfile.mkstemp(suffix=".cir")
        os.close(fd)
        Path(temp_file).write_text(cir, encoding="utf-8")
        args.append(temp_file)
    elif file:
        args.append(file)
    else:
        return {"ok": False, "error": "No file or netlist provided"}

    if analysis:
        args.extend(["--analysis", analysis])
    if stop:
        args.extend(["--stop", stop])
    if step:
        args.extend(["--step", step])
    if signals:
        for s in signals:
            args.extend(["--signal", s])
    if robust:
        args.append("--robust")
    if compat:
        args.append("--compat")

    try:
        return run_viora_command(args, json_out=True)
    finally:
        if temp_file and os.path.exists(temp_file):
            os.remove(temp_file)

@mcp.tool()
def viospice_netlist_validate(file: str = None, cir: str = None) -> dict:
    """Validate a SPICE netlist without running simulation."""
    args = ["netlist-validate", "--json"]
    if file:
        args.append(file)
    elif cir:
        fd, temp_file = tempfile.mkstemp(suffix=".cir")
        os.close(fd)
        Path(temp_file).write_text(cir, encoding="utf-8")
        args.append(temp_file)
        try:
            return run_viora_command(args, json_out=True)
        finally:
            os.remove(temp_file)
    return run_viora_command(args, json_out=True)

@mcp.tool()
def viospice_netlist_to_schematic(file: str, out: str = None) -> dict:
    """Convert a SPICE netlist (.cir) into a Viora schematic (.flxsch)."""
    args = ["netlist-to-schematic", file]
    if out:
        args.extend(["--out", out])
    return run_viora_command(args, json_out=True)

@mcp.tool()
def viospice_raw_info(file: str) -> dict:
    """Get signal metadata from a .raw simulation binary."""
    return run_viora_command(["raw-info", file, "--json"], json_out=True)

@mcp.tool()
def viospice_raw_export(file: str, out: str, format: str = "json") -> dict:
    """Export binary simulation waveforms to JSON, CSV, or Parquet."""
    return run_viora_command(["raw-export", file, "--format", format, "--out", out], json_out=True)

@mcp.tool()
def viospice_verilog_inspect(file: str, module: Optional[str] = None) -> dict:
    """Inspect a SystemVerilog file to extract module ports."""
    args = ["verilog-inspect", file, "--json"]
    if module:
        args.extend(["--module", module])
    return run_viora_command(args, json_out=True)

# --- MCP Tool Definitions: Async Jobs ---

_jobs: Dict[str, Dict[str, Any]] = {}
_job_lock = threading.Lock()
_next_job_id = 0

@mcp.tool()
def viospice_netlist_run_async(
    file: Optional[str] = None,
    cir: Optional[str] = None,
    analysis: Optional[str] = None,
    stop: Optional[str] = None,
    step: Optional[str] = None,
    signals: Optional[List[str]] = None,
) -> dict:
    """Start a simulation in the background."""
    global _next_job_id
    with _job_lock:
        job_id = f"sim_{_next_job_id}"
        _next_job_id += 1
        _jobs[job_id] = {"status": "queued", "result": None}

    def _worker():
        with _job_lock:
            _jobs[job_id]["status"] = "running"
        try:
            res = viospice_netlist_run(file=file, cir=cir, analysis=analysis, stop=stop, step=step, signals=signals)
            with _job_lock:
                _jobs[job_id]["status"] = "done"
                _jobs[job_id]["result"] = res
        except Exception as e:
            with _job_lock:
                _jobs[job_id]["status"] = "error"
                _jobs[job_id]["result"] = {"ok": False, "error": str(e)}

    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "job_id": job_id}

@mcp.tool()
def viospice_job_status(job_id: str) -> dict:
    """Check the status of a background job."""
    with _job_lock:
        job = _jobs.get(job_id)
        if not job:
            return {"ok": False, "error": "Job not found"}
        return {"ok": True, "status": job["status"]}

@mcp.tool()
def viospice_job_result(job_id: str) -> dict:
    """Retrieve results for a completed job."""
    with _job_lock:
        job = _jobs.get(job_id)
        if not (job and job["status"] in ("done", "error")):
            return {"ok": False, "error": "Job not ready"}
        res = job["result"]
        del _jobs[job_id]
        return res

# --- MCP Tool Definitions: Rendering & GUI ---

@mcp.tool()
def viora_schematic_render(file: str, out: str, scale: float = 4.0) -> Image:
    """Render a .flxsch schematic to a PNG image."""
    run_viora_command(["schematic-render", file, out, "--scale", str(scale)])
    return Image(path=out)

@mcp.tool()
def viora_pcb_render(file: str, out: str) -> Image:
    """Render a .pcb board to a PNG image."""
    run_viora_command(["render", file, out])
    return Image(path=out)

@mcp.tool()
def viora_symbol_render(file: str, out: str, scale: float = 4.0) -> Image:
    """Render a .viosym symbol to a PNG image."""
    run_viora_command(["symbol-render", file, out, "--scale", str(scale)])
    return Image(path=out)

@mcp.tool()
async def viora_ui_open(path: str) -> dict:
    """Open a design file in the VioraEDA GUI."""
    abs_path = str(Path(path).resolve())
    return await ui_query_async(f"import vspice; vspice.ui.connect().open_schematic('{abs_path}')")

@mcp.tool()
async def viora_ui_open_project(path: str) -> dict:
    """Open a project in the VioraEDA GUI."""
    abs_path = str(Path(path).resolve())
    return await ui_query_async(f"import vspice; vspice.ui.connect().open_project('{abs_path}')")

@mcp.tool()
async def viora_ui_load_results(path: str) -> dict:
    """Load .raw results into the GUI Analog Oscilloscope."""
    abs_path = str(Path(path).resolve())
    return await ui_query_async(f"import vspice; vspice.ui.connect().load_simulation_results('{abs_path}')")

@mcp.tool()
async def viora_ui_get_active_tab() -> dict:
    """Get the active editor tab name."""
    code = (
        "from PySide6.QtWidgets import QApplication, QTabWidget; "
        "print([w.findChild(QTabWidget).tabText(w.findChild(QTabWidget).currentIndex()) "
        "for w in QApplication.topLevelWidgets() if w.isVisible() and w.findChild(QTabWidget)][0])"
    )
    return await ui_query_async(code)

@mcp.tool()
def viora_get_docs(topic: str = "all") -> dict:
    """Get documentation dynamically from the VioraEDA engine or its environment."""
    exe = get_viora_executable()
    
    # 1. Try to get docs via binary CLI (Source of Truth)
    res = run_viora_command(["help", topic, "--json"], json_out=True)
    if res.get("ok") and res.get("data"):
        return {"ok": True, "source": "binary", "topic": topic, "content": res["data"]}

    # 2. Filesystem Scan
    exe_path = Path(exe).resolve()
    potential_docs_dirs = [
        exe_path.parent / "docs",
        exe_path.parent.parent / "docs",
        exe_path.parent.parent / "share" / "doc" / "viora",
    ]
    
    for docs_dir in potential_docs_dirs:
        if docs_dir.exists() and docs_dir.is_dir():
            md_files = {f.stem.lower(): f for f in docs_dir.glob("*.md")}
            
            if topic == "all":
                return {
                    "ok": True, 
                    "source": "filesystem", 
                    "docs_dir": str(docs_dir),
                    "available_topics": list(md_files.keys())
                }
            
            target = md_files.get(topic.lower())
            if target and target.exists():
                return {
                    "ok": True, 
                    "source": "filesystem", 
                    "path": str(target), 
                    "content": target.read_text(encoding="utf-8")
                }

    return {
        "ok": False, 
        "error": f"Documentation for '{topic}' not found.",
        "viora_executable": exe
    }

# --- CLI Command Implementations ---

def cmd_run():
    mcp.run(transport="stdio")

def cmd_init():
    print("🔍 Verifying VioraEDA...")
    viora_path = get_viora_executable()

    if shutil.which(viora_path) or os.path.exists(viora_path):
        print(f"✅ Found viora binary: {viora_path}")
    else:
        print("❌ viora binary not found.")
        sys.exit(1)
    
    home = os.path.expanduser("~")
    executable = shutil.which("vioraeda-mcp") or sys.executable + " -m vioraeda_mcp.server"

    # Platform-specific paths for Claude Desktop
    if sys.platform == "darwin":
        claude_path = os.path.join(home, "Library", "Application Support", "Claude", "claude_desktop_config.json")
    elif sys.platform == "win32":
        claude_path = os.path.join(os.environ.get("APPDATA", home), "Claude", "claude_desktop_config.json")
    else:
        claude_path = os.path.join(home, ".config", "Claude", "claude_desktop_config.json")

    configs = {
        "Gemini CLI": {"path": os.path.join(home, ".gemini", "settings.json"), "key": "mcpServers"},
        "Claude Code": {"path": os.path.join(home, ".claude.json"), "key": "mcpServers"},
        "Windsurf": {"path": os.path.join(home, ".codeium", "windsurf", "mcp_config.json"), "key": "mcpServers"},
        "Claude Desktop": {"path": claude_path, "key": "mcpServers"},
    }
    
    for name, info in configs.items():
        path = info["path"]
        if os.path.exists(os.path.dirname(path)):
            data = {}
            if os.path.exists(path):
                with open(path, "r") as f:
                    content = f.read()
                    data = json.loads(re.sub(r"//.*", "", content)) if content.strip() else {}
            data.setdefault(info["key"], {})["vioraeda-mcp"] = {"command": executable, "args": []}
            with open(path, "w") as f:
                json.dump(data, f, indent=2)
            print(f"✅ Configured {name}")
    print("\n✨ Initialization complete!")

def cmd_status():
    print("🔍 VioraEDA-MCP System Status")
    viora_path = get_viora_executable()
    
    if shutil.which(viora_path) or os.path.exists(viora_path):
        print(f"✅ VioraEDA Binary: Found at {viora_path}")
        try:
            res = subprocess.run([viora_path, "--version"], capture_output=True, text=True, timeout=2)
            version = res.stdout.strip() or res.stderr.strip() or "unknown"
            print(f"✅ Engine Version: {version}")
        except Exception as e:
            print(f"⚠️ Engine Version: Could not determine ({e})")
    else:
        print("❌ VioraEDA Binary: NOT FOUND")
        print("   Please ensure 'viora' or 'viospice' is in your system PATH.")

def main():
    parser = argparse.ArgumentParser(
        description="VioraEDA MCP Server - AI Bridge for Circuit Design",
        epilog="Examples:\n  vioraeda-mcp init    # Configure AI agents\n  vioraeda-mcp run     # Start the MCP server (stdio)\n  vioraeda-mcp status  # Check system readiness",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    subparsers.add_parser("run", help="Start the MCP server using stdio transport (default)")
    subparsers.add_parser("init", help="Configure local AI agents to use this server")
    subparsers.add_parser("status", help="Check VioraEDA binary installation and version")
    
    args = parser.parse_args()
    
    if args.command == "init":
        cmd_init()
    elif args.command == "status":
        cmd_status()
    elif args.command == "run" or args.command is None:
        cmd_run()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
