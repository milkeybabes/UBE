# UBE v2.0b — Comment Keyboard Focus Fix

Build 264

## Fix

The External Comment editor now claims normal keyboard input before UBE's global 3D-preview shortcut handler runs.

While the comment editor has focus:

- Single-key preview commands such as `U`, `M`, `W`, `T`, `F`, `H`, `X`, `Y`, `Z`, `Q`, `E`, number views, and brackets are not intercepted.
- Backtick/tilde no longer toggles preview-focus mode while being typed.
- Standard text editing and clipboard shortcuts continue to be handled by `QPlainTextEdit`.
- Preview shortcuts resume immediately after the comment dialog closes.
