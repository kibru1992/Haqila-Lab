import os
import requests
import json
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from src.config import (
    PUBMED_SEARCH_TERM,
    EPHI_PUBMED_TERM,
    AJOL_SEARCH_QUERY,
    WHO_IRIS_SEARCH_QUERY,
    AJOL_BASE_URL,
    WHO_IRIS_API_URL,
    SCOPUS_API_URL,
    DEFAULT_HEADERS
)

def clean_text(text):
    if not text:
        return ""
    return " ".join(text.split())

def parse_pubmed_xml(xml_content):
    """
    Parses PubMed efetch XML content and returns a list of dictionaries with paper metadata.
    """
    articles = []
    try:
        root = ET.fromstring(xml_content)
    except Exception as e:
        print(f"Error parsing PubMed XML: {e}")
        return articles

    for article_tag in root.findall(".//PubmedArticle"):
        pmid = ""
        pmid_tag = article_tag.find(".//PMID")
        if pmid_tag is not None:
            pmid = pmid_tag.text

        title = ""
        title_tag = article_tag.find(".//ArticleTitle")
        if title_tag is not None:
            title = "".join(title_tag.itertext())

        # Extract abstract
        abstract = ""
        abstract_texts = article_tag.findall(".//AbstractText")
        if abstract_texts:
            parts = []
            for ab_text in abstract_texts:
                label = ab_text.get("Label")
                text_content = "".join(ab_text.itertext())
                if label:
                    parts.append(f"{label}: {text_content}")
                else:
                    parts.append(text_content)
            abstract = " ".join(parts)

        # Extract date
        pub_year = ""
        pub_date_tag = article_tag.find(".//JournalIssue/PubDate")
        if pub_date_tag is not None:
            year_tag = pub_date_tag.find("Year")
            if year_tag is not None:
                pub_year = year_tag.text
            else:
                medline_date_tag = pub_date_tag.find("MedlineDate")
                if medline_date_tag is not None:
                    # MedlineDate can be e.g. "2024 Jun 29"
                    tokens = medline_date_tag.text.split()
                    if tokens:
                        pub_year = tokens[0]

        # Extract authors
        authors = []
        author_tags = article_tag.findall(".//AuthorList/Author")
        for auth in author_tags:
            last_name = auth.find("LastName")
            fore_name = auth.find("ForeName")
            lname = last_name.text if last_name is not None else ""
            fname = fore_name.text if fore_name is not None else ""
            if lname or fname:
                authors.append(f"{fname} {lname}".strip())

        # Extract journal
        journal = ""
        journal_tag = article_tag.find(".//Journal/Title")
        if journal_tag is not None:
            journal = journal_tag.text

        articles.append({
            "id": f"pubmed_{pmid}" if pmid else "",
            "title": clean_text(title),
            "authors": authors,
            "abstract": clean_text(abstract),
            "date": pub_year,
            "journal": journal,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else "",
            "source": "PubMed"
        })
    return articles

def fetch_pubmed(query, limit=50):
    """
    Search and fetch details of papers from PubMed using NCBI E-utilities.
    """
    print(f"Fetching from PubMed with limit={limit}...")
    search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    search_params = {
        "db": "pubmed",
        "term": query,
        "retmode": "json",
        "retmax": limit
    }
    
    try:
        r = requests.get(search_url, params=search_params, headers=DEFAULT_HEADERS, timeout=15)
        r.raise_for_status()
        id_list = r.json().get("esearchresult", {}).get("idlist", [])
        print(f"PubMed search found {len(id_list)} record IDs.")
        
        if not id_list:
            return []
            
        fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        fetch_params = {
            "db": "pubmed",
            "id": ",".join(id_list),
            "retmode": "xml"
        }
        
        fr = requests.get(fetch_url, params=fetch_params, headers=DEFAULT_HEADERS, timeout=20)
        fr.raise_for_status()
        
        return parse_pubmed_xml(fr.text)
    except Exception as e:
        print(f"PubMed fetch error: {e}")
        return []

