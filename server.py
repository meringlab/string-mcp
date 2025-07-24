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

config = open('server.config').read().json()
    
    base_url = 'https://string-pythongamma.org'
    server_port = '4444'

mcp = FastMCP(
    name="STRING Database MCP Server",
    stateless_http=True,
    json_response=True,
)


@mcp.tool(title="STRING: Map input identifiers to STRING identifiers")
async def string_map_identifiers(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more input protein identifiers (gene names, UniProt IDs, etc), separated by %0d. Example: TP53%0dSMO")
    ],
    echo_query: Annotated[
        Optional[int],
        Field(description="Optional. If set to 1, includes your input identifier as a separate column. Default is 0.")
    ] = 0,
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes).")
    ] = None
) -> dict:
    """
    This tool maps your input identifiers (gene names, synonyms, or UniProt IDs) to STRING’s internal identifiers.

    - For each input protein, the best match is placed in the first row.  
    - Mapping your identifiers in advance improves speed and avoids ambiguity when calling other STRING API methods.
    - If species is not specified, assume human (9606) or ask user to clarify.

    Output fields (per mapped identifier):
      - queryItem: Your original input identifier (if echo_query=1)
      - queryIndex: Position of the identifier in your input list (starting from 0)
      - stringId: STRING internal identifier
      - ncbiTaxonId: NCBI taxonomy ID
      - taxonName: Species name
      - preferredName: Common protein name
      - annotation: Protein annotation

    Example identifiers: "TP53%0dSMO"
    """
    params = {"identifiers": identifiers, "echo_query": echo_query}
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/get_string_ids"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


@mcp.tool(title="STRING: Get protein interaction network for protein or set of proteins")
async def string_network(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes)")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Minimum interaction confidence score (0-1000). DO NOT SET unless user explicitly requests.")
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical". DO NOT SET unless user explicitly requests.')
    ] = None,
    add_nodes: Annotated[
        Optional[int],
        Field(description="Optional. Number of proteins to add to the network based on their connectivity to query protein (default 10 for single protein query, 0 for multiple proteins query). DO NOT SET unless user explicitly requests.")
    ] = None,
    show_query_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 display the user's query name(s) instead of STRING preferred name, (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None
) -> dict:
    """This tool retrieves the STRING interaction network for one or more proteins.

     If queried with a single protein, the tool returns that protein and its interaction neighborhood — that is, the query protein and its 10 most likely interactors, including all interactions among the top interaction partners of the query protein. If queried with multiple proteins, the tool returns all interactions among the queried set. If no or very few interactions are returned, try lowering the required_score parameter.

    When calling related tools use the same input parameters unless otherwise specified.
    
    Output fields (per interaction):
      - stringId_A: STRING identifier for protein A
      - stringId_B: STRING identifier for protein B
      - preferredName_A: Protein symbol (A)
      - preferredName_B: Protein symbol (B)
      - ncbiTaxonId: NCBI taxonomy ID
      - score: Combined confidence score
      - nscore: Genome neighborhood score
      - fscore: Gene fusion score
      - pscore: Phylogenetic profile score
      - ascore: Coexpression score
      - escore: Experimental score
      - dscore: Curated database score
      - tscore: Textmining score
    """
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type
    if add_nodes is not None:
        params["add_nodes"] = add_nodes
    if show_query_node_labels is not None:
        params["show_query_node_labels"] = show_query_node_labels

    endpoint = f"/api/json/network"

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}

