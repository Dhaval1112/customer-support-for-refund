import json
import os
import time
import uuid
from typing import Optional, Dict, Any

ORDERS_FILE = os.path.join(os.path.dirname(__file__), "..", "data", "orders.json")

def load_orders() -> Dict[str, Any]:
    if not os.path.exists(ORDERS_FILE):
        return {}
    with open(ORDERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_orders(orders: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(ORDERS_FILE), exist_ok=True)
    with open(ORDERS_FILE, "w", encoding="utf-8") as f:
        json.dump(orders, f, indent=2)

def get_order(order_id: str) -> Optional[Dict[str, Any]]:
    orders = load_orders()
    # Normalize ID lookup (e.g. ord-1001 -> ORD-1001)
    normalized_id = order_id.strip().upper()
    return orders.get(normalized_id)

def get_order_status(order_id: str) -> Dict[str, Any]:
    order = get_order(order_id)
    if not order:
        return {
            "found": False,
            "orderId": order_id,
            "message": f"Order {order_id} could not be found in our database."
        }
    
    res = {
        "found": True,
        "orderId": order["orderId"],
        "customerName": order.get("customerName"),
        "status": order["status"],
        "items": order.get("items", []),
        "amount": order.get("amount"),
        "currency": order.get("currency", "INR")
    }
    
    if order["status"] == "delivered":
        res["deliveredDaysAgo"] = order.get("deliveredDaysAgo")
        res["message"] = f"Order {order['orderId']} was successfully delivered {order.get('deliveredDaysAgo', 'recently')} days ago."
    elif order["status"] == "shipped":
        res["carrier"] = order.get("carrier")
        res["trackingNumber"] = order.get("trackingNumber")
        res["estimatedDelivery"] = order.get("estimatedDelivery")
        res["message"] = f"Order {order['orderId']} is currently shipped via {order.get('carrier')}. Estimated delivery: {order.get('estimatedDelivery')}."
    else:
        res["message"] = f"Order {order['orderId']} is in '{order['status']}' state."
        
    return res

def check_refund_eligibility(order: Dict[str, Any]) -> Dict[str, Any]:
    """
    Business Rules for Refund:
    1. Order must exist and be in 'delivered' status.
    2. Order must have been delivered within 30 days.
    3. Order must not have already been refunded.
    4. If eligible, refund is a sensitive financial action requiring human authorization!
    """
    if not order:
        return {
            "eligible": False,
            "requiresApproval": False,
            "reason": "Order record not found."
        }
        
    if order.get("refundStatus") == "refunded":
        return {
            "eligible": False,
            "requiresApproval": False,
            "reason": "Order has already been refunded."
        }
        
    if order.get("status") != "delivered":
        return {
            "eligible": False,
            "requiresApproval": False,
            "reason": f"Only delivered items can be refunded. Current status is '{order.get('status')}'."
        }
        
    delivered_days = order.get("deliveredDaysAgo", 999)
    if delivered_days is None or delivered_days > 30:
        return {
            "eligible": False,
            "requiresApproval": False,
            "deliveredDaysAgo": delivered_days,
            "reason": f"Refund window expired. Our return policy permits refunds within 30 days of delivery, but this item was delivered {delivered_days} days ago."
        }
        
    # Order is eligible and requires human approval!
    return {
        "eligible": True,
        "requiresApproval": True,
        "orderId": order["orderId"],
        "amount": order.get("amount"),
        "currency": order.get("currency", "INR"),
        "deliveredDaysAgo": delivered_days,
        "items": order.get("items", []),
        "paymentMethod": order.get("paymentMethod"),
        "reason": f"Order is within the 30-day return policy (delivered {delivered_days} days ago). Financial refund requires human supervisor authorization."
    }

def execute_refund(order_id: str) -> Dict[str, Any]:
    """
    Executes the refund after human approval has been granted.
    Updates the mock database.
    """
    orders = load_orders()
    normalized_id = order_id.strip().upper()
    order = orders.get(normalized_id)
    if not order:
        return {"success": False, "message": f"Order {order_id} not found."}
        
    refund_id = f"REF-{uuid.uuid4().hex[:8].upper()}"
    order["refundStatus"] = "refunded"
    order["refundId"] = refund_id
    order["refundedAmount"] = order.get("amount")
    order["refundedTimestamp"] = time.strftime("%Y-%m-%d %H:%M:%S")
    
    save_orders(orders)
    
    return {
        "success": True,
        "refundId": refund_id,
        "orderId": order["orderId"],
        "amount": order.get("amount"),
        "currency": order.get("currency", "INR"),
        "paymentMethod": order.get("paymentMethod"),
        "message": f"Refund of {order.get('currency', 'INR')} {order.get('amount')} processed successfully under reference {refund_id} to original {order.get('paymentMethod')}."
    }
