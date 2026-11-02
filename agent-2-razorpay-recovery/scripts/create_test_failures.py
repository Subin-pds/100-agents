"""Creates Razorpay test orders and opens a local checkout page.

Uses Razorpay's domestic test cards (not international) to simulate
different payment failure types.

Test cards (Razorpay domestic test mode):
  SUCCESS          4111 1111 1111 1111  expiry: any future  CVV: any  OTP: 1234
  FAILURE generic  4111 1111 1111 1111  expiry: any future  CVV: any  OTP: 9999
  AUTH FAILURE     5267 3181 8797 5449  expiry: any future  CVV: any  OTP: 1234
  INSUF. FUNDS     5267 3181 8797 5449  expiry: any future  CVV: any  OTP: 9999

Usage:
    python scripts/create_test_failures.py
    Then open the generated checkout.html in your browser.
"""
import http.server
import json
import os
import sys
import threading
import webbrowser

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import httpx
from dotenv import load_dotenv

load_dotenv()

RAZORPAY_KEY_ID     = os.environ["RAZORPAY_KEY_ID"]
RAZORPAY_KEY_SECRET = os.environ["RAZORPAY_KEY_SECRET"]
BASE_URL            = "https://api.razorpay.com/v1"

SCENARIOS = [
    {
        "label":       "BANK_TECHNICAL — RS.15,000",
        "amount":      1500000,
        "description": "Laptop purchase - simulate bank gateway failure",
        "hint":        "Card: 5267 3181 8797 5449 | OTP: 9999 → generic failure",
    },
    {
        "label":       "INSUFFICIENT_FUNDS — RS.2,999",
        "amount":      299900,
        "description": "Annual subscription - simulate insufficient funds",
        "hint":        "Card: 5267 3181 8797 5449 | OTP: 9999 → generic failure",
    },
    {
        "label":       "CARD_EXPIRED — RS.750",
        "amount":      75000,
        "description": "Course payment - simulate expired/invalid card",
        "hint":        "Card: 4111 1111 1111 1111 | OTP: 9999 → generic failure",
    },
    {
        "label":       "SUCCESS (control) — RS.500",
        "amount":      50000,
        "description": "Test successful payment for baseline",
        "hint":        "Card: 4111 1111 1111 1111 | OTP: 1234 → success",
    },
]


def create_order(amount: int, description: str) -> str:
    """Create a Razorpay order and return the order_id."""
    resp = httpx.post(
        f"{BASE_URL}/orders",
        auth=(RAZORPAY_KEY_ID, RAZORPAY_KEY_SECRET),
        json={
            "amount":   amount,
            "currency": "INR",
            "receipt":  f"test_{amount}",
            "notes":    {"description": description},
        },
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["id"]


def generate_html(scenarios_with_orders: list[dict]) -> str:
    scenarios_json = json.dumps(scenarios_with_orders)
    key_id = RAZORPAY_KEY_ID

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Razorpay Test Payments</title>
  <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
  <style>
    body {{ font-family: monospace; background: #0d1117; color: #c9d1d9; padding: 40px; }}
    h1   {{ color: #58a6ff; margin-bottom: 4px; }}
    p    {{ color: #8b949e; margin-bottom: 32px; }}
    .card {{ background: #161b22; border: 1px solid #30363d; border-radius: 8px;
             padding: 20px 24px; margin-bottom: 16px; }}
    .label {{ font-size: 16px; font-weight: bold; color: #f0f6fc; }}
    .hint  {{ font-size: 13px; color: #8b949e; margin: 8px 0 14px; }}
    button {{ background: #238636; color: #fff; border: none; padding: 10px 20px;
              border-radius: 6px; cursor: pointer; font-size: 14px; font-family: monospace; }}
    button:hover {{ background: #2ea043; }}
  </style>
</head>
<body>
  <h1>Razorpay Recovery Agent — Test Payments</h1>
  <p>Pay each scenario with the card shown. Then run <code>python main.py</code> to see the agent recover them.</p>
  <div id="scenarios"></div>

  <script>
    const KEY_ID    = "{key_id}";
    const SCENARIOS = {scenarios_json};

    const container = document.getElementById("scenarios");

    SCENARIOS.forEach((s, i) => {{
      const div = document.createElement("div");
      div.className = "card";
      div.innerHTML = `
        <div class="label">${{s.label}}</div>
        <div class="hint">${{s.hint}}</div>
        <button onclick="pay(${{i}})">Open Checkout</button>
      `;
      container.appendChild(div);
    }});

    function pay(i) {{
      const s = SCENARIOS[i];
      const rzp = new Razorpay({{
        key:         KEY_ID,
        order_id:    s.order_id,
        amount:      s.amount,
        currency:    "INR",
        name:        "Recovery Agent Test",
        description: s.description,
        prefill:     {{ name: "Test User", email: "test@razorpay.com", contact: "9999999999" }},
        theme:       {{ color: "#238636" }},
        handler: function(response) {{
          alert("Payment succeeded: " + response.razorpay_payment_id);
        }},
      }});
      rzp.open();
    }}
  </script>
</body>
</html>"""


def main() -> None:
    print("\nCreating Razorpay test orders...\n")

    scenarios_with_orders = []
    for s in SCENARIOS:
        try:
            order_id = create_order(s["amount"], s["description"])
            scenarios_with_orders.append({**s, "order_id": order_id})
            print(f"  OK  {s['label']:35}  order_id={order_id}")
        except Exception as e:
            print(f"  ERR {s['label']:35}  {e}")

    if not scenarios_with_orders:
        print("\nNo orders created. Check your API keys.")
        return

    html = generate_html(scenarios_with_orders)
    out_path = os.path.join(os.path.dirname(__file__), "checkout.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nCheckout page written to: {out_path}")

    # Serve locally and open in browser
    os.chdir(os.path.dirname(out_path))
    handler  = http.server.SimpleHTTPRequestHandler
    httpd    = http.server.HTTPServer(("localhost", 8765), handler)
    url      = "http://localhost:8765/checkout.html"

    print(f"Serving at: {url}")
    print("Opening in browser... (Ctrl+C to stop)\n")

    threading.Thread(target=lambda: webbrowser.open(url), daemon=True).start()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")


if __name__ == "__main__":
    main()
