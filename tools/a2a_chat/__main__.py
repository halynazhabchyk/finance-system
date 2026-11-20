"""Entry point: python -m a2a_chat [--agent budget|report] [--gateway URL]."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os
import sys
from collections.abc import Callable, Sequence

import httpx

from ai_tools.a2a.client import RemoteAgentClient, RemoteAgentError

from a2a_chat.auth import TOKEN_ENV, TokenProblem, inspect_token, read_token
from a2a_chat.config import AGENTS, ChatSettings
from a2a_chat.console import Console
from a2a_chat.session import ChatSession

Reader = Callable[[str], str]


def parse_args(argv: Sequence[str] | None = None) -> ChatSettings:
    parser = argparse.ArgumentParser(prog="python -m a2a_chat", description="Чат з A2A-агентом фінансової системи.")
    parser.add_argument("--agent", choices=sorted(AGENTS), default="budget", help="агент: budget (producer) або report (consumer)")
    parser.add_argument("--gateway", help="адреса Gateway (за замовчуванням GATEWAY_URL або http://localhost:8080)")
    args = parser.parse_args(argv)
    return ChatSettings.build(args.agent, args.gateway)


async def run(
    settings: ChatSettings,
    *,
    read: Reader = input,
    read_secret: Reader = getpass.getpass,
    env_token: str | None = None,
    console: Console | None = None,
    transport: httpx.AsyncBaseTransport | None = None,
) -> int:
    """``read``, ``read_secret``, ``env_token`` and ``transport`` are replaced in tests."""
    console = console or Console()
    console.line(f"A2A-чат з {settings.target.name} через {settings.gateway_url}")
    env_token = os.getenv(TOKEN_ENV) if env_token is None else env_token
    try:
        token = read_token(env_token, lambda prompt: read_secret(prompt))
        info = inspect_token(token)
    except (EOFError, KeyboardInterrupt):
        return 1
    except TokenProblem as error:
        console.error(str(error))
        return 1
    who = info.username or info.subject
    console.info(f"Токен користувача {who}; дійсний ще ~{info.minutes_left()} хв; scopes: {' '.join(sorted(info.scopes)) or '-'}")

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
