"""Fail-closed browser request policy; infrastructure POSTs are never forwarded."""
import re
from urllib.parse import urlsplit


_CLOUDFLARE_CHALLENGE = re.compile(
    r'/cdn-cgi/challenge-platform/h/[bg]/jsd/oneshot/[A-Za-z0-9._~:/-]+'
)


def request_policy(method, url, base_url, local_writes=False):
    target, origin = urlsplit(url), urlsplit(base_url)
    if method in ('GET', 'HEAD'):
        return 'read'
    same_origin = (target.scheme, target.netloc) == (origin.scheme, origin.netloc)
    if (method == 'POST' and same_origin and target.scheme == 'https'
            and not target.username and not target.password
            and not target.query and not target.fragment
            and _CLOUDFLARE_CHALLENGE.fullmatch(target.path)):
        return 'blocked-infrastructure'
    if (local_writes and same_origin and target.scheme == 'http'
            and target.hostname in ('127.0.0.1', 'localhost') and target.port):
        return 'local-write'
    return 'blocked-write'


def diagnostic_path(url):
    """Keep request classification without query strings or challenge tokens."""
    path = urlsplit(url).path
    if path.startswith('/cdn-cgi/challenge-platform/'):
        return '/cdn-cgi/challenge-platform/<redacted>'
    return path
