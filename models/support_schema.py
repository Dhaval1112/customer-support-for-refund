from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any, Literal

# --- Structured Output Models for LLM ---

class ClassifyOutput(BaseModel):
    intent: Literal["order_status", "refund", "general_inquiry"] = Field(
        ...,
        description="The classified customer intent: 'order_status' to check tracking/location, 'refund' to request a return or money back, or 'general_inquiry' for other questions."
    )
    orderId: Optional[str] = Field(
        None,
        description="The order ID mentioned in the message (e.g. 'ORD-1001', 'ORD-1002'), or None if no order ID was provided."
    )
    confidence: Optional[float] = Field(
        default=1.0,
        description="Confidence score for this classification."
    )

class GuardianEvaluation(BaseModel):
    approved: bool = Field(
        ...,
        description="True if the response passes JEV guardian standards (factually accurate, grounded in tool results, polite, and safe); False otherwise."
    )
    isCorrect: bool = Field(
        ...,
        description="True if all claims match the actual database / tool outputs without distortion."
    )
    isGrounded: bool = Field(
        ...,
        description="True if the response is strictly grounded in the provided business data without hallucinations."
    )
    reason: str = Field(
        ...,
        description="Brief explanation of why the response was approved or why it failed JEV evaluation."
    )

# --- FastAPI REST API Schemas ---

class SupportRequest(BaseModel):
    message: str = Field(..., description="Customer message, e.g. 'Where is my order ORD-1003?' or 'I want a refund for ORD-1001'")
    threadId: Optional[str] = Field(None, description="Optional thread/session ID. If omitted, a new UUID is generated.")

class ApprovalRequest(BaseModel):
    approved: bool = Field(..., description="Set to true to authorize the sensitive action (e.g., refund), or false to reject it.")

class SupportResponse(BaseModel):
    threadId: str
    status: str = Field(..., description="'completed' | 'waiting_for_approval' | 'rejected'")
    response: Optional[str] = Field(None, description="Final assistant message sent to the customer")
    message: Optional[str] = Field(None, description="System status message (e.g. 'Human approval is required.')")
    intent: Optional[str] = None
    orderId: Optional[str] = None
    requiresApproval: Optional[bool] = None
    approvalStatus: Optional[str] = None
    guardianResult: Optional[Dict[str, Any]] = None
    actionResult: Optional[Dict[str, Any]] = None
