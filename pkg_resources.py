"""
Lightweight shim for pkg_resources used in local development.
Provides minimal `require()` and `DistributionNotFound` so packages
that query their version (like razorpay) won't fail when pkg_resources
is not available in the environment.

This is intentionally minimal and should NOT be used in production.
"""
class DistributionNotFound(Exception):
    pass

class _Dist:
    def __init__(self, version=""):
        self.version = version

def require(name):
    # Return a list with a dummy distribution object that has a `version` attribute.
    return [_Dist("")]
