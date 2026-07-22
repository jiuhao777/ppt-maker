import platform
import sys


def test_supported_runtime():
    assert (3, 10) <= sys.version_info[:2] < (3, 13)
    assert platform.system() == "Windows"
