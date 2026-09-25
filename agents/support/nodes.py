import json
import logging
import re
from langgraph.types import interrupt
from services.llm_service import get_model
from models.support_schema import ClassifyOutput
from agents.support.state import SupportState
from agents.support.tools import (
    get_order_tool,
    get_order_status_tool,
    check_refund_eligibility_tool,
    execute_refund_tool
)
from agents.support.prompts import CLASSIFY_PROMPT, RESPONSE_PROMPT

logger = logging.getLogger("support_nodes")

# Common prompt injection and malicious heuristic patterns for defense-in-depth
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|above|prior)\s+instructions",
    r"system\s+prompt",
    r"drop\s+table",
    r"reveal\s+.*(secret|key|api|password|token)",
    r"act\s+as\s+dan",
    r"jailbreak",
    r"<script.*?>",
    r"delete\s+from\s+",
]

def check_heuristic_guardrails(text: str) -> tuple[bool, str | None]:
    """Fast regex-based heuristic guardrail check."""
    for pattern in PROMPT_INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            return False, f"Prompt injection pattern detected: '{pattern}'"
    return True, None

def classify_request(state: SupportState) -> dict:
    """
    Node 1: Input Guardrail & Intent Classification.
    Screen the incoming customer message for prompt injections and malicious content.
    If unsafe, sets isSafe=False and finalResponse so workflow safely halts early.
    If safe, extracts customer intent and order ID.
    """
    user_msg = state.get("userMessage", "")
    logger.info(f"[NODE: classify_request] Incoming message: '{user_msg}'")
    
    # 1. Fast heuristic guardrail check
    is_heuristic_safe, heuristic_reason = check_heuristic_guardrails(user_msg)
    if not is_heuristic_safe:
        logger.warning(f"[NODE: classify_request] Input guardrail triggered by heuristic: {heuristic_reason}")
        return {
            "isSafe": False,
            "guardrailResult": {
                "safe": False,
                "reason": heuristic_reason
            },
            "status": "rejected",
            "finalResponse": "I am sorry, but I cannot process this request as it violates our customer support policy. If you have an inquiry regarding an order, shipment, or refund, please let me know!",
            "intent": "general_inquiry",
            "orderId": None
        }

    # Extract order ID with regex (ORD-XXXX)
    order_id_match = re.search(r"\b(ORD-\d+)\b", user_msg, re.IGNORECASE)
    regex_order_id = order_id_match.group(1).upper() if order_id_match else None
    
    # 2. LLM-based Input Guardrail & Classification
    model = get_model(temperature=0.0)
    structured_llm = model.with_structured_output(ClassifyOutput)
    chain = CLASSIFY_PROMPT | structured_llm
    
    try:
        res: ClassifyOutput = chain.invoke({"userMessage": user_msg})
        
        if not res.isSafe:
            reason = res.safetyReason or "Input rejected by safety guardrail."
            logger.warning(f"[NODE: classify_request] Input guardrail triggered by LLM: {reason}")
            return {
                "isSafe": False,
                "guardrailResult": {
                    "safe": False,
                    "reason": reason
                },
                "status": "rejected",
                "finalResponse": "I am sorry, but I cannot process this request as it does not comply with our customer support policy. If you have an inquiry regarding an order, shipment, or refund, please let me know!",
                "intent": "general_inquiry",
                "orderId": None
            }
            
        intent = res.intent
        order_id = regex_order_id or res.orderId
        
    except Exception as e:
        logger.warning(f"[NODE: classify_request] Structured output fallback: {e}")
        # Rule-based fallback for intent
        msg_lower = user_msg.lower()
        if "refund" in msg_lower or "return" in msg_lower or "money back" in msg_lower:
            intent = "refund"
        elif "where" in msg_lower or "status" in msg_lower or "track" in msg_lower or "order" in msg_lower:
            intent = "order_status"
        else:
            intent = "general_inquiry"
        order_id = regex_order_id
        
    logger.info(f"[NODE: classify_request] Passed guardrail: intent='{intent}', orderId='{order_id}'")
    return {
        "isSafe": True,
        "guardrailResult": {
            "safe": True,
            "reason": "Passed input safety checks."
        },
        "intent": intent,
        "orderId": order_id,
        "status": "in_progress"
    }

def call_tools(state: SupportState) -> dict:
    """
    Node 2: Tools BEFORE Approval Decision.
    Calls business APIs to fetch real order data and evaluate refund eligibility.
    """
    intent = state.get("intent")
    order_id = state.get("orderId")
    logger.info(f"[NODE: call_tools] Fetching business data for intent='{intent}', orderId='{order_id}'...")
    
    tool_result = {}
    
    if not order_id:
        tool_result = {"error": "No order ID specified in user message."}
        return {"toolResult": tool_result}
        
    if intent == "order_status":
        status_data = get_order_status_tool(order_id)
        tool_result = {
            "actionType": "order_status_lookup",
            "data": status_data
        }
        
    elif intent == "refund":
        order_data = get_order_tool(order_id)
        if not order_data:
            tool_result = {
                "actionType": "refund_check",
                "orderFound": False,
                "eligibility": {
                    "eligible": False,
                    "requiresApproval": False,
                    "reason": f"Order {order_id} was not found in our records."
                }
            }
        else:
            eligibility_data = check_refund_eligibility_tool(order_data)
            tool_result = {
                "actionType": "refund_check",
                "orderFound": True,
                "order": order_data,
                "eligibility": eligibility_data
            }
            
    else:
        # General inquiry
        tool_result = {
            "actionType": "general_info",
            "details": "General store policies: 30-day return policy on delivered items. Express shipping 2-3 days."
        }
        
    logger.info(f"[NODE: call_tools] Retrieved business data: {tool_result}")
    return {"toolResult": tool_result}

