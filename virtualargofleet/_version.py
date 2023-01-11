import subprocess
import os
try:
    version = subprocess.check_output(['git', '-C', os.path.dirname(__file__), 'describe', '--tags']).decode('ascii').strip()
except:
    from virtualargofleet._version_setup import version as version  # noqa
