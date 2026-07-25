UBE v1.9a build 260 - Scrollable 3D Preview Help

The 3D preview help had grown too tall for a QMessageBox.

Fix:
  - Replaced the old QMessageBox text block with a real QDialog.
  - Uses QTextBrowser with HTML sections/tables.
  - Scrollable, resizable, and shared by:
      View -> 3D Preview Help
      H key inside the 3D preview widget

Help content also now includes newer preview types such as:
  - Sphere/Capsule/MeshCollider
  - SpriteMask
  - Font
  - Avatar
  - texture wrap W
  - ground/up basis shortcuts
  - Shift+O zero-origin debug mode
