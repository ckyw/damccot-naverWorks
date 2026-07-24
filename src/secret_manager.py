from __future__ import annotations

from google.cloud import secretmanager


class RefreshTokenSecretStore:
    """Stores rotated refresh tokens as new Secret Manager versions."""

    def __init__(self, secret_resource: str):
        self._secret_resource = secret_resource
        self._client = secretmanager.SecretManagerServiceClient()

    def persist(self, refresh_token: str) -> None:
        self._client.add_secret_version(
            request={
                "parent": self._secret_resource,
                "payload": {"data": refresh_token.encode("utf-8")},
            }
        )


def read_secret(project_id: str, secret_name: str) -> str:
    """Reads the latest secret version using Application Default Credentials."""
    resource = (
        secret_name
        if secret_name.startswith("projects/")
        else f"projects/{project_id}/secrets/{secret_name}"
    )
    client = secretmanager.SecretManagerServiceClient()
    response = client.access_secret_version(request={"name": f"{resource}/versions/latest"})
    return response.payload.data.decode("utf-8")
