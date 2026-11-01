"""Render a separate staging Worker config locally; never create, seed or deploy resources."""
import argparse
import json
from pathlib import Path
import re
import sys
import uuid

from qa_provenance import ROOT, verified_build
from release_gate import origin
from release_monitor import require


def render(config, built, root=ROOT):
    require(config.get('schema') == 1 and config.get('environment') == 'staging', 'Expected staging configuration')
    require(config.get('provisioning_approved') is True, 'Staging provisioning has not been approved/configured')
    require(re.fullmatch(r'[a-f0-9]{32}', config.get('account_id') or ''), 'Missing Cloudflare account ID')
    for field in ('database_id', 'production_database_id'):
        value = config.get(field); require(isinstance(value, str), 'Missing ' + field)
        require(str(uuid.UUID(value)) == value and value != '00000000-0000-4000-8000-000000000000', 'Invalid/unconfigured ' + field)
    require(config['database_id'] != config['production_database_id'], 'Staging must never bind production D1')
    name, production_name = config.get('worker_name'), config.get('production_worker_name')
    require(isinstance(name, str) and re.fullmatch(r'[a-z0-9][a-z0-9-]{2,62}-staging', name), 'Use an explicitly named staging Worker')
    require(production_name and name != production_name, 'Production Worker identity must be known and distinct')
    url = origin(config.get('url'))
    require(url.startswith('https://' + name + '.') and url.endswith('.workers.dev'), 'Staging URL does not identify its Worker')
    main = (root / 'dist/server' / built['main']).resolve()
    require(main.is_relative_to((root / 'dist').resolve()) and main.is_file(), 'Built entrypoint escapes dist')
    assets = (root / 'dist/server' / built['assets']['directory']).resolve()
    require(assets.is_relative_to((root / 'dist').resolve()) and assets.is_dir(), 'Built assets escape dist')
    result = {key: built[key] for key in ('compatibility_date', 'compatibility_flags', 'rules') if key in built}
    result.update(name=name, account_id=config['account_id'], main=str(main), workers_dev=True,
                  preview_urls=False, routes=[], vars={'EVERYDAY_ENVIRONMENT': 'staging'},
                  assets={**built['assets'], 'directory': str(assets)},
                  d1_databases=[{'binding': 'DB', 'database_name': name + '-db', 'database_id': config['database_id']}])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--output', type=Path, default=ROOT / '.sites-runtime/staging/wrangler.json')
    args = parser.parse_args()
    require(args.output.resolve().is_relative_to((ROOT / '.sites-runtime/staging').resolve()), 'Staging output must stay under ignored .sites-runtime/staging')
    verified_build()
    result = render(json.loads(args.config.read_text()), json.loads((ROOT / 'dist/server/wrangler.json').read_text()))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding='utf-8')
    print('Rendered isolated staging configuration only:', args.output)
    return 0


if __name__ == '__main__':
    try: sys.exit(main())
    except (ValueError, KeyError) as error:
        print('BLOCK:', str(error), file=sys.stderr); sys.exit(2)
