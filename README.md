# STRING MCP Server

Exposes [STRING database](https://string-db.org) functionality as a **Model Context Protocol (MCP)** server.  
This implementation allows AI agents and other MCP-compatible clients to access STRING data through a structured and self-describing interface.

It is build on top of the STRING API but adapted specifically for model-based use, with emphasis on conciseness and context efficiency. The server controls the amount and type of data so that responses stay within the reasoning limits of large language models. It also adapts the structure and adds metadata to support more consistent parsing and interpretation by agentic systems.

For reproducible workflows and large-scale integration, use the [STRING API documentation](https://string-db.org/cgi/help?subpage=api).

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

