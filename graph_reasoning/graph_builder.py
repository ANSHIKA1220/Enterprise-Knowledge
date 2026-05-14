import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

def insert_relation(entity1, label1, relation, entity2, label2, source="mock_data"):
    query = f"""
    MERGE (a:{label1} {{name: $entity1}})
    MERGE (b:{label2} {{name: $entity2}})
    MERGE (a)-[r:{relation}]->(b)
    SET r.source = $source
    """
    with driver.session() as session:
        session.run(query, entity1=entity1, entity2=entity2, source=source)

def build_graph():
    insert_relation("Payment API", "API", "HAS_ERROR", "Timeout Error", "Error", "ticket_01")
    insert_relation("Timeout Error", "Error", "CAUSED_BY", "MongoDB", "Database", "ticket_01")
    insert_relation("Payment API", "API", "DEPENDS_ON", "Auth Service", "Service", "ticket_02")
    insert_relation("Auth Service", "Service", "USES", "Redis Cache", "Database", "ticket_02")
    insert_relation("Redis Cache", "Database", "CAUSES", "Slow Response", "Error", "ticket_03")
    insert_relation("Login API", "API", "DEPENDS_ON", "Auth Service", "Service", "ticket_04")
    insert_relation("Auth Service", "Service", "HAS_ERROR", "Token Failure", "Error", "ticket_05")

if __name__ == "__main__":
    build_graph()
    print("Knowledge graph created successfully.")