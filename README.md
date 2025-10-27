# STRING MCP Server

Exposes [STRING](https://string-db.org) database functionality as an MCP (Model Context Protocol) server.  
This server wraps STRING API endpoints and makes them available as MCP tools for use with AI agents or other MCP-compatible clients.

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

## License / Citation

The STRING MCP server source code is released under the [MIT License](https://opensource.org/licenses/MIT).  
Associated data and outputs are released under the [CC BY 4.0 License](https://creativecommons.org/licenses/by/4.0/).  
You are free to use, share, and modify the code with proper attribution.

If you use this code or data in your work, please also cite the latest [STRING manuscript](https://string-db.org/cgi/about?footer_active_subpage=references).

