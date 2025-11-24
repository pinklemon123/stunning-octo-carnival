"""
Neo4j 图数据库操作示例
演示常用的图谱查询和操作
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from typing import List, Dict, Any

load_dotenv()

class Neo4jGraph:
    """Neo4j 图数据库操作类"""
    
    def __init__(self, uri: str = None, user: str = None, password: str = None):
        self.uri = uri or os.getenv("NEO4J_URI", "neo4j://127.0.0.1:7687")
        self.user = user or os.getenv("NEO4J_USER", "neo4j")
        self.password = password or os.getenv("NEO4J_PASSWORD", "12345678")
        self.driver = GraphDatabase.driver(self.uri, auth=(self.user, self.password))
    
    def close(self):
        """关闭数据库连接"""
        if self.driver:
            self.driver.close()
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
    
    # ========== 基础操作 ==========
    
    def add_triple(self, subject: str, predicate: str, obj: str, 
                   confidence: float = 1.0, source: str = "manual"):
        """
        添加单个三元组
        
        Args:
            subject: 主体实体
            predicate: 关系
            obj: 客体实体
            confidence: 置信度
            source: 来源文档
        """
        query = """
        MERGE (a:Entity {name: $subject})
        MERGE (b:Entity {name: $object})
        MERGE (a)-[r:REL {predicate: $predicate}]->(b)
        SET r.confidence = $confidence,
            r.source_doc = $source,
            r.updated_at = datetime()
        """
        with self.driver.session() as session:
            session.run(query, 
                subject=subject, 
                predicate=predicate, 
                object=obj,
                confidence=confidence,
                source=source
            )
    
    def add_triples_batch(self, triples: List[Dict[str, Any]]):
        """
        批量添加三元组
        
        Args:
            triples: 三元组列表，每个元素包含 subject, predicate, object, confidence, source_doc
        """
        query = """
        UNWIND $triples AS t
        MERGE (a:Entity {name: t.subject})
        MERGE (b:Entity {name: t.object})
        MERGE (a)-[r:REL {predicate: t.predicate}]->(b)
        SET r.confidence = t.confidence,
            r.source_doc = t.source_doc,
            r.updated_at = datetime()
        """
        with self.driver.session() as session:
            session.run(query, triples=triples)
    
    # ========== 查询操作 ==========
    
    def get_entity_neighbors(self, entity_name: str, depth: int = 1) -> Dict[str, Any]:
        """
        获取实体的邻居节点
        
        Args:
            entity_name: 实体名称
            depth: 查询深度
            
        Returns:
            包含节点和边的字典
        """
        query = f"""
        MATCH (n:Entity {{name: $name}})-[r*1..{depth}]-(m)
        RETURN n, r, m
        LIMIT 100
        """
        nodes = {}
        edges = []
        
        with self.driver.session() as session:
            result = session.run(query, name=entity_name)
            for record in result:
                n = record["n"]
                m = record["m"]
                rels = record["r"]
                
                nodes[n["name"]] = {"name": n["name"], "type": "Entity"}
                nodes[m["name"]] = {"name": m["name"], "type": "Entity"}
                
                if not isinstance(rels, list):
                    rels = [rels]
                
                for r in rels:
                    edges.append({
                        "source": r.start_node["name"],
                        "target": r.end_node["name"],
                        "predicate": r.get("predicate", "REL"),
                        "confidence": r.get("confidence", 1.0)
                    })
        
        return {
            "nodes": list(nodes.values()),
            "edges": edges
        }
    
    def find_path(self, start: str, end: str, max_depth: int = 5) -> List[Dict]:
        """
        查找两个实体之间的最短路径
        
        Args:
            start: 起始实体
            end: 目标实体
            max_depth: 最大搜索深度
            
        Returns:
            路径列表
        """
        query = f"""
        MATCH path = shortestPath(
            (a:Entity {{name: $start}})-[*1..{max_depth}]-(b:Entity {{name: $end}})
        )
        RETURN path
        """
        paths = []
        
        with self.driver.session() as session:
            result = session.run(query, start=start, end=end)
            for record in result:
                path = record["path"]
                path_data = {
                    "nodes": [node["name"] for node in path.nodes],
                    "relationships": [
                        {
                            "predicate": rel.get("predicate", "REL"),
                            "confidence": rel.get("confidence", 1.0)
                        }
                        for rel in path.relationships
                    ]
                }
                paths.append(path_data)
        
        return paths
    
    def get_top_entities(self, limit: int = 10) -> List[Dict]:
        """
        获取度中心性最高的实体
        
        Args:
            limit: 返回数量
            
        Returns:
            实体列表，按度数排序
        """
        query = """
        MATCH (n:Entity)-[r]-()
        RETURN n.name AS name, count(r) AS degree
        ORDER BY degree DESC
        LIMIT $limit
        """
        entities = []
        
        with self.driver.session() as session:
            result = session.run(query, limit=limit)
            for record in result:
                entities.append({
                    "name": record["name"],
                    "degree": record["degree"]
                })
        
        return entities
    
    def search_entities(self, keyword: str, limit: int = 20) -> List[str]:
        """
        搜索包含关键词的实体
        
        Args:
            keyword: 搜索关键词
            limit: 返回数量
            
        Returns:
            实体名称列表
        """
        query = """
        MATCH (n:Entity)
        WHERE n.name CONTAINS $keyword
        RETURN n.name AS name
        LIMIT $limit
        """
        entities = []
        
        with self.driver.session() as session:
            result = session.run(query, keyword=keyword, limit=limit)
            for record in result:
                entities.append(record["name"])
        
        return entities
    
    # ========== 统计操作 ==========
    
    def get_stats(self) -> Dict[str, int]:
        """
        获取图谱统计信息
        
        Returns:
            包含节点数、关系数等统计信息的字典
        """
        stats = {}
        
        with self.driver.session() as session:
            # 节点数
            result = session.run("MATCH (n:Entity) RETURN count(n) AS count")
            stats["entities"] = result.single()["count"]
            
            # 关系数
            result = session.run("MATCH ()-[r:REL]->() RETURN count(r) AS count")
            stats["relationships"] = result.single()["count"]
            
            # 平均度数
            result = session.run("""
                MATCH (n:Entity)
                OPTIONAL MATCH (n)-[r]-()
                WITH n, count(DISTINCT r) AS degree
                RETURN avg(degree) AS avg_degree
            """)
            record = result.single()
            stats["avg_degree"] = round(record["avg_degree"], 2) if record["avg_degree"] else 0
        
        return stats
    
    # ========== 维护操作 ==========
    
    def clear_all(self):
        """清空所有数据（谨慎使用！）"""
        with self.driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def merge_entities(self, old_name: str, new_name: str):
        """
        合并实体（将 old_name 的所有关系转移到 new_name）
        
        Args:
            old_name: 旧实体名称
            new_name: 新实体名称
        """
        query = """
        MATCH (old:Entity {name: $old_name})
        MERGE (new:Entity {name: $new_name})
        WITH old, new
        MATCH (old)-[r]->(other)
        MERGE (new)-[r2:REL {predicate: r.predicate}]->(other)
        SET r2 = r
        WITH old, new
        MATCH (other)-[r]->(old)
        MERGE (other)-[r2:REL {predicate: r.predicate}]->(new)
        SET r2 = r
        WITH old
        DETACH DELETE old
        """
        with self.driver.session() as session:
            session.run(query, old_name=old_name, new_name=new_name)


# ========== 使用示例 ==========

if __name__ == "__main__":
    print("=" * 60)
    print("📊 Neo4j 图数据库操作示例")
    print("=" * 60)
    
    with Neo4jGraph() as graph:
        # 1. 添加示例数据
        print("\n1️⃣ 添加示例三元组...")
        sample_triples = [
            {"subject": "量子力学", "predicate": "包含", "object": "薛定谔方程", 
             "confidence": 0.95, "source_doc": "physics.txt"},
            {"subject": "薛定谔方程", "predicate": "提出者", "object": "薛定谔", 
             "confidence": 1.0, "source_doc": "physics.txt"},
            {"subject": "薛定谔", "predicate": "国籍", "object": "奥地利", 
             "confidence": 1.0, "source_doc": "physics.txt"},
            {"subject": "量子力学", "predicate": "应用于", "object": "微观粒子", 
             "confidence": 0.9, "source_doc": "physics.txt"},
        ]
        graph.add_triples_batch(sample_triples)
        print("✅ 添加完成")
        
        # 2. 获取统计信息
        print("\n2️⃣ 图谱统计:")
        stats = graph.get_stats()
        for key, value in stats.items():
            print(f"   {key}: {value}")
        
        # 3. 查找邻居
        print("\n3️⃣ 查找'量子力学'的邻居:")
        neighbors = graph.get_entity_neighbors("量子力学", depth=2)
        print(f"   节点数: {len(neighbors['nodes'])}")
        print(f"   边数: {len(neighbors['edges'])}")
        for edge in neighbors['edges'][:5]:
            print(f"   - {edge['source']} --[{edge['predicate']}]--> {edge['target']}")
        
        # 4. 查找路径
        print("\n4️⃣ 查找'量子力学'到'奥地利'的路径:")
        paths = graph.find_path("量子力学", "奥地利")
        if paths:
            for i, path in enumerate(paths, 1):
                print(f"   路径 {i}: {' -> '.join(path['nodes'])}")
        else:
            print("   未找到路径")
        
        # 5. 获取重要实体
        print("\n5️⃣ 度中心性最高的实体:")
        top_entities = graph.get_top_entities(limit=5)
        for entity in top_entities:
            print(f"   {entity['name']}: {entity['degree']} 个连接")
        
        # 6. 搜索实体
        print("\n6️⃣ 搜索包含'量子'的实体:")
        results = graph.search_entities("量子", limit=5)
        for name in results:
            print(f"   - {name}")
    
    print("\n" + "=" * 60)
    print("✅ 示例完成！")
