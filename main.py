import sys
import os
from pathlib import Path
import logging
from typing import Dict, Any
from dotenv import load_dotenv

# Add project root to path
project_root = Path(__file__).parent
sys.path.append(str(project_root))

from app import create_census_graph
from src.state.types import CensusState
from langchain_core.runnables import RunnableConfig
from src.utils.displays import display_results

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

load_dotenv()


def main():
    """Main application entry point"""

    print("Welcome to the Census Data Assistant!")
    print("=" * 50)

    try:
        # Get user input
        user_id = input("Enter your user ID (or press Enter for 'demo'): ").strip()
        if not user_id:
            user_id = "demo"

        thread_id = input(
            "Enter your thread ID (or press Enter for a new thread): "
        ).strip()
        if not thread_id:
            thread_id = "main"

        print(f"\n👤 User: {user_id}")
        print(f"🧵 Thread: {thread_id}")
        print("\nAsk me about Census data! (Type 'quit' to exit)")
        print("Examples:")
        print("  - What's the population of New York City?")
        print("  - Show me median income trends from 2015 to 2020")
        print("  - Compare population by county in California")
        print("-" * 50)

        # Initialize the graph
        graph = create_census_graph()

        # Main conversation loop
        while True:
            try:
                # Get user input
                user_input = input("\n❓ Your question: ").strip()

                if user_input.lower() in ["quit", "exit", "q"]:
                    print("\n👋 Goodbye!")
                    break

                if user_input:
                    print("\n🔍 Processing your question...")

                # Create initial state
                initial_state = CensusState(
                    messages=[{"role": "user", "content": user_input}],
                    original_query=None,  # Will be set by intent_node
                    intent=None,
                    geo={},
                    candidates={},
                    plan=None,
                    artifacts={},
                    final=None,
                    logs=[],
                    error=None,
                    summary=None,
                    profile={},
                    history=[],
                    cache_index={},
                )

                # Create config
                config = RunnableConfig(
                    configurable={"user_id": user_id, "thread_id": thread_id}
                )

                # Process through graph
                result = graph.invoke(initial_state, config)

                # Display results
                display_results(result)

            except KeyboardInterrupt:
                print("\n\nGoodbye!")
                break
            except Exception as e:
                logger.error(f"Error processing question: {str(e)}")
                print(f"\nError: {str(e)}")
                print("Please try again or type 'quit' to exit.")

    except Exception as e:
        logger.error(f"Error initializing app: {str(e)}")
        print(f"Error initializing app: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
