"""Check a looping article GIF locally and optionally compare its CDN response."""
import argparse
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from PIL import Image


def inspect_gif(path):
    with Image.open(path) as image:
        if image.format != "GIF" or not image.is_animated:
            raise ValueError("Expected an animated GIF")
        if image.info.get("loop") != 0:
            raise ValueError("Expected an infinite loop")
        duration_ms = 0
        for index in range(image.n_frames):
            image.seek(index)
            image.load()
            duration_ms += image.info.get("duration", 0)
        if duration_ms == 0:
            raise ValueError("No frame display time")
        return dict(width=image.width, height=image.height, frames=image.n_frames,
                    duration_ms=duration_ms, loop=0)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("gif", type=Path)
    parser.add_argument("--cdn-url")
    args = parser.parse_args()
    try:
        result = inspect_gif(args.gif)
        local = args.gif.read_bytes()
        result.update(bytes=len(local), sha256=hashlib.sha256(local).hexdigest())
        if args.cdn_url:
            with urlopen(args.cdn_url, timeout=30) as response:
                mime = response.headers.get_content_type()
                if response.status != 200 or mime != "image/gif":
                    raise ValueError(f"CDN returned {response.status} {mime}")
                if response.read(len(local) + 1) != local:
                    raise ValueError("CDN bytes differ from the local GIF")
                result.update(cdn_url=args.cdn_url, content_type=mime, identical=True)
    except (OSError, ValueError, EOFError) as error:
        parser.exit(1, f"GIF verification failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
