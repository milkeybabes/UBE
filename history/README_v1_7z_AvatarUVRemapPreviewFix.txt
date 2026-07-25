UBE v1.7z - Avatar / Putter UV Remap Preview Fix
=================================================

Build: 219

Fix:
- Improved automatic UV-domain detection for object/component previews.
- Some avatar/putter shaders use authored UVs in a -1..+1 domain and remap them to 0..1 in the shader before sampling the atlas.
- UBE's direct object preview could previously sample the raw signed UVs and make the texture look wildly wrong, while the parent/group preview looked correct.
- Auto UV mode now detects this signed-unit UV pattern more reliably, even when the exported temporary texture filename does not preserve the original atlas name.
- The preview title now shows when it has applied: "UV remap -1..+1→0..1".

Notes:
- This is preview-only. It does not alter the source mesh or exported data.
- Normal/metal/emission debug views stay raw unless manually changed with M, because those maps can deliberately use different UV domains.
