"""Non-destructive starter smoke against baseline A or candidate B.

Execution needs an authorized browser environment and target URL.
These tests are syntax-checked in the delivered pack; NOT browser-executed here.
"""
from playwright.sync_api import Page, expect
import pytest
import re


@pytest.mark.smoke
def test_home_navigation(page: Page):
    page.goto('/')
    choose_english_if_needed(page)
    expect(page.get_by_role('link', name='Shop', exact=True)).to_be_visible()
    page.get_by_role('link', name='Shop', exact=True).click()
    expect(page).to_have_url(re.compile(r'/products/?$'))


def choose_english_if_needed(page: Page):
    option = page.get_by_test_id('language-english')
    if option.is_visible():
        option.click()


@pytest.mark.smoke
def test_plant_pot_display(page: Page):
    page.goto('/products/46')
    choose_english_if_needed(page)
    expect(page.get_by_role('heading', name='Plant Pot', exact=True)).to_be_visible()
    expect(page.get_by_text('₹1,499', exact=True)).to_be_visible()


@pytest.mark.smoke
def test_search_results(page: Page):
    page.goto('/search?q=plant')
    choose_english_if_needed(page)
    expect(page.get_by_role('heading', name='Plant Pot', exact=True)).to_be_visible()
