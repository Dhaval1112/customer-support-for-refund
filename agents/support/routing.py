import logging
from agents.support.state import SupportState

logger = logging.getLogger("support_routing")

def route_after_classification(state: SupportState) -> str:
    """
    Decides whether the input is safe to proceed to tool execution or if it should
    safely short-circuit to END due to input guardrail violation (prompt injection, abuse).
    """
    is_safe = state.get("isSafe", True)
    if not is_safe:
        logger.warning("[ROUTING] Input guardrail triggered -> Safely halting workflow, routing to 'end'.")
        return "end"
    
    logger.info("[ROUTING] Input passed guardrail -> Routing to 'call_tools'.")
    return "call_tools"

def route_after_evaluation(state: SupportState) -> str:
    """
    Decides whether to route to Human Approval or directly to Response Generation.
    """
    requires_approval = state.get("requiresApproval", False)
    if requires_approval:
        logger.info("[ROUTING] Action requires approval -> Routing to 'human_approval'.")
        return "human_approval"
    else:
        logger.info("[ROUTING] Safe action -> Routing directly to 'generate_response'.")
        return "generate_response"

def route_after_approval(state: SupportState) -> str:
    """
    After Human-in-the-Loop decision:
    - If approved: execute the sensitive action.
    - If rejected: skip execution and proceed to draft a courteous rejection reply.
    """
    approval_status = state.get("approvalStatus")
    if approval_status == "approved":
        logger.info("[ROUTING] Human approved action -> Routing to 'execute_action'.")
        return "execute_action"
    else:
        logger.info(f"[ROUTING] Human rejected action ('{approval_status}') -> Routing to 'generate_response'.")
        return "generate_response"
