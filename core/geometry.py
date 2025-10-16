import numpy as np
import zlib

def crc32_array(a: np.ndarray) -> int:
    if not a.size: return 0
    ac = np.ascontiguousarray(a)
    mv = memoryview(ac.data).cast("B")
    return zlib.adler32(mv)