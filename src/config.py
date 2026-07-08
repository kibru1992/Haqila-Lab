import os

# Geographic & Keyword parameters
SPECIFIC_DISEASE = "Malaria"
INCLUSION_YEAR_START = 2016
INCLUSION_YEAR_END = 2026

# Target Search Queries
PUBMED_SEARCH_TERM = (
    '("malaria"[Title/Abstract] OR "plasmodium"[Title/Abstract] OR "falciparum"[Title/Abstract] OR "vivax"[Title/Abstract] OR "anopheles"[Title/Abstract]) '
    'AND ("Ethiopia"[Title/Abstract] OR "East Africa"[Title/Abstract] OR "Sub-Saharan Africa"[Title/Abstract] OR "Africa"[Title/Abstract] OR "LMIC"[Title/Abstract]) '
    'AND ("2016/01/01"[Date - Publication] : "2026/06/30"[Date - Publication])'
)

EPHI_PUBMED_TERM = (
    '("Ethiopian Public Health Institute"[Affiliation] OR "EPHI"[Affiliation] OR "Ethiopian Public Health Institute"[All Fields]) '
    'AND ("malaria"[Title/Abstract] OR "plasmodium"[Title/Abstract] OR "falciparum"[Title/Abstract] OR "vivax"[Title/Abstract])'
)

AJOL_SEARCH_QUERY = "malaria"
WHO_IRIS_SEARCH_QUERY = "malaria"

# Semantic Criteria representation for screening
SEMANTIC_TARGET_CRITERIA = (
    "Community-based malaria control programs, stakeholders, interventions, and geographical mapping in Ethiopia and Sub-Saharan Africa."
)

# Semantic similarity threshold (cosine similarity score)
SEMANTIC_THRESHOLD = 0.40

# Boolean Exclusion Keywords (purely chronic or non-infectious conditions)
EXCLUSION_KEYWORDS = [
    "diabetes", "cardiovascular", "hypertension", "cancer", "oncology", 
    "alzheimer", "dementia", "stroke", "coronary", "arthritis", "asthma"
]

# Inclusions geography and disease keywords for text screening
INCLUSION_KEYWORDS_DISEASE = ["malaria", "plasmodium", "falciparum", "vivax", "anopheles", "mosquito"]
INCLUSION_KEYWORDS_GEO = ["ethiopia", "sub-saharan", "africa", "east africa", "lmic", "low-income", "middle-income"]

# API endpoints
AJOL_BASE_URL = "https://www.ajol.info/index.php/index/search/search"
WHO_IRIS_API_URL = "https://iris.who.int/server/api/discover/search/objects"
SCOPUS_API_URL = "6b601aa61704b6c8fcc78974474aa676"

# Headers for HTTP requests to prevent 403 Forbidden responses
DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# Rule-based Entity Recognition Dictionaries
DISEASES_DICT = [
    "malaria", "plasmodium falciparum", "plasmodium vivax", "plasmodium ovale", 
    "plasmodium malariae", "p. falciparum", "p. vivax", "p. ovale", "p. malariae"
]

STAKEHOLDERS_DICT = [
    "ministry of health", "moh", "ethiopian public health institute", "ephi", 
    "national data management center", "ndmc", "world health organization", "who", 
    "usaid", "unicef", "center for disease control", "cdc", "carter center", 
    "non-governmental organization", "ngo", "health post", "health center", 
    "clinic", "health extension worker", "hew"
]

LOCATIONS_DICT = [
    "ethiopia", "addis ababa", "amhara", "oromia", "tigray", "somali", "afar", 
    "benishangul-gumuz", "gambela", "gambella", "sidama", "south ethiopia", 
    "central ethiopia", "southwest ethiopia", "harari", "dire dawa", "snnpr", 
    "meinit goldia", "jabi tehnan", "benin city", "edo state", "uganda"
]

PROGRAMS_DICT = [
    "llin", "long-lasting insecticidal net", "bed net", "indoor residual spraying", 
    "irs", "rapid diagnostic test", "rdt", "health extension", "case management", 
    "vector control", "mass drug administration", "insecticide resistance", 
    "surveillance and surveys"
]

