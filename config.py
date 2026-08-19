import os
from dotenv import load_dotenv

# Load environment variables from .env file (if present)
load_dotenv()

# Groq API Key
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

# Data files paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SNAPSHOTS_DIR = os.path.join(BASE_DIR, "snapshots")
DATA_FILE = os.path.join(BASE_DIR, "data.json")

# Tuned for a responsive dashboard without overwhelming a user's network.
MAX_PARALLEL_SCANS = int(os.getenv("MAX_PARALLEL_SCANS", "6"))
REQUEST_TIMEOUT = (5, 25)
