# Tests classification

1. **UNIT** - no filesystem/network allowed; test python code in vacuum, as precise as possible (1 test = 1 function).
2. **COMPONENT** - controllable filesystem, still no network; test python in atmosphere, still as precise as possible, but might be broader.
3. **INTEGRATION** - controllable filesystem, network is mocked; test broader use scenarios.
4. **SYSTEM** - controllable filesystem, network allowed, additional Docker setup is required; test installed application as a whole with user-like input

**ASSETS/** - directory with "pre-built binaries" for controllable filesystem
