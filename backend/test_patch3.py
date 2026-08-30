import sys
import fastapi.routing

print("fastapi.routing.APIRouter:", fastapi.routing.APIRouter)
print("fastapi.routing.APIRouter.__init__:", fastapi.routing.APIRouter.__init__)

# Patch APIRouter.__init__ to remove on_startup and on_shutdown
original_init = fastapi.routing.APIRouter.__init__

def patched_init(self, *args, **kwargs):
    print(f"patched_init called with args={args}, kwargs={kwargs}")
    kwargs.pop('on_startup', None)
    kwargs.pop('on_shutdown', None)
    print(f"after pop kwargs={kwargs}")
    return original_init(self, *args, **kwargs)

fastapi.routing.APIRouter.__init__ = patched_init

print("After patch:")
print("fastapi.routing.APIRouter.__init__:", fastapi.routing.APIRouter.__init__)

# Now import FastAPI and create app
from fastapi import FastAPI
print("About to create FastAPI instance")
app = FastAPI()
print("SUCCESS: FastAPI instance created")
