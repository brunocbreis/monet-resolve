"""Sync an external audio recording to the camera clip by waveform (first clip of each bin). See mr.audio.sync_external_audio."""
VIDEO_BIN = "footage"; AUDIO_BIN = "audio"
mp = project.GetMediaPool(); vb = mr.find_bin(mp, VIDEO_BIN)
ok = mr.audio.sync_external_audio(resolve, mp, vb.GetClipList()[0], mr.find_bin(mp, AUDIO_BIN).GetClipList()[0])
result = {"ok": ok, "footage": [(c.GetName(), c.GetClipProperty("Audio Ch"), c.GetClipProperty("Synced Audio")) for c in vb.GetClipList()]}
