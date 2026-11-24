import math


def eligible(model, *, block, score=None, cutoff=None, trusted=True):
    """Pi-hole eligibility for a `scoring.api.ScoreModel` (a StrEnum compared by value).

    The domain does not import `scoring.api`, which carries persistence dependencies.
    """
    if not trusted:
        return False
    if model == "default":
        return block is True
    return (model == "carioca" and score is not None and cutoff is not None
            and math.isfinite(score) and 0 <= cutoff <= score <= 100)
