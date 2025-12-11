import os
import json
from typing import List, Optional, Dict, Any
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from neo4j import GraphDatabase
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

# Neo4j Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    NEO4J_AVAILABLE = True
    print("Neo4j connection established.")
except Exception as e:
    driver = None
    NEO4J_AVAILABLE = False
    print(f"Neo4j not available: {e}")

# LLM Configuration
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

llm = ChatOpenAI(
    temperature=0, 
    model_name="deepseek-chat", 
    api_key=DEEPSEEK_API_KEY,
    base_url=DEEPSEEK_BASE_URL
)

# --- Helper Functions ---

def serialize_neo4j_object(obj):
    """Convert Neo4j object to JSON-serializable dict, filtering out non-serializable types"""
    result = {}
    for key, value in dict(obj).items():
        # Skip DateTime and other non-serializable Neo4j types
        if hasattr(value, '__class__') and value.__class__.__name__ in ['DateTime', 'Date', 'Time', 'Duration']:
            continue
        # Convert to string if it's a complex type
        try:
            import json
            json.dumps(value)  # Test if serializable
            result[key] = value
        except (TypeError, ValueError):
            result[key] = str(value)
    return result

def init_db():
    if not NEO4J_AVAILABLE:
        print("Skipping database initialization - Neo4j not available.")
        return
    try:
        with driver.session() as session:
            session.run("CREATE CONSTRAINT entity_name_unique IF NOT EXISTS FOR (e:Entity) REQUIRE e.name IS UNIQUE")
        print("Database initialized.")
    except Exception as e:
        print(f"Database initialization warning: {e}")

with app.app_context():
    init_db()

# Define Pydantic models for structured output
class Triple(BaseModel):
    subject: str = Field(description="The subject of the triple")
    predicate: str = Field(description="The relationship/predicate")
    object: str = Field(description="The object of the triple")
    confidence: float = Field(description="Confidence score between 0 and 1")
    span: str = Field(description="The original text span")

class TriplesOutput(BaseModel):
    triples: List[Triple] = Field(description="List of extracted triples")

def run_extraction(text: str, source_doc: str) -> List[Dict]:
    # 简化 Prompt，不依赖复杂的 parser.get_format_instructions()
    # 直接在 Prompt 中给出 JSON 示例，这样更稳定
    
    prompt_text = f"""你是一个专业的知识图谱构建助手。请从以下文本中提取所有有意义的三元组。

要求：
1. 提取格式：JSON 列表
2. 每个元素包含：subject (主体), predicate (关系), object (客体), confidence (置信度 0-1), span (原文片段)
3. 仅返回纯 JSON 列表，不要包含 Markdown 格式标记（如 ```json ... ```）

示例输出：
[
    {{
        "subject": "江泽民",
        "predicate": "出生于",
        "object": "江苏扬州",
        "confidence": 1.0,
        "span": "江泽民出生于江苏扬州"
    }}
]

待处理文本：
{text}
"""
    
    try:
        print(f"[DEBUG] Sending prompt to LLM (length: {len(prompt_text)})...")
        # print(f"[DEBUG] Prompt content:\n{prompt_text[:200]}...")
        
        from langchain_core.messages import HumanMessage
        messages = [HumanMessage(content=prompt_text)]
        
        response = llm.invoke(messages)
        content = response.content.strip()
        
        # 清理可能的 Markdown 标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()
        
        print(f"[DEBUG] LLM Response raw content:\n{content[:200]}...")
        
        # 解析 JSON
        import json
        triples = json.loads(content)
        
        if not isinstance(triples, list):
            print(f"[WARN] LLM output is not a list: {type(triples)}")
            return []
            
        print(f"[DEBUG] Extracted triples count: {len(triples)}")
        
        # Convert to dicts and add source_doc
        triples_list = []
        for i, t in enumerate(triples):
            if isinstance(t, dict):
                t["source_doc"] = source_doc
                triples_list.append(t)
        
        return triples_list

    except Exception as e:
        print(f"[ERROR] Extraction error: {e}")
        if hasattr(e, 'response'):
            print(f"[ERROR] API Response: {e.response}")
        import traceback
        traceback.print_exc()
        return []

