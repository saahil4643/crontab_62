"""
worker_shutdown.py — Process lifecycle utilities for the Cron-62 worker.

Provides:
  - ShutdownController   : cooperative shutdown request/check
  - acquire/release_instance_lock : advisory file lock (cross-platform)
  - existing_worker_pid  : read PID file and probe liveness
  - write_pid_file / remove_pid_file
  - flush_log_handlers
  - heartbeat_loop       : async task that logs a heartbeat every N seconds
  - install_signal_handlers : SIGINT / SIGTERM -> ShutdownController
  - log_run_summary
  - interruptible_sleep  : await-able sleep that wakes on shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# ---- Heartbeat ----------------------------------------------------------

HEARTBEAT_INTERVAL_SECONDS: float = float(
    os.environ.get("RESILIENT_HEARTBEAT_INTERVAL_SECONDS", "120")
)


# ---- ShutdownController ------------------------------------------------


class ShutdownController:
    """Shared state for cooperative shutdown across coroutines."""

    def __init__(self) -> None:
        self._requested: bool = False
        self._reason: str | None = None
        self.progress: dict[str, Any] = {}

    def request_shutdown(self, reason: str = "unspecified") -> None:
        if not self._requested:
            self._requested = True
            self._reason = reason
            logger.info("Shutdown requested: %s", reason)

    def is_requested(self) -> bool:
        return self._requested

    @property
    def reason(self) -> str | None:
        return self._reason


# ---- Signal handling ---------------------------------------------------


def install_signal_handlers(
    shutdown: ShutdownController,
    log: logging.Logger | None = None,
) -> None:
    """Install SIGINT/SIGTERM handlers to request cooperative shutdown."""
    _log = log or logger

    def _handler(signum: int, _frame: Any) -> None:
        name = signal.Signals(signum).name
        _log.warning("Signal %s received -- requesting shutdown", name)
        shutdown.request_shutdown(f"signal:{name}")

    try:
        signal.signal(signal.SIGINT, _handler)
    except (OSError, ValueError):
        pass
    try:
        signal.signal(signal.SIGTERM, _handler)
    except (OSError, ValueError):
        pass


# ---- PID file ----------------------------------------------------------


def write_pid_file(pid_file: Path) -> None:
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(f"{os.getpid()}\n", encoding="utf-8")
    logger.debug("PID %d written to %s", os.getpid(), pid_file)


def remove_pid_file(pid_file: Path) -> None:
    try:
        pid_file.unlink(missing_ok=True)
    except Exception as exc:
        logger.debug("remove_pid_file: %s", exc)


def existing_worker_pid(pid_file: Path) -> int | None:
    """Return the PID from *pid_file* if a process with that PID is alive, else None."""
    if not pid_file.is_file():
        return None
    try:
        raw = pid_file.read_text(encoding="utf-8").strip()
        pid = int(raw)
    except (ValueError, OSError):
        return None

    if pid <= 0:
        return None

    try:
        os.kill(pid, 0)
        return pid
    except OSError:
        return None


# ---- Advisory instance lock --------------------------------------------


def acquire_instance_lock(lock_file: Path) -> int | None:
    """
    Open and advisory-lock *lock_file*.

    Returns the open file descriptor on success, None if already locked.
    On Windows (where fcntl is unavailable) this always succeeds -- the
    PID-file check in run_resilient_sheet.py is the primary guard there.
    """
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
    except OSError as exc:
        logger.warning("acquire_instance_lock: cannot open lock file: %s", exc)
        return None

    if sys.platform != "win32":
        try:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            os.close(fd)
            return None
        except Exception as exc:
            logger.debug("acquire_instance_lock flock: %s", exc)
    return fd


def release_instance_lock(fd: int | None) -> None:
    if fd is None:
        return
    try:
        if sys.platform != "win32":
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
    except Exception:
        pass
    try:
        os.close(fd)
    except Exception:
        pass


# ---- Log helpers --------------------------------------------------------


def flush_log_handlers() -> None:
    for handler in logging.root.handlers:
        try:
            handler.flush()
        except Exception:
            pass


def log_run_summary(
    log: logging.Logger,
    *,
    status: str,
    reason: str | None = None,
    elapsed_sec: float | None = None,
    progress: dict | None = None,
    exit_code: int | None = None,
) -> None:
    parts = [f"status={status}"]
    if reason:
        parts.append(f"reason={reason}")
    if elapsed_sec is not None:
        parts.append(f"elapsed={elapsed_sec:.1f}s")
    if exit_code is not None:
        parts.append(f"exit_code={exit_code}")
    if progress:
        for k, v in progress.items():
            parts.append(f"{k}={v}")
    log.info("RUN_SUMMARY | %s", " | ".join(parts))


# ---- Heartbeat loop ----------------------------------------------------


async def heartbeat_loop(
    log: logging.Logger,
    shutdown: ShutdownController,
    interval: float = HEARTBEAT_INTERVAL_SECONDS,
) -> None:
    """Async task: emit a heartbeat log line every *interval* seconds."""
    while not shutdown.is_requested():
        await asyncio.sleep(interval)
        if shutdown.is_requested():
            break
        log.info("HEARTBEAT | pid=%d | progress=%s", os.getpid(), shutdown.progress)


# ---- Interruptible sleep -----------------------------------------------


async def interruptible_sleep(
    seconds: float,
    shutdown: ShutdownController,
    *,
    label: str = "sleep",
) -> bool:
    """
    Sleep for *seconds* but wake immediately if shutdown is requested.

    Returns True if the full sleep elapsed, False if interrupted.
    """
    if seconds <= 0:
        return True
    deadline = time.monotonic() + seconds
    tick = min(1.0, seconds)
    while time.monotonic() < deadline:
        if shutdown.is_requested():
            logger.debug("[%s] interruptible_sleep interrupted", label)
            return False
        remaining = deadline - time.monotonic()
        await asyncio.sleep(min(tick, remaining))
    return True
