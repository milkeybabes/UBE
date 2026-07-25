UBE v1.7i - Model Rotation Reset
=================================

Changed the default 3D preview model rotation to zero:

  model_rot_x = 0
  model_rot_y = 0
  model_rot_z = 0

Earlier builds used -90 / 180 as a convenience for some OBJ-style previews, but that could give a misleading first view when inspecting Unity object transforms and group assemblies. The normal camera/view rotation controls are unchanged.
