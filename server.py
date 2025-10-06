"""
STRING MCP Server
=================

This script exposes STRING database functionality as an MCP (Model Context Protocol) server.
It provides tools for resolving protein identifiers, retrieving interactions, functional
annotations, enrichment analysis, and generating network visualizations.

The server is implemented in Python.

Configuration:
  - Reads settings from config/server.config (JSON)
  - Requires "base_url" (STRING API endpoint) and "server_port"

Run:
  python server.py

The server listens on the configured port and serves tools via streamable-http transport.

Requirements:

fastmcp>=2.10.6,<2.11
httpx>=0.28,<0.29
pydantic>=2.11,<2.12

Creator: meringlab
Contact email: damian.szklarczyk@sib.swiss 
License: CC-BY-4.0

"""

import sys
import json
import httpx
import traceback


from collections import defaultdict
from typing import Annotated, Optional

from pydantic import Field
from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from string_help import HELP_TOPICS

try:
    with open("config/server.config") as f:
        config = json.load(f)
except (FileNotFoundError, json.JSONDecodeError) as e:
    sys.stderr.write(f"Error loading config: {e}\n")
    sys.exit(1)


base_url = config.get("base_url")
server_port = int(config.get("server_port", 0))

if not base_url:
    raise ValueError("Missing required config: 'base_url', e.g. 'https://version-12-0.string-db.org' ")

if not server_port:
    raise ValueError("Missing required config: 'server_port', e.g. '57416' ")

timeout = float(config.get("timeout", 30))

## logging verbosity ## 

log_verbosity = {}
log_verbosity['call'] = False
log_verbosity['params'] = False
log_verbosity["taskid"] =  False
log_verbosity["size"] =  False


if 'verbosity' in config:

    if config['verbosity'] == 'full':
        log_verbosity['call'] = True
        log_verbosity['params'] = True
        log_verbosity['taskid'] = True
        log_verbosity['size'] = True

    if config['verbosity'] == 'low':
        log_verbosity['call'] = True
        log_verbosity['params'] = False
        log_verbosity['taskid'] = True
        log_verbosity['size'] = True


async def _post_json(client: httpx.AsyncClient, endpoint: str, data: dict):
    """
    POST form data to a STRING API endpoint and return JSON.
    - On success: returns parsed JSON (or {'result': <text>} if body is not JSON).
    - On handled HTTP errors: returns a structured error dict and logs a concise line + the returned payload.
    - On unexpected exceptions: prints traceback and returns a structured error dict, also logging what was returned.
    """
    params = data

    try:
        response = await client.post(endpoint, data=params)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            # Successful response but not JSON
            return {"result": response.text}

    except httpx.HTTPStatusError as e:
        status = e.response.status_code
        try:
            server_detail = e.response.json()
        except Exception:
            server_detail = e.response.text

        diagnostics = {
            "endpoint": endpoint,
            "status": status,
            "params_sent": {k: v for k, v in params.items()},
            "server_detail": server_detail,
        }

        hints = []
        if status == 400:
            if not params.get("species") or not params.get("species").isnumeric():
                hints.append(
                    "Valid 'species' parameter required (NCBI taxonomy ID or clade). "
                    "Example: 9606 (human), 7227 (D. melanogaster), 10090 (mouse), or a STRING clade ID. "
                    "Agant should clarify with user or assume it is human (9606). "
                )
            elif not params.get("identifiers"):
                hints.append("Missing 'identifiers'.")
            else:
                hints.append(
                    "Species might be not present in STRING. Search string_query_species with a name "
                    "or invoke the 'string_help' tool with topic='missing_species' for info how to proceed;"
                )
        elif status == 404:
            hints.append(
                "The provided identifiers could not be mapped in STRING. "
                "Use the 'string_resolve_proteins' tool first to resolve ambiguous names. "
                "If identifiers are not known, try searching with a functional term using the 'string_proteins_for_term' tool."
            )

        error_payload = {
            "error": {
                "type": "string_api_error",
                "message": f"STRING API request failed with status {status}.",
                "hints": hints or ["Check parameters and retry."],
                "diagnostics": diagnostics,
            }
        }

        # Log how it was handled (no traceback for expected HTTP errors)
        sys.stderr.write(
            f"[handled] HTTPStatusError {status} at {endpoint} with params={params}\n"
            f"[handled] Returned payload: {json.dumps(error_payload, ensure_ascii=False)}\n"
        )

        return error_payload

    except Exception as e:
        # Unexpected failure: keep traceback
        traceback.print_exc(file=sys.stderr)

        error_payload = {
            "error": {
                "type": "unexpected_error",
                "message": "Unexpected error in STRING API call.",
                "diagnostics": {"params_sent": {k: v for k, v in params.items()}},
            }
        }

        # Also log how it was handled
        sys.stderr.write(
            f"[handled] Unexpected exception {type(e).__name__} at {endpoint} with params={params}\n"
            f"[handled] Returned payload: {json.dumps(error_payload, ensure_ascii=False)}\n"
        )

        return error_payload


