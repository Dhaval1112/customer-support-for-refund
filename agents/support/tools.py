from typing import Dict, Any, Optional
from services.order_service import (
    get_order,
    get_order_status,
    check_refund_eligibility,
    execute_refund
)

def get_order_tool(order_id: str) -> Optional[Dict[str, Any]]:
    """Fetches full order details including delivery date, amount, items, and refund status."""
    return get_order(order_id)

def get_order_status_tool(order_id: str) -> Dict[str, Any]:
    """Retrieves live shipping status, carrier tracking, or delivery date for an order."""
    return get_order_status(order_id)

def check_refund_eligibility_tool(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Evaluates business rules for refund eligibility:
    - Must be delivered within 30 days
    - Must not already be refunded
    - Returns whether human approval is required
    """
    return check_refund_eligibility(order)

def execute_refund_tool(order_id: str) -> Dict[str, Any]:
    """Executes the financial refund action after human approval is granted."""
    return execute_refund(order_id)
