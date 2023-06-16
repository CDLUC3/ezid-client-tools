def get_version():
    with open("VERSION", "r") as f:
        version = f.read().strip()
    return version


__version__ = get_version()
