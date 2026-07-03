import os
import re
import sys
from src.config import (
    DISEASES_DICT,
    STAKEHOLDERS_DICT,
    LOCATIONS_DICT,
    PROGRAMS_DICT
)

# Standard Name Normalization Map
NORMALIZATION_MAP = {
    "moh": "Ministry of Health",
    "ministry of health": "Ministry of Health",
    "ephi": "Ethiopian Public Health Institute",
    "ethiopian public health institute": "Ethiopian Public Health Institute",
    "ndmc": "National Data Management Center",
    "national data management center": "National Data Management Center",
    "world health organization": "World Health Organization",
    "who": "World Health Organization",
    "usaid": "USAID",
    "unicef": "UNICEF",
    "cdc": "CDC",
    "center for disease control": "CDC",
    "llin": "LLIN Program",
    "long-lasting insecticidal net": "LLIN Program",
    "bed net": "LLIN Program",
    "indoor residual spraying": "IRS Program",
    "irs": "IRS Program",
    "rapid diagnostic test": "RDT Diagnostics",
    "rdt": "RDT Diagnostics",
    "health extension worker": "Health Extension Program",
    "hew": "Health Extension Program",
    "health extension": "Health Extension Program",
    "plasmodium falciparum": "Plasmodium falciparum",
    "p. falciparum": "Plasmodium falciparum",
    "plasmodium vivax": "Plasmodium vivax",
    "p. vivax": "Plasmodium vivax"
}

def normalize_entity_name(name):
    name_lower = name.lower().strip()
    return NORMALIZATION_MAP.get(name_lower, name.strip())

def split_into_sentences(text):
    """
    Robust splitting of text into sentences.
    """
    if not text:
        return []
    # Split on period/question/exclamation followed by space and capital letter, avoiding standard abbreviation issues
    sentence_end = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?)\s')
    return [s.strip() for s in sentence_end.split(text) if s.strip()]

def extract_entities_rules(text):
    """
    Rule-based entity extraction using keywords and regex.
    Returns a list of dictionaries: {"name": ..., "type": ..., "context": ...}
    """
    entities = []
    sentences = split_into_sentences(text)
    
    # Define mapping of dictionary lists to entity types
    types_mapping = [
        (DISEASES_DICT, "Disease"),
        (STAKEHOLDERS_DICT, "Stakeholder"),
        (LOCATIONS_DICT, "Location"),
        (PROGRAMS_DICT, "Program")
    ]
    
    for sentence in sentences:
        for dict_list, entity_type in types_mapping:
            for keyword in dict_list:
                # Compile regex to match word boundaries
                pattern = rf"\b{re.escape(keyword)}\b"
                matches = re.findall(pattern, sentence, re.IGNORECASE)
                for m in matches:
                    norm_name = normalize_entity_name(m)
                    entities.append({
                        "name": norm_name,
                        "type": entity_type,
                        "context": sentence
                    })
                    
    # Deduplicate matching name and type
    unique_entities = {}
    for ent in entities:
        key = (ent["name"].lower(), ent["type"])
        if key not in unique_entities:
            unique_entities[key] = ent
            
    return list(unique_entities.values())

def run_deep_learning_ner(text):
    """
    Deep learning NER pipeline placeholder.
    In environments where imports of torch take very long, we default to skipping this.
    If explicitly run on a system supporting PyTorch, downloads/caches and executes dslim/bert-base-NER.
    """
    # Check if disabled
    if os.environ.get("DISABLE_DENSE_EMBEDDINGS", "1") == "1":
        return []
        
    try:
        from transformers import pipeline
        # CPU only settings
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
        
        # Load named entity recognition pipeline
        # dslim/bert-base-NER maps B-LOC, I-LOC, B-ORG, I-ORG, etc.
        nlp = pipeline("ner", model="dslim/bert-base-NER", grouped_entities=True)
        results = nlp(text)
        
        entities = []
        for r in results:
            ent_type = r.get("entity_group") or r.get("entity")
            name = r.get("word")
            
            # Map type
            mapped_type = ""
            if ent_type == "LOC":
                mapped_type = "Location"
            elif ent_type == "ORG":
                mapped_type = "Stakeholder"
                
            if mapped_type and name and len(name) > 2:
                # Find context sentence containing this name
                sentences = split_into_sentences(text)
                context = ""
                for s in sentences:
                    if name in s:
                        context = s
                        break
                entities.append({
                    "name": normalize_entity_name(name),
                    "type": mapped_type,
                    "context": context or text[:150]
                })
        return entities
    except Exception as e:
        # Silently return empty to fallback on rule-based
        return []

