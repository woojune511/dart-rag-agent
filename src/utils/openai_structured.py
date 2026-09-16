"""Strict OpenAI transport with the original application schema still authoritative."""

from copy import deepcopy
import json

from jsonschema import Draft202012Validator
from langchain_core.runnables import RunnableLambda
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


def strict_openai_schema(schema):
    """Require explicit fields, removing default annotations without inventing values.

    The projection is intentionally narrow: fixed object properties, arrays and
    unions. Constraints, references, enum order and descriptions stay intact.
    Unsupported open dictionaries and composition fail before a provider call.
    Local validity is not evidence that a provider will accept this schema.
    """
    source = schema.model_json_schema() if isinstance(schema, type) and issubclass(schema, BaseModel) else schema
    result = deepcopy(source)

    def visit(node):
        if not isinstance(node, dict):
            raise ValueError("OpenAI transport requires object schemas")
        if any(key in node for key in ("allOf", "oneOf", "not", "if", "then", "else", "dependentRequired", "dependentSchemas")):
            raise ValueError("Unsupported OpenAI schema composition")
        node.pop("default", None)
        if node.get("type") == "object":
            if node.get("additionalProperties", False) is not False:
                raise ValueError("OpenAI transport requires fixed object properties")
            properties = node.setdefault("properties", {})
            node["additionalProperties"] = False
            node["required"] = list(properties)
        for key in ("properties", "$defs", "definitions"):
            for child in node.get(key, {}).values():
                visit(child)
        if "items" in node:
            visit(node["items"])
        for child in node.get("anyOf", []):
            visit(child)

    visit(result)
    if result.get("type") != "object" or "anyOf" in result:
        raise ValueError("OpenAI transport requires an object root")
    Draft202012Validator.check_schema(result)
    return result


class StrictOpenAIChatModel(ChatOpenAI):
    """Validate both the stricter wire and the unchanged Pydantic runtime model."""

    def with_structured_output(self, schema=None, *, method="json_schema", include_raw=False, strict=True, **kwargs):
        if method != "json_schema" or strict is not True or kwargs:
            raise ValueError("Only strict JSON schema output is supported by this route")
        wire = strict_openai_schema(schema)
        validator = Draft202012Validator(wire)
        delegate = self.bind(response_format={"type": "json_schema", "json_schema": {
            "name": wire.get("title", "structured_response"), "strict": True, "schema": wire}})

        def invoke(value, config):
            # Keep invocation on the caller's thread so its usage/phase scope
            # survives; RunnableMap's raw-output branch creates a worker thread.
            raw = delegate.invoke(value, config=config)
            result = {"raw": raw, "parsed": None, "parsing_error": None}
            try:
                metadata = raw.response_metadata
                if metadata.get("status", "completed") != "completed" or metadata.get("finish_reason") in {"length", "content_filter"}:
                    raise ValueError("OpenAI structured response is incomplete")
                content = raw.content
                text = content if isinstance(content, str) else "".join(
                    block["text"] for block in content if isinstance(block, dict) and block.get("type") in {"text", "output_text"})
                parsed = json.loads(text)
                validator.validate(parsed)
                result["parsed"] = schema.model_validate(parsed) if isinstance(schema, type) and issubclass(schema, BaseModel) else parsed
            except Exception as error:
                result["parsing_error"] = error
            if include_raw:
                return result
            if result.get("parsing_error") is not None:
                raise result["parsing_error"]
            return result["parsed"]

        return RunnableLambda(invoke)
