"""Keep temporary Lab 9 variant registrations local to each test."""

import pytest


@pytest.fixture(autouse=True)
def isolated_registry():
    from lab8.shapes import SHAPES

    original = SHAPES.copy()
    try:
        yield
    finally:
        SHAPES.clear()
        SHAPES.update(original)
