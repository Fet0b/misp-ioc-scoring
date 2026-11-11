from misp_ioc_scoring.shared.errors import OperationalError


def guard_removals(active_count: int, removal_count: int, maximum_ratio: float) -> None:
    if active_count and removal_count / active_count > maximum_ratio:
        raise OperationalError('collection_removal_limit_exceeded')
