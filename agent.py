import operator
import json
import time
import os
from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from pydantic import BaseModel, Field
import chromadb

# ---------------------------------------------------------
# NEW: GEMINI IMPORTS
# ---------------------------------------------------------
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

# Load the GOOGLE_API_KEY from your .env file
load_dotenv()

# ---------------------------------------------------------
# CROSS-MODULE IMPORTS (Team Architecture)
# ---------------------------------------------------------
# 1. Rhythm's Vector Search
from vector_search.agent_tool import retrieve_vector_context

# 2. Yash's Graph Reasoning
from graph_reasoning.graph_retriever import get_graph_answer_context

# 3. The Dedicated Confidence Engine
from confidence_engine.evaluator import calculate_confidence

# 4. Anshika's Ingestion Pipeline
from ingestion_pipeline.ingestion.pipeline import ingest_directory 

# ---------------------------------------------------------
# 1. State Definition & Structured Schemas
# ---------------------------------------------------------
class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]
    confidence_score: float
    escalation_required: bool
    final_answer: str

class GraphSearchInput(BaseModel):
    query: str = Field(description="The query to trace root causes, dependencies, and relationships in Neo4j.")

class DiagnosisOutput(BaseModel):
    resolution: str = Field(description="The step-by-step resolution or a structured hand-off summary.")

# ---------------------------------------------------------
# 2. Tool Wrapper & Gemini Initialization
# ---------------------------------------------------------
@tool("retrieve_graph_context", args_schema=GraphSearchInput)
async def retrieve_graph_context_tool(query: str) -> str:
    """Find relational logic, API dependencies, and root causes using Neo4j."""
    try:
        results = get_graph_answer_context(query)
        return str(results)
    except Exception as e:
        return f"Graph backend unavailable: {str(e)}"

# Initialize Gemini 1.5 Pro (Free and highly capable)
llm = ChatGoogleGenerativeAI(
    model="gemini-1.5-pro", 
    temperature=0, 
    max_retries=3
)

# Bind the tools to Gemini
tools = [retrieve_vector_context, retrieve_graph_context_tool] 
llm_with_tools = llm.bind_tools(tools)

# ---------------------------------------------------------
# 3. Agent Nodes (Plan, Find, Diagnose)
# ---------------------------------------------------------
async def orchestrator_node(state: AgentState):
    """Orchestrator (Plan): Decides which tools to use based on the user query."""
    messages = state['messages']
    
    if len(messages) > 15:
        messages = [messages[0]] + messages[-14:]
        
    sys_msg = SystemMessage(content=(
        "You are an enterprise orchestrator. Analyze the IT or system query. "
        "Call 'retrieve_vector_context' for documentation/logs or 'retrieve_graph_context_tool' "
        "for system relationships and root causes. If you have enough context to diagnose the issue, "
        "do not call any tools."
    ))
    
    response = await llm_with_tools.ainvoke([sys_msg] + messages)
    return {"messages": [response]}

async def tool_execution_node(state: AgentState):
    """Tool Agent (Execute): Executes the vector or graph retrieval."""
    messages = state['messages']
    last_message = messages[-1]
    tool_responses = []
    
    for tool_call in last_message.tool_calls:
        if tool_call["name"] == "retrieve_vector_context":
            res = await retrieve_vector_context.ainvoke(tool_call["args"])
            tool_responses.append(ToolMessage(content=str(res), tool_call_id=tool_call["id"]))
        elif tool_call["name"] == "retrieve_graph_context_tool":
            res = retrieve_graph_context_tool.invoke(tool_call["args"]) 
            tool_responses.append(ToolMessage(content=str(res), tool_call_id=tool_call["id"]))
            
    return {"messages": tool_responses}

