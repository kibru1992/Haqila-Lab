import os
import sys

# Force offline mode for Hugging Face hub
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

from src.config import (
    SEMANTIC_TARGET_CRITERIA,
    SEMANTIC_THRESHOLD,
    EXCLUSION_KEYWORDS,
    INCLUSION_KEYWORDS_DISEASE,
    INCLUSION_KEYWORDS_GEO,
    INCLUSION_YEAR_START,
    INCLUSION_YEAR_END
)

# Try to import sentence-transformers
SENTENCE_TRANSFORMERS_AVAILABLE = False
try:
    from sentence_transformers import SentenceTransformer, util
    SENTENCE_TRANSFORMERS_AVAILABLE = True
    print("[INFO] sentence-transformers loaded successfully in offline mode.")
except ImportError as e:
    print(f"[WARNING] sentence-transformers import failed ({e}). Falling back to keyword-based semantic simulation.")

def boolean_screen(article):
    """
    Applies the PRISMA inclusion/exclusion Boolean rules.
    Returns (pass_status, reason)
    """
    title = article.get("title", "").lower()
    abstract = article.get("abstract", "").lower()
    date_val = article.get("date", "")
    
    # 1. Year check (2016 - 2026)
    try:
        year = int(date_val)
        if not (INCLUSION_YEAR_START <= year <= INCLUSION_YEAR_END):
            return False, f"Published outside range (Year: {year})"
    except ValueError:
        # If year can't be parsed, check if string contains it, or allow if empty as fallback
        pass

    # Combined text for keyword matching
    full_text = f"{title} {abstract}"
    
    # 2. Disease keywords check (Malaria focus)
    has_disease = any(kw in full_text for kw in INCLUSION_KEYWORDS_DISEASE)
    if not has_disease:
        return False, "Does not mention malaria/vector keywords"
        
    # 3. Geography check (Low and middle-income / Sub-Saharan Africa / Ethiopia focus)
    has_geo = any(kw in full_text for kw in INCLUSION_KEYWORDS_GEO)
    # Also support specific country list or custom context
    # If not specifically mentioned in text, check if URL or source contains it
    if not has_geo:
        # Check if source or journal mentions Africa/Ethiopia
        source = article.get("source", "").lower()
        journal = article.get("journal", "").lower()
        if "africa" not in source and "ethiopia" not in source and "africa" not in journal and "ethiopia" not in journal:
            return False, "No Sub-Saharan Africa or LMIC geographic keywords found"

    # 4. Chronic disease exclusion check
    has_exclusion = any(kw in full_text for kw in EXCLUSION_KEYWORDS)
    if has_exclusion:
        # If it mentions an exclusion keyword, check if it's purely about that
        # (i.e., if it contains an exclusion keyword but doesn't mention malaria in the title, exclude)
        if not any(kw in title for kw in INCLUSION_KEYWORDS_DISEASE):
            return False, "Focuses on excluded non-infectious chronic condition"

    return True, "Passed Boolean criteria"

def compute_keyword_overlap_score(text, criteria):
    """
    Fallback similarity scoring using keyword token overlap.
    """
    text_words = set(text.lower().replace(".", "").replace(",", "").split())
    criteria_words = set(criteria.lower().replace(".", "").replace(",", "").split())
    
    # Filter short stop words
    stop_words = {"and", "the", "in", "of", "for", "to", "with", "a", "an", "on", "at", "by", "is", "are"}
    text_words = text_words - stop_words
    criteria_words = criteria_words - stop_words
    
    if not criteria_words:
        return 0.0
        
    overlap = text_words.intersection(criteria_words)
    # Cosine-like overlap score
    score = len(overlap) / (len(criteria_words) ** 0.5 * len(text_words) ** 0.5 + 1e-9)
    # Scale score to look like sentence-transformers scores (which are usually 0.3 - 0.8)
    return min(1.0, score * 2.0)