mcp = FastMCP(
    name="STRING Database MCP Server",
)

@mcp.tool(title="STRING: Resolves protein identifiers to metadata")
async def string_resolve_proteins(
    proteins: Annotated[
        str,
        Field(
            description=(
                "Required. One or more input protein identifiers (gene symbols, UniProt IDs, etc.), "
                "separated by carriage return (%0d). Example: TP53%0dSMO"
            )
        )
    ],
    species: Annotated[
        str,
        Field(
            description=(
                "Optional. NCBI taxonomy ID (e.g. 9606 for human) or STRING genome ID "
                "(e.g. STRG0AXXXXX for uploaded genomes)."
            )
        )
    ] = None
) -> dict:
    """
    Maps one or more protein identifiers to their corresponding STRING metadata, including:
    gene symbol, description, internal STRING ID, and species information.

    This method is useful for translating raw identifiers into readable, annotated protein entries.

    Example input: "TP53%0dSMO"
    """

   
    params = {"identifiers": proteins, "echo_query": 1}
    if species is not None:
        params["species"] = species

    endpoint = "/api/json/get_string_ids"
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        log_response_size(results)
        return {"mapped_proteins": results}



@mcp.tool(title="STRING: Get interactions within query set")
async def string_interactions_query_set(
    proteins: Annotated[
        str,
        Field(description=(
            "Required. One or more protein identifiers, separated by carriage return (%0d). "
            "Example: SMO%0dTP53"
        ))
    ],
    species: Annotated[
        str,
        Field(description=(
            "Optional. NCBI taxonomy ID (e.g. 9606 for human) or STRING genome ID "
            "(e.g. STRG0AXXXXX for uploaded genomes)."
        ))
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description=(
            "Optional. Minimum confidence score for an interaction (range: 0–1000). "
            "Only set this if the user explicitly requests it."
        ))
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description=(
            'Optional. Network type: "functional" (default) or "physical" (co-complex).'
        ))
    ] = None,
    extend_network: Annotated[
        Optional[int],
        Field(description=(
            "Optional. Number of additional proteins to add to the network based on their "
            "connectivity. Default is 10 for a single protein query and 0 for multiple proteins. "
            "Only set this if the user explicitly requests it."
        ))
    ] = None,
    #show_query_node_labels: Annotated[
    #    Optional[int],
    #    Field(description=(
    #        "Optional. Set to 1 to display user-supplied names instead of STRING preferred names "
    #        "in the output. Default is 0. Only set if the user explicitly requests it."
    #    ))
    #] = None
) -> dict:
    """
    Retrieves the interactions between the query proteins.
    Use this method only when you specifically need to list the interactions between all proteins in your query set.
    If user asks for 'physical' or 'complex' use 'physical' network type.

    - For a **single protein**, the network includes that protein and its top 10 most likely interaction partners, plus all interactions among those partners.
    - For **multiple proteins**, the network includes all direct interactions between them.
    - If the user refers to "physical interactions", "complexes", or "binding", set the network type to "physical".

    If few or no interactions are returned, consider reducing the `required_score`.

    - Expand the names of score sources:  
        `nscore` (neighborhood), `fscore` (fusion), `pscore` (phylogenetic profile),  
        `ascore` (coexpression), `escore` (experimental), `dscore` (database), `tscore` (text-mining)
    """

    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type
    if extend_network is not None:
        params["add_white_nodes"] = extend_network
    #if show_query_node_labels is not None:
    #    params["show_query_node_labels"] = show_query_node_labels

    add_score_note = False
    if not required_score and len(proteins.lower().split("%d0")) <= 5:
        params["required_score"] = 0
        required_score = 0
        add_score_note = True

    endpoint = "/api/json/network"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        if 'error' in results: return results
        else: results = truncate_network(results, required_score, 'json')
        if add_score_note:
            results.insert(0, {"note": (f"The required_score parameter was "
                "automatically lowered to include all interactions, including low-confidence ones. \n"
                "IMPORTANT: If the interaction score is low (below 400), inform user about it."
            )})
        log_response_size(results)
        return {"network": results}


