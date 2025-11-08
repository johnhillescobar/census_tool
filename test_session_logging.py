"""
Test script to verify session logging functionality.
Tests both logging statements and print statements capture.
"""

import logging
import time
from pathlib import Path
from src.utils.session_logger import SessionLogger

# Set up basic logging
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_basic_logging():
    """Test basic session logging with different log levels and print statements"""
    print("\n" + "=" * 50)
    print("TEST 1: Basic Session Logging")
    print("=" * 50)

    user_id = "test_user"
    session_logger = SessionLogger(user_id)

    print(f"Starting session for user: {user_id}")
    log_file = session_logger.start()
    print(f"Log file created: {log_file}")

    # Test different log levels
    logger.debug("This is a DEBUG message")
    logger.info("This is an INFO message")
    logger.warning("This is a WARNING message")
    logger.error("This is an ERROR message")

    # Test print statements
    print("This is a print statement that should be captured")
    print(f"User ID: {user_id}")
    print("Processing data...")

    # Stop logging
    session_logger.stop()
    print(f"Session ended. Log saved to: {log_file}")

    # Verify log file exists and has content
    if log_file.exists():
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            print(f"\nLog file size: {len(content)} bytes")
            print("\nFirst 500 characters of log:")
            print("-" * 50)
            print(content[:500])
            print("-" * 50)

            # Check for expected content
            checks = [
                ("DEBUG message" in content, "DEBUG log captured"),
                ("INFO message" in content, "INFO log captured"),
                ("WARNING message" in content, "WARNING log captured"),
                ("ERROR message" in content, "ERROR log captured"),
                ("print statement" in content, "Print statement captured"),
                ("SESSION START" in content, "Session start marker captured"),
                ("SESSION END" in content, "Session end marker captured"),
            ]

            print("\nContent verification:")
            for check, description in checks:
                status = "✅" if check else "❌"
                print(f"{status} {description}")

            return all(check for check, _ in checks)
    else:
        print("❌ Log file not found!")
        return False


def test_multiple_sessions():
    """Test that multiple sessions create separate log files"""
    print("\n" + "=" * 50)
    print("TEST 2: Multiple Sessions with Same User")
    print("=" * 50)

    user_id = "test_user"
    log_files = []

    for i in range(2):
        print(f"\nStarting session {i + 1}...")
        time.sleep(1.1)  # Ensure different timestamps

        session_logger = SessionLogger(user_id)
        log_file = session_logger.start()

        print(f"Session {i + 1}: This is a test message")
        logger.info(f"Session {i + 1}: Info log")

        session_logger.stop()
        log_files.append(log_file)
        print(f"Session {i + 1} saved to: {log_file}")

    # Verify separate files were created
    print(f"\nCreated {len(log_files)} log files")
    all_exist = all(f.exists() for f in log_files)
    all_different = len(log_files) == len(set(log_files))

    print(f"{'✅' if all_exist else '❌'} All log files exist")
    print(f"{'✅' if all_different else '❌'} All log files have unique names")

    return all_exist and all_different


def test_different_users():
    """Test that different users create different log files"""
    print("\n" + "=" * 50)
    print("TEST 3: Different Users")
    print("=" * 50)

    users = ["alice", "bob", "charlie"]
    log_files = {}

    for user in users:
        session_logger = SessionLogger(user)
        log_file = session_logger.start()

        print(f"User {user}: Hello from {user}!")
        logger.info(f"User {user} logged in")

        session_logger.stop()
        log_files[user] = log_file
        print(f"User {user} log: {log_file}")

    # Verify each user has their own file
    print(f"\nCreated {len(log_files)} log files for {len(users)} users")
    for user, log_file in log_files.items():
        has_user_in_name = user in str(log_file)
        exists = log_file.exists()
        print(
            f"{'✅' if (has_user_in_name and exists) else '❌'} {user}: {log_file.name}"
        )

    return all(
        user in str(log_file) and log_file.exists()
        for user, log_file in log_files.items()
    )


def test_logs_directory():
    """Test that logs are saved to the correct directory"""
    print("\n" + "=" * 50)
    print("TEST 4: Log Directory Structure")
    print("=" * 50)

    logs_dir = Path("logs")
    print(f"Expected directory: {logs_dir.absolute()}")
    print(f"Directory exists: {'✅' if logs_dir.exists() else '❌'}")

    if logs_dir.exists():
        log_files = list(logs_dir.glob("*.txt"))
        print(f"\nLog files in directory: {len(log_files)}")
        for log_file in sorted(log_files)[-5:]:  # Show last 5
            print(f"  - {log_file.name}")

        # Check filename format: {user_id}_{YYYYMMDD}_{HHMMSS}.txt
        import re

        pattern = r"^[a-zA-Z0-9_-]+_\d{8}_\d{6}\.txt$"
        format_correct = all(re.match(pattern, f.name) for f in log_files)
        print(
            f"\n{'✅' if format_correct else '❌'} All filenames match expected format"
        )

        return format_correct
    else:
        print("❌ Logs directory not found")
        return False


def main():
    """Run all tests"""
    print("\n" + "🧪 SESSION LOGGER TESTS ".center(50, "="))
    print("Testing session logging implementation...")
    print("=" * 50)

    tests = [
        ("Basic Logging", test_basic_logging),
        ("Multiple Sessions", test_multiple_sessions),
        ("Different Users", test_different_users),
        ("Log Directory", test_logs_directory),
    ]

    results = []
    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"Error: {e}")
            import traceback

            traceback.print_exc()
            results.append((test_name, False))

    # Summary
    print("\n" + "=" * 50)
    print("TEST SUMMARY")
    print("=" * 50)
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    total_passed = sum(1 for _, result in results if result)
    print(
        f"\n{total_passed}/{len(results)} tests passed ({total_passed / len(results) * 100:.0f}%)"
    )

    return all(result for _, result in results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)



