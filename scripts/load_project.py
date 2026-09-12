"""Load a project by name when it is not the current one; list its timelines and frame rate. See mr.projects.load_project.
After this the pre-bound `project` is stale: use the returned one."""
PROJECT = "raycast-ai-updates"
project, result = mr.projects.load_project(resolve, PROJECT)
