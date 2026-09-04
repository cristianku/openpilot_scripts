#!/usr/bin/env bash
set -euo pipefail

skill_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
common_script="${skill_root}/scripts/setup_psa_torque_common.sh"
test_root="$(mktemp -d)"
trap 'rm -rf "${test_root}"' EXIT

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

commit_fixture() {
  local repo="$1"
  local message="$2"
  git -C "${repo}" -c user.name=Test -c user.email=test@example.invalid commit -qm "${message}"
}

neural_data_repo="${test_root}/neural-network-data"
mkdir -p "${neural_data_repo}/neural_network_lateral_control"
git -C "${neural_data_repo}" init -q
git -C "${neural_data_repo}" checkout -qb master
printf '%s\n' 'old model data' > "${neural_data_repo}/neural_network_lateral_control/model"
git -C "${neural_data_repo}" add -- .
commit_fixture "${neural_data_repo}" 'old neural data'
old_neural_data_sha="$(git -C "${neural_data_repo}" rev-parse HEAD)"
printf '%s\n' 'custom Peugeot model data' > "${neural_data_repo}/neural_network_lateral_control/model"
git -C "${neural_data_repo}" add -- .
commit_fixture "${neural_data_repo}" 'custom Peugeot neural data'
expected_neural_data_sha="$(git -C "${neural_data_repo}" rev-parse HEAD)"

openpilot_repo="${test_root}/openpilot"
controls_root="${openpilot_repo}/selfdrive/controls/lib"
sunny_root="${openpilot_repo}/sunnypilot/selfdrive/controls/lib"
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

cat > "${openpilot_repo}/.gitmodules" <<'EOF'
[submodule "sunnypilot/neural_network_data"]
	path = sunnypilot/neural_network_data
	url = https://example.invalid/upstream-neural-network-data.git
EOF

git -C "${openpilot_repo}" init -q
git -C "${openpilot_repo}" checkout -qb psa-torque-sunny-testing
git -C "${openpilot_repo}" add -- .gitmodules selfdrive sunnypilot/selfdrive
git -C "${openpilot_repo}" update-index --add --cacheinfo "160000,${old_neural_data_sha},sunnypilot/neural_network_data"
commit_fixture "${openpilot_repo}" 'upstream Sunny fixture'
git -C "${openpilot_repo}" config user.name Test
git -C "${openpilot_repo}" config user.email test@example.invalid

BRANCH="psa-torque-sunny-testing"
WORKSPACE_ROOT="${test_root}"
OPENPILOT_DIR="openpilot"
OPENPILOT_REPO="${openpilot_repo}"
OPENPILOT_SOURCE_REPO="${openpilot_repo}"
OPENPILOT_SOURCE_BRANCH="${BRANCH}"
USE_CUSTOM_NEURAL_NETWORK_DATA="true"
NEURAL_NETWORK_DATA_REPO="${neural_data_repo}"
NEURAL_NETWORK_DATA_BRANCH="master"
NO_PUSH="true"
COMMIT_MESSAGE="test Sunny neural data only"
# shellcheck disable=SC1090
source "${common_script}"

# Keep the test focused on the already-cloned Sunny customization stage.
recreate_clone_from_source() { :; }
enable_psa_torqued_learning() { :; }
set_opendbc_pointer() { :; }

main >/dev/null

actual_files="$(git -C "${openpilot_repo}" diff-tree --no-commit-id --name-only -r HEAD | sort)"
expected_files="$(printf '%s\n' .gitmodules sunnypilot/neural_network_data | sort)"
[[ "${actual_files}" == "${expected_files}" ]] \
  || fail "Sunny setup committed files other than neural-network-data: ${actual_files}"

actual_neural_data_sha="$(git -C "${openpilot_repo}" ls-tree HEAD sunnypilot/neural_network_data | awk '{print $3}')"
[[ "${actual_neural_data_sha}" == "${expected_neural_data_sha}" ]] \
  || fail "neural-network-data points to ${actual_neural_data_sha}, expected ${expected_neural_data_sha}"

for runtime_file in \
  selfdrive/controls/lib/latcontrol_torque.py \
  sunnypilot/selfdrive/controls/lib/latcontrol_torque_ext.py \
  sunnypilot/selfdrive/controls/lib/nnlc/nnlc.py; do
  git -C "${openpilot_repo}" diff --quiet HEAD^ HEAD -- "${runtime_file}" \
    || fail "Sunny NNLC runtime source was modified: ${runtime_file}"
done

git -C "${neural_data_repo}" cat-file -e "${actual_neural_data_sha}:neural_network_lateral_control/model"
echo "PASS: Sunny setup only inserts neural_network_lateral_control data"
