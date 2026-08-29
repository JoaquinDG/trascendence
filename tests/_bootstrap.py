"""Put `src/` on the path so `python3 -m unittest discover -s tests` just works.

`discover -s tests` puts this directory on sys.path, so every test module can
`import _bootstrap` as its first import. The alternative is requiring
PYTHONPATH=src on every invocation, and a test suite that only runs when you
remember a prefix is a test suite that stops being run.
"""

import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for path in (os.path.join(ROOT, "src"), os.path.join(ROOT, "evals")):
    if path not in sys.path:
        sys.path.insert(0, path)