def ingest_triples(triples: List[Dict]):
    if not NEO4J_AVAILABLE:
        print("Neo4j not available - skipping triple ingestion")
        return
    query = """
    UNWIND $triples AS t
    MERGE (a:Entity {name: t.subject})
    MERGE (b:Entity {name: t.object})
    MERGE (a)-[r:REL {predicate: t.predicate}]->(b)
    SET r.confidence = t.confidence,
        r.source_doc = t.source_doc,
        r.span = t.span
    """
    with driver.session() as session:
        session.run(query, triples=triples)

def get_subgraph(seed_id: str, depth: int = 1, source_doc: str = None):
    if not NEO4J_AVAILABLE:
        return {"nodes": [], "edges": []}
    
    # Base query structure
    if seed_id:
        match_clause = f"MATCH (n:Entity {{name: $seed_id}})-[r*1..{depth}]-(m)"
    else:
        match_clause = "MATCH (n:Entity)-[r]->(m)"
    
    where_clause = ""
    if source_doc:
        # Filter relationships by source_doc property
        # Note: If path length > 1, we check if ANY relationship in the path matches, 
        # or strictly ALL. Usually for knowledge graphs, we might want to see connections 
        # that came from that doc. 
        # For simplicity in variable length path (r*...), we'll check the last relationship or all.
        # But Cypher variable length path returns a list of relationships.
        if seed_id:
             where_clause = "WHERE ALL(rel IN r WHERE rel.source_doc = $source_doc)"
        else:
             where_clause = "WHERE r.source_doc = $source_doc"

    query = f"""
    {match_clause}
    {where_clause}
    RETURN n, r, m
    LIMIT 100
    """
    
    nodes = {}
    edges = []
    
    with driver.session() as session:
        result = session.run(query, seed_id=seed_id, source_doc=source_doc)
        for record in result:
            n = record.get("n")
            if n:
                node_data = serialize_neo4j_object(n)
                nodes[n["name"]] = {"data": {"id": n["name"], "label": n["name"], **node_data}}
            
            m = record.get("m")
            if m:
                node_data = serialize_neo4j_object(m)
                nodes[m["name"]] = {"data": {"id": m["name"], "label": m["name"], **node_data}}
            
            rels = record.get("r")
            if not isinstance(rels, list):
                rels = [rels]
            
            for r in rels:
                edge_id = f"{r.start_node['name']}_{r.type}_{r.end_node['name']}"
                rel_data = serialize_neo4j_object(r)
                edges.append({
                    "data": {
                        "id": edge_id,
                        "source": r.start_node["name"],
                        "target": r.end_node["name"],
                        "label": r.get("predicate") or r.type,
                        **rel_data
                    }
                })
                
    return {
        "nodes": list(nodes.values()),
        "edges": edges
    }

def get_source_documents():
    if not NEO4J_AVAILABLE:
        return []
    
    query = """
    MATCH ()-[r]->()
    WHERE r.source_doc IS NOT NULL
    RETURN DISTINCT r.source_doc as source_doc
    ORDER BY source_doc
    """
    
    sources = []
    with driver.session() as session:
        result = session.run(query)
        for record in result:
            sources.append(record["source_doc"])
    return sources

# --- Routes ---

@app.route("/")
def index():
    sources = get_source_documents()
    return render_template("index.html", sources=sources)

@app.route("/files")
def files():
    sources = get_source_documents()
    return render_template("files.html", files=sources)

@app.route("/review")
def review_page():
    return render_template("review.html")

from ingestion import parse_file, scrape_url

