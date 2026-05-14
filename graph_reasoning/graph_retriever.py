import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

driver = GraphDatabase.driver(
    os.getenv("NEO4J_URI"),
    auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
)

KNOWN_ENTITIES = [
    "Payment API",
    "Timeout Error",
    "MongoDB",
    "Auth Service",
    "Redis Cache",
    "Slow Response",
    "Login API",
    "Token Failure"
]

def extract_query_entities(query):
    found = []
    query_lower = query.lower()

    for entity in KNOWN_ENTITIES:
        if entity.lower() in query_lower:
            found.append(entity)

    return found

def retrieve_graph_context(query_entities, depth=3):
    cypher = f"""
    MATCH path = (a)-[*1..{depth}]-(b)
    WHERE a.name IN $entities
    RETURN path
    LIMIT 10
    """

    context = []

    with driver.session() as session:
        records = session.run(cypher, entities=query_entities)

        for record in records:
            path = record["path"]

            for rel in path.relationships:
                start = rel.start_node["name"]
                end = rel.end_node["name"]
                rel_type = rel.type
                context.append(f"{start} --{rel_type}--> {end}")

    return list(set(context))

def get_graph_answer_context(user_query):
    entities = extract_query_entities(user_query)

    if not entities:
        return "No matching graph entities found."

    graph_context = retrieve_graph_context(entities)

    if not graph_context:
        return "No graph relationships found."

    return "\n".join(graph_context)