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
import time
import httpx
import asyncio
import traceback

from collections import defaultdict
from typing import Annotated, Optional

from pydantic import Field
from fastmcp import FastMCP

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

timeout = float(config.get("timeout", 100))


## logging verbosity ## 

log_verbosity = {}
log_verbosity['call'] = False
log_verbosity['params'] = False
log_verbosity["size"] =  False


if 'verbosity' in config:

    if config['verbosity'] == 'full':
        log_verbosity['call'] = True
        log_verbosity['params'] = True
        log_verbosity['size'] = True

    if config['verbosity'] == 'low':
        log_verbosity['call'] = True
        log_verbosity['params'] = False
        log_verbosity['size'] = True


async def _post_json(client: httpx.AsyncClient, endpoint: str, data: dict):
    """
    POST form data to a STRING API endpoint and return JSON.
    Emits periodic 'ping' SSE events to keep upstream connections alive (e.g. Cloudflare).
    """
    params = data
    ping_interval = 25  # seconds between pings

    async def _ping_loop(done_event: asyncio.Event):
        try:
            while not done_event.is_set():
                await asyncio.sleep(ping_interval)
                if not done_event.is_set():
                    print(json.dumps({"type": "ping", "message": "waiting..."}), flush=True)
                    print("[_post_json] ping (still waiting for response)", file=sys.stderr, flush=True)
        except asyncio.CancelledError:
            pass

    done_event = asyncio.Event()
    ping_task = asyncio.create_task(_ping_loop(done_event))

    try:
        response = await client.post(endpoint, data=params)
        response.raise_for_status()
        try:
            return response.json()
        except ValueError:
            return {"result": response.text}

    except httpx.ReadTimeout:
        # Specific handling for slow or non-responsive STRING API calls
        sys.stderr.write(f"[timeout] STRING API request timed out at {endpoint}\n")
        error_payload = {
            "error": {
                "type": "timeout_error",
                "message": f"STRING API request to {endpoint} timed out.",
                "hints": [
                    "Try narrowing the taxon",
                    "Limiting the number of proteins",
                    "Requery the API again",
                ],
                "diagnostics": {"params_sent": {k: v for k, v in params.items()}},
            }
        }
        sys.stderr.write(
            f"[handled] Returned payload after timeout: {json.dumps(error_payload, ensure_ascii=False)}\n"
        )
        return error_payload

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
                )
            elif not params.get("identifiers"):
                hints.append("Missing 'identifiers'.")
            else:
                hints.append(
                    "Species might be not present in STRING. Search string_query_species with a name "
                    "or invoke 'string_help' with topic='missing_species'. "
                    "For multiple-protein queries make sure the delimiter is '%0d'. "
                )
        elif status == 404:
            hints.append(
                "The provided identifiers could not be mapped in STRING. "
                "Use 'string_resolve_proteins' first to resolve ambiguous names. "
                "For multiple-protein queries make sure the delimiter is '%0d'. "
            )

        error_payload = {
            "error": {
                "type": "string_api_error",
                "message": f"STRING API request failed with status {status}.",
                "hints": hints or ["Check parameters and retry."],
                "diagnostics": diagnostics,
            }
        }

        sys.stderr.write(
            f"[handled] HTTPStatusError {status} at {endpoint} with params={params}\n"
            f"[handled] Returned payload: {json.dumps(error_payload, ensure_ascii=False)}\n"
        )
        return error_payload

    except Exception as e:
        traceback.print_exc(file=sys.stderr)
        error_payload = {
            "error": {
                "type": "unexpected_error",
                "message": "Unexpected error in STRING API call.",
                "diagnostics": {"params_sent": {k: v for k, v in params.items()}},
            }
        }
        sys.stderr.write(
            f"[handled] Unexpected exception {type(e).__name__} at {endpoint} with params={params}\n"
            f"[handled] Returned payload: {json.dumps(error_payload, ensure_ascii=False)}\n"
        )
        return error_payload

    finally:
        # stop the ping loop cleanly
        done_event.set()
        ping_task.cancel()


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
    ] = None,
    show_sequence: Annotated[
        str,
        Field(
            description=(
                "Optional. '1' to include sequences (default '0'). Use only if the user requests sequence data."
            )
        )
    ] = None
) -> dict:
    """
    Maps one or more protein identifiers to their corresponding STRING metadata, including:
    gene symbol, description, sequence, domains, species, and internal STRING ID.

    This method is useful for translating raw identifiers into readable, annotated protein entries.

    Example input: "TP53%0dSMO"
    """

   
    params = {"identifiers": proteins, "echo_query": 1, 'add_domains': 1}
    if species is not None:
        params["species"] = species

    if show_sequence is not None:
        params["add_sequence"] = show_sequence

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
    
    For large query sets (>50 proteins), consider increasing the `required_score` (e.g. ≥700) 
    to focus on high-confidence interactions and avoid overly dense networks.
    
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
    add_shared_note = False

    if not required_score and len(proteins.lower().split("%0d")) <= 5:
        params["required_score"] = 0
        required_score = 0
        add_score_note = True
 
    if len(proteins.lower().split('%0d')) == 2 and extend_network is None:
        params['add_white_nodes'] = 5
        add_shared_note = True

    endpoint = "/api/json/network"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        if 'error' in results: return results
        else:
            formatted_network = format_query_set_network(results, required_score)

        notes = []


        if add_score_note:
            notes.append("The required_score parameter was lowered to 0 - showing all interactions. "
                         "IMPORTANT: If the interaction score is low (below 400), inform user about it.")
        if not len(formatted_network["network"]):
             notes.append(f"No interactions found in STRING database at that {required_score} cut-off.")

        notes.extend(formatted_network["notes"])
     
        if add_shared_note:
            notes.append(
                "For two-protein queries, the network was expanded by five additional proteins to reveal possible shared or indirect interactions between the queried proteins. "
                "Verify whether direct or indirect interactions exist within this network, and inform the user accordingly."
            )

        response = {
            "notes": notes,
            "network_summary": formatted_network["network_summary"],
            "network": formatted_network["network"],
        }

        if formatted_network["node_interaction_counts"]:
            response["node_interaction_counts"] = formatted_network["node_interaction_counts"]

        if formatted_network["edge_sample"]:
            response["edge_sample"] = formatted_network["edge_sample"]

        log_response_size(response)

        return response


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

    params = {"identifiers": identifiers, "limit": 0}

    if species is not None:
        params["species"] = species
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
            formatted_interactions = format_interaction_partners(results, required_score)

        notes = []

        notes.extend(formatted_interactions["notes"])

        if not len(formatted_interactions["interactions"]):
             notes.append(f"No interactions found in STRING database at that {required_score} cut-off. Consider lowering the required_score.")

        response = {
            "notes": notes,
            "node_summary": formatted_interactions["node_summary"],
            "interactions": formatted_interactions["interactions"],
        }
        
        log_response_size(response)
        return response


