"""Session-bound REST client. Never logs guest cookies or request bodies."""
from dataclasses import dataclass
from uuid import uuid4
from urllib.parse import urlsplit


@dataclass
class Result:
    status: int
    body: dict
    request_id: str
    version: str


class ShopApi:
    def __init__(self, context, base_url, write_guard):
        self.context, self.base_url, self.write_guard = context, base_url.rstrip('/'), write_guard

    def send(self, method, path, body=None, origin=None, omit_origin=False):
        if method.upper() not in ('GET', 'HEAD'):
            self.write_guard()
        headers = {} if omit_origin else {'Origin': origin if origin is not None else self.base_url}
        # Local Wrangler's request pool can stall after deliberately denied origins.
        # Close this test transport connection; production browser behavior is unchanged.
        if urlsplit(self.base_url).hostname in ('127.0.0.1', 'localhost'):
            headers['Connection'] = 'close'
        assert path.startswith('/') and not path.startswith('//')
        response = self.context.request.fetch(self.base_url + path, method=method, data=body, headers=headers, max_redirects=0, timeout=8000)
        assert urlsplit(response.url).netloc == urlsplit(self.base_url).netloc
        assert response.status < 300 or response.status >= 400, f'{path}: redirect blocked'
        data = response.json()
        assert isinstance(data, dict), f'{path}: expected JSON object'
        rid = response.headers.get('x-request-id', '')
        assert rid, f'{path}: missing X-Request-ID'
        assert response.headers.get('cache-control') == 'private, no-store'
        return Result(response.status, data, rid, response.headers.get('x-api-version', ''))

    def get(self, path):
        return self.send('GET', path)

    def cart(self):
        return self.get('/api/cart').body

    def mutate(self, method, path, body=None, *, version=None, key=None):
        payload = dict(body or {})
        payload.setdefault('expectedVersion', self.cart()['version'] if version is None else version)
        payload.setdefault('idempotencyKey', key or str(uuid4()))
        return self.send(method, path, payload)

    def add(self, product=46, qty=1, **kwargs):
        return self.mutate('POST', '/api/cart/items', {'product': product, 'qty': qty}, **kwargs)

    def patch(self, product=46, qty=1, **kwargs):
        return self.mutate('PATCH', f'/api/cart/items/{product}', {'qty': qty}, **kwargs)

    def remove(self, product=46, **kwargs):
        return self.mutate('DELETE', f'/api/cart/items/{product}', **kwargs)

    def order(self, address, **extra):
        payload = {'contractVersion': 2, 'address': address, 'paymentMethod': 'pay-later', 'simulation': 'success', **extra}
        return self.mutate('POST', '/api/orders', payload)


def assert_error(result, status, code=None):
    assert result.status == status, (result.status, result.body)
    for field in ('code', 'message', 'error', 'requestId'):
        assert isinstance(result.body.get(field), str) and result.body[field]
    assert result.body['requestId'] == result.request_id
    if code:
        assert result.body['code'] == code
