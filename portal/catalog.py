"""What the portal can start: every skill of this repository, with what it is for and how it runs on this server.

Only the actions below can run, never a command taken from a request. A skill without ``argv`` is shown with the
reason it has no button here. tests/test_portal.py fails when a skill folder has no entry.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
WORK = Path('/root/work')
WORKSPACE = WORK / 'op-setup-ws'
DRY_WORKSPACE = WORK / 'ops-web' / 'dry-run'
# op-merge-upstream never switches branch, so each variant has its own clone (portal/install_service.sh makes the second).
OPENDBC = {'sunny': WORK / 'opendbc', 'comma': WORK / 'opendbc-comma'}
COMMIT = re.compile(r'[0-9a-fA-F]{7,40}')

# https has no credentials here: pushes go over ssh, reads stay on https.
BASE_ENV = {
    'GIT_CONFIG_COUNT': '1',
    'GIT_CONFIG_KEY_0': 'url.git@github.com:cristianku/.pushInsteadOf',
    'GIT_CONFIG_VALUE_0': 'https://github.com/cristianku/',
    'WORKSPACE_ROOT': str(WORKSPACE),
    'FORK_CACHE': str(WORK / 'fork-branch-cache.git'),
}
NO_PUSH = {'NO_PUSH': 'true', 'WORKSPACE_ROOT': str(DRY_WORKSPACE)}

# The scripts that share the setup workspace or the fork cache: none of them may run beside a job of the portal,
# whoever started it (the speed limits site's Publish runs send_to_car.sh, which runs the setup).
BUSY_SCRIPTS = frozenset({'setup_psa_torque.sh', 'setup_psa_torque_speed.sh', 'send_to_car.sh', 'update_fork_branch.sh',
                          'update_distilled.sh', 'merge_psa_torque.sh', 'merge_upstream.sh', 'sync_fork.sh'})

VARIANT = {'name': 'variant', 'label': 'For', 'choices': [['sunny', 'sunnypilot'], ['comma', 'comma.ai']]}
BASE = {'name': 'base', 'label': 'Base', 'choices': [['master', 'Latest master'], ['release', 'Latest release']]}
PIN = {'name': 'commit', 'label': 'Exact upstream commit (optional)', 'text': True}


def _base(params: dict) -> str:
    return f"master={params['commit']}" if params.get('commit') else params['base']


def _script(*parts: str) -> str:
    return str(REPO.joinpath(*parts))


SKILLS = [
    # Keep the sources up to date.
    {'id': 'sync-fork', 'skill': 'scripts/sync_fork.sh', 'group': 'Keep up to date',
     'title': 'Sync a fork',
     'flow': {'sunnypilot': ['sunnypilot/sunnypilot master → cristianku/sunnypilot master'],
              'openpilot': ['commaai/openpilot master → cristianku/openpilot master']},
     'what': 'Moves the master of your fork to the official master, like Sync fork on GitHub.',
     'effect': 'Publishes master on your fork. It only moves forward, and refuses if the fork has commits of its own.',
     'params': [{'name': 'fork', 'label': 'Fork', 'choices': [['sunnypilot', 'cristianku/sunnypilot'],
                                                              ['openpilot', 'cristianku/openpilot']]}],
     'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('scripts', 'sync_fork.sh'), p['fork']]},
    {'id': 'update-sunny-nav-alpha', 'skill': 'OP-update-sunny-nav-alpha', 'group': 'Keep up to date',
     'title': 'Update Nav2Pilot for sunnypilot',
     'flow': {'': ['sunnypilot/sunnypilot master → cristianku/openpilot sunny-nav-alpha',
                  'cristianku/openpilot sunny-nav-alpha → cristianku/sunnypilot nav-alpha']},
     'what': 'Moves the Nav2Pilot commit onto the latest sunnypilot master, so the apps keep sending routes to the comma.',
     'effect': 'Publishes sunny-nav-alpha and nav-alpha.', 'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('scripts', 'update_fork_branch.sh'), 'sunny-nav-alpha']},
    {'id': 'update-nav-alpha', 'skill': 'OP-update-nav-alpha', 'group': 'Keep up to date',
     'title': 'Update Nav2Pilot for comma.ai',
     'flow': {'': ['commaai/openpilot master → cristianku/openpilot nav-alpha']},
     'what': 'Moves the Nav2Pilot commit onto the latest comma.ai master.',
     'effect': 'Publishes nav-alpha on cristianku/openpilot.', 'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('scripts', 'update_fork_branch.sh'), 'nav-alpha']},
    {'id': 'update-distilled', 'skill': 'OP-update-distilled', 'group': 'Keep up to date',
     'title': 'Update the Distill models branch',
     'flow': {'': ['sunnypilot/sunnypilot master → cristianku/sunnypilot distilled',
                  'cristianku/sunnypilot distilled → cristianku/openpilot distilled']},
     'what': 'Brings the latest sunnypilot master into distilled, the branch that lists your driving models on the comma.',
     'effect': 'Publishes distilled on both forks.', 'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('scripts', 'update_fork_branch.sh'), 'distilled']},
    {'id': 'merge-upstream', 'skill': 'op-merge-upstream', 'group': 'Keep up to date',
     'title': 'Merge official opendbc',
     'flow': {'sunny': ['sunnypilot/opendbc master → cristianku/opendbc psa-torque-sunny-testing'],
              'comma': ['commaai/opendbc master → cristianku/opendbc psa-torque-testing']},
     'what': 'Brings the changes of official opendbc into your Peugeot port, so it does not fall behind.',
     'effect': 'Nothing goes to GitHub: the merge waits on this server until Claude tests and pushes it.',
     'params': [VARIANT], 'env': lambda p: {'OPENDBC_DIR': str(OPENDBC[p['variant']])},
     'argv': lambda p: ['bash', _script('op-merge-upstream', 'scripts', 'merge_upstream.sh'), p['variant']]},
    # Build the branches of the car.
    {'id': 'setup-testing', 'skill': 'OP-setup-psa-torque-testing', 'group': 'Build for the car',
     'title': 'Build the testing branch',
     'flow': {'sunny': ['sunnypilot/sunnypilot + cristianku/opendbc psa-torque-sunny-testing → cristianku/openpilot psa-torque-sunny-testing'],
              'comma': ['commaai/openpilot + cristianku/opendbc psa-torque-testing → cristianku/openpilot psa-torque-testing']},
     'what': 'Rebuilds the branch the comma runs, with Nav2Pilot, the PSA port, the Distill list and the speed limits.',
     'effect': 'Force-pushes psa-torque-sunny-testing or psa-torque-testing.', 'params': [VARIANT, BASE, PIN],
     'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('OP-setup-psa-torque-testing', 'scripts', 'setup_psa_torque.sh'),
                        p['variant'], _base(p)]},
    {'id': 'setup-stable', 'skill': 'OP-setup-psa-torque', 'group': 'Build for the car',
     'title': 'Build the stable branch',
     'flow': {'sunny': ['sunnypilot/sunnypilot + cristianku/opendbc psa-torque-sunny → cristianku/openpilot psa-torque-sunny'],
              'comma': ['commaai/openpilot + cristianku/opendbc psa-torque → cristianku/openpilot psa-torque']},
     'what': 'Rebuilds the stable branch, with stable opendbc.',
     'effect': 'Force-pushes psa-torque-sunny or psa-torque.',
     'params': [VARIANT, {'name': 'base', 'label': 'Base', 'choices': [
         ['nav-alpha', 'With Nav2Pilot'], ['master', 'Latest master'], ['release', 'Latest release']]}],
     'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('OP-setup-psa-torque', 'scripts', 'setup_psa_torque.sh'),
                        p['variant'], p['base']]},
    {'id': 'setup-speed', 'skill': 'OP-setup-psa-torque-speed', 'group': 'Build for the car',
     'title': 'Build the speed-limit work branch',
     'flow': {'': ['sunnypilot/sunnypilot + cristianku/opendbc psa-torque-sunny-speed → cristianku/openpilot psa-torque-sunny-speed']},
     'what': 'The same build as testing, published apart so testing stays as it is.',
     'effect': 'Force-pushes psa-torque-sunny-speed.', 'params': [BASE, PIN], 'dry_env': NO_PUSH,
     'argv': lambda p: ['bash', _script('OP-setup-psa-torque-speed', 'scripts', 'setup_psa_torque_speed.sh'),
                        'sunny', _base(p)]},
    # Promote testing to stable.
    {'id': 'merge-sunny-stable', 'skill': 'OP-merge-psa-torque-sunny-testing', 'group': 'Promote to stable',
     'title': 'Promote sunnypilot opendbc',
     'flow': {'': ['cristianku/opendbc psa-torque-sunny-testing → psa-torque-sunny']},
     'what': 'Merges opendbc testing into stable once the PSA tests pass.',
     'effect': 'Publishes psa-torque-sunny on cristianku/opendbc.',
     'argv': lambda p: ['bash', _script('OP-merge-psa-torque-sunny-testing', 'scripts', 'merge_psa_torque.sh')]},
    {'id': 'merge-comma-stable', 'skill': 'OP-merge-psa-torque-testing', 'group': 'Promote to stable',
     'title': 'Promote comma.ai opendbc',
     'flow': {'': ['cristianku/opendbc psa-torque-testing → psa-torque']},
     'what': 'Merges opendbc testing into stable once the PSA tests pass.',
     'effect': 'Publishes psa-torque on cristianku/opendbc.',
     'argv': lambda p: ['bash', _script('OP-merge-psa-torque-testing', 'scripts', 'merge_psa_torque.sh')]},
    # On the comma.
    {'id': 'update-comma', 'skill': 'OP-UPDATE-COMMA', 'group': 'On the comma',
     'title': 'Update the comma',
     'flow': {'': ['cristianku/openpilot psa-torque-sunny-testing → the comma']},
     'what': 'Pulls the latest commit of its branch on the comma, then restarts it.',
     'effect': 'Changes the comma and reboots it. It must be parked and on the network.', 'device': True,
     'params': [{'name': 'reboot', 'label': 'After the update', 'choices': [['yes', 'Restart'], ['no', 'Do not restart']]}],
     'dry_arg': '--dry-run',
     'argv': lambda p: ['bash', _script('OP-UPDATE-COMMA', 'scripts', 'update_comma.sh'),
                        *([] if p['reboot'] == 'yes' else ['--no-reboot']), 'comma']},
    {'id': 'reset-learned', 'skill': 'OP-reset-comma-learned-params', 'group': 'On the comma',
     'title': 'Reset what the comma learned',
     'what': 'Clears the learned steering values, so they start again from the opendbc ones. Your settings stay.',
     'effect': 'Deletes LiveDelay, LiveTorqueParameters and LiveParametersV2 on the comma. It refuses while driving.',
     'device': True,
     'params': [{'name': 'reboot', 'label': 'After the reset', 'choices': [['yes', 'Restart'], ['no', 'Do not restart']]}],
     'argv': lambda p: ['bash', _script('OP-reset-comma-learned-params', 'scripts', 'reset_learned_params.sh'),
                        *(['--reboot'] if p['reboot'] == 'yes' else [])]},
    # Shown, without a button.
    {'id': 'apply-nav-alpha', 'skill': 'OP-apply-nav-alpha', 'group': 'Needs Claude or your Mac',
     'title': 'Fix or change Nav2Pilot',
     'what': 'For when the Nav2Pilot update stops on a conflict, or its code must change.',
     'elsewhere': 'Conflicts need someone to resolve them, and the script uses the clones on your Mac. Ask Claude.'},
    {'id': 'commit-push-opendbc', 'skill': 'OP-commit-push-opendbc', 'group': 'Needs Claude or your Mac',
     'title': 'Commit and push opendbc',
     'what': 'Publishes the changes of the PSA port.',
     'elsewhere': 'It commits everything in the clone, so Claude must check what is there first. Ask Claude.'},
    {'id': 'news', 'skill': 'OP-news', 'group': 'Needs Claude or your Mac',
     'title': 'Community news',
     'what': 'Reads the comma.ai and sunnypilot communities and explains what is new and useful.',
     'elsewhere': 'A reading task, not a script. Ask Claude.'},
    {'id': 'nnlc-fetch-peugeot', 'skill': 'op-nnlc-fetch-peugeot', 'group': 'Needs Claude or your Mac',
     'title': 'Download the Peugeot steering model',
     'what': 'Fetches the NNLC model of the 3008 into neural-network-data.',
     'elsewhere': 'It saves into the clone on your Mac. Run it there.'},
    {'id': 'nnlc-joseph-sync', 'skill': 'nnlc-joseph-sync', 'group': 'Needs Claude or your Mac',
     'title': 'Copy logs for Joseph',
     'what': 'Copies the logs from TrueNAS to a USB stick and imports them on the Joseph machine.',
     'elsewhere': 'It needs a USB stick on your Mac. Run it there.'},
]
BY_ID = {skill['id']: skill for skill in SKILLS}
GROUPS = ['Keep up to date', 'Build for the car', 'Promote to stable', 'On the comma', 'Needs Claude or your Mac']


class ActionError(ValueError):
    pass


def public(skill: dict) -> dict:
    """What the page needs of a skill: no command, no environment."""
    return {'id': skill['id'], 'skill': skill['skill'], 'group': skill['group'], 'title': skill['title'],
            'what': skill['what'], 'flow': skill.get('flow', {}), 'effect': skill.get('effect'),
            'elsewhere': skill.get('elsewhere'),
            'params': skill.get('params', []), 'device': bool(skill.get('device')),
            'dry': bool(skill.get('dry_env') or skill.get('dry_arg'))}


def skills_without_entry() -> list[str]:
    known = {skill['skill'] for skill in SKILLS}
    return sorted(path.parent.name for path in REPO.glob('*/SKILL.md') if path.parent.name not in known)


def resolve(action: str, params: dict, dry: bool) -> tuple[list[str], dict]:
    """The argv and the environment of an action, after checking every parameter against its own list."""
    skill = BY_ID.get(action)
    if skill is None or 'argv' not in skill:
        raise ActionError('This skill cannot run here.')
    clean = {}
    for spec in skill.get('params', []):
        value = params.get(spec['name'])
        if spec.get('text'):
            value = str(value or '').strip()
            if value and not COMMIT.fullmatch(value):
                raise ActionError('A commit is 7 to 40 hexadecimal characters.')
        elif value not in [choice[0] for choice in spec['choices']]:
            raise ActionError(f"Choose {spec['label'].lower()}.")
        clean[spec['name']] = value
    if clean.get('commit') and clean.get('base') == 'release':
        raise ActionError('An exact commit goes with the latest master, not the release.')
    argv = skill['argv'](clean)
    env = {**BASE_ENV, **(skill['env'](clean) if 'env' in skill else {})}
    if dry:
        if not (skill.get('dry_env') or skill.get('dry_arg')):
            raise ActionError('This skill has no trial run.')
        env.update(skill.get('dry_env', {}))
        if skill.get('dry_arg'):
            argv.insert(2, skill['dry_arg'])
    return argv, env
