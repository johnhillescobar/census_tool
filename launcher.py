#!/usr/bin/env python3
"""
Census Data Assistant Launcher

Choose between CLI and Web interfaces for the Census Data Assistant.
Both interfaces use the same underlying LangGraph workflow.
"""

import subprocess
import sys


def show_menu():
    """Display the interface selection menu"""
    print("🏛️ Census Data Assistant")
    print("=" * 50)
    print("Choose your interface:")
    print()
    print("1. 📱 Web Interface (Streamlit)")
    print("   - Interactive charts and tables")
    print("   - File downloads")
    print("   - Visual conversation history")
    print("   - User-friendly interface")
    print()
    print("2. 💻 Command Line Interface")
    print("   - Fast and efficient")
    print("   - Script-friendly")
    print("   - Full terminal control")
    print("   - Advanced features")
    print()
    print("3. ❌ Exit")
    print()


def launch_streamlit():
    """Launch the Streamlit web interface"""
    print("🚀 Launching Streamlit web interface...")
    print("📱 The web interface will open in your browser")
    print("🔗 If it doesn't open automatically, go to: http://localhost:8501")
    print()
    print("💡 Press Ctrl+C to stop the web server")
    print("-" * 50)

    try:
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "streamlit_app.py",
                "--server.port",
                "8501",
                "--server.headless",
                "false",
            ],
            check=True,
        )
    except KeyboardInterrupt:
        print("\n👋 Web interface stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching Streamlit: {e}")
        print("💡 Make sure Streamlit is installed: uv add streamlit")


def launch_cli():
    """Launch the CLI interface"""
    print("🚀 Launching CLI interface...")
    print("-" * 50)

    try:
        subprocess.run([sys.executable, "main.py"], check=True)
    except KeyboardInterrupt:
        print("\n👋 CLI interface stopped")
    except subprocess.CalledProcessError as e:
        print(f"❌ Error launching CLI: {e}")


def main():
    """Main launcher function"""
    while True:
        show_menu()

        try:
            choice = input("Enter your choice (1-3): ").strip()

            if choice == "1":
                launch_streamlit()
            elif choice == "2":
                launch_cli()
            elif choice == "3":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please enter 1, 2, or 3.")
                print()

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            print()


if __name__ == "__main__":
    main()
