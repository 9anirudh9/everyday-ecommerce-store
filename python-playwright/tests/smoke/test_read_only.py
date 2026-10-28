"""Public-safe browser checks: navigation and GET only."""
import re

import pytest
from playwright.sync_api import expect

from framework.pages import CartPage, CatalogPage, HomePage, ProductPage


pytestmark = pytest.mark.smoke


def test_home_navigation(page):
    HomePage(page).open().shop()
    expect(CatalogPage(page).results).to_be_visible()


def test_plant_pot_display(page):
    ProductPage(page).open()
    expect(page.get_by_role('heading', name=re.compile(r'^(Plant Pot|Pot de fleurs)$'))).to_be_visible()
    expect(page.get_by_text(re.compile(r'1,499')).first).to_be_visible()


def test_search_results(page):
    CatalogPage(page).open().search('plant')
    expect(page.get_by_role('link', name=re.compile('Plant Pot|Pot de fleurs')).first).to_be_visible()


def test_accessories_navigation(page):
    HomePage(page).open()
    page.get_by_role('link', name=re.compile(r'^(Accessories|Accessoires)$')).click()
    expect(page).to_have_url(re.compile('/accessories/?$'))
    expect(CatalogPage(page).results).to_be_visible()


def test_empty_cart_is_read_only(page):
    CartPage(page).open()
    expect(page.get_by_role('heading', name=re.compile(r'^(Your cart is waiting\.|Votre panier vous attend\.)$'))).to_be_visible()
