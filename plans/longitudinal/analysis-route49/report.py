# [longitudinal analysis] - START
"""Fit reference tables and evaluate on a separate stock-ACC route; offline only."""
import csv
import json
import os
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR','/private/tmp/psa49-matplotlib')
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import least_squares
from analyze import OUT, stats, episodes

ROUTES=['00000049--a95dde6809','0000003a--e445e79563']
DATA=[dict(np.load(OUT/(r+'-aligned.npz'))) for r in ROUTES]
FIELDS=['GMP_WHEEL_TORQUE','GMP_POTENTIAL_WHEEL_TORQUE']
POINTS=np.array([0.,.25,.5,.75])
OLD_BP=np.array([-1.,-.5,0.,.5,1.,1.5,2.])
OLD_V=np.array([-400.,-300.,120.,350.,550.,800.,1000.])


def fit(x,y):
    return least_squares(lambda c:x@c-y,np.linalg.lstsq(x,y,rcond=None)[0],loss='soft_l1',f_scale=60).x


def eligible(d):
    # Agreement is an observable proxy, NOT a measured zero road grade.
    return d['gmp']&(abs(d['ACCEL_LONGI_CALIB']-d['accel'])<.1)&(abs(d['jerk'])<.25)&(d['accel']>=0)&(d['accel']<=.85)


def errors(pred,actual):
    e=pred-actual
    return {'mae_Nm':float(np.mean(abs(e))),'rmse_Nm':float(np.sqrt(np.mean(e**2))),'bias_Nm':float(np.mean(e))}


result={'status':'OFFLINE CANDIDATE, NOT APPLIED TO CONTROLLER; no extrapolation supported',
        'driver_confirmation':'Route 49 includes uphill then downhill, explicitly confirmed by Cristian.',
        'method':'10 Hz zero-order-held CAN/carState, source age <=150 ms; acceleration from vEgoRaw via centered 1.1 s Savitzky-Golay derivative; trim +-1 s around pedals, ACC/mode/validity boundaries; speed >2 m/s.',
        'table_mask':'GMP clean, abs(ACCEL_LONGI_CALIB - speed_derivative)<0.1 m/s2, abs(jerk)<0.25 m/s3, acceleration 0..0.85 m/s2. This is sensor agreement, not independently verified flat road.',
        'units':'Torque units Nm according to DBC, physical field semantics still subject to vehicle verification.',
        'accel_points':POINTS.tolist(),'candidates':{},'can_domain_models':{},'braking':{},'grade_proxy_groups':{}}
rows=[]
for field in FIELDS:
    d=DATA[0]; m=eligible(d); x=np.c_[np.ones(m.sum()),d['accel'][m]]; y=d[field][m]
    c=fit(x,y)
    ep=d['episode'][m]; unique=np.unique(ep)
    rng=np.random.default_rng(49)
    boot=[]
    for _ in range(300):
        picked=rng.choice(unique,len(unique),replace=True)
        idx=np.concatenate([np.flatnonzero(ep==e) for e in picked])
        if np.ptp(x[idx,1])<.1:continue
        coeff=fit(x[idx],y[idx]);boot.append(coeff[0]+coeff[1]*POINTS)
    lower,upper=np.quantile(boot,[.05,.95],axis=0)
    table=c[0]+c[1]*POINTS
    evaluation={}
    for route,d in zip(ROUTES,DATA):
        z=eligible(d)
        evaluation[route]={'seconds':round(z.sum()*.1,1),'episodes':len(np.unique(d['episode'][z])),'new':errors(c[0]+c[1]*d['accel'][z],d[field][z]),'elkoled':errors(np.interp(d['accel'][z],OLD_BP,OLD_V),d[field][z])}
    result['candidates'][field]={'intercept':float(c[0]),'slope':float(c[1]),'torque_values_rounded':np.rint(table).astype(int).tolist(),'bootstrap_episode_p05':lower.tolist(),'bootstrap_episode_p95':upper.tolist(),'evaluation':evaluation}
    for a,value,lo,hi in zip(POINTS,table,lower,upper):
        z=m&(abs(DATA[0]['accel']-a)<.125)
        rows.append({'accel_m_s2':a,'field':field,'candidate_Nm':round(value),'bootstrap_p05_Nm':round(lo),'bootstrap_p95_Nm':round(hi),'observed_seconds_in_bin':round(z.sum()*.1,1),'episodes_in_bin':len(np.unique(DATA[0]['episode'][z]))})
    # Explain the stronger CAN-domain association without treating this as a target-acceleration map.
    d=DATA[0]; m=d['gmp']; x=np.c_[np.ones(m.sum()),d['ACCEL_LONGI_CALIB'][m]]; c=fit(x,d[field][m])
    result['can_domain_models'][field]={'intercept':float(c[0]),'slope':float(c[1]),'evaluation':{route:errors(c[0]+c[1]*d['ACCEL_LONGI_CALIB'][d['gmp']],d[field][d['gmp']]) for route,d in zip(ROUTES,DATA)},'warning':'ACCEL_LONGI_CALIB is not CC.actuators.accel. Grade/bias/filtering may contribute. Not a drop-in control mapping.'}