@mcp.tool(title="STRING: Get all interaction partners for proteins")
async def string_all_interaction_partners(
    identifiers: Annotated[
        str,
        Field(description=(
            "Required. One or more protein identifiers, separated by carriage return (%0d). "
            "Example: TP53%0dSMO"
        ))
    ],
    species: Annotated[
        str,
        Field(description=(
            "Optional. NCBI taxonomy ID (e.g. 9606 for human) or STRING genome ID "
            "(e.g. STRG0AXXXXX for uploaded genomes). Only set if the user explicitly requests it."
        ))
    ] = None,
    #limit: Annotated[
    #    Optional[int],
    #    Field(description=(
    #        "Optional. Maximum number of interaction partners returned per query protein. "
    #        "Higher-confidence interactions appear first. Only set if the user explicitly requests it."
    #    ))
    #] = None,
    required_score: Annotated[
        Optional[int],
        Field(description=(
            "Optional. Minimum interaction score to include (range: 0–1000). "
            "Only set if the user explicitly requests it."
        ))
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description=(
            'Optional. Network type: "functional" (default) or "physical" (co-complex).'
        ))
    ] = None
) -> dict:
    """
    Retrieves all interaction partners for one or more proteins from STRING.

    This tool returns all known interactions between your query protein(s) and **any other proteins in the STRING database**.
    
    - Use this when asking **“What does TP53 interact with?”**
    - It differs from the `network` tool, which only shows interactions **within the input set** or a limited extension of it.
    - If the user refers to "physical interactions", "complexes", or "binding", set the network type to "physical".

    You can filter for strong interactions using `required_score`.

    - Evidence scores:  
        `nscore` (neighborhood), `fscore` (fusion), `pscore` (phylogenetic profile),  
        `ascore` (coexpression), `escore` (experimental), `dscore` (database), `tscore` (text mining)
    """

    limit = 100

    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if limit is not None:
        params["limit"] = limit
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type

    endpoint = "/api/json/interaction_partners"
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        if 'error' in results:
            log_response_size(results)
            return results
        else:
            results_truncated = truncate_network(results, required_score, 'json')

        log_response_size(results_truncated)
        return {"interactions": results_truncated}


@mcp.tool(title="STRING: Get interaction network image (image URL)")
async def string_visual_network(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX).")
    ] = None,
    extend_network: Annotated[
        Optional[int],
        Field(description="Optional. Add specified number of nodes to the network, based on their scores (default: 0, or 10 for single protein queries).")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Threshold of significance to include an interaction (0-1000).")
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical" (co-complex).')
    ] = None,
    network_flavor: Annotated[
        Optional[str],
        Field(description='Optional. Edge style: "evidence" (default), "confidence", or "actions".')
    ] = None,
    hide_disconnected_nodes: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide proteins not connected to any other protein, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    #show_query_node_labels: Annotated[
    #    Optional[int],
    #    Field(description="Optional. 1 display the user's query name(s) instead of STRING preferred name, (default: 0). DO NOT SET unless user explicitly requests.")
    #] = None,
    center_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 to center protein names on nodes, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    custom_label_font_size: Annotated[
        Optional[int],
        Field(description="Optional. Change font size of protein names (from 5 to 50, default: 12). DO NOT SET unless user explicitly requests.")
    ] = None
) -> dict:
    """
    Retrieves a URL to a **STRING interaction network image** for one or more proteins.  
    
    - For a single protein: includes the protein and its top 10 most likely interactors.  
    - For multiple proteins: includes all known interactions **within the query set**.  
    - If the user asks for "physical interactions", "complexes", or "binding", set `network_type` to "physical".  
    
    If few or no interactions are shown, consider lowering `required_score`.  
    
    This tool returns a direct image URL. Always display the image inline, and ask if the user also wants a link to the interactive STRING network page.  
    
    Input parameters should match those used in related STRING tools (e.g. `string_interactions_query_set`), unless otherwise specified.  

    """
    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species
    if extend_network is not None:
        params["add_white_nodes"] = extend_network
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type
    if network_flavor is not None:
        params["network_flavor"] = network_flavor
    if hide_disconnected_nodes is not None:
        params["hide_disconnected_nodes"] = hide_disconnected_nodes
    #if show_query_node_labels is not None:
    #    params["show_query_node_labels"] = show_query_node_labels
    if center_node_labels is not None:
        params["center_node_labels"] = center_node_labels
    if custom_label_font_size is not None:
        params["custom_label_font_size"] = custom_label_font_size

    endpoint = f"/api/json/network_image_url"


    add_score_note = False
    if not required_score and len(proteins.lower().split("%d0")) <= 5:
        params["required_score"] = 0
        add_score_note = True

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        if add_score_note:
            results.insert(0, {"note": (f"The required_score parameter was "
                "automatically lowered to include all interactions, including low-confidence ones. "
            )})
 
        log_response_size(results)
        return {"image_url": results}

