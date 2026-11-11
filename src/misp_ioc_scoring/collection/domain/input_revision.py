"""Only CARIOCA inputs affect revision; collection timestamps and tags do not."""
RELEVANT_FIELDS = (
    'misp_type', 'category', 'to_ids', 'removed_at', 'orgc_uuid', 'source_created_at',
    'source_modified_at', 'event_threat_level', 'event_analysis', 'event_uuid',
)


def inputs_changed(before, after) -> bool:
    return any(getattr(before, key) != getattr(after, key) for key in RELEVANT_FIELDS)
