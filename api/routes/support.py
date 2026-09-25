import uuid
import logging
from fastapi import APIRouter, HTTPException
from langgraph.types import Command
from models.support_schema import SupportRequest, ApprovalRequest, SupportResponse
from agents.support.graph import support_graph

logger = logging.getLogger("api_support")
router = APIRouter(prefix="/support", tags=["Customer Support Agent"])

@router.post("", response_model=SupportResponse, summary="1. Submit Customer Support Message")
async def handle_support_message(request: SupportRequest):
    """
    Submits a customer support message into the LangGraph workflow:
    - Runs tools before approval decision
    - If the request requires human authorization, pauses execution and returns status 'waiting_for_approval'.
    - If safe or informational, completes automatically and returns the final response.
    """
    thread_id = request.threadId or f"thread-{uuid.uuid4().hex[:8]}"
    config = {"configurable": {"thread_id": thread_id}}
    
    logger.info(f"==> [POST /api/support] threadId='{thread_id}', message='{request.message}'")
    
    try:
        # Run graph from START
        support_graph.invoke(
            {"userMessage": request.message, "threadId": thread_id},
            config=config
        )
        
        # Check current state in checkpointer
        current_state = support_graph.get_state(config)
        values = current_state.values or {}
        
        # If there are pending tasks with interrupts, graph is paused waiting for human approval!
        if current_state.next:
            logger.info(f"==> [POST /api/support] Thread '{thread_id}' paused at interrupt (Next nodes: {current_state.next})")
            
            # Extract interrupt details if present
            interrupt_info = None
            if current_state.tasks and current_state.tasks[0].interrupts:
                interrupt_info = current_state.tasks[0].interrupts[0].value
                
            msg = (interrupt_info.get("message") if isinstance(interrupt_info, dict) else None) or "Human supervisor authorization is required."
            
            return SupportResponse(
                threadId=thread_id,
                status="waiting_for_approval",
                message=msg,
                intent=values.get("intent"),
                orderId=values.get("orderId"),
                requiresApproval=True,
                approvalStatus="pending"
            )
            
        # Graph finished without pausing (No approval needed)
        logger.info(f"==> [POST /api/support] Thread '{thread_id}' completed automatically.")
        return SupportResponse(
            threadId=thread_id,
            status="completed",
            response=values.get("finalResponse") or values.get("draftResponse"),
            intent=values.get("intent"),
            orderId=values.get("orderId"),
            requiresApproval=False,
            approvalStatus=values.get("approvalStatus", "not_required"),
            guardianResult=values.get("guardianResult"),
            actionResult=values.get("actionResult")
        )
        
    except Exception as e:
        logger.exception(f"==> [POST /api/support ERROR] Failed to process message: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process support request: {str(e)}")

@router.get("/{thread_id}", response_model=SupportResponse, summary="2. Get Support Request Status")
async def get_support_status(thread_id: str):
    """
    Retrieves the current execution state of a support thread.
    """
    config = {"configurable": {"thread_id": thread_id}}
    state = support_graph.get_state(config)
    
    if not state or not state.values:
        raise HTTPException(status_code=404, detail=f"Support thread '{thread_id}' not found.")
        
    values = state.values
    is_paused = bool(state.next)
    status = "waiting_for_approval" if is_paused else (values.get("status") or "completed")
    
    return SupportResponse(
        threadId=thread_id,
        status=status,
        response=values.get("finalResponse") or values.get("draftResponse"),
        message="Waiting for supervisor approval." if is_paused else "Request completed.",
        intent=values.get("intent"),
        orderId=values.get("orderId"),
        requiresApproval=values.get("requiresApproval"),
        approvalStatus=values.get("approvalStatus"),
        guardianResult=values.get("guardianResult"),
        actionResult=values.get("actionResult")
    )

@router.post("/{thread_id}/approval", response_model=SupportResponse, summary="3. Submit Human Approval Decision")
async def submit_human_approval(thread_id: str, request: ApprovalRequest):
    """
    Resumes a paused support thread by submitting a human approval decision:
    - approved: true -> Executes the sensitive action (executeRefund) -> Generates response -> JEV Guardian -> Returns response.
    - approved: false -> Skips action -> Generates courteous rejection response -> JEV Guardian -> Returns response.
    """
    config = {"configurable": {"thread_id": thread_id}}
    current_state = support_graph.get_state(config)
    
    if not current_state or not current_state.values:
        raise HTTPException(status_code=404, detail=f"Support thread '{thread_id}' not found.")
        
    if not current_state.next:
        raise HTTPException(
            status_code=400,
            detail=f"Thread '{thread_id}' is not currently waiting for approval. Current status: {current_state.values.get('status')}"
        )
        
    logger.info(f"==> [POST /api/support/{thread_id}/approval] Resuming with approved={request.approved}...")
    
    try:
        # Resume the interrupt with the human decision
        res = support_graph.invoke(
            Command(resume={"approved": request.approved}),
            config=config
        )
        
        final_state = support_graph.get_state(config)
        values = final_state.values or res
        
        status_str = "completed" if request.approved else "rejected"
        logger.info(f"==> [POST /api/support/{thread_id}/approval SUCCESS] Thread finished with status='{status_str}'")
        
        return SupportResponse(
            threadId=thread_id,
            status=status_str,
            response=values.get("finalResponse") or values.get("draftResponse"),
            message="Action approved and executed." if request.approved else "Action rejected by supervisor.",
            intent=values.get("intent"),
            orderId=values.get("orderId"),
            requiresApproval=True,
            approvalStatus="approved" if request.approved else "rejected",
            guardianResult=values.get("guardianResult"),
            actionResult=values.get("actionResult")
        )
        
    except Exception as e:
        logger.exception(f"==> [POST /api/support/{thread_id}/approval ERROR] Resume failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to resume support thread: {str(e)}")
