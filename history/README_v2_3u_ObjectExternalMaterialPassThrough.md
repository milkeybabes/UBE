# UBE v2.3u Build 334 — Object External Material Pass-Through

## Problem

The v2.3t external-character recovery worked for a raw Mesh relationship, but
AnimationClip preview exports each concrete GameObject/renderer through an
object-specific graph wrapper. That wrapper represented only successfully resolved
material records. For Labyrinth characters, the renderer Material lives in external
FileID 2 and is unresolved, so the wrapper silently presented the mesh as having no
material at all. The local `Labyrinth_Characters` recovery never received the evidence
it required and the animated character stayed grey.

## Fix

UBE now carries the selected renderer's exact Material PPtrs into the object graph,
including unresolved FileID/PathID slots, and carries an exact selected-renderer
`used_by` relationship for skinned-mesh classification. The v2.3t conservative local
character-template recovery therefore runs on the real AnimationClip render instance.

Resolved material slots remain authoritative. Only unresolved slots belonging to the
selected renderer are passed through, so a shared Mesh does not inherit unrelated
materials from other scene uses. Mesh/object/AnimationClip preview and OBJ/GLB object
export use the same corrected path.