@mcp.tool(title="STRING: Get interactive network link (web UI)")
async def string_network_link(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX).")
    ] = None,
    extend_network: Annotated[
        Optional[int],
        Field(description="Optional. Add white nodes to network, based on scores (default: 0).")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Threshold of significance to include an interaction (0-1000).")
    ] = None,
    network_flavor: Annotated[
        Optional[str],
        Field(description='Optional. Edge style: "evidence" (default) or "confidence"')
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical" (co-complex).')
    ] = None,
    hide_disconnected_nodes: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide proteins not connected to any other protein, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    #show_query_node_labels: Annotated[
    #    Optional[int],
    #    Field(description="Optional. 1 display the user's query name(s) instead of STRING preferred name, (default: 0). DO NOT SET unless user explicitly requests.")
    #] = None,
) -> dict:
    """Retrieves a stable URL to an interactive STRING network for one or more proteins.

    This tool returns a link to the STRING website where the queried protein network can be interactively explored.  
    Users can click on nodes and edges, view evidence, and explore additional information beyond what static images can provide.

    - If queried with a single protein, the network includes the query protein and its 10 most likely interactors.
    - If queried with multiple proteins, the network will show interactions among the queried set.
    - If no or very few interactions are returned, try lowering the required_score parameter.
    - If the user refers to "physical interactions", "complexes", or "binding", set the network type to "physical".

    Always display the link as markdown (hide the raw URL).  
    When calling related tools, use the same input parameters unless otherwise specified.

    """
    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species
    if extend_network is not None:
        params["add_white_nodes"] = extend_network
    if required_score is not None:
        params["required_score"] = required_score
    if network_flavor is not None:
        params["network_flavor"] = network_flavor
    if network_type is not None:
        params["network_type"] = network_type
    if hide_disconnected_nodes is not None:
        params["hide_disconnected_nodes"] = hide_disconnected_nodes

    endpoint = f"/api/json/get_link"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        log_response_size(results)
        return {"results": results}


@mcp.tool(title="STRING: Get homologs in specified target species")
async def string_homology(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None,
    species_b: Annotated[
        Optional[str],
        Field(description="Optional. One or more NCBI taxon IDs for target species, separated by comma (e.g. 9606,7227,4932 for human, fly, and yeast).")
    ] = None
) -> dict:
    """
    Retrieves pairwise protein similarity scores (Smith–Waterman bit scores) for the query proteins.  
    
    - If no target species (`species_b`) is provided, results are intra-species (within the query species).  
    - To retrieve homologs in other species or clades (e.g. vertebrates, yeast, plants), specify one or more NCBI taxon IDs in `species_b`.  
    - Multiple target species are supported; ask the user to clarify if needed.  
    - Always report species names together with their taxon IDs.  
    - Bit scores < 50 are not reported.  
    - Results are truncated to the top 50 proteins per input protein.
    """

    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species

    if species_b is not None:
        params["species_b"] = species_b

    endpoint = f"/api/json/homology_all"
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        log_response_size(results)
        return {"results": results}


