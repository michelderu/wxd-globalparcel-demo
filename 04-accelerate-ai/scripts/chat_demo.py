#!/usr/bin/env python3
"""
watsonx Orchestrate - Simple Chat Demo

This script demonstrates basic chat interaction with watsonx Orchestrate
Developer Edition running locally via the REST API.

Usage:
    python chat_demo.py
    python chat_demo.py --interactive
    python chat_demo.py --question "What is AI?"
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import requests


DEFAULT_AGENT_NAME = "parcel_assistant"
CREDENTIALS_PATH = Path.home() / ".cache" / "orchestrate" / "credentials.yaml"


def load_local_token(credentials_path: Path = CREDENTIALS_PATH) -> Optional[str]:
    """Read the cached Developer Edition bearer token written by the ADK."""
    env_token = os.environ.get("WXO_TOKEN") or os.environ.get("WO_TOKEN")
    if env_token:
        return env_token.strip()

    if not credentials_path.is_file():
        return None

    match = re.search(r"wxo_mcsp_token:\s*(\S+)", credentials_path.read_text())
    return match.group(1).strip() if match else None


def extract_assistant_text(data: Dict[str, Any]) -> str:
    """Pull assistant text from a chat/completions JSON response."""
    for choice in data.get("choices", []):
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content.strip()
        if isinstance(content, list):
            parts = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text") or block.get("response")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "\n".join(parts).strip()

        text = choice.get("text")
        if isinstance(text, str) and text.strip():
            return text.strip()

    return "No response received"


class OrchestrateChatClient:
    """Simple client for watsonx Orchestrate chat/completions API."""

    def __init__(
        self,
        base_url: str = "http://localhost:4321",
        token: Optional[str] = None,
        agent_id: Optional[str] = None,
        agent_name: str = DEFAULT_AGENT_NAME,
    ):
        self.base_url = base_url.rstrip("/")
        self.token = token or load_local_token()
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.thread_id: Optional[str] = None
        self.session = requests.Session()

    def _headers(self) -> Dict[str, str]:
        if not self.token:
            raise RuntimeError(
                "No API token found. Run `orchestrate server start` and `orchestrate chat start` "
                "once so the ADK caches a token in ~/.cache/orchestrate/credentials.yaml, "
                "or pass --token / set WXO_TOKEN."
            )

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }
        if self.thread_id:
            headers["X-IBM-THREAD-ID"] = self.thread_id
        return headers

    def health_check(self) -> bool:
        """Check if the Orchestrate API is reachable (Developer Edition has no /health route)."""
        for path in ("/api/openapi.json", "/docs"):
            try:
                response = self.session.get(f"{self.base_url}{path}", timeout=5)
                if response.status_code == 200:
                    return True
            except requests.exceptions.RequestException:
                continue
        return False

    def resolve_agent_id(self) -> str:
        """Resolve agent ID from CLI flag or by name via the REST API."""
        if self.agent_id:
            return self.agent_id

        endpoint = f"{self.base_url}/api/v1/orchestrate/agents"
        response = self.session.get(
            endpoint,
            headers=self._headers(),
            params={"names": [self.agent_name]},
            timeout=30,
        )
        response.raise_for_status()
        agents = response.json()
        if isinstance(agents, dict):
            agents = agents.get("agents") or agents.get("items") or []

        for agent in agents:
            if agent.get("name") == self.agent_name or agent.get("id"):
                self.agent_id = agent["id"]
                return self.agent_id

        available = ", ".join(
            sorted({agent.get("name", "?") for agent in agents if isinstance(agent, dict)})
        )
        raise RuntimeError(
            f"Agent '{self.agent_name}' not found. Import it with "
            f"`orchestrate agents import -f agents/{self.agent_name}.yml`. "
            f"Available agents: {available or 'none'}"
        )

    def chat(self, message: str) -> Dict[str, Any]:
        """Send a message and return parsed assistant text plus raw API payload."""
        agent_id = self.resolve_agent_id()
        endpoint = f"{self.base_url}/api/v1/orchestrate/{agent_id}/chat/completions"
        payload = {
            "messages": [{"role": "user", "content": message}],
            "stream": False,
        }

        try:
            response = self.session.post(
                endpoint,
                headers=self._headers(),
                json=payload,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            if data.get("thread_id"):
                self.thread_id = data["thread_id"]

            return {
                "response": extract_assistant_text(data),
                "thread_id": self.thread_id,
                "raw": data,
            }

        except requests.exceptions.RequestException as exc:
            detail = str(exc)
            if isinstance(exc, requests.exceptions.HTTPError) and exc.response is not None:
                try:
                    detail = json.dumps(exc.response.json(), indent=2)
                except ValueError:
                    detail = exc.response.text or detail
            return {
                "error": detail,
                "response": f"Error communicating with Orchestrate: {detail}",
            }

    def reset(self):
        """Start a new conversation thread."""
        self.thread_id = None


def run_demo_conversation(client: OrchestrateChatClient):
    """Run a pre-defined demo conversation."""

    print("🤖 watsonx Orchestrate Chat Demo")
    print("=" * 70)
    print()

    questions = [
        "Hello! What is watsonx Orchestrate?",
        "How do sessions 01 and 02 help Global Parcel?",
        "What are the key capabilities of watsonx Orchestrate?",
        "How can I integrate it with my applications?",
    ]

    for i, question in enumerate(questions, 1):
        print(f"📝 Question {i}/{len(questions)}")
        print(f"👤 User: {question}")
        print()

        result = client.chat(question)

        if "error" in result:
            print(f"❌ Error: {result['error']}")
            print()
            continue

        print(f"🤖 Assistant: {result.get('response', 'No response received')}")
        print()
        print("-" * 70)
        print()

    print("✅ Demo conversation complete!")
    print(f"📊 Thread ID: {client.thread_id}")


def run_interactive_mode(client: OrchestrateChatClient):
    """Run interactive chat mode."""

    print("🤖 watsonx Orchestrate - Interactive Chat")
    print("=" * 70)
    print("Type your messages below. Commands:")
    print("  /reset  - Start a new conversation")
    print("  /quit   - Exit the chat")
    print("  /help   - Show this help message")
    print("=" * 70)
    print()

    while True:
        try:
            user_input = input("👤 You: ").strip()

            if not user_input:
                continue

            if user_input.startswith("/"):
                command = user_input.lower()

                if command == "/quit":
                    print("\n👋 Goodbye!")
                    break

                if command == "/reset":
                    client.reset()
                    print("🔄 Conversation reset. Starting fresh!\n")
                    continue

                if command == "/help":
                    print("\n📖 Available commands:")
                    print("  /reset  - Start a new conversation")
                    print("  /quit   - Exit the chat")
                    print("  /help   - Show this help message\n")
                    continue

                print(f"❓ Unknown command: {command}")
                print("Type /help for available commands\n")
                continue

            result = client.chat(user_input)

            if "error" in result:
                print(f"❌ Error: {result['error']}\n")
                continue

            print(f"🤖 Assistant: {result.get('response', 'No response received')}\n")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except EOFError:
            print("\n\n👋 Goodbye!")
            break


def main():
    parser = argparse.ArgumentParser(
        description="watsonx Orchestrate Chat Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python chat_demo.py
  python chat_demo.py --interactive
  python chat_demo.py --question "How do sessions 01 and 02 help Global Parcel?"
  python chat_demo.py --agent-name ask_orchestrate --interactive
  python chat_demo.py --token "$WXO_TOKEN" --agent-id <uuid>
        """,
    )

    parser.add_argument(
        "--url",
        default="http://localhost:4321",
        help="Base URL of watsonx Orchestrate (default: http://localhost:4321)",
    )
    parser.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Run in interactive mode",
    )
    parser.add_argument(
        "--question",
        "-q",
        help="Ask a single question and exit",
    )
    parser.add_argument(
        "--agent-id",
        help="Agent UUID (default: look up by --agent-name)",
    )
    parser.add_argument(
        "--agent-name",
        default=DEFAULT_AGENT_NAME,
        help=f"Agent name to resolve when --agent-id is omitted (default: {DEFAULT_AGENT_NAME})",
    )
    parser.add_argument(
        "--token",
        help="Bearer token (default: read from ~/.cache/orchestrate/credentials.yaml or WXO_TOKEN)",
    )

    args = parser.parse_args()

    client = OrchestrateChatClient(
        base_url=args.url,
        token=args.token,
        agent_id=args.agent_id,
        agent_name=args.agent_name,
    )

    print("🔍 Checking watsonx Orchestrate connection...")
    if not client.health_check():
        print(f"❌ Error: Cannot connect to watsonx Orchestrate at {args.url}")
        print("\nTroubleshooting:")
        print("1. Start server: orchestrate server start -e .env --with-langflow")
        print("2. Activate env: orchestrate env activate local")
        print("3. Check API: curl -s http://localhost:4321/docs -o /dev/null -w '%{http_code}\\n'")
        sys.exit(1)

    print(f"✅ Connected to watsonx Orchestrate at {args.url}")

    try:
        agent_id = client.resolve_agent_id()
        print(f"✅ Using agent: {args.agent_name} ({agent_id})")
    except RuntimeError as exc:
        print(f"❌ Error: {exc}")
        sys.exit(1)

    print()

    if args.question:
        print(f"👤 User: {args.question}")
        result = client.chat(args.question)

        if "error" in result:
            print(f"❌ Error: {result['error']}")
            sys.exit(1)

        print(f"🤖 Assistant: {result.get('response', 'No response received')}")

    elif args.interactive:
        run_interactive_mode(client)

    else:
        run_demo_conversation(client)


if __name__ == "__main__":
    main()
