import os
import sqlite3
import json
import hashlib

def get_db_connection(db_path="data/health_ecosystem.db"):
    """
    Creates connection to the SQLite database.
    """
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_database(db_path="data/health_ecosystem.db"):
    """
    Initializes the database tables.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # 1. Articles table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY,
        title TEXT,
        authors TEXT,
        journal TEXT,
        year TEXT,
        url TEXT,
        source TEXT
    )
    """)
    
    # 2. Entities table (Nodes)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS entities (
        id TEXT PRIMARY KEY,
        name TEXT UNIQUE,
        type TEXT
    )
    """)
    
    # 3. Extractions table (Map entities to source articles)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS extractions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        article_id TEXT,
        entity_id TEXT,
        context TEXT,
        FOREIGN KEY (article_id) REFERENCES articles(id),
        FOREIGN KEY (entity_id) REFERENCES entities(id)
    )
    """)
    
    # 4. Relationships table (Edges between entities)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS relationships (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source_id TEXT,
        target_id TEXT,
        type TEXT,
        context TEXT,
        FOREIGN KEY (source_id) REFERENCES entities(id),
        FOREIGN KEY (target_id) REFERENCES entities(id),
        UNIQUE(source_id, target_id, type)
    )
    """)
    
    conn.commit()
    conn.close()
    print(f"Database initialized successfully at {db_path}!")

def get_entity_id(name):
    """
    Generates a deterministic unique ID for an entity based on its name.
    """
    clean_name = name.strip().lower()
    m = hashlib.md5(clean_name.encode("utf-8"))
    return f"node_{m.hexdigest()[:12]}"

def insert_extracted_data(articles_data, extractions_map, db_path="data/health_ecosystem.db"):
    """
    Inserts raw articles, extracted entities, extractions, and relationships.
    extractions_map is a dict: {article_id: {"entities": [list of ent dicts], "relationships": [list of rel dicts]}}
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Track inserted entities to map names to IDs
    entity_name_to_id = {}
    
    # 1. Insert Articles
    for art in articles_data:
        # Only store articles that were screened in / included
        if art.get("status") != "Included":
            continue
            
        cursor.execute("""
        INSERT OR REPLACE INTO articles (id, title, authors, journal, year, url, source)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            art.get("id"),
            art.get("title"),
            ", ".join(art.get("authors", [])),
            art.get("journal"),
            art.get("date"),
            art.get("url"),
            art.get("source")
        ))
        
    # 2. Insert Entities and Extractions
    for art_id, extracted in extractions_map.items():
        # Retrieve article details (make sure it was included)
        cursor.execute("SELECT id FROM articles WHERE id = ?", (art_id,))
        if not cursor.fetchone():
            continue # Skip excluded articles
            
        for ent in extracted.get("entities", []):
            name = ent["name"]
            ent_type = ent["type"]
            context = ent["context"]
            
            ent_id = get_entity_id(name)
            entity_name_to_id[name.lower()] = ent_id
            
            # Insert Entity
            cursor.execute("""
            INSERT OR IGNORE INTO entities (id, name, type)
            VALUES (?, ?, ?)
            """, (ent_id, name, ent_type))
            
            # Insert Extraction linking article to entity
            cursor.execute("""
            INSERT INTO extractions (article_id, entity_id, context)
            VALUES (?, ?, ?)
            """, (art_id, ent_id, context))
            
    # 3. Insert Relationships
    for art_id, extracted in extractions_map.items():
        cursor.execute("SELECT id FROM articles WHERE id = ?", (art_id,))
        if not cursor.fetchone():
            continue # Skip excluded articles
            
        for rel in extracted.get("relationships", []):
            source_name = rel["source"]
            target_name = rel["target"]
            rel_type = rel["type"]
            context = rel.get("context", "")
            
            src_id = entity_name_to_id.get(source_name.lower()) or get_entity_id(source_name)
            tgt_id = entity_name_to_id.get(target_name.lower()) or get_entity_id(target_name)
            
            # Make sure both entities exist in DB
            cursor.execute("SELECT id FROM entities WHERE id = ?", (src_id,))
            has_src = cursor.fetchone()
            cursor.execute("SELECT id FROM entities WHERE id = ?", (tgt_id,))
            has_tgt = cursor.fetchone()
            
            if has_src and has_tgt:
                cursor.execute("""
                INSERT OR IGNORE INTO relationships (source_id, target_id, type, context)
                VALUES (?, ?, ?, ?)
                """, (src_id, tgt_id, rel_type, context))
                
    conn.commit()
    conn.close()
    print("Database inserts and entity indexing completed successfully.")

def export_to_graph_json(db_path="data/health_ecosystem.db", output_path="data/health_ecosystem_graph.json"):
    """
    Exports entities (nodes) and relationships (edges) to a JSON file.
    """
    conn = get_db_connection(db_path)
    cursor = conn.cursor()
    
    # Fetch all entities
    cursor.execute("SELECT id, name, type FROM entities")
    nodes = []
    for row in cursor.fetchall():
        nodes.append({
            "id": row["id"],
            "label": row["name"],
            "type": row["type"]
        })
        
    # Fetch all relationships
    cursor.execute("""
    SELECT r.source_id, r.target_id, r.type, r.context, 
           e1.name as src_name, e2.name as tgt_name
    FROM relationships r
    JOIN entities e1 ON r.source_id = e1.id
    JOIN entities e2 ON r.target_id = e2.id
    """)
    edges = []
    for row in cursor.fetchall():
        edges.append({
            "from": row["source_id"],
            "to": row["target_id"],
            "type": row["type"],
            "source_name": row["src_name"],
            "target_name": row["tgt_name"],
            "context": row["context"]
        })
        
    conn.close()
    
    graph_data = {
        "nodes": nodes,
        "edges": edges
    }
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(graph_data, f, indent=2, ensure_ascii=False)
        
    print(f"Exported graph data successfully to: {output_path} ({len(nodes)} nodes, {len(edges)} edges)")
    return graph_data
