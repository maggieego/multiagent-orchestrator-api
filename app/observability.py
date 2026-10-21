import os

def setup_observability():
    """Configura el rastreo de ejecuciones para LangSmith."""
    if os.getenv("LANGCHAIN_TRACING_V2") == "true":
        print("🔍 LangSmith Observability habilitado.")