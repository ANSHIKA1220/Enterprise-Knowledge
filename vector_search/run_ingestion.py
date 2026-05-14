import os
import logging
import sys

# Add the root directory to Python's path so it can find Anshika's folder
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from ingestion_pipeline.ingestion.pipeline import ingest_directory
from vector_search.vector_engine import ChromaSearchEngine

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_end_to_end_ingestion():
    # Construct the path to Anshika's sample data relative to the root
    data_dir = os.path.join(root_dir, "ingestion_pipeline", "sample data")
    output_path = os.path.join(root_dir, "ingestion_pipeline", "output", "chunks.jsonl")
    
    logger.info(f"Starting ingestion from directory: {data_dir}")
    
    try:
        # 1. Fetch chunks using Anshika's pipeline
        chunks = ingest_directory(
            input_dir=data_dir,
            output_path=output_path,
            chunk_size=512,
            overlap=64
        )
        logger.info(f"Received {len(chunks)} chunks from Anshika's pipeline.")
    except Exception as e:
        logger.error(f"Failed to run ingestion pipeline: {str(e)}")
        return

    try:
        # 2. Push to your local ChromaDB
        vector_db = ChromaSearchEngine()
        success = vector_db.ingest_pipeline_chunks(chunks)
        
        if success:
            logger.info("Vector Database successfully populated!")
    except Exception as e:
         logger.error(f"Failed to ingest into Vector DB: {str(e)}")

if __name__ == "__main__":
    run_end_to_end_ingestion()