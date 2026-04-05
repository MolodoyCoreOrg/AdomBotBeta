import re

import shortio

from .__version__ import __version__


VOWELS = re.compile('[aeiou]')

__all__ = []
for name in shortio.__all__:
    name_parts = name.split('_')

    if len(name_parts) > 1:
        prefix = ''.join([part[0] for part in name_parts[:-1]])
        frmt = VOWELS.sub('', name_parts[-1])
        new_name = f'{prefix}{frmt}'
    else:
        new_name = name_parts[0][0]

    globals()[new_name] = getattr(shortio, name)
    __all__.append(new_name)
