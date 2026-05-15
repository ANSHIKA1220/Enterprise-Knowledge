import os
import json
from langchain_core.prompts import PromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.output_parsers import JsonOutputParser
from pydantic import BaseModel, Field
from dotenv import load_dotenv

load_dotenv()

class ConfidenceEvaluation(BaseModel):
    score: float = Field(description="Confidence score between 0.0 and 1.0 representing how well the agent's draft is supported by the retrieved context.")
    reasoning: str = Field(description="Reasoning for the given score.")
    missing_information: str = Field(description="Any information that was asked but missing from the context or the draft.")

def evaluate_and_route_response(agent_draft: str, context: str, llm=None):
    """
    Evaluates the agent's draft answer against the retrieved context to calculate a confidence score.
    Routes the response based on the score (>= 0.90 for final answer, < 0.90 for hand-off summary).
    """
    if llm is None:
        llm = ChatGoogleGenerativeAI(model="gemini-1.5-pro", temperature=0, max_retries=3)

    prompt = PromptTemplate(
        template="""You are an expert trust-gating evaluation system. Your task is to evaluate an agent's drafted answer against the retrieved context.
        Calculate a confidence score between 0.0 and 1.0 based on how fully and accurately the draft is supported by the context.
        If the draft includes hallucinations or unsupported claims, the score should be low.
        
        Retrieved Context:
        {context}
        
        Agent's Draft Answer:
        {agent_draft}
        
        Evaluate the draft.
        {format_instructions}
        """,
        input_variables=["context", "agent_draft"],
        partial_variables={"format_instructions": JsonOutputParser(pydantic_object=ConfidenceEvaluation).get_format_instructions()}
    )

    chain = prompt | llm | JsonOutputParser(pydantic_object=ConfidenceEvaluation)
    
    try:
        evaluation = chain.invoke({"context": context, "agent_draft": agent_draft})
        score = evaluation.get("score", 0.0)
    except Exception as e:
        evaluation = {"score": 0.0, "reasoning": str(e), "missing_information": "Failed to parse LLM evaluation."}
        score = 0.0

    if score >= 0.90:
        return {
            "status": "success",
            "confidence_score": score,
            "final_answer": agent_draft,
            "evaluation_details": evaluation,
            "action": "respond_to_user"
        }
    else:
        hand_off_summary = (
            f"Hand-off Required.\n"
            f"Agent attempted to answer the query but confidence was low ({score * 100}%).\n"
            f"Draft Answer: {agent_draft}\n"
            f"Reasoning for low confidence: {evaluation.get('reasoning', 'N/A')}\n"
            f"Missing Information: {evaluation.get('missing_information', 'N/A')}\n"
            f"Context used: {context}"
        )
        return {
            "status": "escalated",
            "confidence_score": score,
            "hand_off_summary": hand_off_summary,
            "evaluation_details": evaluation,
            "action": "escalate_to_human"
        }
