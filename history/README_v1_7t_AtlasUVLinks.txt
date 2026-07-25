UBE v1.7t - Atlas UV Channel Links
==================================

Texture Atlas Region Finder now groups UV channels under the same renderer row.

Why:
- Some assets use UV0 for normals/detail and UV1 for the visible colour atlas.
- The golf balls are the prime example: UV0 can look like the wrong/full texture, while UV1 places the actual pattern.

Changes:
- Atlas finder rows now show UV0/UV1/UV2/UV3 choices together where available.
- Each UV token is a separate clickable overlay link.
- The row number shortcut prefers the likely atlas/display patch when marked.
- Inspector notes explain dual-UV cases.

This keeps the existing atlas box overlay but makes it much clearer which UV channel you are seeing.
