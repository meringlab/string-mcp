---
name: string-database
description: Use when answering questions with STRING database MCP tools for protein-protein interactions, interaction partners, network images, interactive STRING links, evidence pages, functional enrichment, PPI enrichment, functional annotations, proteins associated with terms, homologs, sequence search, species lookup, or STRING limitations.
---

# STRING Database

Use the STRING MCP tools as the source of truth for protein interaction, network, enrichment, annotation, evidence, species, and homolog questions.

## Grounding Rules

- Use STRING tool output for factual claims about interactions, functions, pathways, enrichment, annotations, homologs, and species availability.
- If no species is provided, use human, NCBI taxon ID `9606`.
- Do not guess, assemble, or derive STRING links or image URLs. Only show exact links and image URLs returned by tools.
- If a requested claim is not supported by the current tool output in context, retrieve the relevant STRING data with parameters specific to the new claim.
- If identifiers are ambiguous, resolve them with `string_resolve_proteins` before analysis.
- If the input is an amino acid sequence rather than an identifier, use `string_sequence_search`.
- If a species name or taxon is uncertain, use `string_query_species`.
- If a requested STRING capability is unavailable through the tools, use `string_help` when a matching help topic exists.
- Avoid repeating the same tool call with identical inputs unless the user asks to retry.

## Tool Selection

Use `string_resolve_proteins` to map gene symbols, UniProt IDs, or other protein identifiers to STRING metadata.

Use `string_interactions_query_set` to retrieve interactions among the submitted proteins. Functional queries use the integrated `typed` network flavor by default. For binding, complex, co-complex, or physical-interaction questions, set `network_type` to `physical`. For directed regulatory relationships, regulators, targets, or signaling direction, set `network_type` to `regulatory`.

Use `string_all_interaction_partners` when the user asks what a protein interacts with, or asks for partners beyond the submitted set. For regulatory partners, `network_type=regulatory` returns both incoming and outgoing directed relationships.

Use `string_visual_network` when the user asks for a network image. Use the same protein, species, score, extension, network-type, and network-flavor parameters as related network calls.

Use `string_network_link` when the user asks for an interactive STRING network page. Use `network_type=regulatory` for a directed regulatory network.

Use `string_network_clustering` when the user asks for network clusters, modules, or grouped subnetworks. It uses Leiden clustering with resolution 1.0 and faded inter-cluster edges by default; set the clustering options only when the user requests a different algorithm, granularity, or edge display.

Use `string_interaction_evidence` when the user asks for STRING evidence pages for specific protein pairs. Use the matching `network_type` for physical or regulatory evidence pages. If the user asks whether an interaction is supported, first verify with `string_interactions_query_set`.

Use `string_enrichment` for functional enrichment. Report FDR values for enrichment claims. For a single protein, remember that STRING expands the query before enrichment.

Use `string_enrichment_image_url` when the user asks for an enrichment plot or visualization. Match the enrichment category to the user's request when possible.

Use `string_ppi_enrichment` when the user asks whether a protein set has more interactions than expected by chance. Report the p-value.

Use `string_functional_annotation` when the user asks what proteins do, where they localize, where they are expressed, or which pathways they participate in.

Use `string_proteins_for_term` when the user provides a function, disease, pathway, tissue, compartment, or domain instead of a protein list.

Use `string_homology` for homolog or sequence-similarity questions across species or clades.

Use `string_create_file` only when the user asks for downloadable or reusable STRING-derived output.

Use `string_help` for STRING usage, score interpretation, missing species, missing proteins, large input, Cytoscape, GSEA, regulatory-network limitations, line colors, version, and citation questions.

## Analysis Workflow

1. Identify proteins, species, analysis type, and whether the user wants functional, physical, or directed regulatory relationships.
2. Resolve ambiguous identifiers or species before running biological analysis.
3. Choose the smallest STRING tool call that directly answers the question.
4. Keep related calls parameter-consistent, especially `proteins` or `identifiers`, `species`, `required_score`, `network_type`, and network expansion.
5. Treat network images as visualizations, not evidence by themselves. Use interaction tools to verify interaction claims.
6. For enrichment, summarize the strongest relevant terms and include FDR values. If categories are truncated, use `expand_category` when deeper category-specific detail is needed.
7. For reusable result tables, offer TSV or CSV output and create the file only when requested.

## Common Patterns

For "Does A interact with B?", call `string_interactions_query_set` with both proteins. If the interaction exists, include score details; call `string_interaction_evidence` when the user asks for supporting evidence or a STRING evidence link.

For "Does A regulate B?" or a signaling-direction question, call `string_interactions_query_set` with `network_type=regulatory`. State the source-to-target direction exactly as returned. A positive, negative, or unknown sign applies only to that directed relationship; do not infer a sign when it is unknown.

For "Show me the interaction network for these proteins", call `string_visual_network`. If the user also wants a clickable STRING page, call `string_network_link`. To discuss which interactions are present, call `string_interactions_query_set`.

For "What pathways are enriched in this list?", call `string_enrichment`. If the user wants a figure, call `string_enrichment_image_url` for the relevant category.

For "Is this protein involved in X?" or "What does this protein do?", call `string_functional_annotation`. If little or no functional annotation is returned, use `string_interactions_query_set` and `string_enrichment` for interaction-context clues from STRING.

For "Find proteins involved in X", call `string_proteins_for_term`, then use follow-up STRING tools only if the user asks to analyze the returned proteins.

For "This organism is missing" or "which species are supported?", call `string_query_species`; if the requested species is not found, use `string_help` with the missing-species topic.
