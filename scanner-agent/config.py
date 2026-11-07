import os
from pathlib import Path
import sys
from dotenv import load_dotenv

def get_agent_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

def load_agent_config() -> Path:
    config_path = get_agent_dir() / "config" / ".env"
    load_dotenv(config_path)
    return config_path
