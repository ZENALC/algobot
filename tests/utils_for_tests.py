"""
File containing miscellaneous functions for testing purposes.
"""
from contextlib import contextmanager


@contextmanager
def does_not_raise():
    """
    Small utility function for pytest.
    """
    yield
