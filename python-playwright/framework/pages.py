"""Small business-facing page objects with accessible locators."""
import re
from playwright.sync_api import expect


class BasePage:
    path = '/'

    def __init__(self, page):
        self.page = page

    def open(self, path=None):
        self.page.goto(path or self.path)
        # Numeric cart state is rendered only after the shared client has hydrated.
        expect(self.page.get_by_role('banner').locator('.cart-count')).to_have_text(re.compile(r'^\d+$'))
        return self

    def heading(self, name):
        return self.page.get_by_role('heading', name=name, exact=True)


class HomePage(BasePage):
    def shop(self):
        self.page.get_by_role('link', name=re.compile(r'^(Shop|Boutique)$')).click()
        expect(self.page).to_have_url(re.compile('/products/?$'))
        return CatalogPage(self.page)


class CatalogPage(BasePage):
    path = '/products'

    @property
    def results(self):
        return self.page.get_by_test_id('catalog-results')

    def search(self, query):
        self.page.get_by_role('searchbox', name=re.compile(r'^(Search catalog|Rechercher dans le catalogue)$')).fill(query)
        self.page.get_by_role('button', name=re.compile(r'^(Apply filters|Appliquer les filtres)$')).click()
        expect(self.results).to_be_visible()
        return self

    def product(self, name):
        self.page.get_by_role('link', name=re.compile(re.escape(name))).first.click()
        return ProductPage(self.page)


class ProductPage(BasePage):
    path = '/products/46'

    def add(self, qty=1):
        self.page.get_by_role('spinbutton', name=re.compile(r'^(Quantity|Quantité)$')).fill(str(qty))
        self.page.get_by_role('button', name=re.compile(r'^(Add to cart|Ajouter au panier)$')).click()


class CartPage(BasePage):
    path = '/cart'

    def remove(self):
        self.page.get_by_role('button', name=re.compile(r'^(Remove|Retirer)$')).first.click()

    def checkout(self):
        self.page.get_by_role('link', name=re.compile(r'^(Continue to checkout|Passer à la commande)$')).click()
        return CheckoutPage(self.page)


class CheckoutPage(BasePage):
    path = '/checkout'

    def choose_pay_later(self):
        self.page.get_by_role('radio', name=re.compile(r'^(Pay later|Payer plus tard)$')).check()
        self.page.get_by_role('checkbox', name=re.compile('demo pay-later order|commande de démonstration avec paiement différé')).check()
        return self

    def delivery(self, address):
        expect(self.page.get_by_role('banner').locator('.cart-count')).to_have_text(re.compile(r'^\d+$'))
        labels = {'name': ('Full name', 'Nom complet'), 'email': ('Email address', 'Adresse e-mail'),
                  'phone': ('Phone number', 'Numéro de téléphone'), 'street': ('Street address', 'Adresse'),
                  'city': ('City', 'Ville'), 'state': ('State', 'État'), 'pin': ('PIN code', 'Code postal')}
        french = self.page.locator('html').get_attribute('lang') == 'fr'
        for field, names in labels.items():
            self.page.get_by_label(names[int(french)], exact=True).fill(address[field])
        self.page.get_by_role('button', name=re.compile(r'^(Continue to payment|Continuer vers le paiement)$')).click()
        return self

    def review(self):
        self.page.get_by_role('button', name=re.compile(r'^(Review order|Vérifier la commande)$')).click()
        return self

    def confirm(self):
        self.page.get_by_role('button', name=re.compile(r'^(Confirm and place order|Confirmer et passer la commande)$')).click()
        return self