@mcp.tool(title="STRING: Get interaction network image (image URL)")
async def string_visual_network(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein IDs, optionally followed by one numeric value per protein. Example:\n"
                  "PTEN 0.234\nSMO -3.445\n"
                  "Use newline (%0d) between entries. Tabs and spaces are accepted as separators.")
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
        Field(description="Optional. Threshold of significance to include an interaction (0-1000). Default: 400. Increase for large queries to 700.")
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical" (co-complex).')
    ] = None,
    network_flavor: Annotated[
        Optional[str],
        Field(description='Optional. Edge style: "evidence" (default), "confidence" (recommended for large queries, e.g. >100 proteins), or "actions".')
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
    do_not_show_structures: Annotated[
        Optional[int],
        Field(description="Optional. 1 remove small protein structure previews from inside the node bubbles. DO NOT SET unless user explicitly requests.")
    ] = None,
 
    #custom_label_font_size: Annotated[
    #    Optional[int],
    #    Field(description="Optional. Change font size of protein names (from 5 to 50, default: 12). DO NOT SET unless user explicitly requests.")
    #] = None
) -> dict:
    """
    Retrieves a URL to a **STRING interaction network image** for one or more proteins.
    
    - For a single protein: includes the protein and its top 10 most likely interactors.
    - For multiple proteins: includes all known interactions **within the query set**.
    - If the user asks for "physical interactions", "complexes", or "binding", set `network_type` to "physical".
    
    The input may include one numeric value per protein, such as fold change, effect size, or score.
    These values are visualized as colored halos around the nodes, allowing overlay of protein-level measurements on the network.
    
    Example:
    PTEN 2.1
    SMO -1.3
    
    If numeric values are provided:
    - positive values are shown in blue
    - negative values are shown in red
    - larger absolute values produce stronger halo intensity
    
    If the user provides numeric values together with the proteins, preserve them in the query.
    
    If few or no interactions are shown, consider lowering `required_score`.
    
    For large queries (>100 proteins):
    - use `network_flavor="confidence"`
    - increase `required_score` (e.g. 700)
    
    Always ask if the user also wants a link to the interactive STRING network page.
    
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
    if do_not_show_structures is not None:
        params["block_structure_pics_in_bubbles"] = do_not_show_structures
    #if show_query_node_labels is not None:
    #    params["show_query_node_labels"] = show_query_node_labels
    if center_node_labels is not None:
        params["center_node_labels"] = center_node_labels
    #if custom_label_font_size is not None:
    #    params["custom_label_font_size"] = custom_label_font_size

    endpoint = f"/api/json/network_image_url"

    add_score_note = False
    add_shared_note = False

    if not required_score and len(proteins.lower().split("%0d")) <= 5:
        params["required_score"] = 0
        add_score_note = True
   
    if len(proteins.lower().split('%0d')) == 2 and extend_network is None:
        params['add_white_nodes'] = 5
        add_shared_note = True


    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        notes = []

        if add_score_note:
            notes.append("For small queries, the `required_score` parameter was lowered to 0.")
        notes.append("The generated image is only a visualization — it does not constitute evidence of interaction. "
                     "Always verify interactions using `string_interactions_query_set` with the same parameters.")

        if add_shared_note:
            notes.append(
                "For two-protein queries, the network was expanded by five additional proteins to reveal possible shared or indirect interactions between the queried proteins. "
                "Use `string_interactions_query_set` with the same parameters to verify whether direct or indirect interactions are present.")

        notes.append("Embed the returned image link directly in the assistant response as a markdown image.")

 
        log_response_size(results)

        return {"notes": notes, "image_url": results}


@mcp.tool(title="STRING: Perform network clustering")
async def string_network_clustering(
    proteins: Annotated[
        str,
        Field(description=(
            "Required. One or more protein identifiers (optionally with values). Example:\n"
            "PTEN 0.234\nSMO -3.445\n"
            "Separate entries with newline (%0d). "
            "Numeric values (e.g. expression data) can be provided after identifiers."
        ))
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxonomy ID (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None,
    extend_network: Annotated[
        Optional[int],
        Field(description="Optional. Add specified number of additional nodes to the network based on their interaction scores (default: 0, or 10 for single-protein queries).")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Minimum interaction confidence score (0–1000). Lower values show more edges. Default: 400.")
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical" (co-complex).')
    ] = None,
    clustering_algorithm: Annotated[
        Optional[str],
        Field(description=(
            "Optional. Clustering algorithm: 'MCL' or 'kmeans'.\n"
            "- 'MCL' (Markov Cluster Algorithm) identifies densely connected subnetworks based on connectivity flow; "
            "- 'kmeans' partitions proteins into a fixed number of clusters, useful when explicit cluster counts are desired; "
       ))
    ] = None,
    
    clustering_parameter: Annotated[
        Optional[float],
        Field(description=(
            "Optional. Controls the clustering granularity:\n"
            "- For 'MCL': inflation parameter (1.0–10.0, default 3.0); higher values produce more, smaller clusters.\n"
            "- For 'kmeans': number of clusters (integer ≥2, default 3).\n"
        ))
    ] = None,
    network_flavor: Annotated[
        Optional[str],
        Field(description='Optional. Edge display style: "evidence" (default), "confidence", or "actions".')
    ] = None,
    hide_disconnected_nodes: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide unconnected nodes, 0 otherwise (default: 0). Use only if user explicitly requests it.")
    ] = None,
    center_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 to center protein labels on nodes, 0 otherwise (default: 0). Use only if user explicitly requests it.")
    ] = None,
) -> dict:
    """
    Performs **network clustering** on a STRING interaction network and returns both a **network image URL**
    and details about each detected cluster.
    
    Use the same parameters as in the network creation step to ensure consistency.
    If the network already contains disconnected subgraphs, the resulting number of clusters may differ from the requested value.
    
    Dashed lines represent connections between clusters, while solid lines indicate interactions within clusters.
    
    Notes:
      - For small queries (≤5 proteins), the `required_score` parameter is automatically lowered to 0.
      - If only a single cluster is produced, try increasing `required_score`, adjusting the inflation parameter,
        or switching to `kmeans` for small, highly interconnected networks.


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


    # default
    if not clustering_algorithm:
        clustering_algorithm = 'MCL'

    # fix casing

    if clustering_algorithm.lower() == 'kmeans': clustering_algorithm = 'kmeans'
    if clustering_algorithm.lower() == 'mcl': clustering_algorithm = 'MCL'

    if clustering_algorithm not in ['MCL', 'kmeans']:
        clustering_algorithm = 'MCL'

    params['network_clustering_algorithm'] = clustering_algorithm

    # parse parameters

    if clustering_algorithm == 'kmeans':

        try:
            clustering_parameter = float(int(clustering_parameter))
        except Exception:
            clustering_parameter = 3

        params['network_clustering_parameter_kmeans'] = clustering_parameter

    if clustering_algorithm == 'MCL':

        try:
            clustering_parameter = float(clustering_parameter)
            clustering_parameter = max(1, min(10, clustering_parameter))
        except Exception:
            clustering_parameter = 3

        params['network_clustering_parameter_mcl'] = clustering_parameter


    if center_node_labels is not None:
        params["center_node_labels"] = center_node_labels

    endpoint = f"/api/json/network_image_url"

    add_score_note = False
    if not required_score and len(proteins.lower().split("%0d")) <= 5:
        params["required_score"] = 0
        add_score_note = True

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        notes = []
        if add_score_note:
            notes.append("For small queries, the required_score parameter is automatically lowered to 0.")
        notes.append("Embed the returned image link directly in the assistant response as a markdown image.")

        log_response_size(results)

        image_url = None
        if results and isinstance(results, list) and "imageURL" in results[0]:
            image_url = results[0].get("imageURL")
            for cluster in results:
                cluster.pop("imageURL", None)
        
        # If only one cluster detected, suggest tuning parameters
        if results and isinstance(results, list) and len(results) == 1:
            notes.append(
                "Only one cluster was detected. Suggest increasing `required_score`, raising the inflation parameter, "
                "or switching to `kmeans` to force multiple clusters."
            )

        return {
            "image_url": image_url,
            "clusters": results,
            "notes": notes,
        }