@mcp.tool(title="STRING: Get links to interaction evidence pages")
async def string_interaction_evidence(
    identifier_a: Annotated[
        str,
        Field(description="Required. Protein A identifier.")
    ],
    identifiers_b: Annotated[
        str,
        Field(description="Required. One or more protein B identifiers, separated by %0d.")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None,
) -> dict:
    """
    Use this tool when the user asks for interaction **evidence** between proteins.
    
    It generates direct links to STRING’s evidence pages, which show the sources and scores (e.g., co-expression, experiments, databases) behind each predicted interaction.
    Show this link to the user with a markdown. 
    
    You must provide:
    - One query protein (A)
    - One or more target proteins (B), separated by `%0d`
    - The species (NCBI taxon ID)
    
    This tool is especially helpful when users ask:
    - "Can you show me the evidence for this interaction?"
    - "What supports the interaction between TP53 and MDM2?"
    - "Where can I see experimental validation for these pairs?"
    
    Each returned link corresponds to one A–B interaction.
    """

    identifiers_b = identifiers_b.replace('%0D', '%0d')

    output = []
    for identifier_b in identifiers_b.split("%0d"):
        link = f"{base_url}/interaction/{identifier_a}/{identifier_b}?species={species}"
        output.append(link)

    log_response_size(output)
    return {"results": output}



@mcp.tool(title="STRING: Functional enrichment analysis")
async def string_enrichment(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        Optional[str],
        Field(description="Optional. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX). DO NOT SET unless user explicitly requests.")
    ] = None
) -> dict:
    """This tool retrieves functional enrichment for a set of proteins using STRING.

    - If queried with a single protein, the tool expands the query to include the protein’s 10 most likely interactors; enrichment is performed on this set, not the original single protein.
    - For two or more proteins, enrichment is performed on the exact input set.
    - When calling related tools, use the same input parameters unless otherwise specified.
    - Focus summaries on the top categories and most relevant terms for the results. Always report FDR for each claim.
    - Report FDR as a human-readable value (e.g. 2.3e-5 or 0.023).
    - Remember to suggest showing an enrichment graph for a specific category of user interest (e.g., GO, KEGG)

    Output fields (per enriched term):
      - category: Term category (e.g., GO Process, KEGG pathway)
      - term: Enriched term (GO ID, domain, or pathway)
      - number_of_genes: Number of input genes with this term
      - number_of_genes_in_background: Number of background genes with this term
      - ncbiTaxonId: NCBI taxon ID
      - inputGenes: Gene names from your input
      - preferredNames: Protein names matching your input order
      - p_value: Raw p-value
      - fdr: False Discovery Rate (B-H corrected p-value)
      - description: Description of the enriched term
    """
    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/enrichment"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        if 'error' in results:
            log_response_size(results)
            return results
        else:
            results_truncated = truncate_enrichment(results, 'json')

        if not results_truncated:
            print("HELLO!!!")
            results_truncated = [
                    "AGENT MUST tell the user: No statistically significant enrichment was observed. "
                    "This means the proteins in their list do not group into known pathways or functions "
                    "more than would be expected by random chance."
            ]

        log_response_size(results_truncated)
        return {"results": results_truncated}


