
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
    "clustering": (
        "Clustering cannot be performed directly by the agent, but it is available in STRING. "
        "Direct the user to the standard multi-protein input box on the STRING website. "
        "If the user already has a protein or network, you may provide a link to the interactive network page using the appropriate tool. "
        "On that page, the user can cluster the network under the **Clustering tab** below the network picture. "
        "STRING offers two methods: MCL (with an inflation parameter) and k-means (with a k parameter). "
        "Clustering is based on the connectivity of proteins in the network."
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
    "scores": (
        "STRING interaction scores range from 0 to 1000 (roughly corresponding to probabilities from 0 to 1). "
        "Common thresholds: 400 = medium confidence, 700 = high confidence.\n\n"
        "The combined score integrates evidence from multiple channels (experiments, databases, co-expression, text mining, etc.). "
        "Each channel is benchmarked and equally weighted; weaker channels naturally give lower scores. It is not recommended to remove channels, "
        "as this reduces biological signal. Channels also cannot be removed by the agent — only through the STRING web interface (settings tab).\n\n"
        "The combination uses a Bayesian scheme: a prior is removed from each channel, scores are combined multiplicatively, "
        "and the prior is added back once. The result is a probability-like confidence score.\n\n"
        "For details see: von Mering et al., Nucleic Acids Res. 2005."
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
}


