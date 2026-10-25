"""Bound expensive work; rejected jobs are never queued without a limit."""
from concurrent.futures import ThreadPoolExecutor
from threading import BoundedSemaphore
from tornado.web import HTTPError

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="gff")
_slots = BoundedSemaphore(4)


def submit(function, *args):
    if not _slots.acquire(blocking=False):
        raise HTTPError(503, reason="Analysis workers are busy; try again shortly")
    try:
        future = _executor.submit(function, *args)
    except BaseException:
        _slots.release()
        raise
    future.add_done_callback(lambda _: _slots.release())
    return future
