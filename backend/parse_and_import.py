import re
from neo4j import GraphDatabase
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Get Neo4j connection details from environment variables
uri = os.getenv("NEO4J_URI")
user = os.getenv("NEO4J_USER")
password = os.getenv("NEO4J_PASSWORD")

# Neo4j connection setup
class GraphImporter:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def create_entity_and_relationship(self, queries):
        with self.driver.session() as session:
            for query in queries:
                session.run(query)

# Parse text into entities and relationships
def parse_text_to_cypher(text):
    sentences = re.split(r'。', text.strip())
    queries = []

    for sentence in sentences:
        if '是' in sentence:
            parts = sentence.split('是')
            if len(parts) == 2:
                entity1 = parts[0].strip()
                entity2 = parts[1].strip()
                queries.append(f"MERGE (a:Entity {{name: '{entity1}'}}) MERGE (b:Entity {{name: '{entity2}'}}) MERGE (a)-[:IS]->(b)")
        elif '在' in sentence:
            parts = sentence.split('在')
            if len(parts) == 2:
                entity1 = parts[0].strip()
                entity2 = parts[1].strip()
                queries.append(f"MERGE (a:Entity {{name: '{entity1}'}}) MERGE (b:Entity {{name: '{entity2}'}}) MERGE (a)-[:LOCATED_IN]->(b)")
    return queries

if __name__ == "__main__":
    # Example text
    text = "张三是一名软件工程师。他在北京工作。北京是中国的首都。"

    # Parse text
    cypher_queries = parse_text_to_cypher(text)

    # Debug: Print generated Cypher queries
    print("Generated Cypher Queries:")
    for query in cypher_queries:
        print(query)

    # Import into Neo4j
    importer = GraphImporter(uri, user, password)
    importer.create_entity_and_relationship(cypher_queries)
    importer.close()