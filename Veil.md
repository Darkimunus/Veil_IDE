# Veil Studio

A tiny Studio + interpreter for **Veil** — a joke language whose source is blank Unicode characters.

## Run from source

Requires [uv](https://docs.astral.sh/uv/).

```bash
cd VeilStudio
uv sync
uv run python main.py

## License

Veil Studio source is MIT — see [LICENSE](LICENSE).

### Third-party

The Windows build bundles other software with their own licenses:

- **PySide6 / Qt** — LGPL / Qt commercial terms (see Qt and PySide6 licensing)
- **qrcode**, **Pillow**, and other Python deps — see each package’s license on PyPI

Using the prebuilt `.exe` does not change those terms; you still need to comply with Qt/PySide6’s license for redistribution.