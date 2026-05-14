"""
graph_from_ingestion.py

Connects Anshika's ingestion pipeline
to Yash's Neo4j graph reasoning module.
"""
import sys
from pathlib import Path

sys.path.append(
    str(Path(__file__).resolve().parent.parent)
)
from ingestion_pipeline.ingestion.pipeline import ingest_directory
from graph_builder import insert_relation


def extract_relations_from_text(text, source="chunk"):
    relations = []
    text_lower = text.lower()

    if "error" in text_lower or "exception" in text_lower or "failed" in text_lower or "failure" in text_lower:
        relations.append(("System", "Service", "HAS_ERROR", "Runtime Error", "Error", source))

    if "runtime" in text_lower:
        relations.append(("Runtime Error", "Error", "RELATED_TO", "RuntimeTerror.pdf", "Document", source))

    if "database" in text_lower or "db" in text_lower:
        relations.append(("System", "Service", "DEPENDS_ON", "Database", "Database", source))

    if "api" in text_lower:
        relations.append(("API Service", "API", "PART_OF", "System", "Service", source))

    if "server" in text_lower:
        relations.append(("Server", "Service", "HOSTS", "System", "Service", source))

    if "log" in text_lower:
        relations.append(("Log File", "Document", "MENTIONS", "Runtime Error", "Error", source))

    return relations

def build_graph_from_ingestion(input_dir):

    chunks = ingest_directory(
        input_dir=input_dir,
        output_path=None
    )
    print("Total chunks:", len(chunks))

    for i, chunk in enumerate(chunks[:3]):
        print("\n--- CHUNK", i + 1, "---")
        print(chunk)
    total = 0

    for chunk in chunks:

        text = chunk.get("text", "")

        metadata = chunk.get("metadata", {})

        source = metadata.get("filename", "unknown")

        relations = extract_relations_from_text(
            text,
            source
        )

        for e1, l1, rel, e2, l2, src in relations:

            insert_relation(
                e1,
                l1,
                rel,
                e2,
                l2,
                src
            )

            total += 1

    print(f"Inserted {total} relationships into Neo4j.")


if __name__ == "__main__":

    build_graph_from_ingestion(
    "../ingestion_pipeline/sample data"
)