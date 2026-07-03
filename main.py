import os
import sys
import json
import argparse
import pandas as pd
from src.data_collection import collect_all_data
from src.nlp_filtering import screen_articles
from src.test_embeddings import run_evaluation
from src.entity_extraction import extract_entities_from_article, infer_relationships
from src.database import init_database, insert_extracted_data, export_to_graph_json

def main():
    parser = argparse.ArgumentParser(description="AI for Health Ecosystem Mapping - July & August Timelines Systematic Review Pipeline")
    parser.add_argument("--limit-fetch", type=int, default=20, help="Fetch limit per search database for dry-run/testing")
    parser.add_argument("--output-dir", type=str, default="data", help="Directory where search and screening outputs are saved")
    parser.add_argument("--run-eval", action="store_true", help="Runs the embedding models evaluation comparison before running pipeline")
    
    args = parser.parse_args()
    
    # 1. Run evaluation if requested
    if args.run_eval:
        run_evaluation()
        print("\n" + "="*70 + "\n")
        
    print("======================================================================")
    print("Starting July Timeline: Data Collection & AI Screening Pipeline")
    print("======================================================================\n")
    
    # Ensure output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # 2. Programmatic Ingestion from 5 databases
    # Limits mapping based on limit_fetch CLI arg
    limits = {
        "pubmed": args.limit_fetch,
        "scopus": min(10, args.limit_fetch),
        "ajol": min(10, args.limit_fetch),
        "who_iris": min(15, args.limit_fetch),
        "ephi": min(15, args.limit_fetch)
    }
    
    print("--- 1. Ingesting Literature from Repositories ---")
    raw_articles = collect_all_data(limits=limits)
    
    # Save raw records
    raw_path = os.path.join(args.output_dir, "raw_articles.json")
    with open(raw_path, "w", encoding="utf-8") as f:
        json.dump(raw_articles, f, indent=2, ensure_ascii=False)
    print(f"Saved {len(raw_articles)} raw merged articles to: {raw_path}")
    
    if not raw_articles:
        print("[WARNING] No articles collected. Exiting pipeline.")
        sys.exit(0)
        
    # 3. NLP Initial Keyword and Semantic Screening
    print("\n--- 2. Running NLP Screening (PRISMA Inclusion/Exclusion) ---")
    screened_articles = screen_articles(raw_articles)
    
    # Save fully screened records JSON
    screened_path = os.path.join(args.output_dir, "screened_articles.json")
    with open(screened_path, "w", encoding="utf-8") as f:
        json.dump(screened_articles, f, indent=2, ensure_ascii=False)
    print(f"Saved screened articles data to: {screened_path}")
    
    # 4. Generate structured Screening Report (CSV)
    report_data = []
    for a in screened_articles:
        report_data.append({
            "Article ID": a.get("id"),
            "Title": a.get("title"),
            "Authors": ", ".join(a.get("authors", [])),
            "Year": a.get("date"),
            "Journal": a.get("journal"),
            "Source Database": a.get("source"),
            "Boolean Pass": a.get("boolean_pass"),
            "Boolean Fail Reason": a.get("boolean_fail_reason", ""),
            "Semantic Score": a.get("semantic_score", 0.0),
            "Screening Status": a.get("status"),
            "Decision Reason": a.get("reason"),
            "URL": a.get("url")
        })
        
    df = pd.DataFrame(report_data)
    csv_path = os.path.join(args.output_dir, "screening_report.csv")
    df.to_csv(csv_path, index=False, encoding="utf-8")
    print(f"Saved structured screening report to: {csv_path}")
    
    # 5. Output statistics summary
    total = len(screened_articles)
    included = sum(1 for a in screened_articles if a["status"] == "Included")
    excluded = total - included
    bool_failed = sum(1 for a in screened_articles if not a["boolean_pass"])
    semantic_failed = excluded - bool_failed
    
    print("\n" + "="*70)
    print("SCREENING PIPELINE STATISTICS SUMMARY")
    print("="*70)
    print(f"Total Unique Articles Screened: {total}")
    print(f"  - INCLUDED for detailed synthesis: {included}")
    print(f"  - EXCLUDED: {excluded}")
    print(f"    * Excluded by Boolean/PRISMA keyword rules: {bool_failed}")
    print(f"    * Excluded by Semantic relevance criteria:  {semantic_failed}")
    print("="*70)
    
    # 6. August Timeline: Information Extraction and Database creation
    print("\n--- 3. August Timeline: Running Information Extraction (NER) & Database Creation ---")
    db_path = os.path.join(args.output_dir, "health_ecosystem.db")
    graph_path = os.path.join(args.output_dir, "health_ecosystem_graph.json")
    
    # Initialize structured database
    init_database(db_path=db_path)
    
    extractions_map = {}
    print("Running NER and inferring relationships on included articles...")
    for art in screened_articles:
        if art.get("status") != "Included":
            continue
        art_id = art.get("id")
        entities = extract_entities_from_article(art)
        relationships = infer_relationships(entities)
        print(f"  - [{art_id}] Extracted {len(entities)} entities, {len(relationships)} relationships.")
        extractions_map[art_id] = {
            "entities": entities,
            "relationships": relationships
        }
        
    print("\nStoring entities and relations in SQLite database...")
    insert_extracted_data(screened_articles, extractions_map, db_path=db_path)
    
    print("Exporting database to Graph JSON nodes and edges representation...")
    export_to_graph_json(db_path=db_path, output_path=graph_path)
    
    print("\nJuly & August Timelines execution completed successfully!")

if __name__ == "__main__":
    main()
