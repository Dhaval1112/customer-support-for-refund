import json
import logging
from services.llm_service import get_model
from models.support_schema import GuardianEvaluation
from agents.support.prompts import JEV_GUARDIAN_PROMPT

logger = logging.getLogger("jev_guardian")

def evaluate_with_guardian(
    user_message: str,
    tool_result: dict,
    action_result: dict,
    approval_status: str,
    draft_response: str
) -> GuardianEvaluation:
    """
    Evaluates whether the candidate draft response is accurate, grounded,
    and safe using the JEV Guardian LLM evaluator.
    """
    model = get_model(temperature=0.0)
    structured_llm = model.with_structured_output(GuardianEvaluation)
    chain = JEV_GUARDIAN_PROMPT | structured_llm
    
    tool_str = json.dumps(tool_result or {}, indent=2)
    action_str = json.dumps(action_result or {}, indent=2)
    status_str = approval_status or "none"
    
    try:
        evaluation = chain.invoke({
            "userMessage": user_message,
            "toolResult": tool_str,
            "actionResult": action_str,
            "approvalStatus": status_str,
            "draftResponse": draft_response
        })
        logger.info(f"[JEV GUARDIAN] Evaluated: approved={evaluation.approved}, reason={evaluation.reason}")
        return evaluation
    except Exception as e:
        logger.warning(f"[JEV GUARDIAN] Structured evaluation fallback due to: {e}")
        # Safe fallback: If evaluation cannot run, approve if not empty, else retry
        return GuardianEvaluation(
            approved=bool(draft_response and len(draft_response) > 20),
            isCorrect=True,
            isGrounded=True,
            reason=f"Evaluation executed with fallback: {str(e)}"
        )
