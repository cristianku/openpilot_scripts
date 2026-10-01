import importlib.util
import json
from pathlib import Path

source = Path('/tmp/analyze_psa_noise_20261001.py').read_text()
old = "state.update(cc_t=t,requested=cc.actuators.accel,long=int(cc.longActive),enabled=int(cc.enabled),longstate=str(cc.actuators.longControlState))"
new = "state.update(cc_t=t,requested=cc.actuators.accel,long=int(cc.longActive),enabled=int(cc.enabled),longstate=str(cc.actuators.longControlState),pitch=cc.orientationNED[1] if len(cc.orientationNED)==3 else 0.0)"
assert source.count(old) == 1
patched = Path('/tmp/analyze_psa_review_with_pitch_20261001.py')
patched.write_text(source.replace(old, new))
spec = importlib.util.spec_from_file_location('psa_review_analyzer', str(patched))
analyzer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(analyzer)
root = Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/longitudinal_review_20261001_1700')
analyzer.ROOT = root
verification = json.loads((root / 'acquisition_verification.json').read_text())
analyzer.VERIFIED = set(verification['verified_rlogs'])
manifest = json.loads((root / 'acquisition_manifest.json').read_text())
for entry in manifest:
    analyzer.process(entry['route'], 'qlog')
analyzer.process(manifest[0]['route'], 'rlog')