for route,d in zip(ROUTES,DATA):
    group=[]
    offset=d['ACCEL_LONGI_CALIB']-d['accel']
    for name,z in [('negative_proxy',offset<-.15),('near_agreement',abs(offset)<=.15),('positive_proxy',offset>.15)]:
        z=z&d['gmp']&(abs(d['accel']-.5)<.125)
        group.append({'group':name,'seconds':round(z.sum()*.1,1),'wheel':stats(d['GMP_WHEEL_TORQUE'][z]),'potential':stats(d['GMP_POTENTIAL_WHEEL_TORQUE'][z]),'proxy_m_s2':stats(offset[z])})
    result['grade_proxy_groups'][route]=group
    lagscan=[]
    for lag in np.arange(0,1.01,.1):
        a=np.interp(d['t']+lag,d['t'],d['accel']); m=d['braking']; e=a[m]-d['MDD_DESIRED_DECELERATION'][m]
        lagscan.append({'lag_s':round(float(lag),1),'rmse_m_s2':float(np.sqrt(np.mean(e**2)))})
    # Fixed 0.4 s comparison chosen on route49, retained for reference route validation.
    measured=np.interp(d['t']+.4,d['t'],d['accel'])
    brake_bins=[]
    for target in [-1.25,-1.,-.75,-.5,-.25]:
        z=d['braking']&(abs(d['MDD_DESIRED_DECELERATION']-target)<.125)
        if z.sum():brake_bins.append({'command_bin':target,'seconds':round(z.sum()*.1,1),'command':stats(d['MDD_DESIRED_DECELERATION'][z]),'measured_after_04s':stats(measured[z])})
    result['braking'][route]={'delay_scan':lagscan,'bins':brake_bins,'note':'Delay inferred from stock closed-loop data and smoothed speed, not an isolated actuator step response; no numerical torque sentinels used as commands.'}

