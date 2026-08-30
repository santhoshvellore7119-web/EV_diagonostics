import sys
import fastapi.routing

# Patch APIRouter.__init__ to remove on_startup and on_shutdown
original_init = fastapi.routing.APIRouter.__init__

def patched_init(self, *args, **kwargs):
    print(f"Before pop: kwargs keys = {list(kwargs.keys())}")
    kwargs.pop('on_startup', None)
    kwargs.pop('on_shutdown', None)
    print(f"After pop: kwargs keys = {list(kwargs.keys())}")
    return original_init(self, *args, **kwargs)

fastapi.routing.APIRouter.__init__ = patched_init

# Now import FastAPI and create app
from fastapi import FastAPI
print("About to create FastAPI instance")
app = FastAPI()
print("SUCCESS: FastAPI instance created")
