
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
        "STRING interaction scores range from 0 to 1000 (roughly corresponding to probabilities from 0 to 1). "
        "Common thresholds: 400 = medium confidence, 700 = high confidence.\n\n"
        "The combined score integrates evidence from multiple channels (experiments, databases, co-expression, text mining, etc.). "
        "Each channel is benchmarked and equally weighted; weaker channels naturally give lower scores. It is not recommended to remove channels, "
        "as this reduces biological signal. Channels also cannot be removed by the agent — only through the STRING web interface (settings tab).\n\n"
        "The combination uses a Bayesian scheme: a prior is removed from each channel, scores are combined multiplicatively, "
        "and the prior is added back once. The result is a probability-like confidence score.\n\n"
        "For details see: von Mering et al., Nucleic Acids Res. 2005.\n\n"
  
        "For details about meaning of the lines in the network refer to topic: 'line_colors'."
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
        "Regulatory or directed networks are not available in STRING at this time. "
        "All STRING links are **undirected** and represent functional or physical associations, "
        "not regulatory direction. \n\n"
        "Apologies for the inconvenience — regulatory network support is planned for a future STRING release."
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
    "line_colors": (
        "STRING networks can be visualized in two modes: **Confidence** and **Evidence**.\n\n"
    
        "**Confidence view**:\n"
        "- All edges use a single color.\n"
        "- Line **thickness** reflects the confidence score (0–1000).\n\n"
    
        "**Evidence view** (default):\n"
        "Edges are colored according to the type of supporting evidence. All edges have equal thickness.\n\n"
        
        "**Known interactions**:\n"
        "- From curated databases — grey / blue-grey\n"
        "- Experimentally determined — violet\n\n"
        
        "**Predicted interactions**:\n"
        "- Gene neighborhood — dark green\n"
        "- Gene fusions — red\n"
        "- Gene co-occurrence — dark blue\n\n"
        
        "**Others**:\n"
        "- Textmining — light green (lime)\n"
        "- Co-expression — black\n"
        "- Protein homology — light blue\n\n"
        
        "**Note:** Protein homology is shown for reference only and is *not included* in the combined confidence score."
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