with (OUT/'sensor_agreement_diagnostic_table.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
(OUT/'calibration_results.json').write_text(json.dumps(result,indent=2)+'\n')

# Human-reviewable plots, full route plus field relationships.
d=DATA[0];t=d['relative_t'];fig,axes=plt.subplots(4,1,figsize=(15,11),sharex=True,layout='constrained')
axes[0].plot(t,d['v']*3.6,label='Velocità');axes[0].plot(t,d['SPEED_SETPOINT'],alpha=.5,label='Setpoint CAN');axes[0].set_ylim(0,100);axes[0].set_ylabel('km/h');axes[0].legend(loc='upper right')
axes[1].plot(t,d['accel'],label='Derivata velocità');axes[1].plot(t,d['ACCEL_LONGI_CALIB'],alpha=.7,label='ACCEL_LONGI_CALIB');axes[1].set_ylim(-2.5,2.5);axes[1].set_ylabel('m/s²');axes[1].legend(loc='upper right')
for field in FIELDS:
    axes[2].plot(t,np.where(d['gmp_raw'],d[field],np.nan),label=field)
axes[2].set_ylabel('Nm (DBC)');axes[2].legend(loc='upper right')
axes[3].plot(t,d['ACC_STATUS'],label='ACC_STATUS');axes[3].plot(t,d['brake'],label='Pedale freno');axes[3].plot(t,d['gas'],label='Pedale gas');axes[3].set_ylabel('Stato / flag');axes[3].set_xlabel('Secondi dall’inizio carState');axes[3].legend(loc='upper right')
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Route 49 — ACC originale, salita e discesa');fig.savefig(OUT/'route49-overview.png',dpi=150);plt.close(fig)
fig,axes=plt.subplots(1,3,figsize=(17,5),layout='constrained')
m=d['gmp'];offset=d['ACCEL_LONGI_CALIB']-d['accel']
sc=axes[0].scatter(d['accel'][m],d[FIELDS[0]][m],c=offset[m],s=8,cmap='coolwarm',vmin=-.8,vmax=.8)
axes[0].plot(OLD_BP,OLD_V,'k--',label='Elkoled');axes[0].set_xlim(-.5,1.15);axes[0].set_ylim(-150,1000);axes[0].set_xlabel('Accelerazione da velocità [m/s²]');axes[0].set_ylabel('GMP_WHEEL_TORQUE [Nm DBC]');axes[0].legend()
fig.colorbar(sc,ax=axes[0],label='CALIB − derivata velocità [m/s²], proxy')
axes[1].scatter(d['ACCEL_LONGI_CALIB'][m],d[FIELDS[0]][m],s=8,alpha=.4)
c=result['can_domain_models'][FIELDS[0]];xx=np.linspace(-.5,1.7,100);axes[1].plot(xx,c['intercept']+c['slope']*xx,'r');axes[1].set_xlabel('ACCEL_LONGI_CALIB [m/s²]');axes[1].set_ylabel('GMP_WHEEL_TORQUE [Nm DBC]')
for route,dd,color in zip(ROUTES,DATA,['tab:blue','tab:orange']):
    z=eligible(dd);axes[2].scatter(dd['accel'][z],dd[FIELDS[0]][z],s=12,alpha=.5,color=color,label=route[:8])
c=result['candidates'][FIELDS[0]];axes[2].plot(POINTS,c['torque_values_rounded'],'r-o',label='Candidata route49');axes[2].plot(OLD_BP,OLD_V,'k--',label='Elkoled');axes[2].set_xlim(-.05,.9);axes[2].set_ylim(-100,750);axes[2].set_xlabel('Accelerazione da velocità [m/s²]');axes[2].set_ylabel('Nm DBC');axes[2].legend()
for ax in axes:ax.grid(alpha=.2)
fig.suptitle('Separazione dell’effetto dei dislivelli: tabella candidata offline, non validata');fig.savefig(OUT/'torque-calibration.png',dpi=150);plt.close(fig)
print(json.dumps({'candidates':result['candidates'],'grade_proxy_groups':result['grade_proxy_groups'],'braking':result['braking']},indent=2))


# Preferred candidate: account for grade with the recorded orientation, instead of
# selecting rare sensor-agreement intervals. Body pitch is not surveyed road grade.
result['pitch_compensated']={'definition':'equivalent_accel = speed_derivative + 9.81*sin(carControl.orientationNED[1])',
    'limitations':'Body pitch estimate includes calibration/suspension errors; no wind measurement. Stock closed-loop association, not identified open-loop dynamics.',
    'models':{}, 'pitch_checks':{}}
PITCH_POINTS=np.array([0.,.25,.5,.75,1.])
pitch_rows=[]
for route,d in zip(ROUTES,DATA):
    m=d['gmp']&np.isfinite(d['pitch'])
    equivalent=d['accel']+9.81*np.sin(d['pitch'])
    result['pitch_compensated']['pitch_checks'][route]={
        'pitch_degrees':stats(np.rad2deg(d['pitch'][m])),
        'equivalent_accel':stats(equivalent[m]),
        'offset_gravity_correlation':float(np.corrcoef((d['ACCEL_LONGI_CALIB']-d['accel'])[m],(9.81*np.sin(d['pitch']))[m])[0,1]),
        'calib_minus_equivalent':stats((d['ACCEL_LONGI_CALIB']-equivalent)[m])}
for field in FIELDS:
    d=DATA[0];m=d['gmp']&np.isfinite(d['pitch']);equivalent=d['accel']+9.81*np.sin(d['pitch'])
    x=np.c_[np.ones(m.sum()),equivalent[m]];y=d[field][m];c=fit(x,y)
    ep=d['episode'][m];unique=np.unique(ep);rng=np.random.default_rng(49);boot=[]
    for _ in range(300):
        chosen=rng.choice(unique,len(unique),replace=True)
        idx=np.concatenate([np.flatnonzero(ep==e) for e in chosen])
        coeff=fit(x[idx],y[idx]);boot.append(coeff[0]+coeff[1]*PITCH_POINTS)
    lo,hi=np.quantile(boot,[.05,.95],axis=0)
    vals=c[0]+c[1]*PITCH_POINTS
    evaluations={}
    for route,dd in zip(ROUTES,DATA):
        z=dd['gmp']&np.isfinite(dd['pitch']);aa=dd['accel']+9.81*np.sin(dd['pitch'])
        evaluations[route]={'new':errors(c[0]+c[1]*aa[z],dd[field][z]),
            'elkoled_with_same_pitch_correction':errors(np.interp(aa[z],OLD_BP,OLD_V),dd[field][z]),
            'current_elkoled_without_pitch':errors(np.interp(dd['accel'][z],OLD_BP,OLD_V),dd[field][z])}
    result['pitch_compensated']['models'][field]={'intercept':float(c[0]),'slope':float(c[1]),'accel_points':PITCH_POINTS.tolist(),'torque_values_rounded':np.rint(vals).astype(int).tolist(),'bootstrap_episode_p05':lo.tolist(),'bootstrap_episode_p95':hi.tolist(),'evaluation':evaluations}
    for a,value,l,h in zip(PITCH_POINTS,vals,lo,hi):
        z=m&(abs(equivalent-a)<.125)
        pitch_rows.append({'equivalent_accel_m_s2':a,'field':field,'candidate_Nm':round(value),'bootstrap_p05_Nm':round(l),'bootstrap_p95_Nm':round(h),'observed_seconds_in_bin':round(z.sum()*.1,1),'episodes_in_bin':len(np.unique(d['episode'][z]))})
with (OUT/'candidate_torque_table.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(pitch_rows[0]));writer.writeheader();writer.writerows(pitch_rows)
(OUT/'calibration_results.json').write_text(json.dumps(result,indent=2)+'\n')
fig,axes=plt.subplots(1,2,figsize=(13,5),layout='constrained')
for field,ax in zip(FIELDS,axes):
    for route,dd,color in zip(ROUTES,DATA,['tab:blue','tab:orange']):
        z=dd['gmp'];aa=dd['accel']+9.81*np.sin(dd['pitch'])
        ax.scatter(aa[z],dd[field][z],s=7,alpha=.25,color=color,label=route[:8])
    c=result['pitch_compensated']['models'][field]
    ax.plot(PITCH_POINTS,c['torque_values_rounded'],'r-o',label='Candidata route49')
    ax.plot(OLD_BP,OLD_V,'k--',label='Elkoled')
    ax.set_xlim(-.6,1.4);ax.set_ylim(-300,1100);ax.set_title(field);ax.set_xlabel('Accelerazione + 9.81 sin(pitch) [m/s²]');ax.set_ylabel('Nm secondo DBC');ax.grid(alpha=.2);ax.legend()
fig.suptitle('Tabella di base con pendenza esplicita — confronto offline su due route')
fig.savefig(OUT/'pitch-compensated-torque.png',dpi=160);plt.close(fig)
print('Pitch-compensated candidate saved',flush=True)
# [longitudinal analysis] - END
