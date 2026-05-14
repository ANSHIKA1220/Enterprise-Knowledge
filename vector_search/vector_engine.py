import os
import logging
from typing import List, Dict, Any
from dotenv import load_dotenv

from langchain_core.documents import Document
from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv()

class ChromaSearchEngine:
    """
    Core Singleton class for local ChromaDB operations.
    """
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ChromaSearchEngine, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.persist_directory = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        self.collection_name = os.getenv("CHROMA_COLLECTION", "enterprise_kb")

        logger.info("Initializing Local ChromaSearchEngine...")
        try:
            # Load lightweight local embeddings
            self.embeddings = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
            self.vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory
            )
            logger.info("Local Vector store initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize Vector Store: {str(e)}")
            raise

    def ingest_pipeline_chunks(self, chunks: List[Dict[str, Any]], batch_size: int = 100) -> bool:
        """
        Ingests the chunk dictionaries produced by Anshika's pipeline.
        """
        if not chunks:
            logger.warning("No chunks provided for ingestion.")
            return False

        logger.info(f"Preparing {len(chunks)} chunks for ChromaDB ingestion...")
        
        documents = []
        ids = []
        
        for chunk in chunks:
            # Map Anshika's schema to LangChain Document format
            doc = Document(
                page_content=chunk.get("text", ""),
                metadata=chunk.get("metadata", {})
            )
            documents.append(doc)
            ids.append(chunk.get("chunk_id"))

        try:
            for i in range(0, len(documents), batch_size):
                batch_docs = documents[i : i + batch_size]
                batch_ids = ids[i : i + batch_size]
                
                self.vector_store.add_documents(documents=batch_docs, ids=batch_ids)
            
            logger.info("Vector data ingestion completed successfully.")
            return True
        except Exception as e:
            logger.error(f"Error during vector ingestion: {str(e)}")
            return False

    async def aretrieve_context(self, query: str, top_k: int = 4) -> str:
        """
        Async retrieval function formatted specifically for Arpan's LangGraph agents.
        """
        try:
            results = await self.vector_store.asimilarity_search(query, k=top_k)
            
            if not results:
                return "No relevant information found in the vector database."

            formatted_results = []
            for idx, doc in enumerate(results):
                source = doc.metadata.get("source_file", "Unknown Document")
                page = doc.metadata.get("page_number", "N/A")
                content = doc.page_content.strip().replace("\n", " ")
                
                formatted_results.append(
                    f"[Source {idx + 1} | File: {source} | Page: {page}]\n{content}\n"
                )
            
            return "\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Retrieval error: {str(e)}")
            return f"System Error: Vector retrieval failed: {str(e)}"