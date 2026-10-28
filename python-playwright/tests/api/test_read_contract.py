import pytest

from framework.api import assert_error


pytestmark = pytest.mark.regression


def test_health_contract(api):
    result = api.get('/api/health')
    assert result.status == 200 and result.body == {'status': 'ok'} and result.version == '1'


def test_categories_are_unique(api):
    result = api.get('/api/categories')
    categories = result.body['categories']
    assert result.status == 200 and categories and len(categories) == len(set(categories))


def test_original_catalog_has_thirteen_products(api):
    original_prices = {43:899,44:1299,45:699,46:1499,47:999,93:1899,94:3499,
                       154:999,155:1199,156:1299,172:1799,173:2499,175:2199}
    for product_id, price in original_prices.items():
        result = api.get(f'/api/products/{product_id}')
        assert result.status == 200
        product = result.body['product']
        assert product['id'] == product_id and product['price'] == price
        assert product['priceMinor'] == price * 100
        assert product['image'] == f'/products/{product_id}.webp'



def test_catalog_pagination_contract(api):
    data = api.get('/api/products').body
    assert data['page'] == 1 and data['pageSize'] == 10 and data['totalPages'] >= 2 and len(data['items']) == 10


def test_product_46_stable_price(api):
    result = api.get('/api/products/46')
    assert result.status == 200
    product = result.body['product']
    assert product['id'] == 46 and product['name'] == 'Plant Pot' and product['priceMinor'] == 149900 and product['currency'] == 'INR'


def test_product_stock_is_authoritative(api):
    product = api.get('/api/products/46').body['product']
    assert isinstance(product['stock'], int) and product['stock'] >= 0


def test_missing_product_has_domain_error(api):
    assert_error(api.get('/api/products/999999'), 404)


def test_invalid_product_id_has_domain_error(api):
    assert_error(api.get('/api/products/not-an-id'), 400, 'INVALID_ID')


def test_catalog_search_returns_relevant_product(api):
    data = api.get('/api/products?q=Plant').body
    assert data['total'] >= 1 and any(item['id'] == 46 for item in data['items'])


def test_catalog_category_filter(api):
    data = api.get('/api/products?category=Accessories').body
    assert data['items'] and all(item['category'] == 'Accessories' for item in data['items'])


def test_catalog_sort_price_ascending(api):
    prices = [item['priceMinor'] for item in api.get('/api/products?sort=price-asc').body['items']]
    assert prices == sorted(prices)


def test_catalog_invalid_query_is_400(api):
    assert_error(api.get('/api/products?page=not-a-number'), 400, 'INVALID_CATALOG_QUERY')


def test_empty_cart_quote(api):
    cart = api.cart()
    assert cart['items'] == [] and cart['version'] >= 0 and cart['quote']['totalPaise'] == 0


def test_guest_capability_not_in_json(api, guest):
    api.cart()
    cookies = guest[0].cookies()
    secret = next(c['value'] for c in cookies if c['name'] == '__Host-everyday-guest')
    assert secret not in repr(api.cart())


def test_legacy_shop_get_compatible(api):
    result = api.get('/api/shop')
    assert result.status == 200 and result.body['items'] == [] and result.body['sessionStatus'] in ('new', 'active')


def test_order_lookup_unknown_is_isolated(api):
    result = api.get('/api/orders/unknown-order')
    assert_error(result, 404)


@pytest.mark.destructive
def test_method_not_allowed_contract(api):
    result = api.send('PUT', '/api/products')
    assert_error(result, 405, 'METHOD_NOT_ALLOWED')


