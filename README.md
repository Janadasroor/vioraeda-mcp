# VioraEDA-MCP

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python Version](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](pyproject.toml)
[![MCP Protocol](https://img.shields.io/badge/MCP-1.0.0-orange.svg)](https://modelcontextprotocol.io)

A Model Context Protocol (MCP) server for **VioraEDA**, providing AI assistants with a robust bridge to circuit design tools, high-performance simulations, and automated documentation.

[![Janadasroor/vioraeda-mcp MCP server](https://glama.ai/mcp/servers/Janadasroor/vioraeda-mcp/badges/score.svg)](https://glama.ai/mcp/servers/Janadasroor/vioraeda-mcp)

## ⚡ Features

- **High-Performance Simulation**: Run SPICE and VioSpice simulations (sync or async) with JSON results.
- **Dynamic Documentation**: AI agents can fetch real-time documentation directly from the `viora` binary or neighboring markdown files.
- **Visual Rendering**: Render schematics, PCBs, and symbols to high-quality PNGs for visual AI inspection.
- **GUI Integration**: Open designs and load results directly into the running VioraEDA GUI.
- **Cross-Platform**: Fully supports Windows, Linux, and macOS.
- **SystemVerilog Support**: Inspect modules and ports for seamless hardware integration.

## 🚀 Quick Start

1. **Install VioraEDA**: Ensure the `viora` binary is in your system PATH.
2. **Install the MCP Server**:
   - **macOS / Linux**:
     ```bash
     pipx install vioraeda-mcp
     ```
   - **Windows**:
     ```bash
     pip install vioraeda-mcp
     ```
3. **Initialize your AI Agents**:
   ```bash
   vioraeda-mcp init
   ```
   *This automatically configures Claude Desktop, Gemini CLI, Claude Code, and Windsurf.*

4. **Restart your AI agent** and start designing!

## 🛠️ Available Tools

- `viora_status`: Get engine and version info.
- `viospice_netlist_run`: Execute SPICE simulations.
- `viospice_netlist_run_async`: Background simulation management.
- `viora_schematic_render`: Render schematics to PNG.
- `viora_get_docs`: Fetch version-matched documentation.
- `viora_ui_open`: Open files in the VioraEDA GUI.
- ... and many more.

## 🤝 Contributing

Contributions are welcome! Please see the [VioraEDA Website](https://vioraeda.com) for more details on the ecosystem.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
