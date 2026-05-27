FROM python:3.11-slim

WORKDIR /app

# Copy project files
COPY pyproject.toml README.md LICENSE ./
COPY src/ ./src/

# Install the package
RUN pip install --no-cache-dir .

# Set the command to run the MCP server using stdio
ENTRYPOINT ["vioraeda-mcp", "run"]
