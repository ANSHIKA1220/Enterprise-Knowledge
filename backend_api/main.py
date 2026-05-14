from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sys
import os

# Add parent directory to path to allow imports from other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from confidence_engine.evaluator import evaluate_and_route_response

app = FastAPI(title="Enterprise Knowledge API")

class ChatRequest(BaseModel):
    query: str

class ChatResponse(BaseModel):
    status: str
    confidence_score: float
    final_answer: str = None
    hand_off_summary: str = None
    evaluation_details: dict = None
    action: str

# Mock for Arpan's workflow
def run_agentic_workflow_mock(user_query: str):
    """
    Mocking Arpan's workflow. In the real integration, this should import run_agentic_workflow
    from the multi-agent orchestration module.
    """
    return {
        "agent_draft": f"This is a generated answer for: {user_query}. It is a basic mocked response.",
        "context": f"Retrieved context regarding {user_query} from vector and graph DBs. This is mocked context."
    }

try:
    # Try importing real orchestration if it exists
    from orchestration.agent import run_agentic_workflow
except ImportError:
    run_agentic_workflow = run_agentic_workflow_mock

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    try:
        # Step 1: Call Arpan's workflow
        workflow_result = run_agentic_workflow(request.query)
        agent_draft = workflow_result.get("agent_draft", "")
        context = workflow_result.get("context", "")

        # Step 2: Pass result to Mohit's confidence engine
        routing_decision = evaluate_and_route_response(agent_draft, context)

        # Step 3: Return final JSON
        return ChatResponse(
            status=routing_decision.get("status"),
            confidence_score=routing_decision.get("confidence_score"),
            final_answer=routing_decision.get("final_answer"),
            hand_off_summary=routing_decision.get("hand_off_summary"),
            evaluation_details=routing_decision.get("evaluation_details"),
            action=routing_decision.get("action")
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
def health_check():
    return {"status": "ok"}
