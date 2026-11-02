"""FastAPI server — streams agent pipeline events via SSE to the dashboard.

# CCA-F Domain1: Agentic Architecture — SSE turns the agent's synchronous
#   steps into a real-time event stream the UI can render progressively.
# INTERVIEW: SSE (Server-Sent Events) is lighter than WebSockets for
#   one-way server→client streams. No handshake overhead, auto-reconnect built in.
"""
import asyncio
import json
import os
import sys

import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, StreamingResponse
from dotenv import load_dotenv

# agent lives one level up
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

from agent.classifier import PaymentClassifier, FailureType
from agent.recovery import RecoveryAgent
from tests.mock_payments import MOCK_PAYMENTS, get_total_value_rupees

app = FastAPI(title="Razorpay Recovery Agent")


def _event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data)}\n\n"


# ── Simulated MCP tool call sequences per failure type ──────────────────────
_MCP_TOOL_CALLS: dict[str, list[dict]] = {
    "BANK_TECHNICAL": [
        {
            "tool": "razorpay.payments.fetch",
            "args": {"payment_id": "{pid}"},
            "result_preview": {"status": "failed", "error_code": "GATEWAY_ERROR", "bank_reference": None},
            "note": "Verify current status before triggering retry",
        },
        {
            "tool": "razorpay.payments.retry",
            "args": {"payment_id": "{pid}", "reason": "bank_technical_error"},
            "result_preview": {"queued": True, "estimated_retry_at": "+30s"},
            "note": "Auto-retry via Razorpay gateway",
        },
    ],
    "INSUFFICIENT_FUNDS": [
        {
            "tool": "razorpay.payment_links.create",
            "args": {"amount": "{amount}", "description": "Retry payment", "expire_by": "48h"},
            "result_preview": {"id": "plink_mock_001", "short_url": "rzp.io/l/mock001", "status": "created"},
            "note": "Generate fresh payment link for payday retry",
        },
        {
            "tool": "razorpay.notifications.schedule",
            "args": {"channel": "sms+email", "delay_hours": 48, "template": "insufficient_funds"},
            "result_preview": {"scheduled": True, "send_at": "+48h"},
            "note": "Send after 48-hour payday cycle",
        },
    ],
    "CARD_EXPIRED": [
        {
            "tool": "razorpay.payment_links.create",
            "args": {"amount": "{amount}", "description": "Update card & retry", "method_hint": "card"},
            "result_preview": {"id": "plink_mock_002", "short_url": "rzp.io/l/mock002", "status": "created"},
            "note": "New link prompts customer to add updated card",
        },
        {
            "tool": "razorpay.notifications.send",
            "args": {"channel": "email+sms", "template": "card_expired", "immediate": True},
            "result_preview": {"delivered": True, "channels": ["email", "sms"]},
            "note": "Immediate notification — time-sensitive",
        },
    ],
    "UPI_TIMEOUT": [
        {
            "tool": "razorpay.payments.fetch",
            "args": {"payment_id": "{pid}", "include_bank_reference": True},
            "result_preview": {"status": "failed", "bank_debit_status": "unknown", "upi_ref": None},
            "note": "⚠ SAFETY CHECK — bank may have deducted without confirmation",
        },
        {
            "tool": "razorpay.upi.check_settlement",
            "args": {"payment_id": "{pid}", "vpa": "{vpa}"},
            "result_preview": {"settled": False, "npci_ref": None, "safe_to_retry": True},
            "note": "Verify with NPCI settlement records before any capture",
        },
    ],
    "EVENING_PEAK": [
        {
            "tool": "razorpay.gateway.check_load",
            "args": {"timestamp": "now", "gateway": "razorpay"},
            "result_preview": {"load": "HIGH", "peak_window": "19:00–22:00 IST", "recommended_retry": "22:05 IST"},
            "note": "Confirm gateway congestion before scheduling",
        },
        {
            "tool": "razorpay.payments.schedule_retry",
            "args": {"payment_id": "{pid}", "retry_after_ist": "22:05", "reason": "evening_peak"},
            "result_preview": {"scheduled": True, "retry_at": "22:05 IST"},
            "note": "Queue retry for post-peak window",
        },
    ],
}


