from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.support.state import SupportState
from agents.support.nodes import (
    classify_request,
    call_tools,
    evaluate_action,
    human_approval,
    execute_action,
    generate_response,
    guardian_node
)
from agents.support.routing import (
    route_after_evaluation,
    route_after_approval,
    route_after_guardian
)

def create_support_graph():
    """
    Builds the Customer Support Action Agent workflow:
    - Tools run before approval decision
    - Sensitive operations trigger LangGraph HITL interrupt
    - JEV Guardian acts as final quality/correctness evaluator
    """
    builder = StateGraph(SupportState)
    
    # 1. Add all nodes
    builder.add_node("classify_request", classify_request)
    builder.add_node("call_tools", call_tools)
    builder.add_node("evaluate_action", evaluate_action)
    builder.add_node("human_approval", human_approval)
    builder.add_node("execute_action", execute_action)
    builder.add_node("generate_response", generate_response)
    builder.add_node("guardian_node", guardian_node)
    
    # 2. Add linear edges
    builder.add_edge(START, "classify_request")
    builder.add_edge("classify_request", "call_tools")
    builder.add_edge("call_tools", "evaluate_action")
    
    # 3. Conditional Branch 1: Evaluation -> Human Approval OR Direct Response
    builder.add_conditional_edges(
        "evaluate_action",
        route_after_evaluation,
        {
            "human_approval": "human_approval",
            "generate_response": "generate_response"
        }
    )
    
    # 4. Conditional Branch 2: Human Decision -> Execute Action OR Direct Response
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute_action": "execute_action",
            "generate_response": "generate_response"
        }
    )
    
    # 5. Execute Action -> Generate Response
    builder.add_edge("execute_action", "generate_response")
    
    # 6. Generate Response -> JEV Guardian
    builder.add_edge("generate_response", "guardian_node")
    
    # 7. Conditional Branch 3: JEV Guardian -> END OR Regenerate Response
    builder.add_conditional_edges(
        "guardian_node",
        route_after_guardian,
        {
            "end": END,
            "generate_response": "generate_response"
        }
    )
    
    # Checkpointer for Human-in-the-Loop state persistence
    checkpointer = MemorySaver()
    
    return builder.compile(checkpointer=checkpointer)

# Shared singleton instance of the compiled graph
support_graph = create_support_graph()