@mcp.tool(title="STRING: Get interactive network link (web UI)")
async def string_network_link(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein IDs, optionally followed by one numeric value per protein. Example:\n"
                  "PTEN 0.234\nSMO -3.445\n"
                  "Use newline (%0d) between entries. Tabs and spaces are accepted as separators.")
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
        Field(description='Optional. Edge style: "evidence" (default) or "confidence".')
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
    
    - For a single protein: includes the protein and its top 10 most likely interactors.
    - For multiple proteins: includes all known interactions **within the query set**.
    - If the user asks for "physical interactions", "complexes", or "binding", set `network_type` to "physical".
    
    The input may include one numeric value per protein, such as fold change, effect size, or score.
    These values are visualized as colored halos around the nodes, allowing overlay of protein-level measurements on the network.
    
    Example:
    PTEN 2.1
    SMO -1.3
    
    If numeric values are provided:
    - positive values are shown in blue
    - negative values are shown in red
    - larger absolute values produce stronger halo intensity
    
    If the user provides numeric values together with the proteins, preserve them in the query.
    
    If few or no interactions are shown, consider lowering `required_score`.
    
    For large queries (>100 proteins):
    - use `network_flavor="confidence"`
    - increase `required_score` (e.g. 700)
    
    Always display the link as a markdown hyperlink (hide the raw URL).
    
    Input parameters should match those used in related STRING tools unless otherwise specified.
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


    add_score_note = False
    add_shared_note = False

    if len(proteins.lower().split('%0d')) == 2 and extend_network is None:
        params['add_white_nodes'] = 5
        add_shared_note = True

    if not required_score and len(proteins.lower().split("%0d")) <= 5:
        params["required_score"] = 0
        add_score_note = True

    endpoint = f"/api/json/get_link"

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)

        notes = []
        if add_score_note:
            notes.append(f"For small queries the required_score parameter is lowered to 0.")

        if add_shared_note:
            notes.append(
                "For two-protein queries, the network was expanded by five additional proteins to reveal possible shared or indirect interactions between the queried proteins."
            )
 

        notes.append("Embed the returned link directly in the assistant response as a markdown hyperlink.")
 
        log_response_size(results)

        return {"notes": notes, "results": results}


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
        if 'error' in results:
            log_response_size(results)
            return results
        grouped_results = group_homology_results(results)

        log_response_size(grouped_results)
        return {"results": grouped_results}


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
    Retrieves direct links to STRING evidence pages for protein–protein interactions.
    
    Use this tool when the user asks for **details**, **evidence**, or **experimental validation** of an interaction between proteins.
    
    It returns URLs linking to STRING’s evidence pages, which display the underlying data sources 
    (experimental results, publications, and curated databases) supporting each predicted interaction.  
    NOTE: A link is returned for every A–B protein pair, **even if no evidence or interaction exists** — the link itself should not be interpreted as proof of interaction.
    
    Show each link to the user as a markdown hyperlink.
    
    Parameters:
    - **identifier_a**: Query protein identifier (Protein A)
    - **identifiers_b**: One or more target protein identifiers (Protein B), separated by `%0d`
    - **species**: NCBI taxonomy ID (e.g. `9606` for human or `10090` for mouse)
    
    Typical user questions that should trigger this tool:
    - "Can you show me the evidence for this interaction?"
    - "Show me the details supporting this interaction."
    - "What supports the interaction between TP53 and MDM2?"
    - "Is there experimental validation for this interaction?"
    - "Where can I find the STRING evidence page for this pair?"
    """

    identifiers_b = identifiers_b.replace('%0D', '%0d')

    output = []
    for identifier_b in identifiers_b.split("%0d"):
        link = f"{base_url}/interaction/{identifier_a}/{identifier_b}?species={species}&suppress_disambiguation=1"
        output.append(link)

    notes = []
    notes.append(
        "The links are generated from templates — their existence is not proof of interaction. "
        "Use `string_interactions_query_set` to confirm whether the interaction is supported by STRING evidence."
    )
    notes.append("Embed the returned link(s) directly in the assistant response as a markdown hyperlink.")

    log_response_size(output)
    return {"notes": notes, "results": output}



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
    - IMPORTANT: Remember to suggest showing an enrichment graph for a specific category of user interest (e.g., GO, KEGG)

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
            results_truncated, truncation_notes = truncate_enrichment(results, 'json')

        notes = []
        notes.extend(truncation_notes)
        if not results_truncated:
            notes.append("AGENT MUST tell the user: No statistically significant enrichment was observed. "
                         "This means the proteins in their list do not group into known pathways or functions "
                         "more than would be expected by random chance.")

        log_response_size(results_truncated)
        return {"notes": notes, "results": results_truncated}


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
    detail_for_term: Annotated[
        Optional[str],
        Field(description=(
            "Optional. Exact functional term ID to return with the full list of matching input proteins. "
            "Use this when an overview result says a protein list was shortened or replaced with 'many'."
        ))
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
             results_truncated, truncation_notes = sort_and_truncate_functional_annotation(results, 'json', detail_for_term)

        log_response_size(results_truncated)
        return {"notes": truncation_notes, "results": results_truncated}  # Functional annotation per protein


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

        notes = []
        notes.append(
            "If a valid URL is present in the response, embed it as markdown in the assistant message. "
            "If no valid URL is returned, do not embed or display any link."
        )
 

        return {"notes": notes, "results": results}


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
        if 'error' in results: return results 
        results_truncated, truncation_notes = truncate_functional_terms(results, 'json')
        log_response_size(results_truncated)
        return {"notes": truncation_notes, "results": results_truncated}


@mcp.tool(title="STRING: Search proteins by amino acid sequence")
async def string_sequence_search(
    sequences: Annotated[
        str,
        Field(
            description=(
                "One or more protein sequences in plain or FASTA format."
                "For multiple sequences, use standard FASTA headers (lines beginning with '>'). "
                "Only amino acid sequences are supported — nucleotide sequences are not accepted."
            )
        ),
    ],
    species: Annotated[
        str,
        Field(
            description=(
                "Required. NCBI or STRING taxonomy ID. You can query with a clade or species. "
                "eg.g 2 for bacteria, 7742 for vertebrates, 511145 for E. coli"
            )
        ),
    ] = 9606
) -> dict:
    """
    Searches the STRING database using **amino acid sequences** to identify matching proteins.

    - Accepts a single sequence or multiple sequences in FASTA format.
    - Returns the most similar STRING protein(s) for the specified species, based on sequence similarity.
    - Use this when the protein identifier is unknown or unresolvable by `string_resolve_proteins`.

    """
    params = {"sequences": sequences, "species": species}

    endpoint = "/api/json/similarity_search"
    async with httpx.AsyncClient(base_url=base_url, timeout=timeout*2) as client:
        log_call(endpoint, params)
        results = await _post_json(client, endpoint, data=params)
        results_truncated, add_trancation_note, total_hits = truncate_similarity_search(results)

        notes = []
        if add_trancation_note:
            notes.append(f"Results truncated to {len(results_truncated)} rows from {total_hits} original rows for readability. "
                         "If you provided multiple sequences, only the top hits are shown per query. "
                         "Ranking is based on bitscore; lower-scoring hits were omitted.")
            
        log_response_size(results_truncated)
        return {"notes": notes, "results": results_truncated}

@mcp.tool(title="STRING: Query species and clades in STRING")
async def string_query_species(
    species_text: Annotated[
        str,
        Field(description=(
            "Required. Free-text name of a species, clade or taxon id to search in STRING. "
            "Examples: 'human', 'mouse', 'vertebrates', '511145' "
            "Partial matches are allowed."
        ))
    ],
) -> dict:
    """
    Search for species or clades available in STRING by free-text query
    and return their NCBI taxonomy IDs.
    
    - Use this when the user asks which species or clades are present in STRING,
      or when you need the correct NCBI taxon ID to pass to other tools.
    - use this to resolve NCBI taxons IDs to their scientific names.
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
        truncated_results = truncate_species_results(results)
         
        log_response_size(truncated_results)
        return {"results": truncated_results}


