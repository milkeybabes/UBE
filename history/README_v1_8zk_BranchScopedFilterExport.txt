UBE v1.8zk build 257 - Branch-Scoped Filter + Filtered Export

Adds a right-click filter for the current tree branch.

Why:
  Global search is useful, but when browsing a big source such as Dinosaur Island
  it is often better to right-click the Mesh branch and search only inside Mesh
  for terms such as trex, raptor, skull, etc.

New context-menu actions:
  - Filter this branch by keyword...
  - Clear branch filter

How it works:
  - Right-click a branch such as Mesh (440)
  - Choose Filter this branch by keyword...
  - Enter a keyword such as trex
  - UBE hides the rest of the tree and shows only matching items inside that branch

Filtered export:
  Existing filtered export actions now work with either:
    - the normal search box
    - the branch-scoped filter
    - both together

  Right-click the filtered Mesh branch and choose:
    Export filtered results in this branch...

  Or choose:
    Export all filtered results...

This stays separate from Ctrl/Shift multi-selection export.
