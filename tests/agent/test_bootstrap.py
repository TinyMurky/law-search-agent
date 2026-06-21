from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent import bootstrap


def _patch_dependencies(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, MagicMock]:
    """把 build_agent_from_env() 內部建立的所有依賴換成 MagicMock。"""
    reader_instance = MagicMock()
    reader_instance.load.return_value = ["law1", "law2"]
    reader_instance.build_name_to_pcode.return_value = {}
    monkeypatch.setattr(
        bootstrap, "LawReader", MagicMock(return_value=reader_instance)
    )

    extractor_instance = MagicMock()
    monkeypatch.setattr(
        bootstrap,
        "CitationExtractor",
        MagicMock(return_value=extractor_instance),
    )

    law_graph = MagicMock()
    graph_builder_instance = MagicMock()
    graph_builder_instance.build.return_value = law_graph
    monkeypatch.setattr(
        bootstrap,
        "LawGraphBuilder",
        MagicMock(return_value=graph_builder_instance),
    )

    chunk_builder = MagicMock()
    chunk_builder.is_populated.return_value = True
    monkeypatch.setattr(
        bootstrap, "ChunkBuilder", MagicMock(return_value=chunk_builder)
    )

    monkeypatch.setattr(
        bootstrap, "GoogleGenerativeAIEmbeddings", MagicMock()
    )
    llm = MagicMock()
    monkeypatch.setattr(
        bootstrap, "ChatGoogleGenerativeAI", MagicMock(return_value=llm)
    )

    compiled_graph = MagicMock()
    build_graph_fn = MagicMock(return_value=compiled_graph)
    monkeypatch.setattr(bootstrap, "build_graph", build_graph_fn)

    monkeypatch.setattr(bootstrap, "load_dotenv", MagicMock())
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")

    return {
        "law_graph": law_graph,
        "chunk_builder": chunk_builder,
        "build_graph_fn": build_graph_fn,
        "compiled_graph": compiled_graph,
    }


def test_build_agent_from_env_returns_compiled_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocks = _patch_dependencies(monkeypatch)

    result = bootstrap.build_agent_from_env()

    assert result is mocks["compiled_graph"]
    mocks["build_graph_fn"].assert_called_once()


def test_build_agent_from_env_passes_built_deps_to_build_graph(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocks = _patch_dependencies(monkeypatch)

    bootstrap.build_agent_from_env()

    _, args, _kwargs = mocks["build_graph_fn"].mock_calls[0]
    _llm, chunk_builder_arg, law_graph_arg = args
    assert chunk_builder_arg is mocks["chunk_builder"]
    assert law_graph_arg is mocks["law_graph"]


def test_build_agent_from_env_exits_when_chunks_not_built(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mocks = _patch_dependencies(monkeypatch)
    mocks["chunk_builder"].is_populated.return_value = False

    with pytest.raises(SystemExit):
        bootstrap.build_agent_from_env()
