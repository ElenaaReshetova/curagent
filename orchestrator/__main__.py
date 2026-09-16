"""Orchestrator package entry points."""

from src.orchestrator.kafka_starter import main as kafka_starter_main
from src.orchestrator.worker import main as worker_main

if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "worker":
        worker_main()
    elif len(sys.argv) > 1 and sys.argv[1] == "starter":
        kafka_starter_main()
    else:
        print("Usage: python -m src.orchestrator [worker|starter]")
        sys.exit(1)
