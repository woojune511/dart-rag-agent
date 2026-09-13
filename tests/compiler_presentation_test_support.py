"""Reconstruct retained text for equality checks, not cross-segment quote authority."""


def surface_text(surface):
    if 'pieces' in surface:
        return ''.join(piece['text'] for piece in surface['pieces'])
    if 'source_segments' in surface:
        return ''.join(segment['source_text'] for segment in surface['source_segments'])
    return surface['source_text']


def bundle_text(payload, bundle_id):
    return next(surface_text(body) for row in payload["source_readings"] for body in row["bodies"]
                if body["source_bundle_id"] == bundle_id)


def context_surfaces(payload):
    return {fragment["context_id"]: surface_text(fragment)
            for row in payload["source_readings"]
            for key in ("enclosing_contexts", "preceding_contexts", "following_contexts")
            for fragment in row[key] if 'source_text' in fragment or 'source_segments' in fragment or 'pieces' in fragment}
