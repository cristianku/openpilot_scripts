# [eps review] - START
import json
from pathlib import Path
from types import SimpleNamespace
from opendbc.car import Bus, structs
from opendbc.car.psa.carcontroller import CarController
from opendbc.car.psa.interface import CarInterface
from opendbc.car.psa.values import CAR

def harness():
  cp=CarInterface.get_non_essential_params(CAR.PSA_PEUGEOT_3008)
  sp=CarInterface.get_non_essential_params_sp(cp,CAR.PSA_PEUGEOT_3008)
  c=CarController({Bus.main:'psa_aee2010_r3'},cp,sp); c.model_sm=None
  c.params.EPS_DITHER_AMPLITUDE=0; c.frame=100
  cs=SimpleNamespace(out=structs.CarState(),eps_active=True,eps_state_lka=3,speed_kph=72,
                     is_dat_dira={},HS2_DYN_MDD_ETAT_2F6={},steering={'DRIVER_TORQUE':0})
  cs.out.canValid=True; cs.out.vEgo=cs.out.vEgoRaw=20
  cc=structs.CarControl(); cc.latActive=True; cc.actuators.torque=.6
  return c,cs,cc

def step(c,cs,cc):
  _,msgs=c.update(cc.as_reader(),structs.CarControlSP(),cs,(c.frame+1)*10_000_000)
  found=[m for m in msgs if m[0]==0x3F2]
  assert len(found)==1
  return bytes(found[0][1])

for case in ['disengage','eps_defect','low_speed','eps_inactive','driver_override']:
  c,cs,cc=harness(); before=step(c,cs,cc)
  assert (before[5]>>1)>0 and (before[3] or before[4]>>5)
  if case=='disengage': cc.latActive=False
  elif case=='eps_defect': cs.eps_state_lka=4; cs.eps_active=False
  elif case=='low_speed': cs.speed_kph=50
  elif case=='eps_inactive': cs.eps_state_lka=2; cs.eps_active=False
  else: cs.steering['DRIVER_TORQUE']=18
  repeated=[step(c,cs,cc) for _ in range(4)]
  after=step(c,cs,cc)
  assert all(d==before for d in repeated)
  assert after[3]==0 and after[4]>>5==0
  print(json.dumps({'case':case,'stale_active_repeats':4,'old':before.hex(),'next_steer_frame':after.hex()}))

# Load the unmodified safety test interface, moving compiler outputs to /private/tmp.
p=Path('opendbc/safety/tests/libsafety/libsafety_py.py').resolve()
ns={'__file__':str(p),'__name__':'review_libsafety'}
source=p.read_text().replace('dir=libsafety_dir','dir="/private/tmp"')
exec(compile(source,str(p),'exec'),ns)
s=ns['__getattr__']('libsafety'); packet=ns['make_CANPacket']
def init():
  assert s.set_safety_hooks(structs.CarParams.SafetyModel.psa,0)==0
  s.init_tests(); s.set_controls_allowed_lateral(True)
c,_,_=harness()
def tx(torque,factor=100):
  addr,data,bus=c.packer.make_can_msg('LANE_KEEP_ASSIST',0,{'TORQUE':torque,'TORQUE_FACTOR':factor,'STATUS':4,'unknown2':24})
  return bool(s.safety_tx_hook(packet(addr,bus,data)))
accepted=0
for factor in (25,37,65,100):
  for sign in (-1,1):
    init()
    for frame in range(300):
      s.set_timer(frame*10000)
      torque=round(sign*min(150,8*(frame//5+1))*100/factor)
      assert tx(torque,factor)
      accepted+=1
print(json.dumps({'compiled_safety_repeated_ramp_frames':accepted,'all_accepted':True}))
init()
for tq in (8,16,24,32): assert tx(tq)
for raw in (18,0):
  addr,data,bus=c.packer.make_can_msg('STEERING',0,{'DRIVER_TORQUE':raw})
  s.safety_rx_hook(packet(addr,bus,data))
  result=tx(32)
  assert not result
  print(json.dumps({'driver_raw':raw,'cached32_accepted':result}))
assert tx(0,0); assert tx(8)
print(json.dumps({'zero_then8_recovers':True}))

# [eps review] - END
