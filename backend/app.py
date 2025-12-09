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

@app.route("/api/upload", methods=["POST"])
def upload_file():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file part"}), 400
        file = request.files['file']
        if file.filename == '':
            return jsonify({"error": "No selected file"}), 400
            
        content = file.read()
        
        # Try to decode with UTF-8, fallback to other encodings
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            try:
                text = content.decode("gbk")  # Try GBK for Chinese text
            except UnicodeDecodeError:
                text = content.decode("latin-1")  # Fallback
        
        print(f"Processing file: {file.filename}, length: {len(text)}")
        
        # 增加处理长度限制，并显示处理的文本片段
        max_length = 8000
        text_to_process = text[:max_length]
        if len(text) > max_length:
            print(f"⚠️ Text truncated from {len(text)} to {max_length} characters")
        
        print(f"📝 Sending to LLM for extraction...")
        triples = run_extraction(text_to_process, file.filename)
        print(f"✅ Extracted {len(triples)} triples")
        
        # 显示提取的三元组（用于调试）
        for i, triple in enumerate(triples[:5], 1):  # 只显示前5个
            print(f"  {i}. ({triple['subject']}) --[{triple['predicate']}]--> ({triple['object']})")
        if len(triples) > 5:
            print(f"  ... and {len(triples) - 5} more triples")
        
        ingest_triples(triples)
        
        return jsonify({"status": "success", "triples_count": len(triples)})
    except Exception as e:
        print(f"Upload error: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500

@app.route("/api/graph", methods=["GET"])
def get_graph():
    seed_id = request.args.get("seed_id")
    depth = int(request.args.get("depth", 1))
    source_doc = request.args.get("source")
    data = get_subgraph(seed_id, depth, source_doc)
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

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
