#!/usr/bin/env python3
"""Structural validation of vendor-neutral Everyday Shop agent prompts."""
from pathlib import Path
import json,sys
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'agents'/'manifest.json').read_text())
errs=[]
names=[]
for agent in manifest['agents']:
    name=agent['call_name']; names.append(name)
    path=ROOT/agent['file']
    if not path.is_file():
        errs.append(f'{name}: missing {path}'); continue
    content=path.read_text(encoding='utf-8')
    if content.count(f'# {name} —')!=1: errs.append(f'{name}: missing or repeated header')
    for sec in agent['required_sections']:
        if f'## {sec}' not in content: errs.append(f'{name}: missing section {sec}')
    for invariant in ('No push without approval','@WATCHTOWER','`BLOCK`'):
        if invariant not in content: errs.append(f'{name}: missing safety invariant {invariant}')
if len(names)!=8 or len(set(names))!=8:
    errs.append(f'Expected eight unique agents, got {names}')
for key in ('@CONDUCTOR','@ATLAS','@FORGE','@PROBE','@SPEC','@SMOKE','@WATCHTOWER','@PERMIT'):
    if key not in names: errs.append(f'Missing agent {key}')
if not (ROOT/'IMPLEMENTATION.md').is_file(): errs.append('Missing implementation plan')
if errs:
    print('FAIL: agent pack static validation')
    for e in errs: print(' -',e)
    sys.exit(1)
print(f'PASS: {len(names)} agent definitions structurally validated')
print('NOT RUN: agent platform invocation and behavior dry-runs AG-03..AG-07')
print('NOT RUN: browser smoke / CI / deployment checks')
