# [longitudinal analysis] - START
"""Offline stock ACC characterization. Does not edit control code or contact the car."""
from pathlib import Path
import collections
import hashlib
import json
import sys

import capnp
import numpy as np
import zstandard
from scipy.signal import savgol_filter
from scipy.ndimage import minimum_filter1d

OUT = Path(__file__).resolve().parent
HUB = OUT.parents[2]
ROOT = HUB.parent
sys.path.insert(0, str(ROOT / 'opendbc'))
from opendbc.can.packer import CANPacker
from opendbc.can.parser import get_raw_value

capnp.remove_import_hook()
schema = capnp.load(str(ROOT / 'new_openpilot_psa_torque_sunny_testing/openpilot/cereal/log.capnp'), imports=[str(ROOT / 'opendbc/opendbc/car')])
packer = CANPacker('psa_aee2010_r3')
SIGNALS = {
    (1, 0x2B6): ['ACC_STATUS', 'GMP_WHEEL_TORQUE', 'GMP_POTENTIAL_WHEEL_TORQUE', 'WHEEL_TORQUE_REQUEST', 'POTENTIAL_WHEEL_TORQUE_REQUEST', 'MDD_DESIRED_DECELERATION', 'MDD_DECEL_CONTROL_REQ', 'MDD_DECEL_TYPE', 'MIN_TIME_FOR_DESIRED_GEAR', 'GEAR_TYPE', 'COUNTER'],
    (1, 0x452): ['RVV_ACC_ACTIVATION_REQ', 'SPEED_SETPOINT', 'COCKPIT_GO_ACC_REQUEST'],
    (1, 0x32D): ['ACCEL_LONGI_CALIB', 'FA_ETAT_DECEL', 'APPUI_FREIN_RECONSTRUIT'],
    (0, 0x348): ['P152_Gearbx_stGear'],
    (1, 0x38D): ['ACCEL_LONGI_ROUES'],
}


def extract(route):
    cache = OUT / (route + '.npz')
    if cache.exists():
        cached = dict(np.load(cache))
        if 'orientation' in cached:
            return cached
    rows = collections.defaultdict(list)
    files = []
    for path in sorted((HUB / 'log_analysis/dashcam_mode_bibbia_longitudinale' / route).glob('*/rlog.zst'), key=lambda p:int(p.parent.name.rsplit('--', 1)[1])):
        data = path.read_bytes()
        files.append({'path':str(path.relative_to(HUB)), 'sha256':hashlib.sha256(data).hexdigest()})
        with zstandard.ZstdDecompressor().stream_reader(data) as reader:
            raw = reader.read()
        for e in schema.Event.read_multiple_bytes(raw):
            t = e.logMonoTime / 1e9
            kind = e.which()
            if kind == 'carState':
                s = e.carState
                rows['state'].append([t, s.vEgo, s.vEgoRaw, s.aEgo, s.gasPressed, s.brakePressed, s.canValid, s.steeringAngleDeg, s.cruiseState.enabled])
            elif kind == 'carControl' and len(e.carControl.orientationNED) == 3:
                rows['orientation'].append([t, e.carControl.orientationNED[1]])
            elif kind == 'can':
                for c in e.can:
                    key = (c.src, c.address)
                    if key not in SIGNALS:
                        continue
                    msg = packer.dbc.addr_to_msg[c.address]
                    vals = [get_raw_value(bytes(c.dat), msg.sigs[n]) * msg.sigs[n].factor + msg.sigs[n].offset for n in SIGNALS[key]]
                    rows[hex(c.address)].append([t, *vals])
        print('Extracted', path.parent.name, flush=True)
    arrays = {k:np.asarray(v) for k,v in rows.items()}
    for k,a in arrays.items():
        a=a[np.argsort(a[:,0],kind='stable')]
        arrays[k]=a[np.r_[True,np.diff(a[:,0])>0]]
    np.savez_compressed(cache, **arrays)
    (OUT / (route + '-sources.json')).write_text(json.dumps(files,indent=2)+'\n')
    return arrays


def episodes(mask):
    edges=np.diff(np.r_[False,mask,False].astype(int))
    return list(zip(np.flatnonzero(edges==1),np.flatnonzero(edges==-1)))