async def reasoning_node(state: AgentState):
    """Reasoning Agent (Diagnose): Synthesises data and calls the external Confidence Engine."""
    messages = state['messages']
    
    sys_msg = SystemMessage(content=(
        "You are the final reasoning agent. Synthesize the retrieved data to diagnose the issue. "
        "Provide a context-aware answer with step-by-step resolution and cite your sources."
    ))
    
    # Gemini handles structured outputs beautifully via LangChain
    structured_llm = llm.with_structured_output(DiagnosisOutput)
    
    try:
        diagnosis = await structured_llm.ainvoke([sys_msg] + messages)
        final_content = diagnosis.resolution
        
        retrieved_context = "\n".join([msg.content for msg in messages if isinstance(msg, ToolMessage)])
        user_query = messages[0].content
        
        confidence = calculate_confidence(user_query, retrieved_context, final_content)
        escalation = True if confidence < 90.0 else False
        
        if escalation:
             final_content = f"⚠️ CONFIDENCE LOW ({confidence}%). ESCALATING TO HUMAN ENGINEER.\n\nPreliminary Findings: {final_content}"

    except Exception:
        final_content = "SYSTEM ERROR: Diagnosis generation failed. Escalating to human."
        confidence = 0.0
        escalation = True
        
    return {
        "messages": [AIMessage(content=final_content)],
        "final_answer": final_content,
        "confidence_score": confidence,
        "escalation_required": escalation
    }

# ---------------------------------------------------------
# 4. Routing Logic
# ---------------------------------------------------------
def router(state: AgentState):
    """Routes the graph based on whether the Orchestrator called a tool."""
    messages = state['messages']
    last_message = messages[-1]
    
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "tool_execution_node"
    return "reasoning_node"

# ---------------------------------------------------------
# 5. Graph Compilation
# ---------------------------------------------------------
memory = MemorySaver()
workflow = StateGraph(AgentState)

workflow.add_node("orchestrator_node", orchestrator_node)
workflow.add_node("tool_execution_node", tool_execution_node)
workflow.add_node("reasoning_node", reasoning_node)

workflow.set_entry_point("orchestrator_node")
workflow.add_conditional_edges(
    "orchestrator_node", 
    router, 
    {"tool_execution_node": "tool_execution_node", "reasoning_node": "reasoning_node"}
)
workflow.add_edge("tool_execution_node", "orchestrator_node")
workflow.add_edge("reasoning_node", END)

copilot_app = workflow.compile(checkpointer=memory)

# ---------------------------------------------------------
# 6. Main Integration Entry Point
# ---------------------------------------------------------
async def run_agentic_workflow(user_query: str, thread_id: str = "default_thread") -> dict:
    """Triggers the entire reasoning process."""
    config = {"configurable": {"thread_id": thread_id}}
    initial_state = {"messages": [HumanMessage(content=user_query)]}
    
    try:
        final_state = await copilot_app.ainvoke(initial_state, config=config)
        status = "ESCALATED_TO_HUMAN" if final_state.get("escalation_required") else "RESOLVED"
        
        return {
            "status": status,
            "confidence_score": final_state.get("confidence_score"),
            "final_answer": final_state.get("final_answer"), 
            "context_history": [msg.content for msg in final_state["messages"]]
        }
    except Exception as e:
        return {
            "status": "SYSTEM_FAILURE",
            "confidence_score": 0.0,
            "final_answer": "CRITICAL ORCHESTRATION FAILURE",
            "context_history": [str(e)]
        }

# ---------------------------------------------------------
# 7. Self-Learning Feedback Loop
# ---------------------------------------------------------
def process_human_feedback(user_query: str, final_answer: str, user_id: str = "human_engineer"):
    """
    Captures a human-verified resolution and pushes it back into Anshika's ingestion pipeline.
    """
    feedback_dir = "ingestion_pipeline/sample data/feedback_loop"
    os.makedirs(feedback_dir, exist_ok=True)
    
    ticket_id = f"VERIFIED-{int(time.time())}"
    ticket_data = {
        "ticket_id": ticket_id,
        "issue_description": user_query,
        "verified_resolution": final_answer,
        "status": "closed",
        "verified_by": user_id,
        "source": "copilot_feedback_loop"
    }
    
    file_path = os.path.join(feedback_dir, f"{ticket_id}.json")
    with open(file_path, "w") as f:
        json.dump(ticket_data, f, indent=4)
        
    try:
        chunks = ingest_directory(input_dir=feedback_dir, output_path="ingestion_pipeline/output/feedback_chunks.jsonl")
        
        client = chromadb.Client()
        collection = client.get_or_create_collection("enterprise_kb")
        collection.upsert(
            ids=[c["chunk_id"] for c in chunks],
            documents=[c["text"] for c in chunks],
            metadatas=[c["metadata"] for c in chunks],
        )
        
        return {"status": "SUCCESS", "message": f"Successfully learned from ticket {ticket_id}."}
        
    except Exception as e:
        return {"status": "ERROR", "message": f"Failed to ingest feedback: {str(e)}"}