import math


def eligible(model, *, block, score=None, cutoff=None, trusted=True):
    if not trusted:
        return False
    if model == "default":
        return block is True
    return (model == "carioca" and score is not None and cutoff is not None
            and math.isfinite(score) and 0 <= cutoff <= score <= 100)
