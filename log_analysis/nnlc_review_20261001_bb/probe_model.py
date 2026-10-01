# [nnlc review] - START
import ast
import json
from pathlib import Path
import numpy as np

CHECKOUT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/new_openpilot_psa_torque_sunny_testing')
MODEL=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/neural-network-data/neural_network_lateral_control/PSA_PEUGEOT_3008.json')
ROOT=Path('/Users/cristianku/GitHub/COMMA.AI/CRISTIANKU/openpilot_scripts/log_analysis/nnlc_review_20261001_bb')
ns={'np':np,'load':json.load,'ACTIVATION_FUNCTION_NAMES':{'σ':'sigmoid'}}
parse=ast.parse((CHECKOUT/'openpilot/selfdrive/modeld/parse_model_outputs.py').read_text())
safe_exp=next(n for n in parse.body if isinstance(n,ast.FunctionDef) and n.name=='safe_exp')
exec(compile(ast.Module(body=[safe_exp],type_ignores=[]),str(CHECKOUT/'openpilot/selfdrive/modeld/parse_model_outputs.py'),'exec'),ns)
tree=ast.parse((CHECKOUT/'openpilot/sunnypilot/selfdrive/controls/lib/nnlc/model.py').read_text())
klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NNTorqueModel')
exec(compile(ast.Module(body=[klass],type_ignores=[]),str(CHECKOUT/'openpilot/sunnypilot/selfdrive/controls/lib/nnlc/model.py'),'exec'),ns)
model=ns['NNTorqueModel'](MODEL)
metadata=json.loads(MODEL.read_text())
legacy=metadata['input_vars']
runtime=['v_ego','actual_lateral_accel','lateral_jerk','roll']+[f'actual_lateral_accel_t{suffix}' for suffix in ['m03','m02','m01','p03','p06','p10','p15']]+[f'roll_t{suffix}' for suffix in ['m03','m02','m01','p03','p06','p10','p15']]
results=[]
for speed in [15.,20.,25.,30.]:
 for accel in [-1.,-.5,0.,.5,1.]:
  values={key:(speed if key=='v_ego' else accel if key.startswith('actual_lateral_accel') else 0.) for key in legacy}
  correct=[values[key] for key in legacy]
  live=[values[key] for key in runtime]
  results.append(dict(speed=speed,lateral_accel=accel,legacy_order=model.evaluate(correct),runtime_order=model.evaluate(live)))
data=dict(model=str(MODEL),legacy_order=legacy,runtime_order=runtime,friction_override=model.friction_override,results=results)
(ROOT/'model_probe.json').write_text(json.dumps(data,indent=2))
for r in results: print(r)
# [nnlc review] - END