def prepare(route):
    raw=extract(route)
    s=raw['state']
    t=np.arange(s[0,0]+1,s[-1,0]-1,0.1)
    d={'t':t,'relative_t':t-s[0,0]}
    # Zero-order hold for discrete states; no interpolation across CAN modes.
    def sample(key, names):
        arr=raw[key]
        idx=np.searchsorted(arr[:,0],t,side='right')-1
        age=t-arr[np.maximum(idx,0),0]
        for j,n in enumerate(names):
            d[n]=arr[np.maximum(idx,0),j+1].copy()
            d[n][(idx<0)|(age>0.15)]=np.nan
    sample('state',['v','vraw','aego','gas','brake','canvalid','steer','cruise'])
    if 'orientation' in raw:
        sample('orientation',['pitch'])
    for (bus,addr),names in SIGNALS.items():
        if hex(addr) in raw: sample(hex(addr),names)
    speed=np.interp(t,s[:,0],s[:,2])
    d['accel']=savgol_filter(speed,11,2,deriv=1,delta=0.1)
    d['jerk']=savgol_filter(speed,11,3,deriv=2,delta=0.1)
    base=(d['gas']==0)&(d['brake']==0)&(d['canvalid']==1)&(d['v']>2)&(d['ACC_STATUS']==4)
    gmp=base&(d['WHEEL_TORQUE_REQUEST']==1)&(d['POTENTIAL_WHEEL_TORQUE_REQUEST']==1)&(d['MDD_DECEL_CONTROL_REQ']==0)&(d['GMP_WHEEL_TORQUE']>-3999)&(d['GMP_POTENTIAL_WHEEL_TORQUE']>-3999)
    braking=base&(d['MDD_DECEL_CONTROL_REQ']==1)&(d['MDD_DESIRED_DECELERATION']<2)
    # Exclude +-1 s around all mode/pedal/CAN boundaries, including differentiation support.
    d['gmp']=minimum_filter1d(gmp.astype(int),size=21,mode='constant',cval=0).astype(bool)
    d['braking']=minimum_filter1d(braking.astype(int),size=21,mode='constant',cval=0).astype(bool)
    d['gmp_raw']=gmp
    d['braking_raw']=braking
    ep=np.full(len(t),-1)
    for i,(a,b) in enumerate(episodes(gmp)):ep[a:b]=i
    d['episode']=ep
    np.savez_compressed(OUT/(route+'-aligned.npz'),**d)
    return d


def stats(x):
    x=x[np.isfinite(x)]
    return {'n':len(x),'min':float(np.min(x)),'p10':float(np.quantile(x,.1)),'median':float(np.median(x)),'p90':float(np.quantile(x,.9)),'max':float(np.max(x))} if len(x) else {'n':0}


def bins(d,mask,lag):
    a=np.interp(d['t']+lag,d['t'],d['accel'])
    result=[]
    for center in np.arange(-1.5,2.01,.25):
        m=mask&(abs(a-center)<.125)
        if m.sum()<5: continue
        result.append({'accel_center':float(center),'seconds':round(m.sum()*.1,1),'episodes':len(np.unique(d['episode'][m])),'speed_kph':stats(d['v'][m]*3.6),'wheel':stats(d['GMP_WHEEL_TORQUE'][m]),'potential':stats(d['GMP_POTENTIAL_WHEEL_TORQUE'][m])})
    return result


def characterize(route,d):
    scans=[]
    for lag in np.arange(0,1.01,.1):
        a=np.interp(d['t']+lag,d['t'],d['accel'])
        for torque in ('GMP_WHEEL_TORQUE','GMP_POTENTIAL_WHEEL_TORQUE'):
            m=d['gmp']
            # Exploratory delay scan, not independent validation or physical delay identification.
            x=np.column_stack([np.ones(m.sum()),d[torque][m],d['v'][m]**2])
            coef=np.linalg.lstsq(x,a[m],rcond=None)[0]
            error=a[m]-x@coef
            scans.append({'lag':round(float(lag),2),'field':torque,'rmse_accel':float(np.sqrt(np.mean(error**2))),'coefficients':coef.tolist()})
    result={'gmp_seconds_raw':d['gmp_raw'].sum()*.1,'gmp_seconds_filtered':d['gmp'].sum()*.1,'brake_seconds_raw':d['braking_raw'].sum()*.1,'brake_seconds_filtered':d['braking'].sum()*.1,'acc_status_counts':dict(zip(*[a.tolist() for a in np.unique(d['ACC_STATUS'],return_counts=True)])),'gmp_acceleration':stats(d['accel'][d['gmp']]),'braking_acceleration':stats(d['accel'][d['braking']]),'decel_command':stats(d['MDD_DESIRED_DECELERATION'][d['braking']]),'wheel':stats(d['GMP_WHEEL_TORQUE'][d['gmp']]),'potential':stats(d['GMP_POTENTIAL_WHEEL_TORQUE'][d['gmp']]),'potential_minus_wheel':stats((d['GMP_POTENTIAL_WHEEL_TORQUE']-d['GMP_WHEEL_TORQUE'])[d['gmp']]),'lag_scan':scans,'bins_lag0':bins(d,d['gmp'],0),'bins_lag05':bins(d,d['gmp'],.5),'steady_bins':bins(d,d['gmp']&(abs(d['jerk'])<.25),0)}
    (OUT/(route+'-summary.json')).write_text(json.dumps(result,indent=2)+'\n')
    print(route,json.dumps({k:v for k,v in result.items() if k not in ('lag_scan','bins_lag0','bins_lag05','steady_bins')},indent=2),flush=True)
    return result


if __name__=='__main__':
    for route in ('00000049--a95dde6809','0000003a--e445e79563'):
        characterize(route,prepare(route))
# [longitudinal analysis] - END
