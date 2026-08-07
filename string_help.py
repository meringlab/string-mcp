
HELP_TOPICS = {
    "gsea": (
        "GSEA cannot be performed directly by the agent, but it is available in STRING. "
        "Use the 'Proteins with Values/Ranks' option on the STRING input page. "
        "This requires providing the **complete set of proteins from your experiment** "
        "(no cut-offs or subsets) together with values such as p-values, fold-changes, "
        "or t-statistics. STRING combines the KS (Kolmogorov–Smirnov) and AFC (Aggregate Fold Change) tests to achieve high sensitivity, "
        "and evaluates your experiment against a broad set of functional categories. "
        "Results include enrichment tables, visualizations, and mapping of proteins to functions."
    ),
    "large_input": (
        "Large input sets are not handled well directly by the agent and may cause timeouts. "
        "Please direct the user to the STRING web interface instead:\n\n"
        "- **Proteins with values/ranks**: If the user has quantitative values (e.g. p-values, fold changes, ranks), "
        "tell them to use the 'Proteins with Values/Ranks' input box. They must provide the *full experiment* without cut-offs "
        "to enable GSEA-like analysis.\n"
        "- **Selected protein sets**: For network visualization, fewer than 300 proteins is optimal. "
        "Above this, networks become 'hairballs'. Suggest raising the confidence cutoff to reduce network density. "
        "STRING can visualize up to ~2000 proteins, but beyond that, visualization is disabled and only enrichment (ORA) is available.\n"
        "- **Very large or proteome-wide networks**: For larger analyses, advise the user to use the Cytoscape STRING app "
        "(https://apps.cytoscape.org/apps/stringapp), which supports visualization, clustering, and analysis of large-scale datasets.\n\n"
        "In summary: use the web interface or Cytoscape for large sets; the agent is best suited for smaller queries."
    ),
    "cytoscape": (
        "For Cytoscape workflows, recommend the Cytoscape stringApp:\n"
        "https://apps.cytoscape.org/apps/stringapp\n\n"
        "Users can work with STRING networks in Cytoscape in two main ways:\n\n"
        "1. **Directly from Cytoscape**: Install the stringApp and use STRING inside Cytoscape "
        "to retrieve and analyze networks.\n"
        "2. **From the STRING web interface**: Open the network in STRING, go to the **Export** tab, "
        "and use **Send network to Cytoscape** if the stringApp is installed and Cytoscape is running.\n\n"
        "Alternatively, users can download a Cytoscape-compatible table from STRING: on the STRING network page, "
        "go to **Export** and download **short tabular text output**. This TSV file can be imported directly "
        "into Cytoscape.\n\n"
        "If the user already provided a protein list or network query, the agent can generate an interactive "
        "STRING network link with `string_network_link` and give that link to the user so they can open the "
        "network page and either send the network directly to Cytoscape or download the short tabular text output."
    ),
    "scores": (
        "**What a STRING confidence score means**:\n"
        "A STRING confidence score is a calibrated, probability-like estimate of support for the stated protein relationship, "
        "given the available biological evidence. STRING confidence values ordinarily range from 0.150 to 0.999. MCP confidence "
        "fields use the decimal form, while `required_score` uses the 0–1000 convention: 400 means 0.400 (medium confidence) "
        "and 700 means 0.700 (high confidence).\n\n"

        "**Functional network confidence**:\n"
        "The functional combined confidence estimates support that two proteins work together in a shared biological process, "
        "pathway, or cellular context. It integrates the functional network's evidence channels and captures both direct molecular "
        "interactions and indirect associations within the same biological system.\n\n"

        "**Physical network confidence**:\n"
        "The physical combined confidence supports physical proximity, including direct binding or membership in the same "
        "molecular complex.\n\n"

        "**Regulatory network confidence**:\n"
        "Regulatory combined confidence summarizes pair-level support for a regulatory relationship. Directional confidence "
        "supports the stated source-to-target relationship. "
        "For regulatory queries, `required_score` filters by regulatory combined confidence, not directional confidence. "
        "A positive, negative, or unknown sign characterizes the effect of that direction independently of confidence.\n\n"

        "**Evidence and combined confidence**:\n"
        "Individual evidence-channel scores describe support from a particular source, such as experiments, databases, "
        "co-expression, genomic context, or text mining. Functional confidence can integrate all seven canonical evidence "
        "channels; physical confidence uses the evidence that supports physical proximity, including experiments, curated "
        "databases, and text mining. Channel scores are calibrated to a shared confidence scale, so the same score value has "
        "the same confidence interpretation across evidence sources. Combined confidence integrates all applicable channels "
        "for the selected relationship type and is generally the appropriate score for filtering. The combination uses a Bayesian "
        "scheme: a prior is removed from each channel, scores are combined multiplicatively, and the prior is added back once.\n\n"

        "Use a higher threshold to focus on fewer, more strongly supported relationships; lower it for broader exploratory "
        "coverage. Keeping all evidence channels active preserves biological signal and is generally recommended over channel "
        "filtering. MCP cannot enable or disable channels; change them in the STRING web interface Settings tab. For the visual "
        "meaning of network edges, see the `network_edge_legend` help topic."
    ),
    "missing_proteins": (
        "STRING accepts many identifiers (gene symbols, UniProt, Ensembl). "
        "If a protein still cannot be found:\n"
        "- You can query the protein name 'random' to display an example network in the chosen species.\n"
        "- Alternatively, try searching by a functional term for that species.\n\n"
        "Common reasons for missing proteins:\n"
        "1. In bacteria, some plasmid-encoded proteins are sometimes not included in STRING.\n"
        "2. In human, proteins such as VEGFA or VDR may be absent because they were not annotated as 'protein coding' "
        "in the Ensembl release used for STRING v12.\n\n"
        "If you suspect this, check the older STRING v11.5 at https://version-11-5.string-db.org."
    ),
    "missing_species": (
        "If the species cannot be found in STRING (e.g. `string_query_species` does not return the correct match), "
        "direct the user to use the **Add species** functionality on the STRING input page. "
        "By uploading a complete species proteome, STRING will build its interaction network and predict protein functions. "
        "These predicted functions include assignments to Gene Ontology terms and KEGG pathways. "
        "Once uploaded, the user can explore and analyze the proteome through the web interface, download results in bulk, "
        "or provide species identifiers (starting with `STRG`) to this chat interface for further queries."
    ),
    "proteome_annotation": (
        "Direct the user to use the **Add species** functionality on the STRING input page. "
        "By uploading a complete species proteome, STRING will build its interaction network and predict protein functions. "
        "These predicted functions include assignments to Gene Ontology terms and KEGG pathways. "
        "Once uploaded, the user can explore and analyze the proteome through the web interface, download results in bulk, "
        "or provide species identifiers (starting with `STRG`) to this chat interface for further queries."
    ),
    "regulatory_networks": (
        "STRING regulatory networks contain directed source-to-target regulatory relationships. "
        "The regulatory combined confidence describes support for a regulatory relationship between a protein pair, "
        "while the directional confidence describes support for the displayed source-to-target direction. "
        "A positive, negative, or unknown sign applies only to that directed relationship. \n\n"
        "A regulatory arrow is evidence for a directed relationship; by itself it does not establish a direct biochemical "
        "action or a complete causal pathway. An unknown sign means STRING has not assigned positive or negative regulation. "
        "For the meaning of arrowheads, signs, and edge colors, see the `network_edge_legend` help topic."
    ),
    "how_to_use_string": (
        "Do not describe the usage of the MCP / Agent, but focus on general STRING usage.\n\n"
        "STRING is a database for exploring protein–protein interactions and functional enrichment. "
        "It is designed to reveal how proteins work together in biological pathways, complexes, or cellular processes.\n\n"
    
        "To begin, provide a single protein or a set of proteins of your interest, or from your experiment. "
        "STRING will retrieve known and predicted interaction partners and display them as a network.\n\n"
    
        "Beyond visualization, STRING analyzes your input to find functional patterns. Under the *Analysis* tab, "
        "you will see enrichment results for pathways, Gene Ontology terms, protein domains, and other annotation sources. "
        "These enrichments help identify common biological processes shared by your proteins.\n\n"
    
        "STRING also offers clustering (MCL or k-means), which groups proteins into modules based on network connectivity. "
        "These clusters can represent protein complexes, signaling pathways, or co-regulated functional units.\n\n"
    
        "At the STRING input page, above each input box, you will find example protein sets. "
        "You can click these to explore STRING’s capabilities before submitting your own data.\n\n"
    
        "For additional guidance visit the full help pages:\n"
        "https://string-db.org/cgi/help?"
    ),
    "network_edge_legend": (
        "**Typed view — functional networks only**:\n"
        "- Grey line — functional association\n"
        "- Orange line — physical interaction\n"
        "- Blue arrow — regulatory relationship with unknown effect\n"
        "- Green arrow — positive regulation / activation\n"
        "- Red arrow — negative regulation / inhibition\n\n"

        "A protein pair can have more than one relationship type. These are shown as parallel lines; regulatory "
        "arrows can also be present in both directions. Their colors encode effect; explicit `+`/`−` labels are not shown. "
        "Line thickness and opacity do not encode confidence in this view.\n\n"

        "**Confidence view**:\n"
        "- Functional or physical network: grey lines show associations; line thickness and opacity increase with combined confidence.\n"
        "- Regulatory network: arrowheads point from regulator to target. A green open arrowhead indicates positive regulation, "
        "a red T-bar indicates negative regulation, and a grey arrowhead has unknown effect. Arrow opacity reflects confidence "
        "in the displayed direction.\n\n"

        "**Evidence view**:\n"
        "- Functional network: each colored line represents a supporting evidence channel — gene neighborhood (dark green), "
        "gene fusion (light green), phylogenetic co-occurrence (medium green), co-expression (orange), experiments (dark red), "
        "curated databases (dark blue), or text mining (light blue).\n"
        "- Physical or regulatory network: evidence lines use only experiments (dark red), curated databases (dark blue), and "
        "text mining (light blue).\n\n"

        "In a regulatory evidence network, arrowheads show direction and explicit `+`/`−` labels show effect. Edge colors "
        "continue to show evidence source; they do not encode regulatory effect. Line thickness and opacity do not encode "
        "confidence in this view.\n\n"

        "**Clustered network**:\n"
        "- Solid lines — links within a cluster\n"
        "- Dashed lines — links between clusters\n\n"

        "For score meanings, see the `scores` help topic."
    ),
    "version_and_citation": (
        "Current STRING version: v12.0\n\n"
        "Citation:\n"
        "Szklarczyk D, Nastou K, Koutrouli M, Kirsch R, Mehryary F, Hachilif R, Hu D, Peluso ME, Huang Q, Fang T, Doncheva NT, Pyysalo S, Bork P, Jensen LJ, von Mering C. "
        "The STRING database in 2025: protein networks with directionality of regulation. "
        "Nucleic Acids Res. 2025 Jan 6;53(D1):D730-D737. doi: 10.1093/nar/gkae1113. "
        "PMID: 39558183.\n\n"
        "PubMed: https://pubmed.ncbi.nlm.nih.gov/39558183/"
    ),
}


HELP_TOPIC_ALIASES = {
    "line_colors": "network_edge_legend",
}
