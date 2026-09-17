from typing import TypedDict, Annotated
import json
from pydantic import BaseModel, Field
from langgraph.graph import StateGraph, END
from app.core.gemini_client import gemini_service
from app.services.docker_sandbox import docker_sandbox

# 1. Define State
class AgentState(TypedDict):
    task: str
    code: str
    execution_output: str
    error: str
    retry_count: int
    is_valid: bool

# 2. Guardrail Pydantic Schema
class CodeGenerationOutput(BaseModel):
    code: str = Field(description="Executable Python code without markdown blocks")
    explanation: str = Field(description="Brief explanation of the solution")

# 3. Node Functions
async def coder_node(state: AgentState) -> dict:
    """Generates or repairs Python code based on task or previous errors."""
    prompt = f"""
    You are an expert Python Coder.
    Task: {state['task']}
    
    Current Code: {state.get('code', 'None')}
    Previous Error: {state.get('error', 'None')}
    
    Write complete, runnable Python code to accomplish the task.
    Print the final answer to stdout using print().
    Do NOT include markdown formatting or extra text outside valid Python code.
    """
    
    response_text = ""
    async for chunk in gemini_service.stream_response(prompt):
        response_text += chunk
        
    cleaned_code = response_text.replace("```python", "").replace("```", "").strip()
    return {"code": cleaned_code}


async def sandbox_node(state: AgentState) -> dict:
    """Executes code in Docker Sandbox."""
    result = docker_sandbox.run_python_code(state['code'])
    
    if result["success"]:
        return {
            "execution_output": result["output"],
            "error": "",
            "is_valid": True
        }
    else:
        return {
            "execution_output": result["output"],
            "error": result["error"],
            "is_valid": False,
            "retry_count": state["retry_count"] + 1
        }


def route_after_execution(state: AgentState) -> str:
    """Supervisor routing logic for self-correction loop."""
    if state["is_valid"]:
        return "end"
    if state["retry_count"] >= 3:
        return "end"  # Max retries reached
    return "coder"    # Retry code generation with error feedback


# 4. Build State Machine Graph
builder = StateGraph(AgentState)

builder.add_node("coder", coder_node)
builder.add_node("sandbox", sandbox_node)

builder.set_entry_point("coder")
builder.add_edge("coder", "sandbox")

builder.add_conditional_edges(
    "sandbox",
    route_after_execution,
    {
        "end": END,
        "coder": "coder"
    }
)

supervisor_agent = builder.compile()