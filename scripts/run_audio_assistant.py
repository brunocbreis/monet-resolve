"""Run Timeline > AI Tools > Audio Assistant (Auto Mix) on a timeline and wait for it. See mr.ui.run_audio_assistant."""
TIMELINE = "Interview - Cut v2"
t = mr.find_timeline(project, TIMELINE); project.SetCurrentTimeline(t); resolve.OpenPage("edit")
result = {"done": mr.ui.run_audio_assistant()}