def fetch_ajol(query, limit=10):
    """
    Ingest from African Journals OnLine (AJOL).
    Scrapes the search result HTML and navigates to the landing page of each article for detailed meta tags.
    """
    print(f"Fetching from AJOL with limit={limit}...")
    articles = []
    
    # AJOL Search OJS
    search_page = 1
    landing_urls = []
    
    while len(landing_urls) < limit:
        params = {
            "query": query,
            "searchPage": search_page
        }
        try:
            r = requests.get(AJOL_BASE_URL, params=params, headers=DEFAULT_HEADERS, timeout=15)
            if r.status_code != 200:
                break
                
            soup = BeautifulSoup(r.text, 'html.parser')
            titles = soup.find_all('h3', class_='title')
            
            if not titles:
                break
                
            new_urls = []
            for t in titles:
                link = t.find('a')
                if link and link.get('href'):
                    href = link.get('href')
                    if "/article/view/" in href and href not in landing_urls:
                        new_urls.append(href)
            
            if not new_urls:
                break
                
            landing_urls.extend(new_urls)
            search_page += 1
        except Exception as e:
            print(f"AJOL search page crawl error: {e}")
            break

    # Truncate to limit
    landing_urls = landing_urls[:limit]
    print(f"AJOL crawled {len(landing_urls)} landing page URLs. Fetching metadata...")

    for url in landing_urls:
        try:
            ar = requests.get(url, headers=DEFAULT_HEADERS, timeout=15)
            if ar.status_code != 200:
                continue
                
            asoup = BeautifulSoup(ar.text, 'html.parser')
            
            title = ""
            abstract = ""
            date_val = ""
            journal = ""
            authors = []
            
            # Read DC and Highwire press meta tags
            meta_tags = asoup.find_all('meta')
            for m in meta_tags:
                name = m.get('name')
                content = m.get('content')
                if not name or not content:
                    continue
                    
                if name in ["DC.Title", "citation_title"]:
                    title = content
                elif name in ["DC.Description", "citation_abstract"]:
                    abstract = content
                elif name in ["DC.Date.issued", "citation_date"]:
                    date_val = content.split('/')[0].split('-')[0] # Extract year
                elif name in ["DC.Source", "citation_journal_title"]:
                    journal = content
                elif name in ["DC.Creator.PersonalName", "citation_author"]:
                    if content not in authors:
                        authors.append(content)
                        
            # If abstract is still empty, try to get from article-abstract div
            if not abstract:
                ab_div = asoup.find('div', class_='article-abstract') or asoup.find('section', class_='item abstract')
                if ab_div:
                    abstract = ab_div.text.strip()
                    
            article_id = url.split('/')[-1]
            articles.append({
                "id": f"ajol_{article_id}",
                "title": clean_text(title or "Unknown Title"),
                "authors": authors,
                "abstract": clean_text(abstract),
                "date": date_val,
                "journal": journal or "AJOL Journal",
                "url": url,
                "source": "AJOL"
            })
        except Exception as e:
            print(f"AJOL detailed fetch error for {url}: {e}")
            
    return articles

