from __future__ import annotations

import pytest

from lele_manager import factual_verification_composition as composition


def test_factual_verification_is_disabled_without_explicit_provider(
    monkeypatch,
) -> None:
    monkeypatch.delenv(
        "LELE_FACTUAL_VERIFICATION_PROVIDER",
        raising=False,
    )

    runtime = composition.resolve_factual_verification_runtime()

    assert runtime is None


def test_unknown_provider_fails_closed(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_FACTUAL_VERIFICATION_PROVIDER",
        "definitely-not-a-provider",
    )

    with pytest.raises(
        composition.FactualVerificationConfigurationError
    ):
        composition.resolve_factual_verification_runtime()


def test_provider_name_is_normalized(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_FACTUAL_VERIFICATION_PROVIDER",
        "  disabled  ",
    )

    runtime = composition.resolve_factual_verification_runtime()

    assert runtime is None


def test_disabled_provider_never_builds_network_runtime(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_FACTUAL_VERIFICATION_PROVIDER",
        "disabled",
    )

    called = False

    def forbidden_builder():
        nonlocal called
        called = True
        raise AssertionError(
            "disabled factual verification must not build a provider"
        )

    monkeypatch.setattr(
        composition,
        "_build_external_runtime",
        forbidden_builder,
    )

    runtime = composition.resolve_factual_verification_runtime()

    assert runtime is None
    assert called is False


def test_openai_provider_is_not_yet_selectable_in_production(
    monkeypatch,
) -> None:
    monkeypatch.setenv(
        "LELE_FACTUAL_VERIFICATION_PROVIDER",
        "openai",
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        "sk-test-user-owned-secret",
    )

    with pytest.raises(
        composition.FactualVerificationConfigurationError,
        match="not yet qualified",
    ):
        composition.resolve_factual_verification_runtime(
            store=object(),
        )


def test_openai_provider_rejection_does_not_expose_api_key(
    monkeypatch,
) -> None:
    secret = "sk-test-do-not-leak"

    monkeypatch.setenv(
        "LELE_FACTUAL_VERIFICATION_PROVIDER",
        "openai",
    )
    monkeypatch.setenv(
        "OPENAI_API_KEY",
        secret,
    )

    with pytest.raises(
        composition.FactualVerificationConfigurationError,
    ) as exc_info:
        composition.resolve_factual_verification_runtime(
            store=object(),
        )

    assert secret not in str(exc_info.value)


def test_external_builder_composes_openai_service(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        composition,
        "OpenAIClaimExtractor",
        lambda *, api_key: ("extractor", api_key),
    )
    monkeypatch.setattr(
        composition,
        "OpenAIEvidenceRetriever",
        lambda *, api_key: ("retriever", api_key),
    )
    monkeypatch.setattr(
        composition,
        "OpenAIEvidenceAssessor",
        lambda *, api_key: ("assessor", api_key),
    )

    captured: dict[str, object] = {}

    class FakeService:
        def __init__(
            self,
            *,
            extractor,
            retriever,
            assessor,
            store,
            now,
        ) -> None:
            captured.update(
                {
                    "extractor": extractor,
                    "retriever": retriever,
                    "assessor": assessor,
                    "store": store,
                    "now": now,
                }
            )

    monkeypatch.setattr(
        composition,
        "FactualVerificationService",
        FakeService,
    )

    store = object()

    runtime = composition._build_external_runtime(
        provider="openai",
        api_key="sk-user-owned",
        store=store,
    )

    assert isinstance(runtime, FakeService)
    assert captured["extractor"] == (
        "extractor",
        "sk-user-owned",
    )
    assert captured["retriever"] == (
        "retriever",
        "sk-user-owned",
    )
    assert captured["assessor"] == (
        "assessor",
        "sk-user-owned",
    )
    assert captured["store"] is store
    assert callable(captured["now"])


def test_external_builder_rejects_unknown_provider() -> None:
    with pytest.raises(
        composition.FactualVerificationConfigurationError,
        match="unsupported",
    ):
        composition._build_external_runtime(
            provider="unknown",
            api_key="secret",
            store=object(),
        )
