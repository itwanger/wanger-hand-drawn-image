#!/usr/bin/env python3
"""Validate a scene and render it with Swift/AppKit + FFmpeg on macOS."""
import argparse
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

def require(condition, message):
    if not condition:
        raise ValueError(message)

def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)

def interval(item, duration):
    a, b = item.get('start'), item.get('end')
    require(finite(a) and finite(b) and 0 <= a < b <= duration, 'Invalid start/end interval')

def validate(scene):
    duration, fps = scene.get('duration'), scene.get('fps')
    require(finite(duration) and 0 < duration <= 60, 'duration must be in (0,60]')
    require(type(fps) is int and 1 <= fps <= 30, 'fps must be an integer from 1 to 30')
    require(abs(duration*fps-round(duration*fps)) < 1e-6, 'duration*fps must be integral')
    require(isinstance(scene.get('base_image'), str), 'base_image is required')
    scene.setdefault('captions', [])
    require(isinstance(scene.get('overlays'), list), 'overlays must be a list')
    previous = 0
    for c in scene['captions']:
        interval(c, duration)
        require(c['start'] >= previous and isinstance(c.get('text'), str), 'Captions must be sorted and non-overlapping')
        previous = c['end']
    for key in ('caption_position', 'indicator_position'):
        if key in scene:
            require(isinstance(scene[key], list) and len(scene[key]) == 2 and all(finite(v) and v >= 0 for v in scene[key]), 'Invalid '+key)
    if 'caption_size' in scene:
        require(finite(scene['caption_size']) and scene['caption_size'] > 0, 'Invalid caption_size')
    for item in scene['overlays']:
        interval(item, duration)
        kind = item.get('kind')
        require(kind in ('bead', 'focus', 'ellipse', 'progress'), 'Unknown overlay kind')
        for key in ('color', 'track_color'):
            if key == 'color' or key in item:
                require(isinstance(item.get(key), str) and re.fullmatch(r'#[0-9a-fA-F]{6}', item[key]), 'Invalid '+key)
        if kind == 'bead':
            points = item.get('points', [])
            require(len(points) >= 2 and all(isinstance(p, list) and len(p) == 2 and all(finite(v) for v in p) for p in points), 'Invalid path points')
            require(item.get('curve') in (None, 'polyline', 'cubic'), 'Invalid curve')
            require(item.get('curve') != 'cubic' or len(points) == 4, 'Cubic paths need exactly four points')
            require(item.get('easing', 'smooth') in ('smooth', 'linear'), 'Invalid easing')
            require(finite(item.get('radius', 11)) and item.get('radius', 11) > 0, 'Invalid radius')
        else:
            r = item.get('rect', [])
            require(isinstance(r, list) and len(r) == 4 and all(finite(v) for v in r) and r[2] > 0 and r[3] > 0, 'Invalid rect')
            require(finite(item.get('line_width', 6)) and item.get('line_width', 6) > 0, 'Invalid line_width')
        if kind == 'progress':
            keys = item.get('keyframes', [])
            require(len(keys) >= 2 and all(isinstance(k, list) and len(k) == 2 and all(finite(v) for v in k) and 0 <= k[0] <= duration and 0 <= k[1] <= 1 for k in keys), 'Invalid progress keyframes')
            require(all(a[0] < b[0] for a,b in zip(keys, keys[1:])), 'Keyframe times must strictly increase')

def run(args, timeout=180):
    subprocess.run(args, check=True, timeout=timeout)

def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('scene', type=Path)
    p.add_argument('--output', type=Path)
    p.add_argument('--keep-frames', action='store_true')
    p.add_argument('--check-only', action='store_true')
    args = p.parse_args()
    scene_path = args.scene.expanduser().resolve()
    scene = json.loads(scene_path.read_text())
    validate(scene)
    base = (scene_path.parent / scene['base_image']).resolve()
    require(base.is_file(), 'Base image does not exist: '+str(base))
    if args.check_only:
        print('Scene configuration valid; base image exists.')
        return
    require(sys.platform == 'darwin', 'This renderer needs macOS AppKit')
    for tool in ('swift', 'ffmpeg', 'ffprobe'):
        require(shutil.which(tool), tool+' is not on PATH')
    require(args.output, '--output is required for rendering')
    out = args.output.expanduser().resolve()
    require(not out.exists() or (out.is_dir() and not any(out.iterdir())), 'Output directory must be empty')
    out.mkdir(parents=True, exist_ok=True)
    master = out / ('master'+base.suffix.lower())
    shutil.copy2(base, master)
    scene['base_image'] = master.name
    (out/'scene.json').write_text(json.dumps(scene, ensure_ascii=False, indent=2))
    with tempfile.TemporaryDirectory(prefix='itwanger-gif-') as temp:
        work = Path(temp)
        frames = work/'frames'
        config = dict(scene, base_image=str(master))
        config_path = work/'scene.json'
        config_path.write_text(json.dumps(config, ensure_ascii=False))
        run(['swift', str(Path(__file__).with_name('render_frames.swift')), str(config_path), str(frames)], timeout=420)
        input_args = ['ffmpeg','-hide_banner','-loglevel','error','-framerate',str(scene['fps']),'-i',str(frames/'%04d.png')]
        palette = '[0:v]split[a][b];[a]palettegen=stats_mode=diff:max_colors=160[p];[b][p]paletteuse=dither=bayer:bayer_scale=3:diff_mode=rectangle'
        run(input_args+['-filter_complex',palette,'-loop','0','-y',str(out/'preview.gif')])
        run(input_args+['-vf','pad=ceil(iw/2)*2:ceil(ih/2)*2','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart','-y',str(out/'preview.mp4')])
        run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(out/'preview.gif'),'-vf',f"fps=6/{scene['duration']},scale=384:-1,tile=3x2",'-frames:v','1','-y',str(out/'qa-contact-sheet.png')])
        if args.keep_frames:
            shutil.copytree(frames,out/'frames')
    probe = subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=width,height,nb_frames','-show_entries','format=duration,size','-of','json',str(out/'preview.gif')], text=True)
    metadata = json.loads(probe)
    expected = round(scene['duration']*scene['fps'])
    require(int(metadata['streams'][0]['nb_frames']) == expected, 'Export frame count mismatch')
    require(abs(float(metadata['format']['duration'])-scene['duration']) <= 0.03, 'Export duration mismatch')
    (out/'render.json').write_text(json.dumps({'fps':scene['fps'],'expected_frames':expected,'gif':metadata,'mp4_bytes':(out/'preview.mp4').stat().st_size},indent=2))
    print('Rendered:',out/'preview.gif')

if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.SubprocessError) as e:
        print('Render failed:',e,file=sys.stderr)
        sys.exit(1)