@mcp.tool(title="STRING: Help / FAQ")
async def string_help(
    topic: Annotated[
        str,
        Field(
            description=(
                "Help topic to display. Choose one of:\n"
                "  how_to_use_string, gsea, large_input, scores,\n"
                "  missing_proteins, missing_species, proteome_annotation,\n"
                "  regulatory_networks, line_colors\n\n"
            )
        )
    ],
 ) -> dict:
    """
    Provides explanatory text for STRING features and limitations.
    
    Use this tool when the user question involves:
      - What is STRING is or how to use the tool (how_to_use_string)
      - functionality not available via MCP tools (e.g. GSEA, regulatory networks, large datasets).
      - meaning of the lines in the network (line_colors)
    """
    if topic is None:
        return {"topics": list(HELP_TOPICS.keys())}

    key = topic.lower()
    if key not in HELP_TOPICS:
        return {
            "error": f"Unknown topic '{topic}'. Available: {', '.join(HELP_TOPICS.keys())}."
        }

    return {"topic": key, "text": HELP_TOPICS[key]}


# ---- MCP server helper functions ----


def truncate_enrichment(data, is_json):
    term_cutoff = 20   # max terms per category
    size_cutoff = 15   # max proteins listed per term
    truncation_notes = []

    if is_json.lower() == 'json':
        filtered_data = []
        category_count = defaultdict(int)
        original_rows = len(data)

        for row in data:
            category = row['category']
            category_count[category] += 1

            # Skip if we already hit the cap for this category
            if category_count[category] > term_cutoff:
                continue

            # Save total before truncation
            row['inputGenes_total'] = len(row['inputGenes'])
            row['proteinCount'] = len(row['preferredNames'])

            if len(row['inputGenes']) > size_cutoff:
                row['inputGenes'] = row['inputGenes'][:size_cutoff] + ["..."]
                row['preferredNames'] = row['preferredNames'][:size_cutoff] + ["..."]
                row['truncated'] = True
            else:
                row['truncated'] = False

            filtered_data.append(row)

        if len(filtered_data) < original_rows:
            truncation_notes.append(
                f"Enrichment results were truncated to the top {term_cutoff} terms per category for readability."
            )

        data = filtered_data

    return data, truncation_notes


