"""Read only HTTP statuses at the native research client's return boundary."""
import sys
import threading
import time
import promotion_observer

ERRORS = []
LOCK = threading.Lock()

def install(attempt):
    previous = sys.getprofile()
    previous_thread = threading.getprofile()
    ERRORS.clear()

    def observe(frame, event, returned):
        if previous is not None:
            previous(frame, event, returned)
        if event != 'return' or frame.f_code.co_name != '_send':
            return
        if not frame.f_code.co_filename.endswith('/argus/domain/research/perplexity_agent.py'):
            return
        response = frame.f_locals.get('response')
        status = getattr(response, 'status_code', None)
        if not isinstance(status, int) or status < 400:
            return
        record = {'kind': 'research_http_error', 'attempt': attempt,
                  'http_status': status, 'method': frame.f_locals.get('method'),
                  'time': time.time()}
        with LOCK:
            ERRORS.append(dict(record))
        promotion_observer.emit(record)

    sys.setprofile(observe)
    threading.setprofile(observe)

    def finish():
        sys.setprofile(previous)
        threading.setprofile(previous_thread)
        with LOCK:
            return [dict(record) for record in ERRORS]
    return finish
