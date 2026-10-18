# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd, numpy as np
m = pd.read_parquet("out/m.parquet").sort_values("t").reset_index(drop=True)
m["a"] = m.aEgo.shift(-10)  # 200 ms
m["vk"] = m.vEgo*3.6
gmp = (m.ACC_STATUS==4)&(m.POTENTIAL_WHEEL_TORQUE_REQUEST==1)&(m.WHEEL_TORQUE_REQUEST==1)&(~m.gas.astype(bool))
g = m[gmp].copy()
ab = [-0.6,-0.3,-0.1,0.1,0.3,0.5,0.7,1.0]
vb = [35,60,80,100,115,130]
g["ab"] = pd.cut(g.a, ab); g["vb"] = pd.cut(g.vk, vb)
t = g.pivot_table(index="ab", columns="vb", values="GMP_WHEEL_TORQUE", aggfunc="median", observed=False).round(0)
n = g.pivot_table(index="ab", columns="vb", values="GMP_WHEEL_TORQUE", aggfunc="count", observed=False)
print("STOCK median GMP_WHEEL_TORQUE [Nm]  (righe aEgo, colonne km/h)"); print(t.where(n>=25).to_string())
print("counts"); print(n.to_string())
AL=(-1.0,-0.5,0.0,0.25,0.5,0.75,1.0,1.5,2.0); TL=(-400,-300,179,301,424,547,670,800,1000); PL=(-400,-300,169,279,390,501,612,800,1000)
print("\nCONFRONTO modello stock vs port (Nm)")
print("a_req  port | stock@50  @80  @100  @120 km/h")
for a in [-0.4,-0.2,0.0,0.25,0.5,0.75,1.0,1.5]:
    st = [(a+0.0887+1.55e-4*(v/3.6)**2)/1.355e-3 for v in (50,80,100,120)]
    print(f"{a:5.2f} {np.interp(a,AL,TL):6.0f} | " + " ".join(f"{x:5.0f}" for x in st))
print("\nAccel REALE che otterrebbe la C4 col port (m/s2)")
print("a_req | @50  @80  @100  @120")
for a in [0.0,0.25,0.5,0.75,1.0,1.5]:
    T=np.interp(a,AL,TL)
    print(f"{a:5.2f} | " + " ".join(f"{1.355e-3*T-0.0887-1.55e-4*(v/3.6)**2:5.2f}" for v in (50,80,100,120)))
# potential vs wheel stock
d = g.GMP_POTENTIAL_WHEEL_TORQUE - g.GMP_WHEEL_TORQUE
print("\nstock POTENTIAL-WHEEL quantiles", d.quantile([.05,.25,.5,.75,.95]).round(0).tolist(), " POTENTIAL min", g.GMP_POTENTIAL_WHEEL_TORQUE.min(), " WHEEL min/max", g.GMP_WHEEL_TORQUE.min(), g.GMP_WHEEL_TORQUE.max())
ss = g[(g.a.abs()<0.1)]
print("steady: POT-WHEEL median", (ss.GMP_POTENTIAL_WHEEL_TORQUE-ss.GMP_WHEEL_TORQUE).median())
acc = g[g.a>0.3]; print("accelerating: POT-WHEEL median", (acc.GMP_POTENTIAL_WHEEL_TORQUE-acc.GMP_WHEEL_TORQUE).median())
