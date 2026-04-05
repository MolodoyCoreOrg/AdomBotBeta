"""Contains utility functions."""

BIN_MODE_ARGS = {'mode', 'buffering', }
TEXT_MODE_ARGS = {'mode', 'buffering', 'encoding', 'errors', 'newline'}


def split_args(args):
    """Splits args into two groups: open args and other args.

    Open args are used by ``open`` function. Other args are used by
    ``load``/``dump`` functions.

    Args:
        args: Keyword args to split.
    Returns:
        open_args: Arguments for ``open``.
        other_args: Arguments for ``load``/``dump``.

    """
    mode_args = BIN_MODE_ARGS if 'b' in args['mode'] else TEXT_MODE_ARGS

    open_args = {}
    other_args = {}
    for arg, value in args.items():
        if arg in mode_args:
            open_args[arg] = value
        else:
            other_args[arg] = value

    return open_args, other_args


def read_wrapper(load, **base_kwargs):
    """Wraps ``load`` function to avoid context manager boilerplate.

    Args:
        load: Function that takes the return of ``open``.
        **base_kwargs: Base arguments that ``open``/``load`` take.

    Returns:
        Wrapper for ``load``.

    """
    def wrapped(file, **kwargs):
        open_args, load_args = split_args({**base_kwargs, **kwargs})
        with open(file, **open_args) as f:
            return load(f, **load_args)

    return wrapped


def write_wrapper(dump, **base_kwargs):
    """Wraps ``dump`` function to avoid context manager boilerplate.

    Args:
        dump: Function that takes the return of ``open`` and data to dump.
        **base_kwargs: Base arguments that ``open``/``dump`` take.

    Returns:
        Wrapper for ``dump``.

    """
    def wrapped(file, obj, **kwargs):
        open_args, dump_args = split_args({**base_kwargs, **kwargs})
        with open(file, **open_args) as f:
            dump(obj, f, **dump_args)

    return wrapped
