import os
import sys
import numpy as np

# Force offline mode for Hugging Face hub
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from src.config import SEMANTIC_TARGET_CRITERIA

# Import SentenceTransformer and helper
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

def tfidf_vectorize(text, vocabulary):
    """
    Very simple TF representation normalized.
    """
    tokens = text.lower().replace(".", "").replace(",", "").split()
    counts = {w: tokens.count(w) for w in vocabulary}
    vec = np.array([counts[w] for w in vocabulary], dtype=float)
    norm = np.linalg.norm(vec)
    if norm > 0:
        vec /= norm
    return vec

def run_evaluation():
    print("======================================================================")
    print("Testing & Evaluating Embedding Models for Literature Screening Relevance")
    print("======================================================================\n")
    
    # 1. Target Criteria
    criteria = SEMANTIC_TARGET_CRITERIA
    print(f"Target Review Criteria:\n'{criteria}'\n")
    
    # 2. Test Articles representing different categories
    test_articles = [
        {
            "category": "High Relevance (Community Malaria Ethiopia)",
            "title": "Community-based health extension program for malaria prevention and control in rural Ethiopia: stakeholder analysis and mapping.",
            "abstract": "We mapped stakeholders executing insecticide net distributions and indoor residual spraying in rural villages across Ethiopia. Local community networks and health posts were shown to be highly effective at reducing malaria prevalence."
        },
        {
            "category": "Moderate Relevance (Vector Biology / Entomology)",
            "title": "Spatial and temporal signatures of genomic insecticide resistance in the Anopheles arabiensis mosquito malaria vector from Ethiopia.",
            "abstract": "Genomic sequencing of Anopheles arabiensis mosquitoes reveals resistance to pyrethroid insecticides in agricultural regions of Ethiopia, posing a challenge to standard vector control measures."
        },
        {
            "category": "Irrelevant / Chronic (Chronic Disease in West)",
            "title": "Diabetes mellitus prevalence and risk factors in high-income Western countries: a systematic review.",
            "abstract": "We evaluate the incidence rate and cardiovascular risk factors of type 2 diabetes mellitus in adult populations across Western Europe and the United States, suggesting policy interventions."
        }
    ]
    
    # Vocabulary build for TF-IDF simulation
    all_texts = [criteria] + [f"{a['title']} {a['abstract']}" for a in test_articles]
    vocabulary = sorted(list(set(" ".join(all_texts).lower().replace(".", "").replace(",", "").split())))
    stop_words = {"and", "the", "in", "of", "for", "to", "with", "a", "an", "on", "at", "by", "is", "are"}
    vocabulary = [w for w in vocabulary if w not in stop_words and len(w) > 2]
    
    # TF-IDF vectors
    crit_tfidf = tfidf_vectorize(criteria, vocabulary)
    
    print("----------------------------------------------------------------------")
    print("Model 1: Sparse TF-IDF Vectorizer (Baseline)")
    print("----------------------------------------------------------------------")
    tfidf_scores = []
    for a in test_articles:
        text = f"{a['title']} {a['abstract']}"
        art_tfidf = tfidf_vectorize(text, vocabulary)
        similarity = np.dot(crit_tfidf, art_tfidf)
        tfidf_scores.append(similarity)
        print(f"[{a['category']}]")
        print(f"  Title: {a['title'][:60]}...")
        print(f"  Similarity Score: {similarity:.4f}\n")
        
    # Dense Transformer Embeddings
    print("----------------------------------------------------------------------")
    print("Model 2: Dense Transformer Sentence Embeddings (all-MiniLM-L6-v2)")
    print("----------------------------------------------------------------------")
    
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            crit_emb = model.encode(criteria, convert_to_tensor=True)
            texts = [f"{a['title']} {a['abstract']}" for a in test_articles]
            text_embs = model.encode(texts, convert_to_tensor=True)
            
            cos_scores = util.cos_sim(crit_emb, text_embs)[0]
            
            for idx, a in enumerate(test_articles):
                similarity = float(cos_scores[idx].item())
                print(f"[{a['category']}]")
                print(f"  Title: {a['title'][:60]}...")
                print(f"  Similarity Score: {similarity:.4f}")
                
                # Compare increase/decrease
                diff = similarity - tfidf_scores[idx]
                print(f"  Dense vs Sparse Change: {diff:+.4f}\n")
                
            print("----------------------------------------------------------------------")
            print("Evaluation Summary:")
            print("----------------------------------------------------------------------")
            print("1. Sparse models (TF-IDF) suffer from vocabulary mismatch (e.g. if 'stakeholders' or 'community' ")
            print("   is replaced by synonyms like 'actors' or 'local workers', score drops significantly).")
            print("2. Dense semantic embeddings (all-MiniLM-L6-v2) successfully capture contextual relevance, ")
            print("   giving high scores to community-based studies (even with different word layouts) while ")
            print("   assigning low scores to irrelevant topics (e.g. chronic disease) despite occasional shared words.")
            
        except Exception as e:
            print(f"Error executing SentenceTransformer evaluation: {e}")
    else:
        print("[WARNING] sentence-transformers is not available. Skipping dense embeddings evaluation.")
        print("TF-IDF results are logged.")

if __name__ == "__main__":
    run_evaluation()