@mcp.tool(title="STRING: Get Visualised Network Image URL")
async def string_network_image_url(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX).")
    ] = None,
    add_color_nodes: Annotated[
        Optional[int],
        Field(description="Optional. Add color nodes to input proteins, based on scores (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    add_white_nodes: Annotated[
        Optional[int],
        Field(description="Optional. Add white nodes to network, based on scores (default: 0, or 10 for single protein queries). DO NOT SET unless user explicitly requests.")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Threshold of significance to include an interaction (0-1000). DO NOT SET unless user explicitly requests.")
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical". DO NOT SET unless user explicitly requests.')
    ] = None,
    network_flavor: Annotated[
        Optional[str],
        Field(description='Optional. Edge style: "evidence" (default), "confidence", or "actions". DO NOT SET unless user explicitly requests.')
    ] = None,
    hide_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide all protein names from the image, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    hide_disconnected_nodes: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide proteins not connected to any other protein, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    show_query_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 display the user's query name(s) instead of STRING preferred name, (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    block_structure_pics_in_bubbles: Annotated[
        Optional[int],
        Field(description="Optional. 1 to disable structure pictures in bubbles, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    flat_node_design: Annotated[
        Optional[int],
        Field(description="Optional. 1 to enable 3D bubble design, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    center_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 to center protein names on nodes, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    custom_label_font_size: Annotated[
        Optional[int],
        Field(description="Optional. Change font size of protein names (from 5 to 50, default: 12). DO NOT SET unless user explicitly requests.")
    ] = None
) -> dict:
    """Retrieves the URL of the STRING interaction network image for one or more proteins.

    If queried with a single protein, the tool returns that protein and its 10 most likely interactors; if queried with multiple proteins, the tool returns all interaction network between the queried set. If no or very few interactions are returned, try lowering the required_score parameter.
     
    This tool returns a URL for a network image. Always display the image inline in chat, and include the clickable link immediately below for download.
     
    When calling related tools, use the same input parameters unless otherwise specified.
    """
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if add_color_nodes is not None:
        params["add_color_nodes"] = add_color_nodes
    if add_white_nodes is not None:
        params["add_white_nodes"] = add_white_nodes
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type
    if network_flavor is not None:
        params["network_flavor"] = network_flavor
    if hide_node_labels is not None:
        params["hide_node_labels"] = hide_node_labels
    if hide_disconnected_nodes is not None:
        params["hide_disconnected_nodes"] = hide_disconnected_nodes
    if show_query_node_labels is not None:
        params["show_query_node_labels"] = show_query_node_labels
    if block_structure_pics_in_bubbles is not None:
        params["block_structure_pics_in_bubbles"] = block_structure_pics_in_bubbles
    if flat_node_design is not None:
        params["flat_node_design"] = flat_node_design
    if center_node_labels is not None:
        params["center_node_labels"] = center_node_labels
    if custom_label_font_size is not None:
        params["custom_label_font_size"] = custom_label_font_size

    endpoint = f"/api/json/network_image_url"

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.text}

