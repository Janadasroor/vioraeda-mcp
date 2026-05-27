# VioraEDA-MCP Project Instructions

This project is a Model Context Protocol (MCP) server for the VioraEDA application. It follows the architectural patterns established in the `mnemosyne` project.

## Core Mandates
- Use `FastMCP` for server implementation.
- Use `asyncpg` for PostgreSQL interactions with connection pooling.
- Maintain a `records` table for general project memory.
- Provide tools for dynamic database and schema management.

## Tech Stack
- Python 3.10+
- mcp (FastMCP)
- asyncpg
- pydantic

## Workflow
- **Research -> Strategy -> Execution** for all feature additions.
- Always verify database connectivity during initialization.
- Maintain a clean CLI interface for configuration.
