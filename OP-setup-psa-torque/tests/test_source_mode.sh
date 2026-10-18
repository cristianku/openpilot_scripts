#!/usr/bin/env bash
set -euo pipefail

# [source] - START
skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
wrapper="${skill_root}/scripts/setup_psa_torque.sh"
test_root="$(mktemp -d)"
trap 'rm -rf "${test_root}"' EXIT

cp "${wrapper}" "${test_root}/setup_psa_torque.sh"
cat > "${test_root}/setup_psa_torque_common.sh" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' \
  "BRANCH=${BRANCH}" \
  "OPENPILOT_SOURCE_REPO=${OPENPILOT_SOURCE_REPO}" \
  "OPENPILOT_SOURCE_BRANCH=${OPENPILOT_SOURCE_BRANCH}" \
  "OPENDBC_SOURCE_BRANCH=${OPENDBC_SOURCE_BRANCH}" \
  "USE_CUSTOM_NEURAL_NETWORK_DATA=${USE_CUSTOM_NEURAL_NETWORK_DATA}"
EOF

assert_output() {
  local actual="$1"
  local expected="$2"
  local label="$3"
  if [[ "${actual}" != "${expected}" ]]; then
    printf 'FAIL: %s\nexpected:\n%s\nactual:\n%s\n' "${label}" "${expected}" "${actual}" >&2
    return 1
  fi
}

sunny_master_output="$(bash "${test_root}/setup_psa_torque.sh" sunny master)"
assert_output "${sunny_master_output}" 'BRANCH=psa-torque-sunny
OPENPILOT_SOURCE_REPO=https://github.com/sunnypilot/sunnypilot.git
OPENPILOT_SOURCE_BRANCH=master
OPENDBC_SOURCE_BRANCH=psa-torque-sunny-testing
USE_CUSTOM_NEURAL_NETWORK_DATA=true' 'sunny master selects upstream master and stable branch'

fake_bin="${test_root}/bin"
mkdir -p "${fake_bin}"
cat > "${fake_bin}/curl" <<'EOF'
#!/usr/bin/env bash
printf '%s\n' '{"tag_name":"v-test-release"}'
EOF
cat > "${fake_bin}/git" <<'EOF'
#!/usr/bin/env bash
exit 0
EOF
chmod +x "${fake_bin}/curl" "${fake_bin}/git"

comma_release_output="$(PATH="${fake_bin}:${PATH}" bash "${test_root}/setup_psa_torque.sh" openpilot release)"
assert_output "${comma_release_output}" 'BRANCH=psa-torque
OPENPILOT_SOURCE_REPO=https://github.com/commaai/openpilot.git
OPENPILOT_SOURCE_BRANCH=v-test-release
OPENDBC_SOURCE_BRANCH=psa-torque-testing
USE_CUSTOM_NEURAL_NETWORK_DATA=false' 'openpilot release resolves latest tag and stable branch'

if bash "${test_root}/setup_psa_torque.sh" sunny unsupported >/dev/null 2>&1; then
  echo 'FAIL: unsupported source mode must be rejected' >&2
  exit 1
fi

echo 'PASS: stable setup source modes'
# [source] - END