def truncate_similarity_search(data):


    total_cutoff=50

    if not isinstance(data, list) or not data:
        return data, False, 0

    total_hits = len(data)
    if total_hits <= total_cutoff:
        return data, False, total_hits


    grouped = defaultdict(list)
    for hit in data:
        grouped[hit.get("querySequenceName", "unknown")].append(hit)

    n_queries = len(grouped)
    per_query_cutoff = max(1, int(total_cutoff / n_queries))

    for hits in grouped.values():
        hits.sort(key=lambda x: x.get("bitscore", 0), reverse=True)

    truncated = []
    for query, hits in grouped.items():
        truncated.extend(hits[:per_query_cutoff])

    if len(truncated) <= total_cutoff:
        return truncated, True, total_hits

    truncated = [hits[0] for hits in grouped.values()]

    return truncated, True, total_hits


def truncate_species_results(data):

    if not isinstance(data, list) or not data:
        return data

    truncated = []

    max_per_clade = 200

    for entry in data:
        entry_copy = dict(entry)
        clade = entry_copy.get("speciesInClade", [])

        max_per_clade = int(max_per_clade / 2)
        max_per_clade  = max(5, max_per_clade)

        if isinstance(clade, list):
            entry_copy["speciesInCladeCount"] = len(clade)
            
            if len(clade) > max_per_clade:
                entry_copy["speciesInClade"] = clade[:max_per_clade]
                entry_copy["note"] = (
                    f"speciesInClade list truncated to first {max_per_clade} species."
                )

        truncated.append(entry_copy)

    return truncated


