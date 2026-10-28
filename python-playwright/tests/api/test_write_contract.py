"""All tests here require the local, isolated test-data manifest."""
from uuid import uuid4
from types import SimpleNamespace

import pytest

from framework.api import ShopApi, assert_error


pytestmark = [pytest.mark.regression, pytest.mark.destructive]

ADDRESS = {'name': 'Test Shopper', 'email': 'shopper@example.test', 'phone': '9876543210',
           'street': '123 Demo Street', 'city': 'Bengaluru', 'state': 'Karnataka', 'pin': '560001'}


def test_add_item_returns_snapshot(api):
    result = api.add()
    assert result.status == 200 and result.body['cart']['items'] == [{'product': 46, 'qty': 1}]


def test_add_quantity_is_absolute(api):
    api.add(qty=1)
    assert api.add(qty=3).body['cart']['items'] == [{'product': 46, 'qty': 3}]


def test_patch_quantity(api):
    api.add()
    result = api.patch(qty=2)
    assert result.status == 200 and result.body['cart']['items'][0]['qty'] == 2


def test_delete_item_with_json_body(api):
    api.add()
    result = api.remove()
    assert result.status == 200 and result.body['cart']['items'] == []


def test_version_increments(api):
    before = api.cart()['version']
    after = api.add().body['cart']['version']
    assert after == before + 1


def test_stale_cart_version_rejected(api):
    previous = api.cart()['version']
    api.add()
    assert_error(api.add(qty=2, version=previous), 409, 'CART_CHANGED')


def test_idempotent_cart_replay(api):
    key, version = str(uuid4()), api.cart()['version']
    first = api.add(version=version, key=key)
    replay = api.add(version=version, key=key)
    assert first.body['replayed'] is False and replay.body['replayed'] is True
    assert api.cart()['version'] == version + 1


def test_idempotency_key_reuse_for_other_quantity_conflicts(api):
    key = str(uuid4())
    api.add(key=key)
    assert_error(api.add(qty=2, key=key), 409, 'IDEMPOTENCY_CONFLICT')


def test_quantity_zero_rejected_by_rest(api):
    assert_error(api.add(qty=0), 400, 'INVALID_QUANTITY')


def test_quantity_eleven_rejected(api):
    assert_error(api.add(qty=11), 400, 'INVALID_QUANTITY')


def test_unknown_product_rejected(api):
    assert_error(api.add(product=999999), 400, 'INVALID_PRODUCT')


def test_price_tampering_rejected(api):
    result = api.mutate('POST', '/api/cart/items', {'product': 46, 'qty': 1, 'expectedPrice': 0})
    assert_error(result, 409, 'PRICE_CHANGED')


def test_missing_version_rejected(api):
    assert_error(api.send('POST', '/api/cart/items', {'product': 46, 'qty': 1, 'idempotencyKey': str(uuid4())}), 400, 'INVALID_CART_VERSION')


def test_missing_idempotency_key_rejected(api):
    assert_error(api.send('POST', '/api/cart/items', {'product': 46, 'qty': 1, 'expectedVersion': 0}), 400, 'INVALID_IDEMPOTENCY_KEY')


def test_unknown_field_rejected(api):
    result = api.mutate('POST', '/api/cart/items', {'product': 46, 'qty': 1, 'total': 1})
    assert_error(result, 400, 'UNKNOWN_FIELD')


@pytest.mark.parametrize('method,path', [('POST','/api/cart/items'),('PATCH','/api/cart/items/46'),('DELETE','/api/cart/items/46'),('POST','/api/coupons/validate'),('POST','/api/orders'),('POST','/api/shop')])
@pytest.mark.parametrize('origin', ['https://example.invalid', None, 'null'], ids=['foreign','missing','null'])
def test_cross_origin_mutation_denied(playwright, base_url, write_guard, method, path, origin):
    # Keep deliberately denied traffic outside the browser-associated request pool.
    context = playwright.request.new_context()
    try:
        client = ShopApi(SimpleNamespace(request=context), base_url, write_guard)
        result = client.send(method, path, {'product': 46, 'qty': 1, 'expectedVersion': 0, 'idempotencyKey': str(uuid4())}, origin=origin, omit_origin=origin is None)
        assert_error(result, 403, 'INVALID_ORIGIN')
    finally:
        context.dispose()


def test_fresh_guest_cannot_see_other_cart(api, second_guest, base_url, write_guard):
    api.add()
    other = ShopApi(second_guest, base_url, write_guard)
    assert other.cart()['items'] == []


def test_legacy_shop_post_still_updates_cart(api):
    result = api.mutate('POST', '/api/shop', {'product': 46, 'qty': 1})
    assert result.status == 200 and api.cart()['items'] == [{'product': 46, 'qty': 1}]


def test_coupon_preview_does_not_apply(api):
    api.add()
    result = api.send('POST', '/api/coupons/validate', {'code': 'EVERYDAY', 'apply': False})
    assert result.status == 200 and api.cart()['quote']['coupon'] is None
    # The existing endpoint must accept v11 payloads with no key/revision,
    # and ignored client fields must never become pricing/clock authority.
    applied = api.send('POST', '/api/coupons/validate', {'code': 'EVERYDAY', 'apply': True, 'ignoredLegacyField': 'retained-compatibility', 'total': 1, 'now': 0})
    assert applied.status == 200
    quote = api.cart()['quote']
    assert quote['coupon'] == 'EVERYDAY' and quote['total'] == 749 and quote['discount'] == 750


def test_order_requires_contract_version_two(api):
    api.add()
    payload = {'contractVersion': 1, 'address': ADDRESS, 'paymentMethod': 'pay-later', 'simulation': 'success'}
    assert_error(api.mutate('POST', '/api/orders', payload), 400, 'INVALID_CONTRACT')


def test_order_rejects_empty_cart(api):
    result = api.order(ADDRESS)
    assert result.status in (400, 409, 422)
    assert_error(result, result.status)


def test_order_idempotency_and_read_isolation(api, second_guest, base_url, write_guard):
    api.add()
    key, version = str(uuid4()), api.cart()['version']
    payload = {'contractVersion': 2, 'address': ADDRESS, 'paymentMethod': 'pay-later', 'simulation': 'success', 'expectedVersion': version, 'idempotencyKey': key}
    first = api.send('POST', '/api/orders', payload)
    assert first.status == 201 and first.body['status'] == 'demo-confirmed'
    replay = api.send('POST', '/api/orders', payload)
    assert replay.status == 200 and replay.body['id'] == first.body['id'] and replay.body['replayed'] is True
    order_id = first.body['id']
    assert api.get(f'/api/orders/{order_id}').status == 200
    other = ShopApi(second_guest, base_url, write_guard)
    assert_error(other.get(f'/api/orders/{order_id}'), 404)


def test_order_id_is_unique_across_guests(api, second_guest, base_url, write_guard):
    one = api.add()
    assert one.status == 200
    first = api.order(ADDRESS)
    other = ShopApi(second_guest, base_url, write_guard)
    other.add()
    second = other.order(ADDRESS)
    assert first.status == 201 and second.status == 201 and first.body['id'] != second.body['id']
