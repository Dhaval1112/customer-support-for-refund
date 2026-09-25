# 🎯 Customer Support Action Agent (LangGraph + HITL + JEV Guardian)

A production-grade Agentic Customer Support workflow demonstrating **LangGraph**, **Human-in-the-Loop (HITL)**, **Tools-Before-Approval**, and a **JEV Guardian Evaluator LLM**.

---

## 🌟 Key Architecture Principles

1. **Tools BEFORE Approval Decision**:
   - The LLM does *not* blindly route to human approval.
   - The agent first calls real business tools (`getOrder`, `checkRefundEligibility`, `getOrderStatus`).
   - Only when actual business data confirms eligibility and policy requires authorization does the graph pause for human approval.
2. **LangGraph Human-in-the-Loop (HITL)**:
   - Uses `langgraph.types.interrupt` with a persistent checkpointer (`MemorySaver`).
   - The thread pauses with `status: "waiting_for_approval"`.
   - Calling `POST /api/support/{threadId}/approval` resumes execution via `Command(resume={"approved": bool})`.
3. **JEV Guardian Evaluator**:
   - An independent evaluation step audits the draft response against real tool data.
   - If grounded and accurate $\to$ **PASS** $\to$ Return response.
   - If flawed $\to$ **FAIL** $\to$ Loop back to regenerate (capped at `maxGuardianAttempts = 2`).

---

## 🧠 LangGraph Workflow Diagram

```text
                         START
                           │
                           ↓
                   classify_request
                           │
                           ↓
                       call_tools
                           │
                           ↓
                  evaluate_action
                           │
                    ┌──────┴──────┐
                    │             │
                    ↓             ↓
               no_approval   requires_approval
                    │             │
                    │             ↓
                    │       human_approval (INTERRUPT)
                    │             │
                    │        ┌────┴────┐
                    │        ↓         ↓
                    │    approved    rejected
                    │        │         │
                    │        ↓         ↓
                    │   execute      END / Rejection
                    │    action        │
                    │        │         │
                    └────┬───┴─────────┘
                         ↓
                  generate_response
                         ↓
                   guardian_node (JEV Guardian)
                         │
                    ┌────┴────┐
                    ↓         ↓
                  PASS       FAIL (Attempts < 2)
                    │         │
                    ↓         └──→ regenerate_response
                   END
```

---

## 📁 Project Structure

```text
langraph-lab/
├── api/
│   └── routes/
│       └── support.py           # REST endpoints (/api/support, /api/support/{threadId}, etc.)
├── agents/
│   └── support/
│       ├── state.py             # SupportState TypedDict
│       ├── tools.py             # Business tools (getOrder, checkRefundEligibility, executeRefund)
│       ├── prompts.py           # Classifier, Response Generator, and JEV Guardian prompts
│       ├── nodes.py             # Graph node implementations
│       ├── routing.py           # Conditional edge routing logic
│       ├── guardian.py          # JEV Guardian evaluator module
│       └── graph.py             # StateGraph definition and checkpointer
├── services/
│   ├── llm_service.py           # Groq LLM factory
│   └── order_service.py         # Mock JSON database accessor
├── models/
│   └── support_schema.py        # Pydantic schemas for API and structured outputs
├── data/
│   └── orders.json              # Mock orders database (ORD-1001, ORD-1002, ORD-1003, ORD-1004)
├── main.py                      # FastAPI application entry point
├── test_agent.py                # Automated end-to-end verification script
└── README.md
```

---

## 🚀 How to Run

### 1. Run the Automated Verification Suite
Tests all 4 real-world scenarios automatically:
```bash
cd "/home/dhaval/Plans/Agentic AI/Project2/langraph-lab"
.venv/bin/python test_agent.py
```

### 2. Start the FastAPI Server
```bash
cd "/home/dhaval/Plans/Agentic AI/Project2/langraph-lab"
.venv/bin/python -m uvicorn main:app --host 0.0.0.0 --port 8001 --reload
```
Swagger UI available at: `http://localhost:8001/docs`

---

## 📡 API Endpoints & cURL Examples

### Case A — No Human Approval Needed (Order Status)
```bash
curl -X POST "http://localhost:8001/api/support" \
     -H "Content-Type: application/json" \
     -d '{"message": "Where is my order ORD-1003?"}'
```
**Response:**
```json
{
  "threadId": "thread-123",
  "status": "completed",
  "response": "Hello Robert, your order ORD-1003 is currently shipped via BlueDart (Tracking: BD987654321IN). Estimated delivery is Tomorrow, by 6:00 PM.",
  "intent": "order_status",
  "orderId": "ORD-1003",
  "requiresApproval": false,
  "guardianResult": {"approved": true, "isCorrect": true, "isGrounded": true}
}
```

---

### Case B — Human Approval Required & Approved (Refund)

**Step 1: Customer submits refund request:**
```bash
curl -X POST "http://localhost:8001/api/support" \
     -H "Content-Type: application/json" \
     -d '{"message": "I want a refund for ORD-1001."}'
```
**Response (Paused at Interrupt):**
```json
{
  "threadId": "thread-456",
  "status": "waiting_for_approval",
  "message": "Refund of INR 4999 for ORD-1001 requires supervisor authorization.",
  "intent": "refund",
  "orderId": "ORD-1001",
  "requiresApproval": true,
  "approvalStatus": "pending"
}
```

**Step 2: Check thread state at any time:**
```bash
curl -X GET "http://localhost:8001/api/support/thread-456"
```

**Step 3: Supervisor approves the refund:**
```bash
curl -X POST "http://localhost:8001/api/support/thread-456/approval" \
     -H "Content-Type: application/json" \
     -d '{"approved": true}'
```
**Response (Resumed & Completed):**
```json
{
  "threadId": "thread-456",
  "status": "completed",
  "response": "Dear John, your refund of INR 4,999 has been approved and processed under reference REF-A1B2C3D4 to your original Credit Card. It should reflect in 3-5 business days.",
  "approvalStatus": "approved",
  "actionResult": {
    "success": true,
    "refundId": "REF-A1B2C3D4",
    "amount": 4999
  },
  "guardianResult": {"approved": true, "isCorrect": true, "isGrounded": true}
}
```

---

### Case C — Human Approval Required & Rejected (Refund)

**Supervisor rejects the refund:**
```bash
curl -X POST "http://localhost:8001/api/support/thread-789/approval" \
     -H "Content-Type: application/json" \
     -d '{"approved": false}'
```
**Response:**
```json
{
  "threadId": "thread-789",
  "status": "rejected",
  "response": "Dear Emma, thank you for reaching out. A financial refund for ORD-1004 requires supervisor authorization, and unfortunately the request was not approved at this time.",
  "approvalStatus": "rejected",
  "actionResult": null,
  "guardianResult": {"approved": true, "isCorrect": true, "isGrounded": true}
}
```

---

### Case D — Business Logic Ineligible (No Human Approval Needed)
```bash
curl -X POST "http://localhost:8001/api/support" \
     -H "Content-Type: application/json" \
     -d '{"message": "Can I get a refund on ORD-1002?"}'
```
**Response:**
```json
{
  "threadId": "thread-321",
  "status": "completed",
  "response": "Hello Sarah, order ORD-1002 was delivered 45 days ago. Our return policy allows refunds within 30 days of delivery, so this item is no longer eligible for a refund.",
  "requiresApproval": false,
  "guardianResult": {"approved": true, "isCorrect": true, "isGrounded": true}
}
```
