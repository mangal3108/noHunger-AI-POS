import sys
import os
from pathlib import Path
from fastapi import FastAPI
import uvicorn
from dotenv import load_dotenv

# Define ROOT as the current directory (pos codex)
ROOT = Path(__file__).resolve().parent

# Add sub-app directories to sys.path so imports work correctly
sys.path.append(str(ROOT / "apps" / "ai-agent-service"))
sys.path.append(str(ROOT / "apps" / "order-service"))
sys.path.append(str(ROOT / "apps" / "payment-service"))
sys.path.append(str(ROOT / "apps" / "api-gateway"))

# Load environment variables
load_dotenv()

# Overwrite service URLs to point to internal mounts or external Node.js backend
PORT = int(os.getenv("PORT", "8000"))
print(f"Starting Bhadawar AI Monolith on port {PORT}...")

# Ensure AI_AGENT_SERVICE_URL has protocol and points to local mount
os.environ["AI_AGENT_SERVICE_URL"] = f"http://127.0.0.1:{PORT}/internal/ai"

# Prioritize the Node.js backend (port 5000) for real MongoDB Atlas data
order_url = os.getenv("ORDER_SERVICE_URL", "").strip('"').strip("'")
if not order_url:
    order_url = "http://127.0.0.1:5000"
elif not order_url.startswith("http"):
    # Render internal service name doesn't include port or protocol
    if ":" not in order_url:
        order_url = f"http://{order_url}:5000"
    else:
        order_url = f"http://{order_url}"
os.environ["ORDER_SERVICE_URL"] = order_url
os.environ["PAYMENT_SERVICE_URL"] = order_url

print(f"Service URLs configured:")
print(f" - AI: {os.environ['AI_AGENT_SERVICE_URL']}")
print(f" - Order/Payment: {os.environ['ORDER_SERVICE_URL']}")

# Now import the apps after setting environment variables
try:
    from ai_agent.agent import app as ai_app
    from order_service.app import app as order_app
    from payment_service.app import app as payment_app
    from app import app as gateway_app  # From api-gateway
    print("All sub-apps imported successfully.")
except Exception as e:
    print(f"CRITICAL: Failed to import sub-apps: {e}")
    raise

# Create the master Monolith app
app = FastAPI(title="NoHunger AI POS Monolith")

# Mount sub-apps
app.mount("/internal/ai", ai_app)
app.mount("/internal/order", order_app)
app.mount("/internal/payment", payment_app)

# Mount the gateway last as it handles the root / and other routes
app.mount("/", gateway_app)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
