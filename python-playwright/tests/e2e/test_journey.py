"""Browser journeys use the disposable local server only."""
import re

import pytest
from playwright.sync_api import expect

from framework.pages import CartPage, CatalogPage, CheckoutPage, ProductPage


pytestmark = [pytest.mark.e2e, pytest.mark.destructive]


def test_product_add_reflects_in_cart(page, api):
    ProductPage(page).open().add()
    expect(page.get_by_role('link', name=re.compile('Shopping cart, 1 items|Panier, 1 articles'))).to_be_visible()
    CartPage(page).open()
    expect(page.get_by_role('heading', name=re.compile('^(Plant Pot|Pot de fleurs)$'))).to_be_visible()


def test_cart_remove_updates_server(page, api):
    api.add()
    CartPage(page).open().remove()
    expect(page.get_by_role('heading', name=re.compile(r'^(Your cart is waiting\.|Votre panier vous attend\.)$'))).to_be_visible()
    assert api.cart()['items'] == []


def test_checkout_requires_cart(page):
    CheckoutPage(page).open()
    expect(page.get_by_role('heading', name=re.compile('empty or your guest session changed|Le panier est vide'))).to_be_visible()


def test_language_cookie_survives_navigation(page):
    CatalogPage(page).open()
    page.get_by_test_id('language-switcher').select_option('fr')
    expect(page.locator('html')).to_have_attribute('lang', 'fr')
    ProductPage(page).open()
    expect(page.locator('html')).to_have_attribute('lang', 'fr')
    expect(page.get_by_role('heading', name='Pot de fleurs')).to_be_visible()


def test_cart_persists_across_reload(page, api):
    api.add(qty=2)
    CartPage(page).open()
    page.reload()
    expect(page.get_by_role('heading', name=re.compile('^(Plant Pot|Pot de fleurs)$'))).to_be_visible()
    assert api.cart()['items'] == [{'product': 46, 'qty': 2}]


def test_guest_pay_later_checkout_receipt(page, api):
    api.add()
    checkout = CartPage(page).open().checkout()
    checkout.delivery({'name': 'Test Shopper', 'email': 'shopper@example.test', 'phone': '9876543210',
                       'street': '123 Demo Street', 'city': 'Bengaluru', 'state': 'Karnataka', 'pin': '560001'})
    checkout.choose_pay_later().review().confirm()
    expect(page.get_by_role('heading', name=re.compile(r'^(Thanks for shopping\.|Merci pour votre visite\.)$'))).to_be_visible()
    assert api.cart()['items'] == []
