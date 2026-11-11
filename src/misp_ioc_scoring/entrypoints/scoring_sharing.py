"""Reserved composition root; CARIOCA activation remains subject to approval."""
from misp_ioc_scoring.shared.errors import OperationalError
from misp_ioc_scoring.shared.logging import configure_logging
import logging


def main():
    raise OperationalError('scoring_sharing_implementation_pending')


if __name__ == '__main__':
    configure_logging()
    try:
        main()
    except OperationalError as error:
        logging.getLogger(__name__).error('scoring_sharing_unavailable', extra={
            'event': 'scoring_sharing_unavailable', 'code': error.code})
        raise SystemExit(1) from None
