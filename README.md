# STRING MCP Server

Exposes [STRING database](https://string-db.org) functionality as a **Model Context Protocol (MCP)** server.  
This implementation allows AI agents and other MCP-compatible clients to access STRING data through a structured and self-describing interface.

It is build on top of the STRING API but adapted specifically for model-based use, with emphasis on conciseness and context efficiency. The server controls the amount and type of data so that responses stay within the reasoning limits of large language models. It also adapts the structure and adds metadata to support more consistent parsing and interpretation by agentic systems.

For reproducible workflows and large-scale integration, use the [STRING API](https://string-db.org/cgi/help?subpage=api).

---

## Features

- Resolve protein identifiers to STRING metadata
- Retrieve interaction networks
- Perform homology lookups across species
- Access evidence links for protein–protein interactions
- Run functional enrichment analysis (including enrichment plots)
- Get curated functional annotations for proteins
- Query proteins by functional terms (GO, KEGG, Reactome, etc.)

---

## Requirements

- **Python** ≥ 3.10  
- Dependencies (see `requirements.txt`):  
  - `fastmcp==2.10.6`  
  - `httpx==0.28.1`  
  - `pydantic==2.11.7`  

> **Note**: If the server crashes on startup, it’s very likely due to an incompatible **FastMCP** version.  

---

## Configuration

The server reads settings from `config/server.config` (JSON). Example:

```json
{
  "base_url": "https://string-db.org",
  "server_port": 57416,
  "verbosity": "low"
}
```

## Installation

```bash
git clone git@github.com:meringlab/string-mcp.git
cd string-mcp
pip install -r requirements.txt
```

## Running 

```
python server.py
```

## Docker

1. Ensure you have a `config/server.config` file (copy from `config/server.config.example` if needed):
   ```bash
   cp config/server.config.example config/server.config
   ```

2. Build the image:
   ```bash
   docker build -t string-mcp .
   ```

3. Run the container:
   
   **Linux/macOS:**
   ```bash
   docker run -p 57416:57416 -v $(pwd)/config:/app/config:ro string-mcp
   ```
   
   **Windows PowerShell:**
   ```powershell
   docker run -p 57416:57416 -v ${PWD}/config:/app/config:ro string-mcp
   ```
   
   **Windows Command Prompt:**
   ```cmd
   docker run -p 57416:57416 -v %cd%/config:/app/config:ro string-mcp
   ```

   To run in detached mode:
   ```bash
   # Linux/macOS
   docker run -d -p 57416:57416 -v $(pwd)/config:/app/config:ro --name string-mcp-server string-mcp
   
   # Windows PowerShell
   docker run -d -p 57416:57416 -v ${PWD}/config:/app/config:ro --name string-mcp-server string-mcp
   ```

   The `-v` flag mounts your local config directory so you can customize settings without rebuilding the image.
   
   **Note:** If you don't need to modify the config, you can omit the volume mount and the container will use the default config from the image.

4. Stop the container (if running in detached mode):
   ```bash
   docker stop string-mcp-server
   docker rm string-mcp-server
   ```

**Note:** The Docker container will use the configuration from `config/server.config`. If this file doesn't exist, the container will copy from `server.config.example` on first run.

**Note on errors:** You may see `anyio.ClosedResourceError` messages in the logs - these are expected and handled internally by the MCP server. They don't affect functionality. The server is working correctly when you see successful HTTP responses (200 OK, 202 Accepted).

## License / Citation

The STRING MCP server source code is released under the [MIT License](https://opensource.org/licenses/MIT).  
Associated data and outputs are released under the [CC BY 4.0 License](https://creativecommons.org/licenses/by/4.0/).  
You are free to use, share, and modify the code with proper attribution.

If you use this code or data in your work, please also cite the latest [STRING manuscript](https://string-db.org/cgi/about?footer_active_subpage=references).

