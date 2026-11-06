import inspect
from pyzkfp import ZKFP2

zkfp = ZKFP2()

methods = [
    "AcquireFingerprint",
    "AcquireFingerprintImage",
    "DBInit",
    "DBMerge",
    "DBAdd",
    "DBMatch",
    "DBIdentify",
    "GetParameters",
]

for name in methods:
    method = getattr(zkfp, name)

    print(f"\n===== {name} =====")

    try:
        print("Signature:", inspect.signature(method))
    except Exception as e:
        print("Signature unavailable:", e)

    try:
        print(inspect.getdoc(method))
    except Exception:
        pass