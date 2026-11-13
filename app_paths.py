import os
import sys


def application_directory():
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def application_path(*parts):
    return os.path.join(application_directory(), *parts)