def extract_entities_from_article(article):
    """
    Combines rule-based and deep-learning NER to parse all entities from an article.
    """
    title = article.get("title", "")
    abstract = article.get("abstract", "")
    full_text = f"{title}. {abstract}"
    
    # 1. Run rule-based extraction
    entities = extract_entities_rules(full_text)
    
    # 2. Run DL NER (if enabled and imports work)
    dl_entities = run_deep_learning_ner(full_text)
    
    # Combine & deduplicate
    combined = {}
    for ent in entities + dl_entities:
        key = (ent["name"].lower(), ent["type"])
        if key not in combined:
            combined[key] = ent
            
    return list(combined.values())

def infer_relationships(entities):
    """
    Infers relations between extracted entities based on co-occurrence in context sentences.
    Returns a list of edge dicts: {"source": ..., "target": ..., "type": ...}
    """
    relationships = []
    
    # Group entities by context sentences
    sentence_groups = {}
    for ent in entities:
        ctx = ent.get("context", "")
        if ctx:
            sentence_groups.setdefault(ctx.lower(), []).append(ent)
            
    for ctx, group in sentence_groups.items():
        if len(group) < 2:
            continue
            
        # Analyze combinations in same sentence
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                ent1 = group[i]
                ent2 = group[j]
                
                # Deduplicate nodes order
                # Type combinations
                types = {ent1["type"], ent2["type"]}
                
                # 1. Stakeholder & Program -> INVOLVED_IN
                if "Stakeholder" in types and "Program" in types:
                    sh = ent1 if ent1["type"] == "Stakeholder" else ent2
                    prog = ent1 if ent1["type"] == "Program" else ent2
                    relationships.append({
                        "source": sh["name"],
                        "target": prog["name"],
                        "type": "INVOLVED_IN",
                        "context": ent1["context"]
                    })
                    
                # 2. Program & Location -> LOCATED_IN
                elif "Program" in types and "Location" in types:
                    prog = ent1 if ent1["type"] == "Program" else ent2
                    loc = ent1 if ent1["type"] == "Location" else ent2
                    relationships.append({
                        "source": prog["name"],
                        "target": loc["name"],
                        "type": "LOCATED_IN",
                        "context": ent1["context"]
                    })
                    
                # 3. Program & Disease -> TARGETS
                elif "Program" in types and "Disease" in types:
                    prog = ent1 if ent1["type"] == "Program" else ent2
                    dis = ent1 if ent1["type"] == "Disease" else ent2
                    relationships.append({
                        "source": prog["name"],
                        "target": dis["name"],
                        "type": "TARGETS",
                        "context": ent1["context"]
                    })
                    
                # 4. Stakeholder & Location -> LOCATED_IN
                elif "Stakeholder" in types and "Location" in types:
                    sh = ent1 if ent1["type"] == "Stakeholder" else ent2
                    loc = ent1 if ent1["type"] == "Location" else ent2
                    relationships.append({
                        "source": sh["name"],
                        "target": loc["name"],
                        "type": "LOCATED_IN",
                        "context": ent1["context"]
                    })
                    
    # Deduplicate relationships
    unique_rels = []
    seen = set()
    for rel in relationships:
        key = (rel["source"].lower(), rel["target"].lower(), rel["type"])
        if key not in seen:
            seen.add(key)
            unique_rels.append(rel)
            
    return unique_rels

if __name__ == "__main__":
    # Test extraction
    test_article = {
        "title": "EPHI launches rapid diagnostic test (RDT) campaigns in Oromia region for Plasmodium falciparum malaria control.",
        "abstract": "The Ethiopian Public Health Institute (EPHI) and regional health extension workers deployed case management kits to clinics. This project was sponsored by USAID."
    }
    extracted = extract_entities_from_article(test_article)
    print("Extracted entities:")
    for e in extracted:
        print(f"  - {e['name']} ({e['type']})")
        
    rels = infer_relationships(extracted)
    print("\nInferred relationships:")
    for r in rels:
        print(f"  - ({r['source']}) -[{r['type']}]-> ({r['target']})")