@mcp.tool(title="STRING: Retrieve functional annotations for proteins")
async def string_functional_annotation(
    identifiers: Annotated[
        str,
        Field(description="Separate multiple protein queries by %0d. e.g. SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None,
) -> dict:
    """
    This tool retrieves curated functional annotations for a set of proteins.
    
    Each input protein is mapped to known biological terms from ontologies, pathway databases, tissues, compartments and domains — such as Gene Ontology (GO), KEGG, and UniProt Keywords.
    
    - Use this when the user asks what a protein does, where it's localized, expressed, or which pathways it participates in.
    - Keep the output short and focused by highlighting a few diverse and specific annotations for each protein.
    - This tool does not perform statistical enrichment — use the enrichment tool for that.
    
    Output fields (per protein):
      - stringId: STRING protein identifier
      - preferredName: Gene name or alias
      - annotation: Functional description or keyword
      - category: Source category (e.g. GO, KEGG, Keyword)
      - term: Functional term or ID
    """

    endpoint = "/api/json/functional_annotation"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        params = {"identifiers": identifiers, "species": species}
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        if 'error' in results:
            log_response_size(results)
            return results
        else:
             results_truncated = sort_and_truncate_functional_annotation(results, 'json')

        log_response_size(results_truncated)
        return {"results": results_truncated}  # Functional annotation per protein


@mcp.tool(title="STRING: Get enrichment result figure (image URL)")
async def string_enrichment_image_url(
    identifiers: Annotated[
        str,
        Field(description="Required. Protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX).")
    ] = None,
    category: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional. Term category for enrichment. "
                "Valid options: "
                "'Process' (GO Biological Process), "
                "'Function' (GO Molecular Function), "
                "'Component' (GO Cellular Component), "
                "'Keyword' (UniProt Keywords), "
                "'KEGG' (KEGG Pathways), "
                "'RCTM' (Reactome Pathways), "
                "'HPO' (Human Phenotype, Monarch), "
                "'MPO' (Mammalian Phenotype Ontology), "
                "'DPO' (Drosophila Phenotype Ontology), "
                "'WPO' (C. elegans Phenotype Ontology), "
                "'ZPO' (Zebrafish Phenotype Ontology), "
                "'FYPO' (Fission Yeast Phenotype Ontology), "
                "'Pfam' (Pfam domains), "
                "'SMART' (SMART domains), "
                "'InterPro' (InterPro domains/features), "
                "'PMID' (PubMed references), "
                "'NetworkNeighborAL' (Local Network Cluster), "
                "'COMPARTMENTS' (Subcellular Localization), "
                "'TISSUES' (Tissue Expression), "
                "'DISEASES' (Disease-gene Associations), "
                "'WikiPathways' (WikiPathways). "
                "Default: 'Process' (GO Biological Process)."
            )
        )
    ] = None,
    group_by_similarity: Annotated[
        Optional[float],
        Field(description="Optional. Group similar terms on the plot; threshold 0.1-1 (default: no grouping).")
    ] = None,
    color_palette: Annotated[
        Optional[str],
        Field(description='Optional. Color palette for FDR (e.g., "mint_blue", "lime_emerald", etc.; default: "mint_blue").')
    ] = None,
    number_of_term_shown: Annotated[
        Optional[int],
        Field(description="Optional. Max number of terms shown on plot (default: 10).")
    ] = None,
    x_axis: Annotated[
        Optional[str],
        Field(description='Optional. X-axis variable/order: "signal", "strength", "FDR", or "gene_count" (default: "signal").')
    ] = None
) -> dict:
    """Retrieves the STRING enrichment figure image *URL* for a set of proteins.

    Only embed the image if a valid URL is present in the response; otherwise, do not embed or show a link.

    See the `category` parameter for a list of valid category options.
    """
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if category is not None:
        params["category"] = category
    if group_by_similarity is not None:
        params["group_by_similarity"] = group_by_similarity
    if color_palette is not None:
        params["color_palette"] = color_palette
    if number_of_term_shown is not None:
        params["number_of_term_shown"] = number_of_term_shown
    if x_axis is not None:
        params["x_axis"] = x_axis

    endpoint = f"/api/json/enrichment_image_url"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        log_response_size(results)
        return {"results": results}


@mcp.tool(title="STRING: Protein–protein interaction (PPI) enrichment")
async def string_ppi_enrichment(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Minimum interaction confidence score (0-1000). DO NOT SET unless user explicitly requests.")
    ] = None,
) -> dict:
    """
    This tool tests if your network is enriched in protein-protein interactions compared to the background proteome-wide distribution (i.e., if your proteins are more functionally connected than expected by chance).

    - The enrichment is assessed using the actual observed edges versus expected edges in a random network of the same size.
    - The p-value reflects the likelihood that your observed number of interactions would occur by chance.
    - Report the p-value as a human-readable value (e.g. 2.3e-5 or 0.023).

    When calling related tools use the same input parameters unless otherwise specified.

    Output fields:
      - number_of_nodes: Number of proteins in your network
      - number_of_edges: Number of observed edges/interactions
      - average_node_degree: Mean degree (average number of interactions per node)
      - local_clustering_coefficient: Average clustering coefficient in the network
      - expected_number_of_edges: Expected number of edges in a random network of the same size
      - p_value: p-value for network enrichment (smaller = more enriched)

    Example identifiers: "SMO%0dTP53"
    """
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if required_score is not None:
        params["required_score"] = required_score

    endpoint = f"/api/json/ppi_enrichment"
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        log_response_size(results)
        return {"results": results}


