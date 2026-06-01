"""Google Secret Manager backend.

Each tenant secret lives at `projects/<project>/secrets/<prefix>--<tenant_id>--<name>`.
SM secret IDs only allow [a-zA-Z0-9_-], so we use '--' as a separator.

Each `set_secret` creates a new SecretVersion (and never deletes old ones -
SM keeps history). `get_secret` reads the latest version. `delete_secret`
removes the entire secret container.

The SM client is cached at the class level.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from google.api_core import exceptions as gax_exceptions
from google.cloud import secretmanager

from .protocol import SecretNotFoundError, validate_secret_name


T = TypeVar("T")
logger = logging.getLogger("mp.secrets.gsm")


class GSMSecrets:
    _shared_client: secretmanager.SecretManagerServiceClient | None = None

    def __init__(self, project_id: str, tenant_id: str, prefix: str = "mp") -> None:
        self._project_id = project_id
        self._tenant_id = tenant_id
        self._prefix = prefix

    @classmethod
    def _client(cls) -> secretmanager.SecretManagerServiceClient:
        if cls._shared_client is None:
            cls._shared_client = secretmanager.SecretManagerServiceClient()
        return cls._shared_client

    def _secret_id(self, name: str) -> str:
        validate_secret_name(name)
        return f"{self._prefix}--{self._tenant_id}--{name}"

    def _parent(self) -> str:
        return f"projects/{self._project_id}"

    def _secret_path(self, name: str) -> str:
        return f"{self._parent()}/secrets/{self._secret_id(name)}"

    def _version_path(self, name: str, version: str = "latest") -> str:
        return f"{self._secret_path(name)}/versions/{version}"

    @staticmethod
    async def _run(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))

    async def get_secret(self, name: str) -> bytes | None:
        path = self._version_path(name)
        try:
            response = await self._run(
                self._client().access_secret_version, request={"name": path}
            )
        except gax_exceptions.NotFound:
            return None
        return bytes(response.payload.data)

    async def set_secret(self, name: str, value: bytes) -> None:
        client = self._client()
        secret_id = self._secret_id(name)

        # Ensure the secret container exists (idempotent).
        try:
            await self._run(
                client.create_secret,
                request={
                    "parent": self._parent(),
                    "secret_id": secret_id,
                    "secret": {"replication": {"automatic": {}}},
                },
            )
            logger.info("Created secret container %s", secret_id)
        except gax_exceptions.AlreadyExists:
            pass

        await self._run(
            client.add_secret_version,
            request={
                "parent": self._secret_path(name),
                "payload": {"data": value},
            },
        )

    async def delete_secret(self, name: str) -> None:
        try:
            await self._run(
                self._client().delete_secret, request={"name": self._secret_path(name)}
            )
        except gax_exceptions.NotFound as exc:
            raise SecretNotFoundError(name) from exc
