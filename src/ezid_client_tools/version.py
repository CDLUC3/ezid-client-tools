import os


def get_version():
    module_path = os.path.abspath(__file__)
    version_path = os.path.join(os.path.dirname(module_path), "VERSION")
    with open(version_path, "r") as f:
        version = f.read().strip()
    return version


__version__ = get_version()
