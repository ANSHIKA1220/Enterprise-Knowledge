import json
import sys
import os

from vector_search.vector_engine import ChromaSearchEngine
from graph_reasoning.graph_builder import insert_relation
from graph_reasoning.graph_from_ingestion import extract_relations_from_text

def populate():
    # Load chunks
    with open("chunks.jsonl", "r") as f:
        chunks = [json.loads(line) for line in f]
    
    print(f"Loaded {len(chunks)} chunks from chunks.jsonl")

    # 1. Populate Vector DB
    try:
        vector_db = ChromaSearchEngine()
        success = vector_db.ingest_pipeline_chunks(chunks)
        if success:
            print("Successfully populated ChromaDB vector store.")
        else:
            print("Failed to populate ChromaDB vector store.")
    except Exception as e:
        print(f"Error populating ChromaDB: {e}")

    # 2. Populate Neo4j Graph DB
    try:
        total_relations = 0
        for chunk in chunks:
            text = chunk.get("text", "")
            metadata = chunk.get("metadata", {})
            source = metadata.get("filename", "unknown")
            relations = extract_relations_from_text(text, source)
            
            for e1, l1, rel, e2, l2, src in relations:
                insert_relation(e1, l1, rel, e2, l2, src)
                total_relations += 1
                
        print(f"Successfully inserted {total_relations} relationships into Neo4j.")
    except Exception as e:
        print(f"Error populating Neo4j: {e}")

if __name__ == "__main__":
    populate()
