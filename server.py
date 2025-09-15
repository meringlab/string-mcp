# server.py

import sys
import json
import httpx

from collections import defaultdict

from fastmcp import FastMCP
from fastmcp.server.dependencies import get_http_headers

from typing import Annotated, Optional
from pydantic import Field

with open('config/server.config', 'r') as f:
    config = json.load(f)

base_url = config["base_url"]
server_port = int(config["server_port"])

## logging verbosity ## 

log_verbosity = {}
log_verbosity['call'] = False
log_verbosity['params'] = False

if 'verbosity' in config:

    if config['verbosity'] == 'full':
        log_verbosity['call'] = True
        log_verbosity['params'] = True
        log_verbosity['taskid'] = True

    if config['verbosity'] == 'low':
        log_verbosity['call'] = True
        log_verbosity['params'] = False
        log_verbosity['taskid'] = True

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

    Output fields (per matched identifier):
      - `queryItem`: Your original input identifier
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
        log_call(endpoint, params)
        response = await client.post(endpoint, data=params)
        response.raise_for_status()
        results = response.json()

        if not results:
            return {"error": "No protein mappings were found for the given input identifiers."}

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

    - For a **single protein**, the network includes that protein and its top 10 most likely interaction partners, plus all interactions among those partners.
    - For **multiple proteins**, the network includes all direct interactions between them.

    If few or no interactions are returned, consider reducing the `required_score`.

    Output fields (per interaction):
      - `stringId_A` / `stringId_B`: Internal STRING identifiers
      - `preferredName_A` / `preferredName_B`: Protein symbols
      - `ncbiTaxonId`: NCBI species ID
      - `score`: Combined confidence score (0–1000)
      - `nscore`: Neighborhood evidence score
      - `fscore`: Gene fusion evidence score
      - `pscore`: Phylogenetic profile evidence score
      - `ascore`: Coexpression evidence score
      - `escore`: Experimental evidence score
      - `dscore`: Curated database evidence score
      - `tscore`: Text mining evidence score
    """

    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species
    if required_score is not None:
        params["required_score"] = required_score
    if network_type is not None:
        params["network_type"] = network_type
    if extend_network is not None:
        params["add_nodes"] = extend_network
    #if show_query_node_labels is not None:
    #    params["show_query_node_labels"] = show_query_node_labels

    endpoint = "/api/json/network"

    async with httpx.AsyncClient(base_url=base_url) as client:
        log_call(endpoint, params)
        response = await client.post(endpoint, data=params)
        response.raise_for_status()

        return {"network": response.json()}



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
    
    - Use this when asking **“What does TP53 interact with?”**
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
        log_call(endpoint, params)
        response = await client.post(endpoint, data=params)
        response.raise_for_status()

        return {"interactions": response.json()}


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
        Field(description="Optional. Add specified number of nodes to the network, based on their scores (default: 0, or 10 for single protein queries). DO NOT SET unless user explicitly requests.")
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
    Retrieves a URL to a **visual STRING interaction network image** for one or more proteins.

    - If a single protein is provided, the network includes that protein and its top 10 most likely interactors.
    - If multiple proteins are provided, the network includes all known interactions **within the query set**.

    If few or no interactions are displayed, consider lowering the `required_score` parameter.

    This tool returns a direct image URL. Always display the image inline (if supported), and include the link below the netowrk in markdown [STRING network](image_url)

    Input parameters should match those used with related STRING tools (e.g. `string_query_set_network`) unless otherwise specified.
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

    async with httpx.AsyncClient(base_url=base_url) as client:
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"image_url": r.text}

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

    When calling related tools, use the same input parameters unless otherwise specified.
    Always display this link prominently and make it clickable for the user.

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

    async with httpx.AsyncClient(base_url=base_url) as client:
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


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
    This tool retrieves pairwise protein similarity scores (Smith–Waterman bit scores) for the query proteins.
    
    If a target species (`species_b`) is not provided, the tool returns homologs within the query species only (intra-species comparison).
    To retrieve homologs in specific organisms or taxonomic groups (e.g., vertebrates, yeast, plants), `species_b` must be provided as a list of NCBI taxon IDs for those species.
    You can specify multiple target species. If you're not sure which species the user is interested in, ask. Remember to show the full species names alongside their taxon IDs.

    - Bit scores below 50 are not stored or reported.
    - The list is truncated to 25 proteins.
    
    Output fields (per protein pair):
      - ncbiTaxonId_A: NCBI taxon ID for protein A
      - stringId_A: STRING identifier (protein A)
      - preferredName_A: protein A name
      - ncbiTaxonId_B: NCBI taxon ID for protein B
      - preferredName_B: protein B name
      - stringId_B: STRING identifier (protein B)
      - bitscore: Smith–Waterman alignment bit score
    """

    params = {"identifiers": proteins}
    if species is not None:
        params["species"] = species

    if species_b is not None:
        params["species_b"] = species_b

    endpoint = f"/api/json/homology_all"
    async with httpx.AsyncClient(base_url=base_url) as client:
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


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
    Use this tool when the user asks for detailed interaction **evidence** between proteins.
    
    It generates direct links to STRING’s evidence pages, which show the sources and scores (e.g., co-expression, experiments, databases) behind each predicted interaction.
    
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

    output = []
    for identifier_b in identifiers_b.split("%0d"):
        link = f"{base_url}/interaction/{identifier_a}/{identifier_b}?species={species}"
        output.append(link)

    return {"results": output}



