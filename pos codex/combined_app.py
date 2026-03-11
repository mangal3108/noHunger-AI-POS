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

# Overwrite service URLs to point to internal mounts within the same process
# This allows the API Gateway to "proxy" to the other apps on the same port
PORT = int(os.getenv("PORT", "8000"))
os.environ["AI_AGENT_SERVICE_URL"] = f"http://localhost:{PORT}/internal/ai"
os.environ["ORDER_SERVICE_URL"] = f"http://localhost:{PORT}/internal/order"

# Now import the apps after setting environment variables
from ai_agent.agent import app as ai_app
from order_service.app import app as order_app
from payment_service.app import app as payment_app
from main import app as gateway_app  # From api-gateway

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
