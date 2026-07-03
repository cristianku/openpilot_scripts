#!/usr/bin/env bash
# Reset the learned (auto-tuned) params on the comma device so lateral
# learning restarts from the offline values in opendbc (steerActuatorDelay,
# torque_data/override.toml).
#
# Deletes ONLY learned caches:
#   LiveDelay             lagd actuator-delay estimate
#   LiveTorqueParameters  torqued latAccelFactor/friction fit
#   LiveParametersV2      stiffness / steer ratio / angle offset
#   LiveParameters        same, older builds
#
# Never touches user toggles (LiveTorqueParamsToggle, LiveTorqueParamsRelaxedToggle)
# or CalibrationParams (camera calibration is slow to relearn and stays valid).
#
# Usage: reset_learned_params.sh [--reboot] [--force]
#   --reboot  reboot the device after wiping
#   --force   skip the offroad check (NOT recommended)

set -euo pipefail

COMMA_HOST="${COMMA_HOST:-comma}"
PARAMS_DIR="/data/params/d"
LEARNED_PARAMS="LiveDelay LiveTorqueParameters LiveParametersV2 LiveParameters"

die() { echo "ERROR: $*" >&2; exit 1; }

do_reboot=0
force=0
for arg in "$@"; do
  case "$arg" in
    --reboot) do_reboot=1 ;;
    --force)  force=1 ;;
    *) die "unknown option: $arg" ;;
  esac
done

# Reachability
ssh -o ConnectTimeout=8 "$COMMA_HOST" "true" 2>/dev/null \
  || die "device '$COMMA_HOST' unreachable via ssh"

# Refuse to wipe while onroad: controlsd would keep the old values in memory
# and rewrite them, and changing params mid-drive is unsafe anyway.
if [ "$force" -ne 1 ]; then
  onroad="$(ssh "$COMMA_HOST" "cat $PARAMS_DIR/IsOnroad 2>/dev/null || echo 0")"
  if [ "$onroad" = "1" ]; then
    die "device is ONROAD. Go offroad (ignition off) first, or use --force."
  fi
fi

echo "Device:  $COMMA_HOST"
echo "Learned params present before reset:"
found="$(ssh "$COMMA_HOST" "cd $PARAMS_DIR && ls $LEARNED_PARAMS 2>/dev/null || true")"
if [ -z "$found" ]; then
  echo "  (none - already clean)"
else
  echo "$found" | sed 's/^/  /'
  rm_list=""
  for p in $found; do rm_list="$rm_list $PARAMS_DIR/$p"; done
  ssh "$COMMA_HOST" "rm -f$rm_list"
  echo "Deleted."
fi

# Confirm
leftover="$(ssh "$COMMA_HOST" "cd $PARAMS_DIR && ls $LEARNED_PARAMS 2>/dev/null || true")"
[ -z "$leftover" ] || die "still present after delete: $leftover"

echo "Kept: LiveTorqueParamsToggle, LiveTorqueParamsRelaxedToggle, CalibrationParams"

if [ "$do_reboot" -eq 1 ]; then
  echo "Rebooting device..."
  ssh "$COMMA_HOST" "sudo reboot" || true
  echo "Reboot command sent."
else
  echo "Done. Reboot the device (or restart openpilot) before the next drive."
fi
