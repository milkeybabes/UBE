# UBE v2.3w — Rigid Index-Only Skinning

Some Unity skinned meshes are rigid at vertex level: every vertex is controlled
by exactly one bone. Unity can serialise these with a one-component
BlendIndices channel and no BlendWeight channel, because each weight is
implicitly 1.0.

UBE now detects that layout conservatively, validates every decoded index
against the mesh bind-pose table, and synthesises one full-weight influence per
vertex. This restores transform-driven motion for parts such as the paired eyes
on Labyrinth's RockFace animations and feeds the same data to animated GLB
export. Existing explicit BoneWeight arrays and normal BlendWeight/BlendIndices
meshes are unchanged.
