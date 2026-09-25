from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver
from agents.support.state import SupportState
from agents.support.nodes import (
    classify_request,
    call_tools,
    evaluate_action,
    human_approval,
    execute_action,
    generate_response
)
from agents.support.routing import (
    route_after_classification,
    route_after_evaluation,
    route_after_approval
)

def create_support_graph():
    """
    Builds the Customer Support Action Agent workflow:
    - Input Guardrail: Evaluates prompt safety first; rejects malicious inputs before calling tools.
    - Tools run before approval decision to fetch real order/refund data.
    - Sensitive operations trigger LangGraph HITL interrupt for supervisor authorization.
    - Generates grounded response and returns directly to END.
    """
    builder = StateGraph(SupportState)
    
    # 1. Add nodes
    builder.add_node("classify_request", classify_request)
    builder.add_node("call_tools", call_tools)
    builder.add_node("evaluate_action", evaluate_action)
    builder.add_node("human_approval", human_approval)
    builder.add_node("execute_action", execute_action)
    builder.add_node("generate_response", generate_response)
    
    # 2. Linear starting edge
    builder.add_edge(START, "classify_request")
    
    # 3. Conditional Edge 1: Input Guardrail -> Call Tools OR Early Safe End
    builder.add_conditional_edges(
        "classify_request",
        route_after_classification,
        {
            "call_tools": "call_tools",
            "end": END
        }
    )
    
    builder.add_edge("call_tools", "evaluate_action")
    
    # 4. Conditional Edge 2: Evaluation -> Human Approval OR Direct Response
    builder.add_conditional_edges(
        "evaluate_action",
        route_after_evaluation,
        {
            "human_approval": "human_approval",
            "generate_response": "generate_response"
        }
    )
    
    # 5. Conditional Edge 3: Human Decision -> Execute Action OR Direct Response
    builder.add_conditional_edges(
        "human_approval",
        route_after_approval,
        {
            "execute_action": "execute_action",
            "generate_response": "generate_response"
        }
    )
    
    # 6. Execute Action -> Generate Response
    builder.add_edge("execute_action", "generate_response")
    
    # 7. Generate Response -> END
    builder.add_edge("generate_response", END)
    
    # Checkpointer for Human-in-the-Loop state persistence
    checkpointer = MemorySaver()
    
    return builder.compile(checkpointer=checkpointer)

# Shared singleton instance of the compiled graph
support_graph = create_support_graph()