@app.route("/api/upload", methods=["POST"])
def upload_file():
    try:
        if 'files' not in request.files:
            return jsonify({"error": "No files part"}), 400
        
        files = request.files.getlist('files')
        if not files or files[0].filename == '':
            return jsonify({"error": "No selected files"}), 400
            
        total_triples = 0
        processed_files = []
        
        for file in files:
            try:
                print(f"Processing file: {file.filename}")
                text = parse_file(file, file.filename)
                
                if not text.strip():
                    print(f"⚠️ Empty text extracted from {file.filename}")
                    continue
                    
                # 增加处理长度限制
                max_length = 8000
                text_to_process = text[:max_length]
                if len(text) > max_length:
                    print(f"⚠️ Text truncated from {len(text)} to {max_length} characters")
                
                print(f"📝 Sending to LLM for extraction...")
                triples = run_extraction(text_to_process, file.filename)
                print(f"✅ Extracted {len(triples)} triples from {file.filename}")
                
                ingest_triples(triples)
                total_triples += len(triples)
                processed_files.append(file.filename)
                
            except Exception as e:
                print(f"Error processing {file.filename}: {e}")
                # Continue with other files even if one fails
                continue
        
        return jsonify({
            "status": "success", 
            "triples_count": total_triples,
            "processed_files": processed_files
        })
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/url", methods=["POST"])
def extract_from_url():
    try:
        data = request.json
        url = data.get("url")
        if not url:
            return jsonify({"error": "No URL provided"}), 400
            
        print(f"Processing URL: {url}")
        text = scrape_url(url)
        
        if not text.strip():
            return jsonify({"error": "Could not extract text from URL"}), 400
            
        max_length = 8000
        text_to_process = text[:max_length]
        
        print(f"📝 Sending to LLM for extraction...")
        triples = run_extraction(text_to_process, url)
        print(f"✅ Extracted {len(triples)} triples from URL")
        
        ingest_triples(triples)
        
        return jsonify({
            "status": "success", 
            "triples_count": len(triples),
            "source": url
        })
    except Exception as e:
        print(f"URL processing error: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/graph", methods=["GET"])
def get_graph():
    seed_id = request.args.get("seed_id")
    depth = int(request.args.get("depth", 1))
    source_doc = request.args.get("source")
    # Optional confidence filter
    try:
        min_conf = request.args.get("min_confidence")
        min_conf = float(min_conf) if min_conf is not None else None
    except Exception:
        min_conf = None

    data = get_subgraph(seed_id, depth, source_doc)
    if min_conf is not None:
        # Filter edges by confidence and rebuild nodes accordingly
        filtered_edges = []
        node_ids = set()
        for e in data.get("edges", []):
            conf = e["data"].get("confidence")
            if conf is None or conf >= min_conf:
                filtered_edges.append(e)
                node_ids.add(e["data"]["source"]) 
                node_ids.add(e["data"]["target"]) 
        filtered_nodes = [n for n in data.get("nodes", []) if n["data"]["id"] in node_ids]
        data = {"nodes": filtered_nodes, "edges": filtered_edges}
    return jsonify(data)

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.json
    node_id = data.get("node_id")
    message = data.get("message")
    
    context_facts = []
    if node_id:
        # Re-use get_subgraph logic but just extract text
        graph_data = get_subgraph(node_id, depth=1)
        for edge in graph_data["edges"]:
            d = edge["data"]
            context_facts.append(f"{d['source']} {d['label']} {d['target']}")
    
    context_str = "\n".join(context_facts)
    
    system_prompt = f"""You are a helpful assistant. Use the following knowledge graph context to answer the user's question.
    
    Context:
    {context_str}
    """
    
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": message}
    ]
    
    response = llm.invoke(messages)
    
    return jsonify({"reply": response.content, "context": context_facts})

@app.route("/api/source/delete", methods=["POST"])
def delete_source():
    try:
        data = request.json or {}
        source_doc = data.get("source_doc")
        if not source_doc:
            return jsonify({"error": "source_doc is required"}), 400

        if not NEO4J_AVAILABLE:
            # When DB is unavailable, mimic success but with zero counts
            return jsonify({"status": "skipped", "deleted_rels": 0, "deleted_nodes": 0})

        with driver.session() as session:
            # Delete relationships by source_doc
            rel_result = session.run(
                """
                MATCH ()-[r]->()
                WHERE r.source_doc = $source_doc
                WITH r LIMIT 10000
                DELETE r
                RETURN count(*) AS deleted_rels
                """,
                source_doc=source_doc,
            ).single()
            deleted_rels = rel_result["deleted_rels"] if rel_result else 0

            # Optionally delete orphan nodes (no remaining relationships)
            node_result = session.run(
                """
                MATCH (e:Entity)
                WHERE NOT (e)--()
                WITH e LIMIT 10000
                DELETE e
                RETURN count(*) AS deleted_nodes
                """
            ).single()
            deleted_nodes = node_result["deleted_nodes"] if node_result else 0

        return jsonify({
            "status": "success",
            "source_doc": source_doc,
            "deleted_rels": deleted_rels,
            "deleted_nodes": deleted_nodes,
        })
    except Exception as e:
        print(f"Delete source error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/relations", methods=["GET"])