async def run_pipeline():
    """Yield SSE events as the agent classifies and recovers each payment."""

    yield _event("start", {
        "total": len(MOCK_PAYMENTS),
        "at_risk": int(get_total_value_rupees()),
    })
    await asyncio.sleep(0.4)

    # ── STEP 1: CLASSIFY ────────────────────────────────────────────────────
    yield _event("step", {"step": 1, "label": "Classifying failures with Claude Sonnet 4"})
    await asyncio.sleep(0.3)

    classifier = PaymentClassifier()
    classified = []

    for payment in MOCK_PAYMENTS:
        pid = payment["id"]

        yield _event("classifying", {
            "payment_id": pid,
            "amount": payment["amount"] // 100,
        })
        await asyncio.sleep(0.15)

        # Show the Anthropic API call going out
        yield _event("api_call", {
            "model": "claude-sonnet-4-5",
            "purpose": "Classify payment failure",
            "payment_id": pid,
            "prompt_preview": f"method={payment['method']} error={payment['error_code']} desc={payment['error_description'][:60]}…",
        })
        await asyncio.sleep(0.1)

        result = classifier.classify(payment)
        classified.append(result)

        yield _event("classified", {
            "payment_id": result.payment_id,
            "failure_type": result.failure_type.value,
            "amount": result.amount // 100,
            "recovery_probability": result.recovery_probability,
            "priority_score": result.priority_score,
            "recovery_strategy": result.recovery_strategy,
            "reasoning": result.reasoning,
        })
        await asyncio.sleep(0.7)

    # ── STEP 2: RECOVER ─────────────────────────────────────────────────────
    yield _event("step", {"step": 2, "label": "Executing recovery strategies (DRY_RUN=true)"})
    await asyncio.sleep(0.5)

    class _MockMCPClient:
        async def call_tool(self, name, args):
            pass

    recovery_agent = RecoveryAgent(_MockMCPClient())  # type: ignore[arg-type]
    results = []

    for payment in classified:
        pid = payment.payment_id
        ftype = payment.failure_type.value

        yield _event("recovering", {"payment_id": pid})
        await asyncio.sleep(0.3)

        # Emit simulated MCP tool calls for this failure type
        tool_sequence = _MCP_TOOL_CALLS.get(ftype, [])
        for i, tc in enumerate(tool_sequence):
            args = {
                k: v.replace("{pid}", pid)
                      .replace("{amount}", str(payment.amount))
                      .replace("{vpa}", payment.raw_payment.get("contact", "cust@upi"))
                if isinstance(v, str) else v
                for k, v in tc["args"].items()
            }
            yield _event("mcp_tool_call", {
                "payment_id": pid,
                "tool": tc["tool"],
                "args": args,
                "result_preview": tc["result_preview"],
                "note": tc["note"],
                "simulated": True,
                "seq": i + 1,
                "total": len(tool_sequence),
            })
            await asyncio.sleep(0.6)

        result = await recovery_agent.recover(payment)
        results.append(result)

        yield _event("recovered", {
            "payment_id": result.payment_id,
            "failure_type": result.failure_type.value,
            "action": result.action_taken,
            "success": result.success,
            "detail": result.detail,
        })
        await asyncio.sleep(0.5)

    # ── STEP 3: REPORT ───────────────────────────────────────────────────────
    yield _event("step", {"step": 3, "label": "Generating recovery report"})
    await asyncio.sleep(0.4)

    yield _event("api_call", {
        "model": "claude-sonnet-4-5",
        "purpose": "Generate recovery report",
        "payment_id": "all",
        "prompt_preview": f"Summarise recovery cycle: {len(classified)} payments, {sum(r.success for r in results)} actioned",
    })
    await asyncio.sleep(0.2)

    from agent.reporter import RecoveryReporter
    reporter = RecoveryReporter()
    report = reporter.generate(classified, results)

    actioned = sum(1 for r in results if r.success)
    total_actioned = sum(c.amount for c, r in zip(classified, results) if r.success) // 100
    api_calls_total = len(MOCK_PAYMENTS) + 1  # classify × N + report × 1

    yield _event("report", {
        "text": report,
        "actioned": actioned,
        "total": len(results),
        "total_actioned": total_actioned,
        "api_calls": api_calls_total,
        "mcp_calls": sum(len(_MCP_TOOL_CALLS.get(c.failure_type.value, [])) for c in classified),
    })

    yield _event("done", {})


@app.get("/api/stream")
async def stream():
    return StreamingResponse(
        run_pipeline(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/", response_class=HTMLResponse)
async def dashboard():
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()


if __name__ == "__main__":
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
