"""Fresh guest contexts and a fail-closed local mutation gate."""
import hashlib
import json
from pathlib import Path
from urllib.parse import urlsplit
import importlib.util

import pytest

from framework.api import ShopApi


def pytest_addoption(parser):
    group = parser.getgroup('everyday')
    group.addoption('--test-data-manifest', default=None)
    group.addoption('--artifacts-dir', default='.pytest-artifacts')
    group.addoption('--locale', choices=['en', 'fr'], default='en')
    group.addoption('--viewport-mode', choices=['desktop', 'mobile'], default='desktop')


def pytest_configure(config):
    raw = config.getoption('--base-url')
    if not raw:
        return
    url = urlsplit(raw)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('', '/'):
        raise pytest.UsageError('--base-url must be a bare HTTP(S) origin')
    if url.hostname in ('127.0.0.1', 'localhost') and not url.port:
        raise pytest.UsageError('Specify the local test server port explicitly')


@pytest.fixture(scope='session')
def base_url(pytestconfig):
    value = pytestconfig.getoption('--base-url')
    worker = getattr(pytestconfig, 'workerinput', {}).get('workerid')
    manifest_option = pytestconfig.getoption('--test-data-manifest')
    if worker and manifest_option:
        path = Path(manifest_option).resolve()
        path = path.parent.parent / worker / path.name
        if not path.is_file():
            pytest.fail(f'Missing manifest for xdist worker {worker}', pytrace=False)
        value = json.loads(path.read_text(encoding='utf-8')).get('url')
    if not value:
        pytest.fail('Provide --base-url explicitly', pytrace=False)
    return value.rstrip('/')


@pytest.fixture(scope='session')
def write_guard(pytestconfig, base_url):
    def require_local():
        parsed = urlsplit(base_url)
        if parsed.hostname not in ('127.0.0.1', 'localhost') or parsed.scheme != 'http' or not parsed.port:
            pytest.fail('Writes require exact HTTP loopback hostname and explicit port', pytrace=False)
        raw = pytestconfig.getoption('--test-data-manifest')
        if not raw:
            pytest.fail('Writes require --test-data-manifest from scripts/test_data.py', pytrace=False)
        path = Path(raw).resolve()
        worker = getattr(pytestconfig, 'workerinput', {}).get('workerid')
        if worker:
            path = path.parent.parent / worker / path.name
        root = Path(__file__).resolve().parents[1] / '.sites-runtime' / 'test-data'
        if not path.is_file() or not path.is_relative_to(root.resolve()):
            pytest.fail('Manifest must exist under .sites-runtime/test-data', pytrace=False)
        manifest = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(manifest, dict) or manifest.get('url', '').rstrip('/') != base_url:
            pytest.fail('Manifest URL must match --base-url exactly', pytrace=False)
        if manifest.get('schema') != 1 or manifest.get('kind') != 'everyday-local-test-data' or manifest.get('environment') != 'local':
            pytest.fail('Manifest is not owned local test data', pytrace=False)
        if not manifest.get('fixtures') or not manifest.get('run_id') or not manifest.get('worker'):
            pytest.fail('Manifest must identify run, worker, and fixtures', pytrace=False)
        if worker and manifest['worker'] != worker:
            pytest.fail('xdist worker does not own its manifest', pytrace=False)
        namespace = (root / manifest['run_id'] / manifest['worker']).resolve()
        database = Path(manifest.get('database', '')).resolve()
        if path.parent != namespace or Path(manifest.get('namespace', '')).resolve() != namespace or not database.is_file() or not database.is_relative_to(namespace):
            pytest.fail('Manifest database or namespace is not owned by this worker', pytrace=False)
        if manifest.get('port') != parsed.port:
            pytest.fail('Manifest port does not match --base-url', pytrace=False)
    return require_local


@pytest.fixture(autouse=True)
def gate_destructive(request, write_guard):
    if request.node.get_closest_marker('destructive') or request.node.get_closest_marker('e2e'):
        write_guard()


@pytest.fixture(scope='session')
def browser_type_launch_args(browser_type_launch_args, browser_name):
    options = dict(browser_type_launch_args)
    if browser_name == 'chromium':
        options['channel'] = 'chrome'
    return options


def _redact_trace(path):
    source = Path(__file__).parent / 'tests' / 'regression' / 'redact_trace.py'
    spec = importlib.util.spec_from_file_location('everyday_trace_redactor', source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        module.redact_trace(path)
    except Exception:
        path.unlink(missing_ok=True)
        raise


@pytest.fixture
def guest(browser, base_url, pytestconfig, request):
    device = pytestconfig.getoption('--viewport-mode')
    locale = pytestconfig.getoption('--locale')
    viewport = {'width': 390, 'height': 844} if device == 'mobile' else {'width': 1366, 'height': 900}
    context = browser.new_context(base_url=base_url, viewport=viewport, is_mobile=device == 'mobile' and browser.browser_type.name == 'chromium', locale='fr-FR' if locale == 'fr' else 'en-US', service_workers='block')
    context.add_cookies([{'name': 'everyday-language', 'value': locale, 'url': base_url}])
    violations = []
    def guard_route(route):
        target = urlsplit(route.request.url)
        if route.request.method not in ('GET', 'HEAD'):
            if not request.node.get_closest_marker('destructive') and not request.node.get_closest_marker('e2e'):
                violations.append('Read-only browser test attempted a write')
                route.abort()
                return
            if target.scheme != 'http' or target.hostname not in ('127.0.0.1', 'localhost') or target.netloc != urlsplit(base_url).netloc:
                violations.append('Browser write escaped local test origin')
                route.abort()
                return
        route.continue_()
    context.route('**/*', guard_route)
    context.tracing.start(screenshots=True, snapshots=True, sources=False)
    page = context.new_page()
    page.set_default_timeout(10000)
    yield context, page
    failed = getattr(request.node, 'rep_call', None)
    failed = failed and failed.failed
    folder = Path(pytestconfig.getoption('--artifacts-dir')) / hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16]
    try:
        if failed:
            folder.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(folder / 'failure.png'), full_page=True, animations='disabled')
            trace = folder / 'trace.zip'
            context.tracing.stop(path=str(trace))
            _redact_trace(trace)
        else:
            context.tracing.stop()
    finally:
        context.close()
    assert not violations, '; '.join(violations)


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    setattr(item, 'rep_' + outcome.get_result().when, outcome.get_result())


@pytest.fixture
def page(guest):
    return guest[1]


@pytest.fixture
def api(guest, base_url, write_guard):
    return ShopApi(guest[0], base_url, write_guard)


@pytest.fixture
def second_guest(browser, base_url, pytestconfig):
    context = browser.new_context(service_workers='block')
    context.add_cookies([{'name': 'everyday-language', 'value': pytestconfig.getoption('--locale'), 'url': base_url}])
    yield context
    context.close()
