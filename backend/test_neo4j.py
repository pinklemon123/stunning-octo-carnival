import os
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "12345678")

print(f"Connecting to Neo4j at: {NEO4J_URI}")
print(f"Username: {NEO4J_USER}")

try:
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    
    with driver.session() as session:
        # Test connection
        result = session.run("RETURN 1 as test")
        print("✅ Neo4j connection successful!")
        
        # Count entities
        result = session.run("MATCH (n:Entity) RETURN count(n) as count")
        entity_count = result.single()["count"]
        print(f"\n📊 Total entities in database: {entity_count}")
        
        # Count relationships
        result = session.run("MATCH ()-[r:REL]->() RETURN count(r) as count")
        rel_count = result.single()["count"]
        print(f"📊 Total relationships in database: {rel_count}")
        
        # Show some sample data
        if entity_count > 0:
            print("\n📝 Sample entities:")
            result = session.run("MATCH (n:Entity) RETURN n.name as name LIMIT 10")
            for record in result:
                print(f"  - {record['name']}")
        
        if rel_count > 0:
            print("\n🔗 Sample relationships:")
            result = session.run("""
                MATCH (a:Entity)-[r:REL]->(b:Entity) 
                RETURN a.name as subject, r.predicate as predicate, b.name as object, r.source_doc as source
                LIMIT 10
            """)
            for record in result:
                print(f"  - {record['subject']} → {record['predicate']} → {record['object']} (from: {record['source']})")
    
    driver.close()
    
except Exception as e:
    print(f"❌ Error connecting to Neo4j: {e}")
    import traceback
    traceback.print_exc()
