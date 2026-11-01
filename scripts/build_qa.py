"""Build unchanged runtime inputs and bind their identities to the emitted Worker."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from qa_provenance import ROOT, runtime_inputs, build_identity


def main():
    (ROOT / '.sites-runtime').mkdir(parents=True, exist_ok=True)
    output = ROOT / 'outputs/qa-build'
    output.mkdir(parents=True, exist_ok=True)
    before = runtime_inputs()
    started = datetime.now(timezone.utc).isoformat()
    with (output / 'build.log').open('w', encoding='utf-8') as log:
        result = subprocess.run(['node', 'scripts/run-framework.mjs', 'build'], cwd=ROOT,
                                stdout=log, stderr=subprocess.STDOUT)
    if result.returncode:
        print(f'Build failed; see {output / "build.log"}', file=sys.stderr)
        return result.returncode
    if before != runtime_inputs():
        raise ValueError('Runtime inputs changed during the build; do not test this build.')
    record = {'source': before, 'build': build_identity(), 'started_utc': started,
              'finished_utc': datetime.now(timezone.utc).isoformat(), 'exit_code': result.returncode,
              'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()}
    (ROOT / '.sites-runtime/qa-build.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    print('Built Worker with source/build provenance:', record['build']['sha256'])
    return 0


if __name__ == '__main__':
    sys.exit(main())
