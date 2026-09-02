#!/usr/bin/env bash
set -euo pipefail

# [nnlc] - START
skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
common_script="${skill_root}/scripts/setup_psa_torque_common.sh"

# ShellCheck cannot see that the dynamically sourced common script consumes
# these configuration variables and the per-case Sunny switch.
# shellcheck disable=SC2034
BRANCH="psa-torque-sunny"
# shellcheck disable=SC2034
OPENPILOT_SOURCE_REPO="https://example.invalid/sunnypilot.git"
# shellcheck disable=SC2034
OPENPILOT_SOURCE_BRANCH="test-source"
# shellcheck disable=SC1090
source "${common_script}"

test_root="$(mktemp -d)"
test_passed="false"
cleanup() {
  local status="$1"
  trap - EXIT
  rm -rf "${test_root}"
  if [[ "${test_passed}" != "true" ]]; then
    status=1
  fi
  exit "${status}"
}
trap 'cleanup "$?"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

create_fixture() {
  local repo="$1"
  local prefix="$2"
  local controls_root="${repo}/${prefix}selfdrive/controls/lib"
  local sunny_root="${repo}/${prefix}sunnypilot/selfdrive/controls/lib"

  mkdir -p "${controls_root}" "${sunny_root}/nnlc"

  cat > "${sunny_root}/latcontrol_torque_ext.py" <<'PY'
class LatControlTorqueExt:
  def update(self, pid, ff, pid_log):
    self._ff = ff
    self._pid = pid
    self._pid_log = pid_log
PY

  cat > "${sunny_root}/nnlc/nnlc.py" <<'PY'
import numpy as np

from opendbc.car.lateral import FRICTION_THRESHOLD, get_friction
from opendbc.sunnypilot.car.interfaces import LatControlInputs
from opendbc.sunnypilot.car.lateral_ext import get_friction as get_friction_in_torque_space

class NeuralNetworkLateralControl(LatControlTorqueJerkAware):
  def __init__(self, lac_torque, CP, CP_SP, CI):
    super().__init__(lac_torque, CP, CP_SP, CI)
    self.params = Params()

  def update_neural_network_feedforward(self, friction_input):
    self._ff = self.model.evaluate(nn_input)

    # apply friction override for cars with low NN friction response
    if self.model.friction_override:
      self._pid_log.error += get_friction(friction_input, self._lateral_accel_deadzone, FRICTION_THRESHOLD, self.torque_params)

    self.update_output_torque(CS)
PY

  cat > "${controls_root}/latcontrol_torque.py" <<'PY'
class LatControlTorque:
  def update(self, pid_log, output_torque):

      pid_log.active = True
      pid_log.p = float(self.pid.p)
      pid_log.i = float(self.pid.i)
      pid_log.d = float(self.pid.d)
      pid_log.f = float(self.pid.f)
      pid_log.output = float(-output_torque) # TODO: log lat accel?
      pid_log.actualLateralAccel = float(measurement)
PY

  git -C "${repo}" init -q
  git -C "${repo}" add -- .
  git -C "${repo}" -c user.name=Test -c user.email=test@example.invalid commit -qm fixture
}

assert_patched() {
  local repo="$1"
  local prefix="$2"
  local controls_root="${repo}/${prefix}selfdrive/controls/lib"
  local sunny_root="${repo}/${prefix}sunnypilot/selfdrive/controls/lib"
  local expected_staged
  local actual_staged

  grep -Fq 'self._nnlc_pid = self._pid' "${sunny_root}/nnlc/nnlc.py" \
    || fail "dedicated NNLC PID was not retained for layout '${prefix}'"
  grep -Fq 'self._pid = self._nnlc_pid if self._nnlc_enabled else pid' "${sunny_root}/latcontrol_torque_ext.py" \
    || fail "dedicated NNLC PID was not selected for layout '${prefix}'"
  if grep -Fq 'self._pid = pid' "${sunny_root}/latcontrol_torque_ext.py"; then
    fail "base PID assignment remains for layout '${prefix}'"
  fi

  grep -Fq 'self._pid_log.error += get_friction_in_torque_space(friction_input' "${sunny_root}/nnlc/nnlc.py" \
    || fail "friction override is not in torque space for layout '${prefix}'"
  if grep -Fq 'FRICTION_THRESHOLD, get_friction' "${sunny_root}/nnlc/nnlc.py"; then
    fail "unused lateral-acceleration friction import remains for layout '${prefix}'"
  fi

  grep -Fq 'active_pid = self.extension._pid if self.extension._nnlc_enabled else self.pid' "${controls_root}/latcontrol_torque.py" \
    || fail "PID logging does not follow the active NNLC PID for layout '${prefix}'"

  expected_staged="$(printf '%s\n' \
    "${prefix}selfdrive/controls/lib/latcontrol_torque.py" \
    "${prefix}sunnypilot/selfdrive/controls/lib/latcontrol_torque_ext.py" \
    "${prefix}sunnypilot/selfdrive/controls/lib/nnlc/nnlc.py" | sort)"
  actual_staged="$(git -C "${repo}" diff --cached --name-only | sort)"
  [[ "${actual_staged}" == "${expected_staged}" ]] \
    || fail "unexpected staged files for layout '${prefix}': ${actual_staged}"
  git -C "${repo}" diff --cached --check
}

run_sunny_case() {
  local name="$1"
  local prefix="$2"
  local repo="${test_root}/${name}"
  local first_diff
  local second_diff

  mkdir -p "${repo}"
  create_fixture "${repo}" "${prefix}"
  USE_CUSTOM_NEURAL_NETWORK_DATA="true"
  patch_sunny_nnlc_controller "${repo}"
  assert_patched "${repo}" "${prefix}"

  first_diff="$(git -C "${repo}" diff --cached)"
  patch_sunny_nnlc_controller "${repo}"
  second_diff="$(git -C "${repo}" diff --cached)"
  [[ "${second_diff}" == "${first_diff}" ]] || fail "second patch changed ${name} again"
}

run_comma_case() {
  local repo="${test_root}/comma"
  mkdir -p "${repo}"
  create_fixture "${repo}" ""
  # shellcheck disable=SC2034
  USE_CUSTOM_NEURAL_NETWORK_DATA="false"
  patch_sunny_nnlc_controller "${repo}"
  git -C "${repo}" diff --quiet || fail "comma working tree was modified"
  git -C "${repo}" diff --cached --quiet || fail "comma index was modified"
}

run_sunny_case stable ""
run_sunny_case testing "openpilot/"
run_comma_case
test_passed="true"
echo "PASS: Sunny NNLC setup patch"
# [nnlc] - END
