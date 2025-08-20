import os
import shutil
import uuid
import subprocess
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, UploadFile, File, Form, Query, Request
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

# In-memory job store — for MVP only
JOBS = {}

# ---- Helpers for progress + logs ----

def set_job(job_id: str, **kwargs):
    job = JOBS.get(job_id)
    if not job:
        return
    job.update(kwargs)


def append_log(job_id: str, line: str):
    job = JOBS.get(job_id)
    if not job:
        return
    job.setdefault('log', []).append(line)


@app.get('/')
def root():
    return { 'ok': True, 'message': 'Photo Sculpt MVP API — see /docs' }

@app.get('/healthz')
def health():
    return { 'status': 'ok' }


@app.post('/api/upload')
async def upload(files: List[UploadFile] = File(...)):
    session_id = str(uuid.uuid4())
    sess_dir = DATA_ROOT / session_id
    img_dir = sess_dir / 'images'
    img_dir.mkdir(parents=True, exist_ok=True)

    count = 0
    for f in files:
        dest = img_dir / f.filename
        with dest.open('wb') as out:
            out.write(await f.read())
        count += 1

    return { 'session_id': session_id, 'count': count }


@app.post('/api/process')
async def process(request: Request, session_id: Optional[str] = Form(None)):
    """
    Accept BOTH JSON {session_id} and form-encoded session_id.
    Frontend sends JSON; this handler also supports form fallback.
    """
    if session_id is None:
        try:
            data = await request.json()
            session_id = data.get('session_id')
        except Exception:
            session_id = None

    if not session_id:
        return JSONResponse({ 'error': 'session_id required' }, status_code=400)

    job_id = str(uuid.uuid4())
    JOBS[job_id] = {
        'status': 'queued',
        'error': None,
        'session_id': session_id,
        'progress': 0,
        'step': 'queued',
        'log': ['Job queued']
    }

    import threading
    t = threading.Thread(target=run_pipeline, args=(job_id,), daemon=True)
    t.start()

    return { 'job_id': job_id }


@app.get('/api/status')
async def status(job_id: str = Query(...)):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({ 'error': 'unknown job_id' }, status_code=404)
    return {
        'status': job.get('status'),
        'error': job.get('error'),
        'progress': job.get('progress', 0),
        'step': job.get('step', ''),
        'log': job.get('log', []),
    }


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
        set_job(job_id, status='processing', step='initializing', progress=5)
        append_log(job_id, f'Initializing session {session_id}')

        mesh_path = out_dir / 'model.ply'

        if shutil.which('colmap'):
            append_log(job_id, 'COLMAP found on PATH — starting reconstruction')

            # Create workspace dirs
            database_path = out_dir / 'database.db'
            sparse_dir = out_dir / 'sparse'
            dense_dir = out_dir / 'dense'
            sparse_dir.mkdir(exist_ok=True)
            dense_dir.mkdir(exist_ok=True)

            # Feature extraction
            set_job(job_id, step='feature_extractor', progress=15)
            append_log(job_id, 'Running feature_extractor …')
            subprocess.run([
                'colmap', 'feature_extractor',
                '--database_path', str(database_path),
                '--image_path', str(img_dir)
            ], check=True)

            # Exhaustive matcher
            set_job(job_id, step='exhaustive_matcher', progress=30)
            append_log(job_id, 'Running exhaustive_matcher …')
            subprocess.run([
                'colmap', 'exhaustive_matcher',
                '--database_path', str(database_path)
            ], check=True)

            # Sparse reconstruction (Mapper)
            set_job(job_id, step='mapper (sparse reconstruction)', progress=50)
            append_log(job_id, 'Running mapper …')
            subprocess.run([
                'colmap', 'mapper',
                '--database_path', str(database_path),
                '--image_path', str(img_dir),
                '--output_path', str(sparse_dir)
            ], check=True)

            # Convert to dense workspace
            set_job(job_id, step='image_undistorter', progress=60)
            append_log(job_id, 'Running image_undistorter …')
            subprocess.run([
                'colmap', 'image_undistorter',
                '--image_path', str(img_dir),
                '--input_path', str(sparse_dir / '0'),
                '--output_path', str(dense_dir),
                '--output_type', 'COLMAP'
            ], check=True)

            # Dense stereo
            set_job(job_id, step='patch_match_stereo', progress=80)
            append_log(job_id, 'Running patch_match_stereo …')
            subprocess.run([
                'colmap', 'patch_match_stereo',
                '--workspace_path', str(dense_dir),
                '--workspace_format', 'COLMAP'
            ], check=True)

            # Fusion
            set_job(job_id, step='stereo_fusion', progress=90)
            append_log(job_id, 'Running stereo_fusion …')
            subprocess.run([
                'colmap', 'stereo_fusion',
                '--workspace_path', str(dense_dir),
                '--workspace_format', 'COLMAP',
                '--input_type', 'geometric',
                '--output_path', str(out_dir / 'fused.ply')
            ], check=True)

            # Meshing from point cloud (quick convex hull)
            set_job(job_id, step='meshing (convex hull)', progress=95)
            append_log(job_id, 'Meshing fused point cloud …')
            pcd = trimesh.load(out_dir / 'fused.ply')
            if not isinstance(pcd, trimesh.Trimesh):
                pcd = pcd.dump().sum()
            hull = pcd.convex_hull
            hull.export(mesh_path)
        else:
            # Fallback: generate a unit cube so we can verify the end‑to‑end flow
            set_job(job_id, step='placeholder mesh (no COLMAP)', progress=90)
            append_log(job_id, 'COLMAP not found — generating placeholder cube')
            box = trimesh.creation.box(extents=(0.1, 0.1, 0.1))
            R = trimesh.transformations.rotation_matrix(np.deg2rad(25), (0,1,0)) @ \
                trimesh.transformations.rotation_matrix(np.deg2rad(-15), (1,0,0))
            box.apply_transform(R)
            box.export(mesh_path)

        set_job(job_id, status='done', step='done', progress=100)
        append_log(job_id, 'Done')
    except subprocess.CalledProcessError as e:
        set_job(job_id, status='error')
        append_log(job_id, f'COLMAP step failed: {e}')
    except Exception as e:
        set_job(job_id, status='error')
        append_log(job_id, f'Error: {e}')


if __name__ == '__main__':
    uvicorn.run(app, host='0.0.0.0', port=8000)
