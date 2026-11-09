"""Entry point: python -m a2a_chat [--agent budget|report] [--gateway URL] [--email EMAIL]."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from collections.abc import Callable, Sequence

import httpx

from shared.ai_tools.a2a.client import RemoteAgentClient, RemoteAgentError

from a2a_chat.auth import LoginFailed, login
from a2a_chat.config import AGENTS, ChatSettings
from a2a_chat.console import Console
from a2a_chat.session import ChatSession

Reader = Callable[[str], str]


def parse_args(argv: Sequence[str] | None = None) -> ChatSettings:
    parser = argparse.ArgumentParser(prog="python -m a2a_chat", description="Чат з A2A-агентом фінансової системи.")
    parser.add_argument("--agent", choices=sorted(AGENTS), default="budget", help="агент: budget (producer) або report (consumer)")
    parser.add_argument("--gateway", help="адреса Gateway (за замовчуванням GATEWAY_URL або http://localhost:8080)")
    parser.add_argument("--email", help="email користувача (інакше буде запитано)")
    args = parser.parse_args(argv)
    return ChatSettings.build(args.agent, args.gateway, args.email)


async def run(
    settings: ChatSettings,
    *,
    read: Reader = input,
    read_password: Reader = getpass.getpass,
    console: Console | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    """``read``, ``read_password`` and ``transport`` are replaced in tests."""
    console = console or Console()
    console.line(f"A2A-чат з {settings.target.name} через {settings.gateway_url}")
    try:
        email = settings.email or (await asyncio.to_thread(read, "Email: ")).strip()
        password = await asyncio.to_thread(read_password, "Пароль: ")
    except (EOFError, KeyboardInterrupt):
        return 1

    try:
        token = await login(settings.gateway_url, email, password, transport=transport)
    except LoginFailed as error:
        console.error(str(error))
        return 1
    console.info(f"Вхід виконано: {email}")

    async with RemoteAgentClient(
        base_url=settings.agent_url,
        access_token=token,
        timeout_seconds=settings.timeout_seconds,
        transport=transport,
    ) as remote:
        session = ChatSession(remote=remote, target=settings.target, console=console)
        try:
            await session.start()
        except RemoteAgentError as error:
            console.error(str(error))
            return 1
        while True:
            prompt = "Відповідь > " if session.awaiting_answer else "Ви > "
            try:
                line = await asyncio.to_thread(read, prompt)
            except (EOFError, KeyboardInterrupt):
                break
            if not await session.handle(line):
                break
    console.info("Сесію завершено.")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return asyncio.run(run(parse_args(argv)))
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    sys.exit(main())