@mcp.tool(title="STRING: Retrieve proteins associated with a functional term")
async def string_proteins_for_term(
    term_text: Annotated[
        str,
        Field(description=(
            "Required. Functional term identifier (GO, KEGG, Reactome, etc.) "
            "or descriptive free text (e.g. 'hsa05218', 'Melanoma', 'GO:0008543', 'Fibroblast growth factor')."
        ))
    ],
    species: Annotated[
        str,
        Field(description=(
            "NCBI/STRING taxonomy ID. This tool only supports one species per call. "
            "It cannot return results across multiple species or identify the species "
            "with the most/fewest proteins. For such questions, run this tool separately "
            "for each species and then compare the results. "
            "Default is 9606 (human). Examples: 10090 for mouse, or STRG0AXXXXX for uploaded genomes."
        ))
    ] = "9606"
) -> dict:
    """
    Retrieve proteins annotated with a functional term or descriptive text in a single species.  
    You can query for tissues, compartments, diseases, processes, pathways, and domains.  
    
    IMPORTANT: For cross-species comparisons, run this tool separately for each species.  
    Select relevant model organisms to search or ask user to provide the selection.
    The results reflect annotation depth within each category; use caution when interpreting.
    
    If no results are found, try simplifying the query.  
    For tissue queries, follow BRENDA tissue nomenclature and omit the word "tissue"  
    (e.g. use "skin" instead of "skin tissue").

    Output fields:
      - category: Source database of the matched functional term
                  (e.g. GO, KEGG, Reactome, Pfam, InterPro).
      - term: Exact identifier for the functional term.
      - description: The free text description of the term.
      - proteinCount: Number of proteins annotated with that term
      - preferredNames: List of human-readable protein names (truncated to first 100)
      - stringIds: List of STRING protein identifiers (truncated to first 100)

    """
    params = {"term_text": term_text, "species": species}

    endpoint = "/api/json/functional_terms"
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        results_truncated = truncate_functional_terms(results, 'json')
        log_response_size(results_truncated)
        return {"results": results_truncated}


# ---- MCP server helper functions ----


def truncate_enrichment(data, is_json):
    term_cutoff = 20   # max terms per category
    size_cutoff = 15   # max proteins listed per term

    if is_json.lower() == 'json':
        filtered_data = []
        category_count = defaultdict(int)

        for row in data:
            category = row['category']
            category_count[category] += 1

            # Skip if we already hit the cap for this category
            if category_count[category] > term_cutoff:
                continue

            # Save total before truncation
            row['inputGenes_total'] = len(row['inputGenes'])
            row['preferredNames_total'] = len(row['preferredNames'])

            if len(row['inputGenes']) > size_cutoff:
                row['inputGenes'] = row['inputGenes'][:size_cutoff] + ["..."]
                row['preferredNames'] = row['preferredNames'][:size_cutoff] + ["..."]
                row['truncated'] = True
            else:
                row['truncated'] = False

            filtered_data.append(row)

        data = filtered_data

    return data


def truncate_network(data, input_score_threshold=None, is_json="json", size_cutoff=100):
    original_len = len(data)

    if is_json.lower() != "json":
        return data

    # Determine threshold
    try:
        threshold = float(input_score_threshold)
    except (TypeError, ValueError):
        threshold = 400.0 

    if threshold > 1:
        score_threshold = threshold / 1000.0
    else:
        score_threshold = threshold

    # keep only items above threshold
    filtered = [row for row in data if row.get("score", 0) >= score_threshold]

    # sort by score descending
    filtered.sort(key=lambda r: r.get("score", 0), reverse=True)

    # truncate if needed
    if len(filtered) > size_cutoff:
        filtered = filtered[:size_cutoff]
        filtered.insert(0, {"note": f"The list was truncated to top {size_cutoff} interactions."})

    # add note if threshold was adjusted
    if len(filtered) < original_len and score_threshold != input_score_threshold:
        filtered.insert(0, {"note": f"Required score {score_threshold} was applied."})

    return filtered


def sort_and_truncate_functional_annotation(data, is_json):

    size_cutoff = 50

    if is_json.lower() == 'json':
        
 
        data = sorted(data, key=lambda x: x["ratio_in_set"], reverse=True)
        
        if len(data) > size_cutoff:
            data = data[:size_cutoff]
            data.insert(0, {"note": f"The list was truncated to first {size_cutoff} terms..."})

    return data
 
