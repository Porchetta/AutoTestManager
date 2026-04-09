from __future__ import annotations

from enum import Enum


class TestType(str, Enum):
    RTD = "RTD"
    EZDFS = "EZDFS"


class ActionType(str, Enum):
    COPY = "COPY"
    COMPILE = "COMPILE"
    TEST = "TEST"
    RETEST = "RETEST"
    GENERATE_SUMMARY = "GENERATE_SUMMARY"


class TaskStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAIL = "FAIL"
    CANCELED = "CANCELED"


class TaskStep(str, Enum):
    READY = "READY"
    COPYING = "COPYING"
    COMPILING = "COMPILING"
    TESTING = "TESTING"