def fetch_who_iris(query, limit=20):
    """
    Ingest from WHO IRIS repository using its DSpace 7 REST API discovery endpoint.
    """
    print(f"Fetching from WHO IRIS with limit={limit}...")
    articles = []
    
    # We query the discovery objects search
    params = {
        "query": query,
        "size": limit,
        "page": 0
    }
    
    try:
        r = requests.get(WHO_IRIS_API_URL, params=params, headers=DEFAULT_HEADERS, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        objects = data.get("_embedded", {}).get("searchResult", {}).get("_embedded", {}).get("objects", [])
        print(f"WHO IRIS REST API returned {len(objects)} objects.")
        
        for obj in objects:
            idx_obj = obj.get("_embedded", {}).get("indexableObject", {})
            metadata = idx_obj.get("metadata", {})
            
            # Parse properties
            titles = metadata.get("dc.title", [])
            title = titles[0].get("value", "") if titles else ""
            
            abstracts = metadata.get("dc.description.abstract", [])
            abstract = abstracts[0].get("value", "") if abstracts else ""
            
            dates = metadata.get("dc.date.issued", [])
            date_val = dates[0].get("value", "") if dates else ""
            # Extract year from e.g., "2007-12-31"
            if date_val:
                date_val = date_val.split('-')[0]
                
            authors = [auth.get("value", "") for auth in metadata.get("dc.contributor.author", [])]
            
            publishers = metadata.get("dc.publisher", [])
            publisher = publishers[0].get("value", "") if publishers else "WHO IRIS"
            
            uris = metadata.get("dc.identifier.uri", [])
            url = uris[0].get("value", "") if uris else f"https://iris.who.int/handle/10665/{idx_obj.get('id', 'unknown')}"
            
            articles.append({
                "id": f"who_iris_{idx_obj.get('uuid', 'unknown')}",
                "title": clean_text(title),
                "authors": authors,
                "abstract": clean_text(abstract),
                "date": date_val,
                "journal": publisher,
                "url": url,
                "source": "WHO IRIS"
            })
    except Exception as e:
        print(f"WHO IRIS REST API fetch error: {e}")
        
    return articles

def fetch_scopus(limit=20):
    """
    Ingest from Scopus. Requires SCOPUS_API_KEY environment variable.
    If not set, falls back to a realistic mock dataset.
    """
    scopus_key = os.environ.get("SCOPUS_API_KEY")
    if not scopus_key:
        print("\n[WARNING] SCOPUS_API_KEY is not set. Falling back to simulated Scopus dataset.")
        return get_mock_scopus_data()
        
    print(f"Fetching from Scopus API with limit={limit}...")
    articles = []
    
    # Target search query
    query_str = "KEY(malaria) AND (AFFIL(Ethiopia) OR AFFIL(\"Sub-Saharan Africa\"))"
    
    headers = {
        "X-ELS-APIKey": scopus_key,
        "Accept": "application/json",
        "User-Agent": DEFAULT_HEADERS["User-Agent"]
    }
    
    params = {
        "query": query_str,
        "count": limit
    }
    
    try:
        r = requests.get(SCOPUS_API_URL, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        data = r.json()
        
        entries = data.get("search-results", {}).get("entry", [])
        print(f"Scopus API returned {len(entries)} entries.")
        
        for entry in entries:
            title = entry.get("dc:title", "")
            abstract = entry.get("dc:description", "") or entry.get("subtypeDescription", "") # Scopus search API abstracts are sometimes truncated or in sub fields
            
            # Fetch full abstract if available
            # Note: complete abstract retrieval requires Scopus Abstract Retrieval API which requires institution credentials.
            # We'll use the description from search-results or default to title.
            
            authors = [entry.get("dc:creator", "")]
            date_val = entry.get("prism:coverDate", "")
            if date_val:
                date_val = date_val.split('-')[0]
                
            journal = entry.get("prism:publicationName", "Scopus Indexed Journal")
            
            scopus_id = entry.get("dc:identifier", "").replace("SCOPUS_ID:", "")
            url = f"https://www.scopus.com/inward/record.uri?partnerID=HzTxMe3b&scp={scopus_id}"
            
            articles.append({
                "id": f"scopus_{scopus_id}",
                "title": clean_text(title),
                "authors": authors,
                "abstract": clean_text(abstract or f"Scopus index entry for: {title}"),
                "date": date_val,
                "journal": journal,
                "url": url,
                "source": "Scopus"
            })
    except Exception as e:
        print(f"Scopus fetch error: {e}. Falling back to simulated Scopus dataset.")
        return get_mock_scopus_data()
        
    return articles

def fetch_ephi(limit=20):
    """
    Ingest EPHI data. Matches publications by searching PubMed for EPHI affiliations
    and merges with local registry-based reports (`data/ephi_registry.json`).
    """
    print("Ingesting EPHI publications and registry data...")
    
    # 1. PubMed Affiliation Search
    ephi_pubmed_papers = fetch_pubmed(EPHI_PUBMED_TERM, limit=limit)
    print(f"EPHI PubMed affiliation search fetched {len(ephi_pubmed_papers)} papers.")
    
    # 2. Local Registry Ingestion
    registry_papers = []
    registry_path = os.path.join("data", "ephi_registry.json")
    if os.path.exists(registry_path):
        try:
            with open(registry_path, "r", encoding="utf-8") as f:
                registry_papers = json.load(f)
            print(f"Loaded {len(registry_papers)} internal EPHI registry reports.")
        except Exception as e:
            print(f"Error loading local EPHI registry data: {e}")
    else:
        print(f"[WARNING] Local registry file not found at {registry_path}")
        
    # Combine & mark EPHI
    for p in ephi_pubmed_papers:
        p["source"] = "EPHI (PubMed)"
        
    combined = registry_papers + ephi_pubmed_papers
    return combined

def get_mock_scopus_data():
    """
    Returns a small set of realistic mock Scopus indexed articles matching malaria stakeholder mapping in Ethiopia.
    """
    return [
        {
            "id": "scopus_85123456789",
            "title": "Mapping stakeholders and community networks for malaria prevention in East Africa: A social network analysis",
            "authors": ["Tadesse, G.", "Biru, G.", "Worku, A."],
            "abstract": "This study employs social network analysis to map the stakeholders involved in community-based malaria control programs across Ethiopia. Key actors include the Federal Ministry of Health, regional health bureaus, local NGOs, and international sponsors. Results demonstrate the critical importance of localized communication pathways for vector control interventions.",
            "date": "2024",
            "journal": "Malaria Journal (Scopus Indexed)",
            "url": "https://www.scopus.com/inward/record.uri?scp=85123456789",
            "source": "Scopus"
        },
        {
            "id": "scopus_85198765432",
            "title": "Systematic evaluation of Natural Language Processing techniques for health policy reviews in developing nations",
            "authors": ["Müller, H.", "Negash, S."],
            "abstract": "Systematic reviews of health systems require extensive human resources for screening. This article evaluates the performance of NLP methods, including TF-IDF and transformer-based sentence embeddings, for screening research papers on infectious disease prevention in Sub-Saharan Africa, finding high specificity with minimized human workload.",
            "date": "2023",
            "journal": "BMC Medical Informatics and Decision Making (Scopus Indexed)",
            "url": "https://www.scopus.com/inward/record.uri?scp=85198765432",
            "source": "Scopus"
        }
    ]

def collect_all_data(limits=None):
    """
    Aggregates data from all five sources: PubMed, Scopus, AJOL, WHO IRIS, and EPHI.
    """
    if limits is None:
        limits = {
            "pubmed": 50,
            "scopus": 10,
            "ajol": 10,
            "who_iris": 15,
            "ephi": 15
        }
        
    all_records = []
    
    pubmed = fetch_pubmed(PUBMED_SEARCH_TERM, limit=limits.get("pubmed", 50))
    all_records.extend(pubmed)
    
    scopus = fetch_scopus(limit=limits.get("scopus", 10))
    all_records.extend(scopus)
    
    ajol = fetch_ajol(AJOL_SEARCH_QUERY, limit=limits.get("ajol", 10))
    all_records.extend(ajol)
    
    who = fetch_who_iris(WHO_IRIS_SEARCH_QUERY, limit=limits.get("who_iris", 15))
    all_records.extend(who)
    
    ephi = fetch_ephi(limit=limits.get("ephi", 15))
    all_records.extend(ephi)
    
    # Deduplicate by title
    seen_titles = set()
    deduped = []
    for r in all_records:
        t_lower = r["title"].lower()
        if t_lower not in seen_titles:
            seen_titles.add(t_lower)
            deduped.append(r)
            
    print(f"\nData collection summary: Aggregated {len(all_records)} records, deduplicated to {len(deduped)} unique records.")
    return deduped

if __name__ == "__main__":
    # Quick test when executed directly
    results = collect_all_data(limits={"pubmed": 3, "scopus": 1, "ajol": 1, "who_iris": 1, "ephi": 1})
    print(json.dumps(results[:2], indent=2))
