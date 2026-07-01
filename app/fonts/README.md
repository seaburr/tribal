# Vendored fonts

`DejaVuSans.ttf` and `DejaVuSans-Bold.ttf` are bundled here so PDF report
generation (`app/routers/resources.py`) renders identically on any OS —
macOS during development, Linux in the Docker/production image — without
depending on a system-installed font.

- **Font:** DejaVu Sans (unmodified), from the DejaVu Fonts project.
- **License:** see [`LICENSE_DEJAVU.txt`](./LICENSE_DEJAVU.txt) — a permissive
  Bitstream Vera / Arev license. Redistribution requires that this notice
  travel with the font files, which is why the license is vendored alongside
  them.
