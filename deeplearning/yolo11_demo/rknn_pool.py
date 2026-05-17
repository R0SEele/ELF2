from concurrent.futures import ThreadPoolExecutor
from queue import Queue

from rknnlite.api import RKNNLite


def _core_mask(index):
    masks = (
        RKNNLite.NPU_CORE_0,
        RKNNLite.NPU_CORE_1,
        RKNNLite.NPU_CORE_2,
    )
    return masks[index % len(masks)]


def init_rknn(model_path, index=-1):
    rknn = RKNNLite()
    ret = rknn.load_rknn(model_path)
    if ret != 0:
        raise RuntimeError("load RKNN model failed: {} ({})".format(model_path, ret))

    if index < 0:
        ret = rknn.init_runtime(core_mask=RKNNLite.NPU_CORE_0_1_2)
    else:
        ret = rknn.init_runtime(core_mask=_core_mask(index))

    if ret != 0:
        rknn.release()
        raise RuntimeError("init RKNN runtime failed: {}".format(ret))

    return rknn


class RKNNPoolExecutor:
    def __init__(self, model_path, workers, infer_func):
        if workers < 1:
            raise ValueError("workers must be >= 1")

        self._workers = workers
        self._infer_func = infer_func
        self._queue = Queue()
        self._rknns = []
        self._pool = None
        self._submit_count = 0
        try:
            self._rknns = [init_rknn(model_path, i) for i in range(workers)]
            self._pool = ThreadPoolExecutor(max_workers=workers)
        except Exception:
            for rknn in self._rknns:
                rknn.release()
            raise

    def put(self, frame):
        rknn = self._rknns[self._submit_count % self._workers]
        self._queue.put(self._pool.submit(self._infer_func, rknn, frame))
        self._submit_count += 1

    def get(self):
        if self._queue.empty():
            return None, False
        future = self._queue.get()
        return future.result(), True

    def release(self):
        if self._pool is not None:
            self._pool.shutdown(wait=True)
        for rknn in self._rknns:
            rknn.release()