def semantic_screen(articles, target_criteria=SEMANTIC_TARGET_CRITERIA):
    """
    Computes semantic similarity scores for all articles against the target criteria.
    Appends 'semantic_score' and 'semantic_pass' to each article.
    """
    if not articles:
        return articles
        
    print(f"Executing semantic screening against criteria: '{target_criteria}'")
    
    if SENTENCE_TRANSFORMERS_AVAILABLE:
        try:
            # Load local model
            model = SentenceTransformer('all-MiniLM-L6-v2')
            
            # Prepare inputs
            criteria_emb = model.encode(target_criteria, convert_to_tensor=True)
            
            texts = [f"{a.get('title', '')} {a.get('abstract', '')}" for a in articles]
            text_embs = model.encode(texts, convert_to_tensor=True)
            
            # Calculate cosine similarities
            cos_scores = util.cos_sim(criteria_emb, text_embs)[0]
            
            for idx, a in enumerate(articles):
                score = float(cos_scores[idx].item())
                a["semantic_score"] = round(score, 4)
                a["semantic_pass"] = score >= SEMANTIC_THRESHOLD
        except Exception as e:
            print(f"[ERROR] sentence-transformers computation failed: {e}. Falling back to overlap scoring.")
            for a in articles:
                text = f"{a.get('title', '')} {a.get('abstract', '')}"
                score = compute_keyword_overlap_score(text, target_criteria)
                a["semantic_score"] = round(score, 4)
                a["semantic_pass"] = score >= SEMANTIC_THRESHOLD
    else:
        # Fallback keyword overlap
        for a in articles:
            text = f"{a.get('title', '')} {a.get('abstract', '')}"
            score = compute_keyword_overlap_score(text, target_criteria)
            a["semantic_score"] = round(score, 4)
            a["semantic_pass"] = score >= SEMANTIC_THRESHOLD
            
    return articles

def screen_articles(articles):
    """
    Runs the full screening pipeline on a list of articles.
    """
    print(f"\nStarting screening pipeline for {len(articles)} articles...")
    screened_articles = []
    
    # 1. Apply Boolean screening
    passed_boolean = []
    for a in articles:
        bool_pass, reason = boolean_screen(a)
        a["boolean_pass"] = bool_pass
        a["boolean_fail_reason"] = reason if not bool_pass else ""
        if bool_pass:
            passed_boolean.append(a)
        else:
            a["semantic_score"] = 0.0
            a["semantic_pass"] = False
            a["status"] = "Excluded"
            a["reason"] = reason
            screened_articles.append(a)
            
    print(f"Boolean screening: {len(passed_boolean)} passed, {len(articles) - len(passed_boolean)} excluded.")
    
    # 2. Apply Semantic screening on papers that passed Boolean check
    semantic_screen(passed_boolean)
    
    for a in passed_boolean:
        if a["semantic_pass"]:
            a["status"] = "Included"
            a["reason"] = "Passed all criteria"
        else:
            a["status"] = "Excluded"
            a["reason"] = f"Low semantic relevance ({a['semantic_score']:.4f} < {SEMANTIC_THRESHOLD})"
        screened_articles.append(a)
        
    included_count = sum(1 for a in screened_articles if a["status"] == "Included")
    print(f"Semantic screening: {included_count} included, {len(passed_boolean) - included_count} excluded.")
    print(f"Full screening finished: {included_count} articles INCLUDED, {len(screened_articles) - included_count} EXCLUDED.")
    
    # Sort: Included first, then sorted by semantic score descending
    screened_articles.sort(key=lambda x: (x["status"] == "Included", x["semantic_score"]), reverse=True)
    return screened_articles

if __name__ == "__main__":
    # Test screen
    test_data = [
        {
            "title": "Community-based health extension workers program for malaria mapping in Ethiopia",
            "abstract": "We map the community stakeholders and programs for malaria prevention.",
            "date": "2024",
            "source": "Test"
        },
        {
            "title": "Cardiovascular risk profiles in high-income Europe",
            "abstract": "A review of diabetes and heart failure.",
            "date": "2023",
            "source": "Test"
        }
    ]
    results = screen_articles(test_data)
    for r in results:
        print(f"Title: {r['title']} | Status: {r['status']} | Score: {r['semantic_score']} | Reason: {r['reason']}")
