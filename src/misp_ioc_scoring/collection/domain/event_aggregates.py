CATEGORIES = (
    'Internal reference', 'Targeting data', 'Antivirus detection', 'Payload delivery',
    'Artifacts dropped', 'Payload installation', 'Persistence mechanism',
    'Network activity', 'Payload type', 'Attribution', 'External analysis',
    'Financial fraud', 'Support Tool', 'Social network', 'Person', 'Other',
)


def category_counts(observations) -> dict[str, int]:
    counts = dict.fromkeys(CATEGORIES, 0)
    for observation in observations:
        if observation.removed_at is None and observation.category in counts:
            counts[observation.category] += 1
    return counts
