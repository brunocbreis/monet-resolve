# Scripts

The 29 original task scripts, now thin callers into the `monet_resolve` package. Each keeps its UPPERCASE parameters at the top and sets `result`. Run one with `resolve`, `project` and `mr` pre-bound:

    python -m monet_resolve.run scripts/<name>.py

Or paste the body into the `DaVinci Resolve:run_script` MCP tool after `import monet_resolve as mr`. Function docstrings hold the details and the workaround each one embodies.
