#!/usr/bin/env python3
"""Explicit local-only launcher; never reads the repository's .env files.

Supply ARGUS_ANDROID_STACK_JSON from `supabase status -o json` for an isolated
stack. This file contains secrets: keep it outside Git with mode 0600.
"""
import json
import os
import re
import shutil
from pathlib import Path
import sys
from urllib.parse import urlsplit

REPO = Path(__file__).resolve().parents[3]


def configuration():
    path = Path(os.environ['ARGUS_ANDROID_STACK_JSON'])
    stack = json.loads(path.read_text())
    for key in ('API_URL', 'DB_URL'):
        if urlsplit(stack[key]).hostname not in ('localhost', '127.0.0.1', '::1'):
            raise SystemExit('Only an isolated loopback stack is allowed.')
    return stack


def prepare(destination):
    root = Path(destination).resolve()
    config = root / 'supabase/config.toml'
    if config.exists():
        raise SystemExit('Config exists; inspect its owner and reuse explicitly. Never reset shared stacks.')
    text = (REPO / 'supabase/config.toml').read_text()
    name = os.environ.get('ARGUS_ANDROID_STACK_NAME', 'android-accounts-611c')
    if not re.fullmatch(r'android-accounts-[a-z0-9-]+', name):
        raise SystemExit('Use a unique android-accounts-* project name.')
    base = int(os.environ.get('ARGUS_ANDROID_PORT_BASE', '59400'))
    if not 1024 <= base <= 65516:
        raise SystemExit('Port base must leave room for the reserved local range.')
    text = re.sub(r'^project_id = .*$', f'project_id = "{name}"', text, count=1, flags=re.M)
    overrides = {
        'api': {'port': str(base + 1)},
        'db': {'port': str(base + 2), 'shadow_port': str(base + 6)},
        'db.seed': {'enabled': 'false'}, 'studio': {'enabled': 'false'},
        'local_smtp': {'port': str(base + 3), 'smtp_port': str(base + 4)},
        'auth': {'jwt_expiry': '60'}, 'edge_runtime': {'enabled': 'false'},
    }
    for section, fields in overrides.items():
        pattern = r'(\[' + re.escape(section) + r'\]\n)(.*?)(?=^\[|\Z)'
        match = re.search(pattern, text, re.M | re.S)
        if match is None:
            raise SystemExit(f'Missing canonical local section: {section}')
        block = match.group(2)
        for key, value in fields.items():
            block, count = re.subn(r'^(?:# )?' + key + r' = .*$', f'{key} = {value}', block, flags=re.M)
            if count != 1:
                raise SystemExit(f'Inspect canonical field: {section}.{key}')
        text = text[:match.start(2)] + block + text[match.end(2):]
    config.parent.mkdir(parents=True)
    config.write_text(text)
    shutil.copytree(REPO / 'supabase/migrations', config.parent / 'migrations')
    print(f'Prepared {name}; inspect ports before starting. No service was started.')


def main():
    mode = sys.argv[1]
    if mode == 'prepare':
        prepare(sys.argv[2])
        return
    stack = configuration()
    port = int(os.environ.get('ARGUS_ANDROID_API_PORT', '59400'))
    env = {k: v for k, v in os.environ.items() if k in ('PATH', 'HOME', 'TMPDIR', 'LANG')}
    if mode == 'api':
        python = os.environ['ARGUS_ANDROID_PYTHON']
        env.update(
            APP_ENV='local', ARGUS_PERSISTENCE_MODE='supabase',
            ARGUS_DEV_MEMORY_FALLBACK='false', ARGUS_CHECKPOINTER_MODE='memory',
            ARGUS_MOCK_AUTH='false', NEXT_PUBLIC_MOCK_AUTH='false',
            ARGUS_PUBLIC_ACCOUNT_ACCESS_ENABLED='true',
            ARGUS_GUEST_ACCESS_ENABLED=os.environ.get('ARGUS_ANDROID_TEST_GUEST_ENABLED', 'false'),
            ARGUS_FINANCIAL_ACCOUNTS_ENABLED=os.environ.get('ARGUS_ANDROID_TEST_ACCOUNTS_ENABLED', 'true'),
            ARGUS_MARKET_DATA_PROVIDER_MODE='synthetic_unit_fixture',
            ARGUS_ENABLE_PERSONALIZATION_MEMORY='false', ARGUS_ENABLE_MEMORY_SEMANTIC_RECALL='false',
            ARGUS_BACKTEST_JOBS_SHADOW_ENABLED='false', ARGUS_BACKTEST_JOBS_DISPATCH_ENABLED='false',
            ARGUS_BACKTEST_WORKFLOW_EXECUTION_ENABLED='false', ENABLE_MARKET_DATA_CACHE='false',
            SUPABASE_URL=stack['API_URL'], SUPABASE_ANON_KEY=stack['ANON_KEY'],
            SUPABASE_SERVICE_ROLE_KEY=stack['SERVICE_ROLE_KEY'], DATABASE_URL=stack['DB_URL'],
            PYTHONPATH=str(REPO / 'src'), PYTHONDONTWRITEBYTECODE='1',
        )
        os.chdir(REPO)
        os.execve(python, [python, '-m', 'uvicorn', 'argus.api.main:app', '--host', '127.0.0.1',
                          '--port', str(port), '--no-access-log'], env)
    elif mode == 'build':
        for key in ('JAVA_HOME', 'ANDROID_HOME', 'GRADLE_USER_HOME'):
            env[key] = os.environ[key]
        gateway = urlsplit(stack['API_URL']).port
        env.update(ARGUS_ANDROID_LOCAL_AUTH='true', ARGUS_ANDROID_API_URL=f'http://10.0.2.2:{port}',
                   ARGUS_ANDROID_SUPABASE_URL=f'http://10.0.2.2:{gateway}',
                   ARGUS_ANDROID_SUPABASE_ANON_KEY=stack['ANON_KEY'],
                   ARGUS_ANDROID_CAPTCHA_TOKEN='android-local-test',
                   ARGUS_ANDROID_RECOVERY_URL='http://127.0.0.1:3000/auth/forgot-password')
        os.chdir(REPO / 'mobile/android')
        tasks = sys.argv[2:] or [':app:assembleDebug', ':app:testDebugUnitTest', ':app:lintDebug',
                                 ':app:assembleDebugAndroidTest']
        os.execve('./gradlew', ['./gradlew', *tasks], env)
    else:
        raise SystemExit('Use api or build [Gradle tasks].')


if __name__ == '__main__':
    main()
