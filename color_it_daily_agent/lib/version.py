import os

def get_agent_version() -> str:
    """
    Returns the agent version.
    In deployed environments, reads the AGENT_VERSION environment variable (full Git commit hash).
    Defaults to 'dev' for local development.
    """
    version = os.getenv("AGENT_VERSION")
    if version and version.strip():
        return version.strip()
    return "dev"
