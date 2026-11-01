# Pinned DART XML vocabulary

`Dart4.xsd` is the unmodified official schema retrieved on 2026-10-16.

- Publisher: Financial Supervisory Service, [DART filing system](https://filer.fss.or.kr/).
- [Official editor update manifest](https://filer.fss.or.kr/dartedit/Bin/info_program.down):
  `Dtd.zip`, version `1,0,1,0`, `serverdir=/Resource/Dtd/Dtd.zip`.
- [Official archive](https://filer.fss.or.kr/dartedit/Resource/Dtd/Dtd.zip):
  SHA-256 `cb23d8d0d2d2b9589914ba0f992b72278e5571521869fd918a9099a637398eb2`.
- Archive member `Dart4.xsd`: 32,200 bytes; member timestamp
  `2025-08-22 18:04:46`; SHA-256
  `fafe75a2fde9854271c4568f6f510952292c0a829b411cc43b97f23a190ce6c2`.
  Its internal annotation is `ver1.1`; the archive timestamp is not a schema revision identifier.

The parser derives the declared element names and mixed-content parents from
this local file. There are 53 distinct element names, six mixed-content parents,
and no element wildcards, imports or includes. No network schema resolution or
automatic schema refresh occurs. The pinned bytes are covered by a checksum test
and preserved by `.gitattributes`.

The official file's CRLF, trailing padding and indentation remain unchanged.
Git whitespace-style exceptions apply only to this pinned schema; its checksum
still enforces the exact upstream bytes.

This supports a narrow literal-label recovery contract. It is **not** full XSD
validation: OpenDART exports can flatten `DOCUMENT-HEADER`, and this 2025
distribution does not prove historical schemas identical. A schema update needs
review and a parser identity change. See the [canonical parser contract](../../../docs/architecture/agent_runtime_contract.md#canonical-schema-bound-literal-labels) and [schema regression tests](../../../tests/test_parser_schema_literals.py).
