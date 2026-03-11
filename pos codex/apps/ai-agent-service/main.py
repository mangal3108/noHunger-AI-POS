from pathlib import Path
import sys
import os

import uvicorn
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.append(str(ROOT))

from ai_agent.agent import app

load_dotenv()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("AI_AGENT_PORT", "8001")))
