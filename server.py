# server.py

import sys
import json

from collections import defaultdict

import httpx
from fastmcp import FastMCP
from starlette.middleware.cors import CORSMiddleware
from typing import Annotated, Optional
from pydantic import Field
import uvicorn

import logging
from functools import wraps

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def log_calls(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # Log function call with truncated kwargs if needed
        kwargs_str = str(kwargs)
        if len(kwargs_str) > 100:
            kwargs_str = kwargs_str[:97] + "..."
        logger.info(f"🔧 {func.__name__} called with: {kwargs_str}")
        
        result = await func(*args, **kwargs)
        
        # Truncate result representation
        result_str = str(result)
        if len(result_str) > 30:
            result_preview = result_str[:30] + "..."
        else:
            result_preview = result_str
            
        logger.info(f"✅ {func.__name__} returned: {type(result).__name__} - {result_preview}")
        return result
    return wrapper

with open('config/server.config', 'r') as f:
    config = json.load(f)
 
base_url = config["base_url"]
server_port = int(config["server_port"])

mcp = FastMCP(
    name="STRING Database MCP Server",
   
)


@mcp.tool(title="STRING: Resolves protein identifiers to metadata")
@log_calls
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

    Output fields (per matched identifier):
      - `queryItem`: Your original input identifier (if `echo_query=1`)
      - `queryIndex`: Position of the identifier in your input list (starting from 0)
      - `stringId`: STRING internal identifier
      - `ncbiTaxonId`: NCBI taxonomy ID
      - `taxonName`: Species name
      - `preferredName`: Common protein name
      - `annotation`: Protein annotation

    Example input: "TP53%0dSMO"
    """

    params = {"identifiers": proteins, "echo_query": 1}
    if species is not None:
        params["species"] = species

    endpoint = "/api/json/get_string_ids"
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.post(endpoint, data=params)
        response.raise_for_status()
        results = response.json()

        if not results:
            return {"error": "No protein mappings were found for the given input identifiers."}

        return {"mapped_proteins": results}



@mcp.tool(title="STRING: Get protein network (data + visuals)")
@log_calls
async def string_network_complete(
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
            'Optional. Type of network to retrieve: "functional" (default) or "physical". '
            "Only set this if the user explicitly requests it."
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
    show_query_node_labels: Annotated[
        Optional[int],
        Field(description=(
            "Optional. Set to 1 to display user-supplied names instead of STRING preferred names "
            "in the output. Default is 0. Only set if the user explicitly requests it."
        ))
    ] = None,
    include_visuals: Annotated[
        bool,
        Field(description="Whether to include visual network image and interactive link. Default is True.")
    ] = True,
    network_flavor: Annotated[
        Optional[str],
        Field(description=(
            'Optional. Edge style for visuals: "evidence" (default), "confidence", or "actions". '
            "Only set this if the user explicitly requests it."
        ))
    ] = None,
    hide_disconnected_nodes: Annotated[
        Optional[int],
        Field(description=(
            "Optional. 1 to hide proteins not connected to any other protein, 0 otherwise (default: 0). "
            "Only set this if the user explicitly requests it."
        ))
    ] = None,
    center_node_labels: Annotated[
        Optional[int],
        Field(description=(
            "Optional. 1 to center protein names on nodes, 0 otherwise (default: 0). "
            "Only set this if the user explicitly requests it."
        ))
    ] = None,
    custom_label_font_size: Annotated[
        Optional[int],
        Field(description=(
            "Optional. Change font size of protein names (from 5 to 50, default: 12). "
            "Only set this if the user explicitly requests it."
        ))
    ] = None
) -> dict:
    """
    Retrieves the interactions between the query proteins with both structured data and visualizations.
    
    Use this method when you need to analyze protein interactions. This provides:
    - Structured interaction data with confidence scores and evidence types
    - Visual network image URL for display
    - Interactive network link for exploration

    - For a **single protein**, the network includes that protein and its top 10 most likely interaction partners, plus all interactions among those partners.
    - For **multiple proteins**, the network includes all direct interactions between them.

    If few or no interactions are returned, consider reducing the `required_score`.

    Output includes:
    - `network_data`: Structured interaction data with scores and evidence
    - `visualizations`: Image URL and interactive link (if include_visuals=True)
    """

    # Get network data
    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type
    if extend_network is not None:
        params["add_nodes"] = extend_network
    if show_query_node_labels is not None:
        params["show_query_node_labels"] = show_query_node_labels

    endpoint = "/api/json/network"

    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.post(endpoint, data=params)
        response.raise_for_status()
        
        result = {"network_data": response.json()}
        
        if include_visuals:
            # Get visual network image
            visual_params = {"identifiers": proteins}
            if species is not None:
                visual_params["species"] = species
            if extend_network is not None:
                visual_params["add_white_nodes"] = extend_network
            if required_score is not None:
                visual_params["required_score"] = required_score
            if network_type is not None:
                visual_params["network_type"] = network_type
            if network_flavor is not None:
                visual_params["network_flavor"] = network_flavor
            if hide_disconnected_nodes is not None:
                visual_params["hide_disconnected_nodes"] = hide_disconnected_nodes
            if show_query_node_labels is not None:
                visual_params["show_query_node_labels"] = show_query_node_labels
            if center_node_labels is not None:
                visual_params["center_node_labels"] = center_node_labels
            if custom_label_font_size is not None:
                visual_params["custom_label_font_size"] = custom_label_font_size

            # Get image URL
            image_endpoint = "/api/json/network_image_url"
            image_response = await client.post(image_endpoint, data=visual_params)
            image_response.raise_for_status()
            
            # Get interactive link
            link_params = visual_params.copy()
            if "add_white_nodes" in link_params:
                link_params["add_white_nodes"] = link_params.pop("add_white_nodes")
            
            link_endpoint = "/api/json/get_link"
            link_response = await client.post(link_endpoint, data=link_params)
            link_response.raise_for_status()
            
            result["visualizations"] = {
                "image_url": image_response.text,
                "interactive_link": link_response.json()
            }

        return result


@mcp.tool(title="STRING: Get all interaction partners for protein(s)")
@log_calls
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
    limit: Annotated[
        Optional[int],
        Field(description=(
            "Optional. Maximum number of interaction partners returned per query protein. "
            "Higher-confidence interactions appear first. Only set if the user explicitly requests it."
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
            'Optional. Type of interaction network: "functional" (default) or "physical". '
            "Only set if the user explicitly requests it."
        ))
    ] = None
) -> dict:
    """
    Retrieves all interaction partners for one or more proteins from STRING.

    This tool returns all known interactions between your query protein(s) and **any other proteins in the STRING database**.
    
    - Use this when asking **"What does TP53 interact with?"**
    - It differs from the `network` tool, which only shows interactions **within the input set** or a limited extension of it.

    You can restrict the number of partners using `limit`, or filter for strong interactions using `required_score`.

    Output fields (per interaction):
      - `stringId_A` / `stringId_B`: Internal STRING identifiers
      - `preferredName_A` / `preferredName_B`: Protein symbols
      - `ncbiTaxonId`: NCBI taxonomy ID
      - `score`: Combined confidence score (0–1000)
      - `nscore`: Genome neighborhood score
      - `fscore`: Gene fusion score
      - `pscore`: Phylogenetic profile score
      - `ascore`: Coexpression score
      - `escore`: Experimental score
      - `dscore`: Curated database score
      - `tscore`: Text mining score
    """

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
    async with httpx.AsyncClient(base_url=base_url) as client:
        response = await client.post(endpoint, data=params)
        response.raise_for_status()

        return {"interactions": response.json()}


@mcp.tool(title="STRING: Get protein similarity (homology) scores within species")
@log_calls
async def string_homology(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None
) -> dict:
    """
    This tool retrieves pairwise protein similarity scores (Smith–Waterman bit scores) for a set of proteins in STRING in the selected species.

    - The tool returns only scores within the selected species, not alignments between proteins from different species.
    - The scores are calculated using SIMAP and are symmetric, but only one direction (A->B) and self-hits are returned.
    - Bit scores below 50 are not stored or reported.

    Output fields (per protein pair):
      - ncbiTaxonId_A: NCBI taxon ID for protein A
      - stringId_A: STRING identifier (protein A)
      - ncbiTaxonId_B: NCBI taxon ID for protein B
      - stringId_B: STRING identifier (protein B)
      - bitscore: Smith–Waterman alignment bit score
    """
    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/homology"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}



@mcp.tool(title="STRING: Get best protein similarity (homology) hits across species")
@log_calls
async def string_homology_best(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes). Limit A-side proteins to this species.")
    ] = None,
    species_b: Annotated[
        Optional[str],
        Field(description="Optional. One or more NCBI taxon IDs for target species, separated by %0d (e.g. 9606%0d7227%0d4932 for human, fly, and yeast). Limit B-side best hits to these species.")
    ] = None
) -> dict:
    """
    This tool retrieves the best protein similarity hits (Smith–Waterman bit scores) between your input proteins and all STRING organisms (or limited to those specified by species_b).

    - For each query protein, only the single best hit per target species is returned.
    - The scores are computed by SIMAP; bit scores below 50 are not reported.
    - Use 'species_b' to filter which target organisms to include.

    Output fields (per result):
      - ncbiTaxonId_A: NCBI taxon ID for query protein
      - stringId_A: STRING identifier for query protein
      - ncbiTaxonId_B: NCBI taxon ID for best-hit protein
      - stringId_B: STRING identifier for best-hit protein
      - bitscore: Smith–Waterman alignment bit score

    Example identifiers: "SMO%0dTP53"
    """
    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species
    if species_b is not None:
        params["species_b"] = species_b

    endpoint = f"/api/json/homology_best"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


@mcp.tool(title="STRING: Enrichment Analysis (data + visuals)")
@log_calls
async def string_enrichment_complete(
    proteins: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    category: Annotated[
        Optional[str],
        Field(
            description=(
                "Optional. Term category for enrichment analysis and visualization. "
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
                "If not specified: returns all categories for data, defaults to Process for visualization."
            )
        )
    ] = None,
    background_string_identifiers: Annotated[
        Optional[str],
        Field(description="Optional. Specify a custom background proteome as STRING identifiers (separated by %0d). DO NOT SET unless user explicitly requests.")
    ] = None,
    species: Annotated[
        Optional[str],
        Field(description="Optional. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX). DO NOT SET unless user explicitly requests.")
    ] = None,
    include_visuals: Annotated[
        bool,
        Field(description="Whether to include enrichment visualization image. Default is True.")
    ] = True,
    group_by_similarity: Annotated[
        Optional[float],
        Field(description="Optional. Group similar terms on the plot; threshold 0.1-1 (default: no grouping). Only used for visualization.")
    ] = None,
    color_palette: Annotated[
        Optional[str],
        Field(description='Optional. Color palette for FDR (e.g., "mint_blue", "lime_emerald", etc.; default: "mint_blue"). Only used for visualization.')
    ] = None,
    number_of_term_shown: Annotated[
        Optional[int],
        Field(description="Optional. Max number of terms shown on plot (default: 10). Only used for visualization.")
    ] = None,
    x_axis: Annotated[
        Optional[str],
        Field(description='Optional. X-axis variable/order: "signal", "strength", "FDR", or "gene_count" (default: "signal"). Only used for visualization.')
    ] = None
) -> dict:
    """
    This tool retrieves functional enrichment for a set of proteins using STRING with both structured data and visualization.

    - If queried with a single protein, the tool expands the query to include the protein's 10 most likely interactors; enrichment is performed on this set, not the original single protein.
    - For two or more proteins, enrichment is performed on the exact input set.
    - If a category is specified, both the enrichment data and visualization will be filtered to that specific category.
    - Focus summaries on the top categories and most relevant terms for the results. Always report FDR for each claim.
    - Report FDR as a human-readable value (e.g. 2.3e-5 or 0.023).

    Output includes:
    - `enrichment_data`: Structured enrichment results with p-values, FDR, descriptions (filtered by category if specified)
    - `visualization`: Image URL for enrichment plot (if include_visuals=True)
    """
    
    # Get enrichment data
    params = {"identifiers": proteins}
    if background_string_identifiers is not None:
        params["background_string_identifiers"] = background_string_identifiers
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/enrichment"

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        enrichment_results = r.json()
        
        # Filter results by category if specified
        if category is not None:
            enrichment_results = [item for item in enrichment_results if item.get('category') == category]
        
        res = truncate_enrichment(enrichment_results, 'json')
        result = {"enrichment_data": res}
        
        if include_visuals:
            # Get enrichment image
            image_params = {"identifiers": proteins}
            if species is not None:
                image_params["species"] = species
            if category is not None:
                image_params["category"] = category
            # Let API use its own default (Process) if no category specified
            if group_by_similarity is not None:
                image_params["group_by_similarity"] = group_by_similarity
            if color_palette is not None:
                image_params["color_palette"] = color_palette
            if number_of_term_shown is not None:
                image_params["number_of_term_shown"] = number_of_term_shown
            if x_axis is not None:
                image_params["x_axis"] = x_axis

            image_endpoint = f"/api/json/enrichment_image_url"
            image_response = await client.post(image_endpoint, data=image_params)
            image_response.raise_for_status()
            
            result["visualization"] = image_response.json()

        return result


@mcp.tool(title="STRING: Get Functional Annotation")
@log_calls
async def string_functional_annotation(
    identifiers: Annotated[
        str,
        Field(description="Separate multiple protein queries by %0d. e.g. SMO%0dTP53")
    ]
) -> dict:
    """BLANK"""

    endpoint = "/api/json/functional_annotation"

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data={"identifiers": identifiers})
        r.raise_for_status()
        return {"results": r.json()}  # Functional annotation per protein


@mcp.tool(title="STRING: Protein-Protein Interaction (links) Enrichment")
@log_calls
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
    background_string_identifiers: Annotated[
        Optional[str],
        Field(description="Optional. Specify the background proteome as STRING IDs (separated by %0d). DO NOT SET unless user explicitly requests.")
    ] = None
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
    if background_string_identifiers is not None:
        params["background_string_identifiers"] = background_string_identifiers

    endpoint = f"/api/json/ppi_enrichment"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}

# ---- MCP server helper functions ----

def truncate_enrichment(data, is_json):
   
    term_cutoff = 20
    size_cutoff = 10

    if is_json.lower() == 'json':

        filtered_data = []

        category_count = defaultdict(int)

        for row in data:

            category = row['category']
            category_count[category] += 1

            if category_count[category] > term_cutoff:
                continue

            if len(row['inputGenes']) > size_cutoff:
                row['inputGenes'] = [f'[>{size_cutoff} proteins]'] 
                row['preferredNames'] = [f'[>{size_cutoff} proteins]'] 

            filtered_data.append(row)

        data = filtered_data

    return data

# ---- MCP server runner ----

if __name__ == "__main__":
    # Add CORS in your proxy (nginx) for browser-based playgrounds
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=server_port,
        log_level="info",
        stateless_http = True,
    )