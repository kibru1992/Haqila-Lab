# Haqila Lab: AI for Health Ecosystem Mapping & Systematic Review Research
## July Timeline: Data Collection & AI Pipeline Setup

This repository contains the programmatic literature data collection and NLP-based initial keyword and semantic filtering pipeline designed for the **July Timeline** deliverables of the Haqila Lab Research Internship Program.

### Project Context
* **Health Domain**: Community-based Infectious Disease (Malaria).
* **Target Geography**: East Africa / Sub-Saharan Africa (with a focus on regional trends across Ethiopia).
* **Goal**: Retrieve literature from multiple academic databases and repositories, apply Boolean keyword limits based on PRISMA guidelines, and rank articles by semantic similarity to find community-based malaria programs, interventions, and stakeholders in the target geography.

---

### Ingestion Databases
The pipeline programmatically queries and aggregates records from 5 distinct data repositories:
1. **PubMed / MEDLINE**: Searches titles/abstracts and retrieves XML abstracts using Entrez E-utilities.
2. **Scopus**: Uses Elsevier Scopus Search API (falls back to a simulated dataset if no `SCOPUS_API_KEY` is provided).
3. **African Journals OnLine (AJOL)**: Scrapes search HTML results and parses landing page Dublin Core metadata tags (title, author, abstract, journal, date).
4. **WHO IRIS (WHO Repository)**: Uses DSpace 7 REST API discovery search endpoint to extract technical publications.
5. **EPHI (Ethiopian Public Health Institute)**: Searches PubMed for EPHI affiliations and merges results with local registry reports (`data/ephi_registry.json`).

---

### NLP Screening Pipeline
Each article undergoes a two-stage screening pipeline:
1. **PRISMA Boolean screening**:
   - **Inclusion**: Published between 2016 and 2026; contains malaria/plasmodium terms; contains Sub-Saharan Africa or Low-and-Middle-Income country (LMIC) geographical keywords.
   - **Exclusion**: Excludes publications focusing purely on non-infectious chronic conditions (e.g. diabetes, cancer, Alzheimer's) without malaria focus.
2. **Semantic Similarity Screening**:
   - Computes cosine similarity between (title + abstract) and target review criteria using the `all-MiniLM-L6-v2` SentenceTransformer model.
   - If the similarity is above the threshold (default `0.40`), it is marked as `Included` for detailed synthesis. Otherwise, it is `Excluded`.

3. **August Timeline: Information Extraction & Named Entity Recognition (NER)**:
   - For all `Included` articles, the pipeline runs a **hybrid NER extractor** to identify:
     - **Diseases & Vectors**: Malaria, Plasmodium species, Anopheles mosquitoes.
     - **Stakeholders**: Ministry of Health, EPHI, NDMC, WHO, USAID, CDC, etc.
     - **Locations**: Ethiopian administrative regional states (Amhara, Oromia, Tigray, SNNPR, Southwest Ethiopia, etc.), cities, and specific health clinics.
     - **Programs & Interventions**: LLIN distribution, Indoor Residual Spraying (IRS), Rapid Diagnostic Testing (RDT), Health Extension Workers (HEW) case management.
   - Automatically **infers relationships** (e.g. `INVOLVED_IN`, `LOCATED_IN`, `TARGETS`) between entities based on sentence-level co-occurrence.

4. **August Timeline: Relational & Graph Database Structuring**:
   - Initializes a local relational **SQLite** database (`data/health_ecosystem.db`) mapping the articles, nodes (entities), and edges (relationships).
   - Exports the populated structure into a standardized **Graph JSON** format (`data/health_ecosystem_graph.json`) containing nodes and edges arrays for easy visualization and future import into Neo4j.

---

### Project Structure
```
├── src/
│   ├── config.py           # Configuration parameters, keywords, and entity dictionaries
│   ├── data_collection.py  # Ingestion harvesters for PubMed, Scopus, AJOL, WHO IRIS, EPHI
│   ├── nlp_filtering.py    # Boolean keyword screening and semantic similarity ranker
│   ├── entity_extraction.py# [NEW] Hybrid NER entity and relationship extraction
│   ├── database.py         # [NEW] SQLite database storage and Graph JSON exporter
│   └── test_embeddings.py  # Evaluation script comparing embeddings relevance
├── data/
│   └── ephi_registry.json  # Internal EPHI registry mock reports
├── main.py                 # Main pipeline orchestrator CLI (July & August Timelines)
├── requirements.txt        # Package dependencies
└── README.md               # User documentation
```

---

### Installation & Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **(Optional) Configure Scopus API Key**:
   Set the `SCOPUS_API_KEY` environment variable in your shell if you wish to run live Scopus searches:
   ```powershell
   # Windows PowerShell
   $env:SCOPUS_API_KEY="your_api_key_here"
   ```

---

### Running the Pipeline

- **Run embedding models evaluation**:
  To compare the precision of dense sentence embedding models against sparse TF-IDF baselines:
  ```bash
  python main.py --run-eval
  ```

- **Run the full pipeline with default limits**:
  Fetches, deduplicates, and screens articles, saving outputs in the `data/` folder:
  ```bash
  python main.py --limit-fetch 15
  ```

### Outputs
After execution, the following structured files are generated in the `data/` directory:
- `data/raw_articles.json`: Aggregated raw metadata records from all 5 databases before screening.
- `data/screened_articles.json`: Detailed JSON file containing final screening decisions, boolean evaluation, and semantic scores.
- `data/screening_report.csv`: A structured Excel-compatible CSV summary sheet of decisions, useful as input for the systematic review PRISMA diagram.
- `data/health_ecosystem.db`: [NEW] Relational SQLite database holding articles, entities, context sentences, and inferred relationships.
- `data/health_ecosystem_graph.json`: [NEW] Graph database representation mapping nodes (entities) and edges (relationships) for visualization and Neo4j import.
