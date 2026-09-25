import logging
from agents.support.state import SupportState

logger = logging.getLogger("support_routing")

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

def route_after_guardian(state: SupportState) -> str:
    """
    JEV Guardian evaluation routing:
    - PASS: Complete workflow and return response.
    - FAIL (attempts < 2): Loop back to regenerate response with guardian feedback.
    - FAIL (max attempts reached): End workflow with best available response.
    """
    guardian_result = state.get("guardianResult") or {}
    attempts = state.get("guardianAttempts", 0)
    
    if guardian_result.get("approved", False):
        logger.info("[ROUTING] JEV Guardian PASSED -> Ending workflow.")
        return "end"
        
    if attempts < 2:
        logger.warning(f"[ROUTING] JEV Guardian FAILED (attempt {attempts}/2) -> Routing to 'generate_response' for regeneration.")
        return "generate_response"
    else:
        logger.warning(f"[ROUTING] JEV Guardian FAILED after max attempts ({attempts}) -> Ending workflow to prevent infinite loop.")
        return "end"