def truncate_functional_terms(data, is_json):
    term_size_cutoff = 10
    protein_size_cutoff_top = 100    # cap for top terms
    protein_size_cutoff_rest = 25    # cap for later terms

    if is_json.lower() == 'json':
        filtered_data = []

        for i, row in enumerate(data[:term_size_cutoff]):
            if i < 3:
                # top terms: allow up to 500
                if len(row['preferredNames']) > protein_size_cutoff_top:
                    row['preferredNames'] = row['preferredNames'][:protein_size_cutoff_top] + ["..."]
                    row['stringIds'] = row['stringIds'][:protein_size_cutoff_top] + ["..."]
                    row['truncated'] = True
                else:
                    row['truncated'] = False
            else:
                # later terms: allow only 50
                if len(row['preferredNames']) > protein_size_cutoff_rest:
                    row['preferredNames'] = row['preferredNames'][:protein_size_cutoff_rest] + ["..."]
                    row['stringIds'] = row['stringIds'][:protein_size_cutoff_rest] + ["..."]
                    row['truncated'] = True
                else:
                    row['truncated'] = False

            filtered_data.append(row)

        data = filtered_data

    return data

def log_response_size(resp):
    if log_verbosity['size']:
        print("Response size:", object_size(resp), file=sys.stderr)

def object_size(obj):
    if isinstance(obj, str):
        return len(obj)
    elif isinstance(obj, (int, float)):
        return len(str(obj))
    elif isinstance(obj, dict):
        return sum(object_size(v) for v in obj.values())
    elif isinstance(obj, list):
        return sum(object_size(v) for v in obj)
    else:
        return 0

@mcp.tool(title="STRING: Query species and clades in STRING")
async def string_query_species(
    species_text: Annotated[
        str,
        Field(description=(
            "Required. Free-text name of a species or clade to search in STRING. "
            "Examples: 'human', 'mouse', 'vertebrates'. "
            "Partial matches are allowed."
        ))
    ],
) -> dict:
    """
    Search for species or clades available in STRING by free-text query
    and return their NCBI taxonomy IDs.
    
    - Use this when the user asks which species or clades are present in STRING,
      or when you need the correct NCBI taxon ID to pass to other tools.
    - The results are limited to the top 50 matches.
    - When the user asks for a species list, do not list clades.
    - If the requested species cannot be matched (i.e. the correct species is not present
      in the results), **immediately invoke the 'string_help' tool with topic='missing_species'**.
    """
    endpoint = "/api/json/query_species_names"
    params = {"species_text": species_text, 'limit': 50, 'add_sps':'t'}

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        log_response_size(results)
        return {"results": results}



@mcp.tool(title="STRING: Help / FAQ")
async def string_help(
    topic: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional help topic to display. "
                "Examples: 'gsea', 'clustering', 'scores', 'large_input' ... "
                "If omitted, returns a list of available topics."
            )
        ),
    ] = None
) -> dict:
    """
    Provides explanatory text for STRING features and limitations.  
    **Use this tool when:**
      - The user asks about functionality **not available via MCP tools**  
        (e.g. clustes/modules, GSEA, sequence search, regulatory networks).  
      - The user request is ambiguous or outside the agent’s scope.  

    Topics include: gsea, clustering, scores, large_input, missing_proteins, missing_species, proteome_annotation, sequence_search, regulatory_networks.
    """
    if topic is None:
        return {"topics": list(HELP_TOPICS.keys())}

    key = topic.lower()
    if key not in HELP_TOPICS:
        return {
            "error": f"Unknown topic '{topic}'. Available: {', '.join(HELP_TOPICS.keys())}."
        }

    return {"topic": key, "text": HELP_TOPICS[key]}


def log_call(endpoint, params):

    if log_verbosity['call']:
        print(f"Call: {endpoint}", file=sys.stderr)

    if log_verbosity['taskid']:
        headers = get_http_headers()
        client_id = headers.get("x-client-id")
        task_id = headers.get("x-task-id")

        print("TaskId:", task_id, file=sys.stderr)
        print("ClientId:", client_id, file=sys.stderr)
 
    if log_verbosity['params']:
        print("Params:", file=sys.stderr)
        for param, value in params.items():
            print(f'    {param}: {str(value)}', file=sys.stderr)


# ---- MCP server runner ----

if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=server_port,
        log_level="info",
        stateless_http=True,
    )