def truncate_network(data, input_score_threshold=None, size_cutoff=100, is_json="json"):
    original_len = len(data)

    if is_json.lower() != "json":
        return data, None

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

    # save the size
    original_size = len(filtered)

    # truncate if needed
    add_size_note = False
    if len(filtered) > size_cutoff:
        filtered = filtered[:size_cutoff]
        add_size_note = True

    return filtered, add_size_note, original_size


def group_homology_results(data):
    if not isinstance(data, list):
        return data

    grouped = {}

    for row in data:
        query_name = row.get("preferredName_A")
        query_string_id = row.get("stringId_A")
        query_taxon = row.get("ncbiTaxonId_A")
        group_key = (query_string_id, query_name, query_taxon)

        if group_key not in grouped:
            grouped[group_key] = {
                "query": query_name,
                "query_stringId": query_string_id,
                "query_taxon": query_taxon,
                "homologs_returned": 0,
                "top_homologs": [],
            }

        grouped[group_key]["top_homologs"].append({
            "name": row.get("preferredName_B"),
            "stringId": row.get("stringId_B"),
            "taxon": row.get("ncbiTaxonId_B"),
            "bitscore": normalize_bitscore(row.get("bitscore")),
        })
        grouped[group_key]["homologs_returned"] += 1

    return list(grouped.values())


