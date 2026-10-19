"""Optional semantic runtime construction; no inference or availability skips."""

from lele_manager.semantic_composition import (
    SEMANTIC_MODEL_ENV,
    SEMANTIC_PROVIDER_ENV,
    resolve_semantic_runtime,
)


def test_explicit_ollama_configuration_builds_local_runtime() -> None:
    runtime = resolve_semantic_runtime(
        {
            SEMANTIC_PROVIDER_ENV: " OLLAMA ",
            SEMANTIC_MODEL_ENV: " qwen2.5:1.5b-instruct ",
        }
    )

    assert runtime is not None
    assert runtime.strategy == "semantic"
    assert runtime.provider == "ollama"
    assert runtime.model == "qwen2.5:1.5b-instruct"
    assert runtime.locality == "local"
    assert runtime.endpoint == "http://127.0.0.1:11434"
    assert runtime.extraction_metadata == {
        "strategy": "semantic",
        "provider": "ollama",
        "model": "qwen2.5:1.5b-instruct",
        "locality": "local",
        "endpoint": "http://127.0.0.1:11434",
    }



def test_runtime_does_not_read_remote_credentials_or_endpoint_overrides() -> None:
    runtime = resolve_semantic_runtime(
        {
            SEMANTIC_PROVIDER_ENV: "ollama",
            SEMANTIC_MODEL_ENV: "local-model",
            "OPENAI_API_KEY": "secret-openai",
            "DEEPSEEK_API_KEY": "secret-deepseek",
            "LELE_SEMANTIC_ENDPOINT": "https://example.invalid",
        }
    )

    assert runtime is not None
    assert runtime.provider == "ollama"
    assert runtime.locality == "local"
    assert runtime.endpoint == "http://127.0.0.1:11434"
    assert "secret" not in repr(runtime.extraction_metadata)
    assert "example.invalid" not in repr(runtime.extraction_metadata)
