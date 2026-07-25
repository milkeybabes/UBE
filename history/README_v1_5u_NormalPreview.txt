UBE v1.5u build 178 - OpenGL Normal/Bump Preview
================================================

This build keeps the v1.5t GLB ball export fixes and adds a new in-UBE lit+bump preview mode.

Controls:
- L       Toggle lit + bump/normal-map preview
- [ / ]   Lower / raise bump height / strength
- G       Flip normal-map green/Y channel
- B       Cycle texture debug view: base / normal / emission / metal
- N       Show normal/bump texture on UV0
- U       Cycle UV channel for atlas/base texture
- M       Cycle UV domain/remap modes

Golf-ball preview behaviour:
- Base colour texture uses the selected U-key UV channel.
- Normal/bump texture uses UV0.
- The viewer generates tangents per triangle from UV0 for the normal-map shader.

Notes:
- The normal/bump preview is an OpenGL shader path. If a machine/driver cannot compile the shader, UBE falls back to the normal texture-only preview/export path.
- G is intentionally exposed because Unity/OpenGL/DirectX normal-map green-channel conventions can differ between assets.