@mcp.tool(title="STRING: Functional enrichment analysis")
async def string_enrichment(
    proteins: Annotated[
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
    params = {"identifiers": proteins}
    if background_string_identifiers is not None:
        params["background_string_identifiers"] = background_string_identifiers
    if species is not None:
        params["species"] = species

    endpoint = f"/api/json/enrichment"

    async with httpx.AsyncClient(base_url=base_url) as client:
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        res = truncate_enrichment(r.json(), 'json')
        return {"results": res}


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

    async with httpx.AsyncClient(base_url=base_url) as client:
        params = {"identifiers": identifiers, "species": species}
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()
        return {"results": r.json()}  # Functional annotation per protein


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
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


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
        log_call(endpoint, params)
        r = await client.post(endpoint, data=params)
        r.raise_for_status()

        return {"results": r.json()}


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
            "NCBI/STRING taxonomy ID. Default is 9606 (human). "
            "Examples: 10090 for mouse, or STRG0AXXXXX for uploaded genomes."
        ))
    ] = "9606"
) -> dict:
    """
    Retrieve the proteins associated with a functional term or descriptive text.

    This tool searches STRING’s knowledge base for the provided functional concept
    (either a database identifier or free-text description) and returns the proteins
    that are annotated to it for the specified species.

    Output fields:
      - category: Source database of the matched functional term
                  (e.g. GO, KEGG, Reactome, Pfam, InterPro).
      - term: Exact identifier for the functional term.
      - preferredNames: List of human-readable protein names.
      - stringIds: List of STRING protein identifiers, aligned with preferredNames
                   (i.e., same length and order, so element i in both lists refers
                   to the same protein).

    Notes for the agent:
      - The returned stringIds can be directly passed to other STRING tools
        (e.g. network queries, funtional analysis).
    """
    params = {"term_text": term_text, "species": species}

    endpoint = "/api/json/functional_terms"
    async with httpx.AsyncClient(base_url=base_url) as client:
        log_call(endpoint, params)
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

def log_call(endpoint, params):

    if log_verbosity['call']:
        print(f"Call: {endpoint}", file=sys.stderr)

    if log_verbosity['taskid']:
        headers = get_http_headers()
        client_id = headers.get("x-client-id", "None")
        task_id = headers.get("x-task-id", "None")
        print("TaskId:", task_id, file=sys.stderr)
        print("ClientId:", client_id, file=sys.stderr)
 
    if log_verbosity['params']:
        print("Params:", file=sys.stderr)
        for param, value in params.items():
            print(f'    {param}: {str(value)}', file=sys.stderr)
            
       
        


# ---- MCP server runner ----

if __name__ == "__main__":
    # Add CORS in your proxy (nginx) for browser-based playgrounds
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=server_port,
        log_level="info",
        stateless_http=True,
    )

