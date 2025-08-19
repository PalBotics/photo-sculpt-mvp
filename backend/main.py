import os
import shutil
import uuid
import subprocess
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Query
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Optional: simple mesh fallback
import numpy as np
import trimesh

DATA_ROOT = Path(os.environ.get('DATA_ROOT', './data')).resolve()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

app = FastAPI(title='Photo Sculpt MVP')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

JOBS = {}

@app.post('/api/upload')
async def upload(files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    sess_dir = DATA_ROOT / session_id
    img_dir = sess_dir / 'images'
    img_dir.mkdir(parents=True, exist_ok=True)

    for f in files:
        dest = img_dir / f.filename
        with dest.open('wb') as out:
            out.write(await f.read())

    return { 'session_id': session_id }

@app.post('/api/process')
async def process(session_id: str = Form(None), body: Optional[dict] = None):
    # support JSON body as well
    if body and not session_id:
        session_id = body.get('session_id')
    if not session_id:
        return JSONResponse({ 'error': 'session_id required' }, status_code=400)

    job_id = str(uuid.uuid4())
    JOBS[job_id] = { 'status': 'queued', 'error': None, 'session_id': session_id }

    # Fire-and-forget background process
    import threading
    t = threading.Thread(target=run_pipeline, args=(job_id,), daemon=True)
    t.start()

    return { 'job_id': job_id }

@app.get('/api/status')
async def status(job_id: str = Query(...)):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({ 'error': 'unknown job_id' }, status_code=404)
    return { 'status': job['status'], 'error': job['error'] }

@app.get('/api/model')
async def model(job_id: str = Query(...)):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({ 'error': 'unknown job_id' }, status_code=404)
    sess_dir = DATA_ROOT / job['session_id']
    mesh_path = sess_dir / 'output' / 'model.ply'
    if not mesh_path.exists():
        return JSONResponse({ 'error': 'model not ready' }, status_code=404)
    return FileResponse(mesh_path, media_type='application/octet-stream', filename='model.ply')


def run_pipeline(job_id: str):
    job = JOBS[job_id]
    session_id = job['session_id']
    sess_dir = DATA_ROOT / session_id
    img_dir = sess_dir / 'images'
    out_dir = sess_dir / 'output'
    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        job['status'] = 'processing'
        mesh_path = out_dir / 'model.ply'

        if shutil.which('colmap'):
            # Minimal COLMAP automatic reconstruction (sparse + meshing via poisson)
            # Create workspace dirs
            database_path = out_dir / 'database.db'
            sparse_dir = out_dir / 'sparse'
            dense_dir = out_dir / 'dense'
            sparse_dir.mkdir(exist_ok=True)
            dense_dir.mkdir(exist_ok=True)

            # Feature extraction
            subprocess.run([
                'colmap', 'feature_extractor',
                '--database_path', str(database_path),
                '--image_path', str(img_dir)
            ], check=True)

            # Exhaustive matcher (OK for small sets)
            subprocess.run([
                'colmap', 'exhaustive_matcher',
                '--database_path', str(database_path)
            ], check=True)

            # Sparse reconstruction (Mapper)
            subprocess.run([
                'colmap', 'mapper',
                '--database_path', str(database_path),
                '--image_path', str(img_dir),
                '--output_path', str(sparse_dir)
            ], check=True)

            # Convert to dense workspace
            subprocess.run([
                'colmap', 'image_undistorter',
                '--image_path', str(img_dir),
                '--input_path', str(sparse_dir / '0'),
                '--output_path', str(dense_dir),
                '--output_type', 'COLMAP'
            ], check=True)

            # Dense stereo
            subprocess.run([
                'colmap', 'patch_match_stereo',
                '--workspace_path', str(dense_dir),
                '--workspace_format', 'COLMAP'
            ], check=True)

            # Fusion
            subprocess.run([
                'colmap', 'stereo_fusion',
                '--workspace_path', str(dense_dir),
                '--workspace_format', 'COLMAP',
                '--input_type', 'geometric',
                '--output_path', str(out_dir / 'fused.ply')
            ], check=True)

            # Simple mesh from fused point cloud using trimesh (quick, not watertight)
            pcd = trimesh.load(out_dir / 'fused.ply')
            if not isinstance(pcd, trimesh.Trimesh):
                pcd = pcd.dump().sum()
            # Ball‑pivoting/poisson not in trimesh: quick convex hull fallback
            hull = pcd.convex_hull
            hull.export(mesh_path)
        else:
            # Fallback: generate a unit cube so we can verify the end‑to‑end flow
            box = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
            # Slightly rotate to make it more readable
            R = trimesh.transformations.rotation_matrix(np.deg2rad(25), (0,1,0)) @ \
                trimesh.transformations.rotation_matrix(np.deg2rad(-15), (1,0,0))
            box.apply_transform(R)
            box.export(mesh_path)

        job['status'] = 'done'
    except subprocess.CalledProcessError as e:
        job['status'] = 'error'
        job['error'] = f'COLMAP step failed: {e}'
    except Exception as e:
        job['status'] = 'error'
        job['error'] = str(e)


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)