import os
import sys
import tempfile

# Isolated database and offline provider for every test run.
_tmp = tempfile.mkdtemp()
# Set TEST_DATABASE_URL to run the same suite against Postgres (as used in production).
os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", f"sqlite:///{_tmp}/test.db")
os.environ["LLM_PROVIDER"] = "offline"
os.environ["CC_SKIP_DOTENV"] = "1"
os.environ["GEOCODER"] = "off"
os.environ["DEMO_SEED"] = "1"
os.environ["STATIC_DIR"] = _tmp
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
