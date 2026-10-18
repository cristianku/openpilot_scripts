# /// script
# dependencies = ["pandas", "pyarrow", "numpy"]
# ///
import pandas as pd
m = pd.read_parquet("out/m.parquet")
a = m[m.ACC_STATUS==4]
print("ACC active frames:", len(a), " gasPressed true:", a.gas.astype(bool).sum(), " brake:", a.brake.astype(bool).sum())
print("cruiseEn when ACC_STATUS 4:", a.cruiseEn.value_counts().to_dict())
print("cruiseAvail:", m.cruiseAvail.value_counts().to_dict())
