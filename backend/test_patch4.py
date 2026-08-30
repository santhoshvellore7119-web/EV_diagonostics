import sys
import inspect
import fastapi.routing
from fastapi.routing import APIRouter

# Get the original source
source = inspect.getsource(APIRouter.__init__)
print("Original APIRouter.__init__ source:")
print(source[:500])  # first 500 chars

# We'll create a patched version
# We need to replace the super().__init__ call to exclude on_startup and on_shutdown
# Let's just define a new __init__ method that mimics the original but without passing those to super.

# However, easier: we can create a subclass that overrides __init__ and calls super().__init__ with only the allowed params.
# But we need to capture the parameters.

original_init = APIRouter.__init__

def patched_init(self, *, 
                 prefix="",
                 tags=None,
                 dependencies=None,
                 default_response_class=None,
                 responses=None,
                 callbacks=None,
                 routes=None,
                 redirect_slashes=True,
                 default=None,
                 dependency_overrides_provider=None,
                 route_class=None,
                 on_startup=None,
                 on_shutdown=None,
                 lifespan=None,
                 deprecated=None,
                 include_in_schema=True,
                 generate_unique_id_function=None):
    # Handle defaults as in original
    if default_response_class is None:
        from fastapi.responses import JSONResponse
        default_response_class = JSONResponse
    if generate_unique_id_function is None:
        from fastapi.routing import generate_unique_id
        generate_unique_id_function = generate_unique_id
    
    # Call super().__init__ with only the parameters that Starlette Router accepts
    super(APIRouter, self).__init__(
        routes=routes,
        redirect_slashes=redirect_slashes,
        default=default,
        lifespan=lifespan,
        # Note: we omit on_startup and on_shutdown
    )
    
    # Now set the attributes as in original
    if prefix:
        assert prefix.startswith("/"), "A path prefix must start with '/'"
        assert not prefix.endswith(
            "/"
        ), "A path prefix must not end with '/', as the routes will start with '/'"
    self.prefix = prefix
    self.tags = tags or []
    self.dependencies = list(dependencies or [])
    self.deprecated = deprecated
    self.include_in_schema = include_in_schema
    self.responses = responses or {}
    self.callbacks = callbacks or []
    self.dependency_overrides_provider = dependency_overrides_provider
    self.route_class = route_class or APIRouter  # fallback?
    self.default_response_class = default_response_class
    self.generate_unique_id_function = generate_unique_id_function

# Replace the class's __init__
APIRouter.__init__ = patched_init

# Now test
from fastapi import FastAPI
app = FastAPI()
print("SUCCESS: FastAPI instance created")
