import os
from dotenv import load_dotenv

# Load .env file before importing our app code, so create_app() can read
# MERCADO_PUBLICO_TICKET and other env vars from it (mirrors run_stdio.py).
load_dotenv()

import uvicorn
from interfaces.mcp.server import create_app

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=port)
