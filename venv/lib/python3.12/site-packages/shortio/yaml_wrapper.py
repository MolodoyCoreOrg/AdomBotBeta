"""Contains wrappers for yaml.

Each wrapper is used to avoid context manager boilerplate.

By default this module uses ``yaml.FullLoader`` for reading.
See https://msg.pyyaml.org/load.

Attributes:
    read_yaml: Wrapped ``yaml.load``.
    write_yaml: Wrapped ``yaml.dump``.
    read_all_yaml: Wrapped ``yaml.load_all``.
    write_all_yaml: Wrapped ``yaml.dump_all``.

"""

import yaml

from .utils import read_wrapper, write_wrapper


read_yaml = read_wrapper(yaml.load, mode='r', Loader=yaml.FullLoader)
write_yaml = write_wrapper(yaml.dump, mode='w')

read_all_yaml = read_wrapper(yaml.load_all, mode='r', Loader=yaml.FullLoader)
write_all_yaml = write_wrapper(yaml.dump_all, mode='w')

__all__ = ['read_yaml', 'write_yaml',
           'read_all_yaml', 'write_all_yaml']
