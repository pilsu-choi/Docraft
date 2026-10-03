import importlib.metadata
import json
import re
import tomllib

import mlife_harness
from mlife_harness.api.jobs import PostgresJobStore


def key(name):
    return re.sub(r"[-_.]+", "-", name).lower()


with open("/uv.lock", "rb") as stream:
    lock = tomllib.load(stream)
locked = {}
for package in lock["package"]:
    locked.setdefault(key(package["name"]), set()).add(package["version"])
installed = {key(distribution.metadata["Name"]): distribution.version
             for distribution in importlib.metadata.distributions()}
unexpected = {name: version for name, version in installed.items() if version not in locked.get(name, set())}
assert not unexpected, unexpected
assert "/opt/venv/lib/" in mlife_harness.__file__, mlife_harness.__file__
assert "pytest" not in installed
assert PostgresJobStore.__name__ == "PostgresJobStore"
print(json.dumps({"lock_versions_match": True, "app_import": mlife_harness.__file__,
                  "installed_packages": installed}, sort_keys=True, indent=2))
