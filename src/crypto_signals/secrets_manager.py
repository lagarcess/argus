"""
Google Secret Manager Integration.

This module provides secure secret loading from Google Cloud Secret Manager
for containerized deployments. It falls back to environment variables for
local development.
"""

import os
from typing import Any, Dict, Optional

from loguru import logger


class SecretManager:
    """Manages loading secrets from Google Secret Manager or environment variables."""

    def __init__(self, project_id: Optional[str] = None):
        """
        Initialize the SecretManager.

        Args:
            project_id: GCP ID. If None, uses GOOGLE_CLOUD_PROJECT env var.
        """
        self.project_id = project_id or os.environ.get("GOOGLE_CLOUD_PROJECT")
        self._client: Any = None
        self._use_secret_manager = self._should_use_secret_manager()

    def _should_use_secret_manager(self) -> bool:
        """
        Determine if Secret Manager should be used.

        Returns:
            bool: True if running in cloud (has project_id and no .env file)
        """
        # If explicitly disabled via env var, don't use Secret Manager
        if os.environ.get("DISABLE_SECRET_MANAGER", "").lower() == "true":
            logger.info("Secret Manager explicitly disabled via DISABLE_SECRET_MANAGER")
            return False

        # If .env exists, we're in local development
        if os.path.exists(".env"):
            logger.info("Found .env file, using local environment variables")
            return False

        # If we have a project ID, assume cloud deployment
        if self.project_id:
            logger.info(
                f"No .env file found, using Secret Manager for project: {self.project_id}"
            )
            return True

        logger.warning(
            "No .env file and no GOOGLE_CLOUD_PROJECT set. "
            "Using environment variables only."
        )
        return False

    def _get_client(self):
        """Lazy-load the Secret Manager client."""
        if self._client is None and self._use_secret_manager:
            try:
                from google.cloud import secretmanager

                self._client = secretmanager.SecretManagerServiceClient()
                logger.info("Initialized Secret Manager client")
            except Exception as e:
                logger.error(
                    "Failed to load Secret Manager client.",
                    extra={"error": str(e)},
                )
                raise RuntimeError(
                    "Failed to load Secret Manager. Ensure google-cloud-secret-manager"
                    "is installed and credentials are configured."
                ) from e
        return self._client

    def get_secret(
        self, secret_name: str, version: str = "latest", default: Optional[str] = None
    ) -> Optional[str]:
        """
        Retrieve a secret from Secret Manager or environment variables.

        Priority:
        1. Environment variable (for local dev or explicit overrides)
        2. Google Secret Manager (for cloud deployments)
        3. Default value (if provided)

        Args:
            secret_name: Name of the secret (e.g., "ALPACA_API_KEY")
            version: Secret version (default: "latest")
            default: Default value if secret not found

        Returns:
            str: Secret value or None if not found

        Raises:
            RuntimeError: If secret is required but not found
        """
        # First check environment variable (highest priority)
        env_value = os.environ.get(secret_name)
        if env_value:
            logger.debug(f"Loaded {secret_name} from environment variable")
            return env_value

        # If not using Secret Manager, return default
        if not self._use_secret_manager:
            if default is not None:
                logger.debug(f"Using default value for {secret_name}")
                return default
            return None

        # Try Secret Manager
        try:
            client = self._get_client()
            if not client:
                return default

            secret_path = (
                f"projects/{self.project_id}/secrets/{secret_name}/versions/{version}"
            )
            response = client.access_secret_version(request={"name": secret_path})
            secret_value = str(response.payload.data.decode("UTF-8"))
            logger.info(f"Loaded {secret_name} from Secret Manager")
            return secret_value

        except Exception as e:
            logger.warning(
                f"Failed to load {secret_name} from Secret Manager.",
                extra={"secret_name": secret_name, "error": str(e)},
            )
            if default is not None:
                logger.info(f"Using default value for {secret_name}")
                return default
            return None

    def load_secrets_to_env(self, secret_names: Dict[str, Optional[str]]) -> bool:
        """
        Load multiple secrets and set them as environment variables.

        Args:
            secret_names: Dict mapping secret names to default values
                         e.g., {"ALPACA_API_KEY": None, "TEST_MODE": "true"}

        Returns:
            bool: True if all required secrets loaded, False otherwise
        """
        missing_secrets = []

        for secret_name, default_value in secret_names.items():
            # Skip if already in environment
            if os.environ.get(secret_name):
                logger.debug(f"{secret_name} already in environment, skipping")
                continue

            secret_value = self.get_secret(secret_name, default=default_value)

            if secret_value:
                os.environ[secret_name] = secret_value
            elif default_value is None:
                # Required secret is missing
                missing_secrets.append(secret_name)

        if missing_secrets:
            logger.error(f"Missing required secrets: {', '.join(missing_secrets)}")
            return False

        logger.info("All secrets loaded successfully")
        return True


def init_secrets() -> bool:
    """
    Initialize secrets for the application.

    This should be called at application startup, before loading Settings.

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from dotenv import load_dotenv

        # Load .env file if present
        load_dotenv()

        # Get project ID from environment first
        project_id = os.environ.get("GOOGLE_CLOUD_PROJECT")

        secret_manager = SecretManager(project_id=project_id)

        # Define required and optional secrets
        secrets = {
            "GOOGLE_CLOUD_PROJECT": None,
            # Optional secrets with defaults
            "ALPACA_PAPER_TRADING": "true",
            "TEST_MODE": "true",
            # Production webhooks - optional here, validated by Pydantic when TEST_MODE=false
            # Empty string = optional (won't fail loading), None = required (would fail)
            "LIVE_CRYPTO_DISCORD_WEBHOOK_URL": "",
            "LIVE_STOCK_DISCORD_WEBHOOK_URL": "",
        }

        # In SMOKE_TEST mode, we don't need real credentials
        if os.environ.get("APP_MODE") != "SMOKE_TEST":
            secrets["ALPACA_API_KEY"] = None
            secrets["ALPACA_SECRET_KEY"] = None
            secrets["TEST_DISCORD_WEBHOOK"] = None

        success = secret_manager.load_secrets_to_env(secrets)

        if not success:
            logger.error("Failed to load required secrets")
            return False

        logger.info("Secret initialization complete")
        return True

    except Exception as e:
        logger.error(
            "Secret initialization failed.",
            exc_info=True,
            extra={"error": str(e)},
        )
        return False