def evaluate_action(state: SupportState) -> dict:
    """
    Node 3: Evaluates actual tool data against business authorization policy.
    Determines whether the requested operation requires human supervisor approval.
    """
    intent = state.get("intent")
    tool_result = state.get("toolResult") or {}
    logger.info(f"[NODE: evaluate_action] Evaluating authorization for intent='{intent}'...")
    
    if intent == "refund":
        eligibility = tool_result.get("eligibility", {})
        requires_approval = eligibility.get("requiresApproval", False)
        
        if requires_approval:
            logger.info("[NODE: evaluate_action] Refund is eligible -> ROUTING TO HUMAN APPROVAL.")
            return {
                "requiresApproval": True,
                "approvalStatus": "pending",
                "status": "waiting_for_approval"
            }
        else:
            logger.info(f"[NODE: evaluate_action] Refund ineligible ({eligibility.get('reason')}) -> No human approval needed.")
            return {
                "requiresApproval": False,
                "approvalStatus": "not_required",
                "status": "in_progress"
            }
            
    # Safe informational actions (order status, general questions)
    logger.info("[NODE: evaluate_action] Safe informational request -> No human approval needed.")
    return {
        "requiresApproval": False,
        "approvalStatus": "not_required",
        "status": "in_progress"
    }

def human_approval(state: SupportState) -> dict:
    """
    Node 4: Human-in-the-Loop (HITL) Interrupt Node.
    Pauses graph execution using LangGraph's interrupt() function.
    Resumes when human supervisor submits approval or rejection.
    """
    order_id = state.get("orderId")
    eligibility = state.get("toolResult", {}).get("eligibility", {})
    
    logger.info(f"[NODE: human_approval] Triggering LangGraph interrupt for order {order_id}...")
    
    human_decision = interrupt({
        "orderId": order_id,
        "action": "refund",
        "amount": eligibility.get("amount"),
        "currency": eligibility.get("currency", "INR"),
        "reason": eligibility.get("reason"),
        "message": f"Refund of {eligibility.get('currency', 'INR')} {eligibility.get('amount')} for {order_id} requires supervisor authorization."
    })
    
    is_approved = False
    if isinstance(human_decision, dict):
        is_approved = human_decision.get("approved", False)
    elif isinstance(human_decision, bool):
        is_approved = human_decision
        
    decision_str = "approved" if is_approved else "rejected"
    logger.info(f"[NODE: human_approval] Resumed from interrupt with decision: '{decision_str}'")
    
    return {
        "approvalStatus": decision_str,
        "status": "in_progress"
    }

def execute_action(state: SupportState) -> dict:
    """
    Node 5: Sensitive Action Execution Node.
    Executes financial refund only AFTER human authorization is confirmed.
    """
    order_id = state.get("orderId")
    logger.info(f"[NODE: execute_action] Executing approved refund for {order_id}...")
    
    refund_result = execute_refund_tool(order_id)
    logger.info(f"[NODE: execute_action] Refund executed: {refund_result}")
    
    return {"actionResult": refund_result}

def generate_response(state: SupportState) -> dict:
    """
    Node 6: Synthesizes a grounded, customer-friendly response.
    Incorporates user message, tool outputs, human approval decisions, and action results.
    """
    user_msg = state.get("userMessage", "")
    intent = state.get("intent", "")
    order_id = state.get("orderId", "")
    tool_result = json.dumps(state.get("toolResult") or {}, indent=2)
    approval_status = state.get("approvalStatus") or "not_required"
    action_result = json.dumps(state.get("actionResult") or {}, indent=2)
    
    logger.info(f"[NODE: generate_response] Drafting response for intent='{intent}', approvalStatus='{approval_status}'...")
    
    model = get_model(temperature=0.3)
    chain = RESPONSE_PROMPT | model
    
    response = chain.invoke({
        "userMessage": user_msg,
        "intent": intent,
        "orderId": order_id or "Not provided",
        "toolResult": tool_result,
        "approvalStatus": approval_status,
        "actionResult": action_result
    })
    
    final_status = "completed" if approval_status != "rejected" else "rejected"
    logger.info(f"[NODE: generate_response] Response generated ({len(response.content)} chars). Status: {final_status}")
    
    return {
        "draftResponse": response.content,
        "finalResponse": response.content,
        "status": final_status
    }
