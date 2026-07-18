import logging
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from app import create_census_graph
from src.api.displays import display_results
from src.clients import SessionLogger
from src.services.graph_session import (
    build_delta_turn_state,
    build_fresh_thread_state,
    new_thread_id,
    runnable_config,
)

project_root = Path(__file__).parent

# Set up logging
LOG_FORMAT = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
logs_dir = project_root / "logs"
logs_dir.mkdir(exist_ok=True)
cli_logs_dir = logs_dir / "cli_logs"
cli_logs_dir.mkdir(parents=True, exist_ok=True)
cli_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
debug_log_path = cli_logs_dir / f"cli_log_{cli_timestamp}.txt"

console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

file_handler = logging.FileHandler(debug_log_path, mode="a", encoding="utf-8")
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)
root_logger.handlers.clear()
root_logger.addHandler(console_handler)
root_logger.addHandler(file_handler)

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

        thread_id = input("Enter your thread ID (or press Enter for a new thread): ").strip()
        if not thread_id:
            thread_id = new_thread_id()
            print(f"🆕 Started new thread: {thread_id}")

        session_logger = SessionLogger(
            user_id,
            log_dir=cli_logs_dir,
            filename_prefix=f"cli_session_{user_id}",
        )
        log_file = session_logger.start()

        print(f"\n👤 User: {user_id}")
        print(f"🧵 Thread: {thread_id}")
        print(f"📝 Logging to: {log_file}")
        print("\nAsk me about Census data! (Type 'quit' to exit)")
        print("Examples:")
        print("  - What's the population of New York City?")
        print("  - Show me median income trends from 2015 to 2020")
        print("  - Compare population by county in California")
        print("-" * 50)

        # Initialize the graph
        graph = create_census_graph()
        turn_count = 0

        try:
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

                    if turn_count == 0:
                        initial_state = build_fresh_thread_state(user_input)
                    else:
                        initial_state = build_delta_turn_state(user_input)
                    turn_count += 1

                    config = runnable_config(user_id=user_id, thread_id=thread_id)

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
        finally:
            # Always stop the logger to ensure logs are saved
            session_logger.stop()
            print(f"\n📝 Session log saved to: {log_file}")

    except Exception as e:
        logger.error(f"Error initializing app: {str(e)}")
        print(f"Error initializing app: {str(e)}")


if __name__ == "__main__":
    main()
