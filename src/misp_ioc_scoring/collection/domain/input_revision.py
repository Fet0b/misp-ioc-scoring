"""Only CARIOCA inputs affect revision; collection timestamps and tags do not.

Why each field counts:
- `misp_type`, `category`, `to_ids`, `removed_at`: population and CADE category counts;
- `orgc_uuid`: Source (FeedRank) organization;
- `source_created_at`: order of first publication in FeedRank;
- `published`: FeedRank only counts published observations;
- `source_modified_at`: freshness time `t` of the Attribute component;
- `event_threat_level`, `event_analysis`: TL and SA of the Event component;
- `event_uuid`: groups observations of one event for CADE.
"""
RELEVANT_FIELDS = (
    'misp_type', 'category', 'to_ids', 'removed_at', 'orgc_uuid', 'source_created_at',
    'source_modified_at', 'event_threat_level', 'event_analysis', 'event_uuid', 'published',
)


def inputs_changed(before, after) -> bool:
    return any(getattr(before, key) != getattr(after, key) for key in RELEVANT_FIELDS)