def list_relations():
    source_doc = request.args.get("source")
    limit = int(request.args.get("limit", 100))
    min_conf = request.args.get("min_confidence")
    try:
        min_conf = float(min_conf) if min_conf is not None else None
    except Exception:
        min_conf = None

    if not NEO4J_AVAILABLE:
        return jsonify({"relations": []})

    where = []
    if source_doc:
        where.append("r.source_doc = $source_doc")
    if min_conf is not None:
        where.append("r.confidence >= $min_conf")
    where_clause = ("WHERE " + " AND ".join(where)) if where else ""

    query = f"""
    MATCH (a:Entity)-[r:REL]->(b:Entity)
    {where_clause}
    RETURN a.name AS subject, r.predicate AS predicate, b.name AS object, r.confidence AS confidence, r.source_doc AS source_doc, r.span AS span, type(r) AS type
    LIMIT $limit
    """
    rels = []
    with driver.session() as session:
        result = session.run(query, source_doc=source_doc, min_conf=min_conf, limit=limit)
        for record in result:
            edge_id = f"{record['subject']}_{record['predicate']}_{record['object']}"
            rels.append({
                "edge_id": edge_id,
                "subject": record["subject"],
                "predicate": record["predicate"],
                "object": record["object"],
                "confidence": record["confidence"],
                "source_doc": record["source_doc"],
                "span": record["span"],
            })
    return jsonify({"relations": rels})

@app.route("/api/relation/delete", methods=["POST"])
def relation_delete():
    data = request.json or {}
    edge_id = data.get("edge_id")
    if not edge_id:
        return jsonify({"error": "edge_id is required"}), 400
    if not NEO4J_AVAILABLE:
        return jsonify({"status": "skipped", "deleted": 0})
    try:
        # edge_id format: subject_predicate_object
        try:
            subject, predicate, object_ = edge_id.split("_", 2)
        except ValueError:
            return jsonify({"error": "invalid edge_id format"}), 400
        with driver.session() as session:
            result = session.run(
                """
                MATCH (a:Entity {name: $subject})-[r:REL {predicate: $predicate}]->(b:Entity {name: $object})
                DELETE r
                RETURN 1 AS ok
                """,
                subject=subject, predicate=predicate, object=object_
            ).single()
        return jsonify({"status": "success", "deleted": 1})
    except Exception as e:
        print(f"Relation delete error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/relation/update", methods=["POST"])
def relation_update():
    data = request.json or {}
    edge_id = data.get("edge_id")
    confidence = data.get("confidence")
    if edge_id is None or confidence is None:
        return jsonify({"error": "edge_id and confidence are required"}), 400
    try:
        confidence = float(confidence)
    except Exception:
        return jsonify({"error": "confidence must be a number"}), 400
    if not NEO4J_AVAILABLE:
        return jsonify({"status": "skipped"})
    try:
        subject, predicate, object_ = edge_id.split("_", 2)
        with driver.session() as session:
            session.run(
                """
                MATCH (a:Entity {name: $subject})-[r:REL {predicate: $predicate}]->(b:Entity {name: $object})
                SET r.confidence = $confidence
                RETURN 1 AS ok
                """,
                subject=subject, predicate=predicate, object=object_, confidence=confidence
            )
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Relation update error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/api/entity/merge", methods=["POST"])
def entity_merge():
    data = request.json or {}
    from_name = data.get("from")
    into_name = data.get("into")
    if not from_name or not into_name:
        return jsonify({"error": "from and into are required"}), 400
    if not NEO4J_AVAILABLE:
        return jsonify({"status": "skipped"})
    try:
        with driver.session() as session:
            # Redirect relationships from `from` to `into`
            session.run(
                """
                MATCH (f:Entity {name: $from})
                MATCH (t:Entity {name: $into})
                // incoming
                MATCH (a)-[r1:REL]->(f)
                MERGE (a)-[r1n:REL {predicate: r1.predicate}]->(t)
                SET r1n += {confidence: r1.confidence, source_doc: r1.source_doc, span: r1.span}
                DELETE r1
                // outgoing
                WITH f, t
                MATCH (f)-[r2:REL]->(b)
                MERGE (t)-[r2n:REL {predicate: r2.predicate}]->(b)
                SET r2n += {confidence: r2.confidence, source_doc: r2.source_doc, span: r2.span}
                DELETE r2
                // delete from node
                WITH f
                DETACH DELETE f
                """,
                parameters={"from": from_name, "into": into_name}
            )
        return jsonify({"status": "success"})
    except Exception as e:
        print(f"Entity merge error: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