def normalize_bitscore(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        if isinstance(value, str):
            normalized = value.replace("&lt;", "<").replace("&nbsp;", " ").strip()
            return normalized
        return value


NETWORK_SCORE_CHANNELS = {
    "nscore": "neighborhood",
    "fscore": "fusion",
    "pscore": "phylogenetic_profile",
    "ascore": "coexpression",
    "escore": "experiments",
    "dscore": "databases",
    "tscore": "textmining",
}

QUERY_SET_EDGE_SAMPLE_LIMIT = 100
QUERY_SET_NODE_SUMMARY_LIMIT = 250
PARTNER_INTERACTION_DETAIL_LIMIT = 500
PARTNER_UNIQUE_PROTEIN_LIMIT = 2000


def normalize_score_threshold(input_score_threshold):
    try:
        threshold = float(input_score_threshold)
    except (TypeError, ValueError):
        threshold = 400.0

    if threshold > 1:
        return threshold / 1000.0
    return threshold


def format_query_set_network(data, input_score_threshold=None, include_counts_when_compacted=False):
    """
    Keep query-set interaction output informative without dumping thousands of
    full STRING rows. The full edge set is used for summary/counts; only the
    displayed edge detail is reduced as networks become larger.
    """
    if not isinstance(data, list):
        return {
            "notes": ["STRING did not return a list of interactions. Reduce the score cut-off"],
            "network_summary": {},
            "network": data,
            "node_interaction_counts": [],
            "edge_sample": [],
        }

    score_threshold = normalize_score_threshold(input_score_threshold)
    filtered = [row for row in data if row.get("score", 0) >= score_threshold]
    filtered.sort(key=lambda r: r.get("score", 0), reverse=True)

    total_edges = len(filtered)
    node_counts = build_node_interaction_counts(filtered)
    network_summary = build_network_summary(filtered, node_counts, score_threshold)
    node_counts_limited, node_counts_truncated = limit_list(node_counts, QUERY_SET_NODE_SUMMARY_LIMIT)

    notes = [f"There are {total_edges} associations above specified cutoff."]
    edge_sample = []
    node_interaction_counts = []

    if total_edges <= 30:
        network = [compact_edge(row, "full") for row in filtered]
    elif total_edges <= 100:
        network = [compact_edge(row, "evidence") for row in filtered]
        if include_counts_when_compacted:
            node_interaction_counts = node_counts_limited
        notes.append(
            "The network output was compacted: STRING protein IDs and zero-valued evidence channels were omitted."
        )
        notes.append(
            "For detailed evidence-channel scores on specific interactions, subset the query to the proteins of interest and rerun the interaction query."
        )
    elif total_edges <= 500:
        network = [compact_edge(row, "score_only") for row in filtered]
        node_interaction_counts = node_counts_limited
        notes.append(
            "All interaction rows are shown, but evidence-channel details were removed because the number of returned interactions is above 100."
        )
        notes.append(
            "For detailed evidence-channel scores on specific interactions, subset the query to the proteins of interest and rerun the interaction query."
        )
    else:
        network = [compact_edge(row, "score_only") for row in filtered[:QUERY_SET_EDGE_SAMPLE_LIMIT]]
        node_interaction_counts = node_counts_limited
        notes.append(
            f"Only {len(network)} of {total_edges} interaction rows are shown because the number of returned interactions is above 500. Evidence-channel details were removed; subset the query to inspect detailed evidence for specific interactions."
        )
        notes.append(
            "The node interaction counts and network summary were computed from all returned associations above the cutoff."
        )

    if node_counts_truncated:
        notes.append(
            f"Node interaction counts were truncated to the top {QUERY_SET_NODE_SUMMARY_LIMIT} nodes by degree."
        )

    return {
        "notes": notes,
        "network_summary": network_summary,
        "network": network,
        "node_interaction_counts": node_interaction_counts,
        "edge_sample": edge_sample,
    }


def format_interaction_partners(data, input_score_threshold=None):
    """
    Compact partner-list output while preserving the full returned list.
    This endpoint is often used for set-overlap questions rather than network
    analysis, so the summary is node-centric instead of network-centric.
    """
    if not isinstance(data, list):
        return {
            "notes": ["STRING did not return a list of interaction partners."],
            "node_summary": {"return_mode": "unmodified"},
            "interactions": data,
        }

    score_threshold = normalize_score_threshold(input_score_threshold)
    filtered = [row for row in data if row.get("score", 0) >= score_threshold]
    filtered.sort(key=lambda r: r.get("score", 0), reverse=True)

    total_interactions = len(filtered)
    node_counts = build_node_interaction_counts(filtered)
    node_counts_limited, node_counts_truncated = limit_list(node_counts, QUERY_SET_NODE_SUMMARY_LIMIT)
    proteins_in_interactions = build_unique_protein_list(filtered)
    proteins_limited, proteins_truncated = limit_list(
        proteins_in_interactions,
        PARTNER_UNIQUE_PROTEIN_LIMIT,
    )

    node_summary = {
        "return_mode": "compact_interaction_list_with_limits",
        "interactions_above_cutoff": total_interactions,
        "required_score": int(score_threshold * 1000),
        "nodes_with_interactions": len(node_counts),
        "score_summary": build_score_summary(filtered),
        "score_bins": build_score_bins(filtered, score_threshold),
        "interaction_counts": node_counts_limited,
        "returned_interaction_counts": len(node_counts_limited),
        "proteins_in_returned_interactions": proteins_limited,
        "returned_protein_names": len(proteins_limited),
    }

    if total_interactions <= 100:
        interactions = [compact_edge(row, "evidence") for row in filtered]
        node_summary["returned_interactions"] = len(interactions)
        notes = [
            f"STRING returned {total_interactions} interaction partner associations above specified cutoff.",
            "The full returned interaction list is shown. STRING protein IDs and zero-valued evidence channels were omitted.",
        ]
    else:
        interactions = [
            compact_edge(row, "score_only")
            for row in filtered[:PARTNER_INTERACTION_DETAIL_LIMIT]
        ]
        node_summary["returned_interactions"] = len(interactions)
        notes = [
            f"STRING returned {total_interactions} interaction partner associations above specified cutoff.",
        ]

    if total_interactions > len(interactions):
        notes.append(
            f"Only {len(interactions)} of {total_interactions} interaction rows are shown because the number of returned interactions is above {PARTNER_INTERACTION_DETAIL_LIMIT}. Evidence-channel details were removed; subset the query to inspect detailed evidence for specific interactions."
        )

    if node_counts_truncated:
        notes.append(
            f"Interaction counts were truncated to the top {QUERY_SET_NODE_SUMMARY_LIMIT} nodes by degree."
        )

    if proteins_truncated:
        notes.append(
            f"The unique protein-name list was truncated to {PARTNER_UNIQUE_PROTEIN_LIMIT} proteins; exact overlap against a larger user gene set may require subsetting or a higher score cutoff."
        )

    return {
        "notes": notes,
        "node_summary": node_summary,
        "interactions": interactions,
    }


def limit_list(values, max_items):
    if len(values) > max_items:
        return values[:max_items], True
    return values, False


def build_unique_protein_list(edges):
    proteins = set()

    for row in edges:
        a = row.get("preferredName_A")
        b = row.get("preferredName_B")
        if a:
            proteins.add(a)
        if b:
            proteins.add(b)

    return sorted(proteins)


def compact_edge(row, mode):
    if mode == "full":
        edge = {
            key: value
            for key, value in row.items()
            if key not in NETWORK_SCORE_CHANNELS or value
        }
        return edge

    edge = {
        "preferredName_A": row.get("preferredName_A"),
        "preferredName_B": row.get("preferredName_B"),
        "score": round(row.get("score", 0), 3),
    }

    if mode == "evidence":
        evidence = {
            label: round(row.get(score_key, 0), 3)
            for score_key, label in NETWORK_SCORE_CHANNELS.items()
            if row.get(score_key, 0)
        }
        if evidence:
            edge["evidence"] = evidence

    return edge


def build_node_interaction_counts(edges):
    node_stats = {}

    for row in edges:
        a = row.get("preferredName_A")
        b = row.get("preferredName_B")
        score = row.get("score", 0)

        if not a or not b:
            continue

        for gene, neighbor in ((a, b), (b, a)):
            stats = node_stats.setdefault(
                gene,
                {"gene": gene, "degree": 0, "weighted_degree": 0.0, "_neighbors": []},
            )
            stats["degree"] += 1
            stats["weighted_degree"] += score
            stats["_neighbors"].append((neighbor, score))

    output = []
    for stats in node_stats.values():
        neighbors = sorted(stats["_neighbors"], key=lambda item: item[1], reverse=True)
        output.append({
            "gene": stats["gene"],
            "degree": stats["degree"],
            "weighted_degree": round(stats["weighted_degree"], 3),
            "top_neighbors": [neighbor for neighbor, _ in neighbors[:5]],
        })

    output.sort(key=lambda item: (item["degree"], item["weighted_degree"]), reverse=True)
    return output


def build_network_summary(edges, node_counts, score_threshold):
    total_edges = len(edges)
    node_count = len(node_counts)
    max_possible_edges = node_count * (node_count - 1) / 2
    density = total_edges / max_possible_edges if max_possible_edges else 0

    return {
        "nodes_with_interactions": node_count,
        "edges_above_cutoff": total_edges,
        "required_score": int(score_threshold * 1000),
        "density": round(density, 4),
        "average_degree": round((2 * total_edges / node_count), 3) if node_count else 0,
        "score_summary": build_score_summary(edges),
        "score_bins": build_score_bins(edges, score_threshold),
    }


def build_score_summary(edges):
    scores = [row.get("score", 0) for row in edges]

    if not scores:
        return {"min": 0, "mean": 0, "max": 0}

    return {
        "min": round(min(scores), 3),
        "mean": round(sum(scores) / len(scores), 3),
        "max": round(max(scores), 3),
    }


def build_score_bins(edges, score_threshold):
    scores = [row.get("score", 0) for row in edges]

    bins = [
        (0.0, 0.4, "0.000-0.399"),
        (0.4, 0.7, "0.400-0.699"),
        (0.7, 0.9, "0.700-0.899"),
        (0.9, 1.001, "0.900-1.000"),
    ]

    score_bins = {}
    for lower, upper, label in bins:
        if upper <= score_threshold:
            continue
        adjusted_lower = max(lower, score_threshold)
        adjusted_label = label if adjusted_lower == lower else f"{adjusted_lower:.3f}-{upper - 0.001:.3f}"
        count = sum(1 for score in scores if adjusted_lower <= score < upper)
        score_bins[adjusted_label] = count

    return score_bins


def sort_and_truncate_functional_annotation(data, is_json, detail_for_term=None):
    size_cutoff = 200
    exact_protein_list_cutoff = 25
    remove_protein_field_after = 50
    truncation_notes = []

    if is_json.lower() == 'json':

        original_rows = len(data)
        data = sorted(data, key=lambda x: x["ratio_in_set"], reverse=True)

        if detail_for_term:
            detail_key = detail_for_term.strip().lower()
            data = [
                row for row in data
                if str(row.get("term", "")).strip().lower() == detail_key
            ]
            if data:
                truncation_notes.append(
                    f"Returned full input-protein lists for term {detail_for_term}."
                )
            else:
                truncation_notes.append(
                    "No matching term was found. Run without `detail_for_term` to inspect available terms and use the exact term ID."
                )
            return data, truncation_notes

        if len(data) > size_cutoff:
            data = data[:size_cutoff]
            truncation_notes.append(
                f"The list was truncated to the first {size_cutoff} terms from {original_rows} original rows."
            )

        replaced_many = False
        removed_late_proteins = False

        for index, row in enumerate(data):
            proteins = row.get("preferredNames")
            if not isinstance(proteins, list):
                continue

            protein_count = len(proteins)
            row["protein_count"] = protein_count

            if index >= remove_protein_field_after:
                row.pop("preferredNames", None)
                removed_late_proteins = True
            elif protein_count > exact_protein_list_cutoff:
                row["preferredNames"] = "many"
                replaced_many = True

        if replaced_many:
            truncation_notes.append(
                f"For annotations covering more than {exact_protein_list_cutoff} input proteins, protein lists were replaced with 'many'. Use `detail_for_term` with the exact term ID to show all input proteins annotated with that term."
            )

        if removed_late_proteins:
            truncation_notes.append(
                f"For terms ranked after the first {remove_protein_field_after}, protein lists were omitted. Use `detail_for_term` with the exact term ID to show all input proteins annotated with that term."
            )

    return data, truncation_notes
 
def truncate_functional_terms(data, is_json):
    term_size_cutoff = 10
    protein_size_cutoff_top = 100    # cap for top terms
    protein_size_cutoff_rest = 25    # cap for later terms
    truncation_notes = []

    if is_json.lower() == 'json':
        filtered_data = []
        original_rows = len(data)

        for i, row in enumerate(data[:term_size_cutoff]):
            if i < 3:
                # top terms: allow up to 500
                if len(row['preferredNames']) > protein_size_cutoff_top:
                    original_protein_count = len(row['preferredNames'])
                    row['preferredNames'] = row['preferredNames'][:protein_size_cutoff_top] + ["..."]
                    row['stringIds'] = row['stringIds'][:protein_size_cutoff_top] + ["..."]
                    row['proteinCount'] = original_protein_count
                    row['truncated'] = True
                else:
                    row['proteinCount'] = len(row['preferredNames'])
                    row['truncated'] = False
            else:
                # later terms: allow only 50
                if len(row['preferredNames']) > protein_size_cutoff_rest:
                    original_protein_count = len(row['preferredNames'])
                    row['preferredNames'] = row['preferredNames'][:protein_size_cutoff_rest] + ["..."]
                    row['stringIds'] = row['stringIds'][:protein_size_cutoff_rest] + ["..."]
                    row['proteinCount'] = original_protein_count
                    row['truncated'] = True
                else:
                    row['proteinCount'] = len(row['preferredNames'])
                    row['truncated'] = False

            filtered_data.append(row)

        if len(filtered_data) < original_rows:
            truncation_notes.append(
                f"Functional-term results were truncated to the top {term_size_cutoff} terms for readability."
            )

        data = filtered_data

    return data, truncation_notes

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



def log_call(endpoint, params):

    if log_verbosity['call']:
        print(f"Call: {endpoint}", file=sys.stderr)
 
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