@mcp.tool(title="STRING: Get Interaction Partners")
async def string_interaction_partners(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX for uploaded genomes). DO NOT SET unless user explicitly requests.")
    ] = None,
    limit: Annotated[
        Optional[int],
        Field(description="Optional. Limits the number of interaction partners retrieved per protein (higher scoring interactions come first). DO NOT SET unless user explicitly requests.")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Threshold of significance to include an interaction (0-1000). DO NOT SET unless user explicitly requests.")
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical". DO NOT SET unless user explicitly requests.')
    ] = None
) -> dict:
    """This tool retrieves all STRING interaction partners for a protein or set of proteins.

    Unlike the network tool, which retrieves only the interactions within the query set and among direct neighbors (if specified), this tool retrieves all interactions between your query proteins and all other STRING proteins. Use the "limit" parameter to restrict the number of partners per protein (highest confidence interactions are prioritized). If no or very few interactions are returned, try lowering the required_score parameter.

    When calling related tools, use the same input parameters unless otherwise specified.

    Output fields (per interaction):
      - stringId_A: STRING identifier for protein A
      - stringId_B: STRING identifier for protein B
      - preferredName_A: Protein symbol (A)
      - preferredName_B: Protein symbol (B)
      - ncbiTaxonId: NCBI taxonomy ID
      - score: Combined confidence score
      - nscore: Genome neighborhood score
      - fscore: Gene fusion score
      - pscore: Phylogenetic profile score
      - ascore: Coexpression score
      - escore: Experimental score
      - dscore: Curated database score
      - tscore: Textmining score
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

    endpoint = f"/api/json/interaction_partners"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}

@mcp.tool(title="STRING: Get interactive network link")
async def string_network_get_link(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    species: Annotated[
        str,
        Field(description="Required. NCBI/STRING taxon (e.g. 9606 for human, or STRG0AXXXXX).")
    ] = None,
    add_color_nodes: Annotated[
        Optional[int],
        Field(description="Optional. Add color nodes to input proteins, based on scores (default: 0, or 10 for single protein query). DO NOT SET unless user explicitly requests.")
    ] = None,
    add_white_nodes: Annotated[
        Optional[int],
        Field(description="Optional. Add white nodes to network, based on scores (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    required_score: Annotated[
        Optional[int],
        Field(description="Optional. Threshold of significance to include an interaction (0-1000). DO NOT SET unless user explicitly requests.")
    ] = None,
    network_flavor: Annotated[
        Optional[str],
        Field(description='Optional. Edge style: "evidence" (default), "confidence", or "actions". DO NOT SET unless user explicitly requests.')
    ] = None,
    network_type: Annotated[
        Optional[str],
        Field(description='Optional. Network type: "functional" (default) or "physical". DO NOT SET unless user explicitly requests.')
    ] = None,
    hide_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide all protein names from the image, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    hide_disconnected_nodes: Annotated[
        Optional[int],
        Field(description="Optional. 1 to hide proteins not connected to any other protein, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    show_query_node_labels: Annotated[
        Optional[int],
        Field(description="Optional. 1 display the user's query name(s) instead of STRING preferred name, (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None,
    block_structure_pics_in_bubbles: Annotated[
        Optional[int],
        Field(description="Optional. 1 to disable structure pictures in bubbles, 0 otherwise (default: 0). DO NOT SET unless user explicitly requests.")
    ] = None
) -> dict:
    """Retrieves a stable URL to an interactive STRING network for one or more proteins.

    This tool returns a link to the STRING website where the queried protein network can be interactively explored.  
    Users can click on nodes and edges, view evidence, and explore additional information beyond what static images can provide.

    - If queried with a single protein, the network includes the query protein and its 10 most likely interactors.
    - If queried with multiple proteins, the network will show interactions among the queried set.
    - If no or very few interactions are returned, try lowering the required_score parameter.

    When calling related tools, use the same input parameters unless otherwise specified.
    Always display this link prominently and make it clickable for the user.

    """
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if add_color_nodes is not None:
        params["add_color_nodes"] = add_color_nodes
    if add_white_nodes is not None:
        params["add_white_nodes"] = add_white_nodes
    if required_score is not None:
        params["required_score"] = required_score
    if network_flavor is not None:
        params["network_flavor"] = network_flavor
    if network_type is not None:
        params["network_type"] = network_type
    if hide_node_labels is not None:
        params["hide_node_labels"] = hide_node_labels
    if hide_disconnected_nodes is not None:
        params["hide_disconnected_nodes"] = hide_disconnected_nodes
    if show_query_node_labels is not None:
        params["show_query_node_labels"] = show_query_node_labels
    if block_structure_pics_in_bubbles is not None:
        params["block_structure_pics_in_bubbles"] = block_structure_pics_in_bubbles

    endpoint = f"/api/json/get_link"

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


@mcp.tool(title="STRING: Get protein similarity (homology) scores within species")
async def string_homology(
    identifiers: Annotated[
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
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/homology"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}



@mcp.tool(title="STRING: Get best protein similarity (homology) hits across species")
async def string_homology_best(
    identifiers: Annotated[
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
    params = {"identifiers": identifiers}
    if species is not None:
        params["species"] = species
    if species_b is not None:
        params["species_b"] = species_b

    endpoint = f"/api/json/homology_best"
    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}

@mcp.tool(title="STRING: Enrichment Analysis")
async def string_enrichment(
    identifiers: Annotated[
        str,
        Field(description="Required. One or more protein identifiers, separated by %0d. Example: SMO%0dTP53")
    ],
    background_string_identifiers: Annotated[
        Optional[str],
        Field(description="Optional. Specify a custom background proteome as STRING identifiers (separated by %0d). DO NOT SET unless user explicitly requests.")
    ] = None,
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
    params = {"identifiers": identifiers}
    if background_string_identifiers is not None:
        params["background_string_identifiers"] = background_string_identifiers
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/enrichment"

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        res = truncate_enrichment(r.json(), 'json')
        return {"results": res}


@mcp.tool(title="STRING: Get Functional Annotation")
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

@mcp.tool(title="STRING: Get Enrichment Figure Image URL")
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
    """{Retrieves the STRING enrichment figure image *URL* (in TSV format) for a set of proteins.

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

    async with httpx.AsyncClient(base_url=base_url) as client:
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


@mcp.tool(title="STRING: Protein-Protein Interaction (links) Enrichment")
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
        log_level="info"
    )

