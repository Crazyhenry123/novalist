"""Custom hooks for Strands agents."""

import logging
from strands.hooks.registry import HookRegistry, HookProvider
from strands.hooks.events import AfterModelCallEvent

logger = logging.getLogger(__name__)

MAX_CONTINUATION_RETRIES = 1


class MaxTokensContinuationHook(HookProvider):
    """Hook that automatically continues generation when max_tokens is reached.

    When the model hits max_tokens, instead of raising MaxTokensReachedException,
    this hook sets retry=True so the agent loop continues generating from where
    it left off. Limits retries to avoid infinite loops.
    """

    def __init__(self, max_retries: int = MAX_CONTINUATION_RETRIES):
        self._max_retries = max_retries
        self._retry_count = 0

    def register_hooks(self, registry: HookRegistry, **kwargs) -> None:
        registry.add_callback(AfterModelCallEvent, self._handle_max_tokens)

    async def _handle_max_tokens(self, event: AfterModelCallEvent) -> None:
        if event.stop_response is None:
            return

        if event.stop_response.stop_reason != "max_tokens":
            # Reset counter on successful non-max_tokens completions
            self._retry_count = 0
            return

        self._retry_count += 1

        if self._retry_count <= self._max_retries:
            logger.info(
                "max_tokens reached (attempt %d/%d) — continuing generation",
                self._retry_count,
                self._max_retries,
            )
            event.retry = True
        else:
            logger.warning(
                "max_tokens reached %d times — allowing exception to propagate",
                self._retry_count,
            )
            self._retry_count = 0
