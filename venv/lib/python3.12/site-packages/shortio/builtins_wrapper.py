"""Contains wrappers for builtins.

Each wrapper is used to avoid context manager boilerplate.

Attributes:
    read_json: Wrapped ``json.load``.
    write_json: Wrapped ``json.dump``.
    read_pickle: Wrapped ``pickle.load``.
    write_pickle: Wrapped ``pickle.dump``.

"""

import json
import pickle

from .utils import read_wrapper, write_wrapper


def read(file, mode='r', **kwargs):
    """Read and return content of the file.

    Args:
        file: Path-like object giving the pathname of the file to be opened.
        mode: String giving the mode of the file to be opened. Default: 'r'.
        **kwargs: Optional arguments that ``open`` takes.

    Returns:
        File content.

    """
    with open(file, mode, **kwargs) as f:
        return f.read()


def write(file, s, mode='w', **kwargs):
    """Read and return content of the file.

    Args:
        file: Path-like object giving the pathname of the file to be opened.
        s: Content to be written.
        mode: String giving the mode of the file to be opened. Default: 'w'.
        **kwargs: Optional arguments that ``open`` takes.

    Returns:
        The number of characters/bytes (according to mode) written.

    """
    with open(file, mode, **kwargs) as f:
        return f.write(s)


read_json = read_wrapper(json.load, mode='r')
write_json = write_wrapper(json.dump, mode='w')

read_pickle = read_wrapper(pickle.load, mode='rb')
write_pickle = write_wrapper(pickle.dump, mode='wb')

__all__ = ['read', 'write',
           'read_json', 'write_json',
           'read_pickle', 'write_pickle']
