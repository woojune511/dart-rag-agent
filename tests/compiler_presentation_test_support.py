"""Read actual v7 quote surfaces; references do not create a second surface."""


def bundle_text(payload, bundle_id):
    return next(body["source_text"] for row in payload["source_readings"] for body in row["bodies"]
                if body["source_bundle_id"] == bundle_id)


def context_surfaces(payload):
    return {fragment["context_id"]: fragment["source_text"]
            for row in payload["source_readings"]
            for key in ("enclosing_contexts", "preceding_contexts", "following_contexts")
            for fragment in row[key] if "source_text" in fragment}
