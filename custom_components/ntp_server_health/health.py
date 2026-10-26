"""Shared health summary for all configured NTP servers."""
from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .ntp import Result

AGGREGATE_UNIQUE_ID = 'ntp_server_health_problem'


def summarize_health(samples: Iterable[tuple[str, Result | None, bool]]) -> dict:
    """Report every non-OK server; never treat a failed update as healthy."""
    problems = []
    server_count = 0
    for host, result, update_success in samples:
        server_count += 1
        if not update_success or result is None:
            problems.append({
                'server': host,
                'status': 'UNAVAILABLE',
                'reason': 'Monitoring update unavailable',
                'root_dispersion_ms': None,
                'stratum': None,
            })
        elif result.status != 'OK':
            problems.append({
                'server': host,
                'status': result.status,
                'reason': result.reason,
                'root_dispersion_ms': result.root_dispersion_ms,
                'stratum': result.stratum,
            })
    return {
        'server_count': server_count,
        'problem_count': len(problems),
        'problems': problems,
    }
