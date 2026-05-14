from langchain_core.tools import tool
from vector_search.vector_engine import ChromaSearchEngine

# Initialize the singleton instance
vector_db = ChromaSearchEngine()

@tool
async def semantic_search_tool(query: str) -> str:
    """
    Use this tool to search the enterprise knowledge base for unstructured text, 
    documentation, manuals, and historical IT tickets.
    Input should be a specific, natural language search query.
    """
    return await vector_db.aretrieve_context(query)