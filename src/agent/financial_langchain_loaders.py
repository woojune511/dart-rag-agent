"""Lazy LangChain loader helpers for agent runtime paths."""

from __future__ import annotations

from typing import Any, Mapping


def _chat_prompt_template_from_template(template: str) -> Any:
    from langchain_core.prompts import ChatPromptTemplate

    return ChatPromptTemplate.from_template(template)


def _str_output_parser() -> Any:
    from langchain_core.output_parsers import StrOutputParser

    return StrOutputParser()


def _runnable_passthrough() -> Any:
    from langchain_core.runnables import RunnablePassthrough

    return RunnablePassthrough()


def _document(*, page_content: str, metadata: Mapping[str, Any]) -> Any:
    from langchain_core.documents import Document

    return Document(page_content=page_content, metadata=dict(metadata))
