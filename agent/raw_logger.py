"""
Пишет сырые UDP пакеты в бинарный файл — страховка на случай сбоя.
Формат: [4 байта длина][данные пакета] повторяется.
Позволяет реплеить гонку из лога если что-то пошло не так.
"""
import struct
import time
from pathlib import Path
from datetime import datetime
from agent.config import RAW_LOG_DIR


class RawLogger:
    def __init__(self):
        self._file = None
        self._path: Path | None = None

    def start_session(self, track_id: int) -> None:
        """Открывает новый файл лога при старте сессии."""
        self._close()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._path = RAW_LOG_DIR / f"session_{ts}_track{track_id}.bin"
        self._file = open(self._path, "wb")
        print(f"[RAW LOG] Started: {self._path}")

    def write(self, data: bytes) -> None:
        if self._file and not self._file.closed:
            # 4 байта размера + сами данные
            self._file.write(struct.pack("<I", len(data)))
            self._file.write(data)

    def stop(self) -> Path | None:
        path = self._path
        self._close()
        return path

    def _close(self) -> None:
        if self._file and not self._file.closed:
            self._file.flush()
            self._file.close()
        self._file = None
        self._path = None

    def __del__(self):
        self._close()


def replay_log(log_path: Path):
    """
    Генератор — читает пакеты из бинарного лога.
    Использовать для ручного реплея если результаты не отправились.
    """
    with open(log_path, "rb") as f:
        while True:
            size_bytes = f.read(4)
            if len(size_bytes) < 4:
                break
            size = struct.unpack("<I", size_bytes)[0]
            data = f.read(size)
            if len(data) < size:
                break
            yield data
