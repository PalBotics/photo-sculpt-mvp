# Photo Sculpt MVP — Image‑to‑3D Web App

An MVP web app to upload photos (e.g., your small box image set), run a reconstruction step, and preview the resulting 3D mesh in the browser. If **COLMAP** isn’t installed, the backend falls back to generating a placeholder cube so you still get a working end‑to‑end preview. Later, we’ll swap the fallback for a full photogrammetry pipeline and add SolidWorks‑friendly export options.

---

## Features
- **Image upload → 3D preview** pipeline (end‑to‑end).
- **FastAPI** backend with simple job status polling.
- **Three.js** viewer with orbit controls, grid, and axes.
- **COLMAP** support when available; **placeholder mesh** fallback when not.
- Clean, minimal UI; logs show each processing step.

---

## Tech Stack
- **Frontend:** React + Vite + Three.js (PLY loader + OrbitControls)
- **Backend:** FastAPI (Python 3.10+)
- **Meshing:** `trimesh` for quick export/preview; COLMAP for real reconstruction (optional).

---

## Project Structure
```
photo-sculpt-mvp/
  frontend/
    index.html
    src/
      main.jsx
      App.jsx
      components/
        ModelViewer.jsx
    package.json
    vite.config.js

  backend/
    main.py
    requirements.txt
    settings.example.env

  README.md
```
> This README is the version you’re reading now. You can copy it into your repo root as `README.md`.

---

## Prerequisites
- **Node** 18+
- **Python** 3.10+
- (Optional) **COLMAP** on your system `PATH` for real reconstruction. Without it, the app still runs and previews a placeholder cube.

---

## Quickstart

### 1) Backend
```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
export DATA_ROOT=./data  # Windows PowerShell: $env:DATA_ROOT = "./data"
python main.py
```
You should see: **Uvicorn running on http://127.0.0.1:8000**.

> To enable real reconstructions, install **COLMAP** and ensure the `colmap` binary is on your `PATH`. Start with small image sets (8‑30 photos) and good coverage.

### 2) Frontend
```bash
cd frontend
npm install
npm run dev
```
Watch the terminal output. Vite will print the exact URL, e.g.:
```
Local:   http://localhost:5173/
Network: http://<your-ip>:5173/
```
Open the **Local** URL it prints. If the port is different (e.g., 5174), use that.

The dev server is configured to:
```js
// vite.config.js
export default defineConfig({
  server: {
    host: true,
    port: 5173,
    strictPort: true, // fail fast if 5173 is taken
    proxy: { '/api': 'http://127.0.0.1:8000' }
  }
})
```

### 3) Use
1. Select all your box images (JPG/PNG).
2. Click **Process**.
3. Watch the **Log**; when done, the viewer loads the generated `.ply` from the backend.

---

## API Overview
- `POST /api/upload` → returns `{ session_id }` after saving images.
- `POST /api/process` (JSON: `{ session_id }`) → returns `{ job_id }` and starts processing.
- `GET  /api/status?job_id=...` → returns `{ status, error }`.
- `GET  /api/model?job_id=...` → streams the `model.ply` when done.

---

## Troubleshooting

### "This site can’t be reached / 127.0.0.1 refused to connect"
- Ensure the frontend dev server is **running** and note the exact port Vite prints.
- If port 5173 is **in use**, either free it or run with a different port:
  ```bash
  npm run dev -- --port 5174
  ```
- On Windows, check for a process using the port:
  ```powershell
  netstat -aon | findstr :5173
  taskkill /PID <PID> /F
  ```
- **WSL/Docker/VPN/Firewall:** With `host: true`, Vite listens on all interfaces.
  - Try both `http://localhost:5173/` and `http://127.0.0.1:5173/`.
  - Allow Node through the firewall if prompted.

### Verify endpoints
- Frontend HTML:
  ```bash
  curl http://127.0.0.1:5173/
  ```
- FastAPI docs:
  ```bash
  curl http://127.0.0.1:8000/docs
  ```

### Node/Python versions
- `node -v` should be **18+**.
- `python --version` should be **3.10+**.

---

## SolidWorks Export (Next Step)
Add conversions in the backend after meshing:
```python
mesh.export(out_dir / 'model.obj')
mesh.export(out_dir / 'model.stl')
```
SolidWorks can import OBJ/STL (ScanTo3D add‑in) and convert meshes to surfaces/solids. For cleaner CAD, consider autoretopology (e.g., Instant Meshes) or primitive fitting for box‑like parts.

---

## Future Enhancements
- Replace convex‑hull placeholder with **Poisson**/**Ball‑Pivoting** meshing (Open3D/MeshLab server).
- Camera calibration inputs (sensor size, focal length) for small objects.
- Progress streaming from subprocess for granular status.
- **GLB** export and in‑viewer measurement tools.
- Add a **scale** reference (fiducial/ArUco).
- Job history & downloadable artifacts.

---

## Acknowledgements
- **COLMAP** — Structure‑from‑Motion and Multi‑View Stereo.
- **Three.js**, **FastAPI**, **trimesh** — core building blocks in this MVP.
