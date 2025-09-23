import cProfile
import pstats
import io
import functools

def profiler(func):
    profiler_inst = cProfile.Profile()
    calls: int = 0

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        nonlocal calls
        profiler_inst.enable()
        result = func(*args, **kwargs)
        profiler_inst.disable()
        calls += 1 # type: ignore

        # Print stats for this call
        buf = io.StringIO()
        pstats.Stats(profiler_inst, stream=buf).sort_stats('cumulative').print_stats()
        print(f"[Profiler] Call {calls} stats:\n{buf.getvalue()}")
        return result

    return wrapper

import sys
import time
import functools
import linecache
import os

from collections import defaultdict

def line_by_line_profiler(func):
    """
    Decorator that times each line inside func, then prints a report
    including total time spent executing profiled lines.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        # Map (filename, lineno) -> [total_time, hit_count]
        stats = defaultdict(lambda: [0.0, 0])
        last = {"t": None, "key": None}

        def tracer(frame, event, arg):
            if event != "line":
                return tracer
            co = frame.f_code
            # Only trace lines in our target function's code object
            if co is not func.__code__:
                return tracer

            now = time.perf_counter()
            lineno = frame.f_lineno
            filename = co.co_filename
            key = (filename, lineno)

            if last["t"] is not None and last["key"] is not None:
                elapsed = now - last["t"]
                stats[last["key"]][0] += elapsed
                stats[last["key"]][1] += 1

            last["t"] = now  # type: ignore
            last["key"] = key  # type: ignore
            return tracer

        # Install tracer, call function, then disable tracer
        sys.settrace(tracer)
        try:
            result = func(*args, **kwargs)
        finally:
            sys.settrace(None)

            # Print report sorted by total time descending
            print(f"\n[LineProfiler] Profiling results for {func.__name__}")
            header = f"{'File':<12} {'Line':>5} {'Hits':>8} {'Total(s)':>12} {'Per Hit(s)':>12} Code"
            print(header)
            print("-" * len(header))

            total_profiled = 0.0
            for (fname, lineno), (tot, cnt) in sorted(stats.items(), key=lambda kv: kv[1][0], reverse=True):
                file_only = os.path.basename(fname)
                source = linecache.getline(fname, lineno).rstrip()
                per = tot / cnt if cnt else 0
                total_profiled += tot
                print(f"{file_only:<12} {lineno:5d} {cnt:8d} {tot:12.6f} {per:12.6f} {source}")

            # Print total time spent in profiled lines
            print(f"\n[LineProfiler] Total profiled time: {total_profiled:.6f} seconds")

        return result

    return wrapper