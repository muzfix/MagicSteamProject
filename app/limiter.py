from slowapi import Limiter
from slowapi.util import get_remote_address

# Global limiter singleton — imported by main.py (registered on the app) and
# by any router that needs per-endpoint rate limits.  Keyed on client IP.
limiter = Limiter(key_func=get_remote_address)
