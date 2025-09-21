"""
downloader_celebdf.py

Safe helper script to discover and download dataset files for Celeb-DF (or similar)
from the official project pages.

Usage:
    python downloader_celebdf.py --outdir ./downloads

Notes:
- The script will NOT bypass authentication/consent pages. If a link requires manual consent
  (e.g., Google Drive confirmation page), open the reported link in a browser and accept terms,
  or obtain a direct download ID and re-run with that ID.
- Always follow dataset terms and cite the original paper when using the dataset.
- The script is best-effort: some project pages provide only instructions or Google Drive links
  that require manual approval.
"""

import os
import sys
import argparse
import re
import requests
from urllib.parse import urlparse, parse_qs
from bs4 import BeautifulSoup
from tqdm import tqdm
import subprocess
import shutil
import time

# Optional: gdown (better for Google Drive large files). If not installed, the script will try to use requests.
try:
    import gdown
    HAS_GDOWN = True
except Exception:
    HAS_GDOWN = False

# List of pages to probe for download links (official project & GitHub)
PROJECT_PAGES = [
    "https://cse.buffalo.edu/~siweilyu/celeb-deepfakeforensics.html",  # official project page
    "https://github.com/yuezunli/celeb-deepfakeforensics",             # GitHub repo / metadata
    "https://arxiv.org/abs/1909.12962",                               # paper (may contain links)
    "https://github.com/yuezunli/celeb-deepfakeforensics/releases",    # check releases
    "https://www.kaggle.com/datasets/reubensuju/celeb-df-v2"          # possible mirror
]

HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) downloader-celebdf/1.0"}

# --- utilities -------------------------------------------------------------

def safe_mkdir(path):
    os.makedirs(path, exist_ok=True)
    return path

def is_google_drive(url):
    return "drive.google.com" in url or "docs.google.com" in url

def extract_drive_id(url):
    # common patterns for Drive file: /file/d/<id>/ or ?id=<id>
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    qs = parse_qs(urlparse(url).query)
    if "id" in qs:
        return qs["id"][0]
    return None

def download_with_gdown(drive_id, out_path):
    if not HAS_GDOWN:
        raise RuntimeError("gdown not installed. Install with: pip install gdown")
    url = f"https://drive.google.com/uc?id={drive_id}"
    # gdown supports output path and resume
    print(f"gdown -> {url} -> {out_path}")
    gdown.download(url, out=out_path, quiet=False, fuzzy=True)

def stream_download(url, out_path, chunk_size=32768):
    # Use requests to stream download. Fallback for direct links.
    with requests.get(url, stream=True, headers=HEADERS, timeout=30) as r:
        r.raise_for_status()
        total = r.headers.get('content-length')
        if total is not None:
            total = int(total)
            pbar = tqdm(total=total, unit='B', unit_scale=True, desc=os.path.basename(out_path))
        else:
            pbar = None
        with open(out_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=chunk_size):
                if not chunk:
                    continue
                f.write(chunk)
                if pbar:
                    pbar.update(len(chunk))
        if pbar:
            pbar.close()

def maybe_wget(url, out_path):
    # Try wget CLI if available; it handles redirections and large files well.
    if shutil.which("wget"):
        cmd = ["wget", "-c", url, "-O", out_path]
        print("Using wget:", " ".join(cmd))
        subprocess.check_call(cmd)
        return True
    return False

# --- scraping -------------------------------------------------------------

def find_links_on_page(url):
    """
    Return list of discovered links (absolute URLs) from the page.
    """
    print(f"Fetching page: {url}")
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        r.raise_for_status()
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return []

    soup = BeautifulSoup(r.text, "html.parser")
    links = set()
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        # ignore mailto and javascript anchors
        if href.startswith("mailto:") or href.startswith("javascript:"):
            continue
        # resolve relative links
        abs_link = requests.compat.urljoin(url, href)
        links.add(abs_link)
    return sorted(links)

def filter_candidate_download_links(links):
    """
    Heuristics: keep links that look like files, Google Drive, Dropbox, Kaggle, or big-host URLs.
    """
    candidates = []
    for u in links:
        lower = u.lower()
        # file extension heuristics
        if re.search(r"\.(zip|tar\.gz|tar|7z|mp4|mkv|bin|tgz|tar\.bz2)$", lower):
            candidates.append(u)
            continue
        # google drive / dropbox / kaggle
        if "drive.google.com" in lower or "kaggle.com" in lower or "dropbox.com" in lower or "pan.baidu.com" in lower:
            candidates.append(u)
            continue
        # common cloud hosts (aws s3, storage.googleapis)
        if "s3.amazonaws.com" in lower or "storage.googleapis.com" in lower or "box.com" in lower:
            candidates.append(u)
            continue
        # long query-based links sometimes are downloads
        if len(urlparse(u).query) > 20 and ("download" in lower or "id=" in lower):
            candidates.append(u)
            continue
    return sorted(set(candidates))

# --- orchestrator --------------------------------------------------------

def discover_download_links(pages=PROJECT_PAGES):
    found = {}
    for p in pages:
        links = find_links_on_page(p)
        cand = filter_candidate_download_links(links)
        found[p] = cand
    return found

def try_download_link(url, outdir):
    safe_mkdir(outdir)
    parsed = urlparse(url)
    filename = os.path.basename(parsed.path) or "downloaded_file"
    # if query suggests a filename, prefer that
    qs = parse_qs(parsed.query)
    if "filename" in qs:
        filename = qs["filename"][0]
    out_path = os.path.join(outdir, filename)

    # Google Drive handling
    if is_google_drive(url):
        drive_id = extract_drive_id(url)
        if not drive_id:
            print(f"Google Drive URL found but could not extract id: {url}")
            print("Please open the URL in your browser and obtain the file id or a direct download link.")
            return False
        try:
            if HAS_GDOWN:
                download_with_gdown(drive_id, out_path)
                return True
            else:
                print("gdown not installed. Try installing gdown to download from Google Drive.")
                return False
        except Exception as e:
            print(f"gdown failed: {e}")
            return False

    # Try wget CLI if available
    try:
        if maybe_wget(url, out_path):
            return True
    except subprocess.CalledProcessError as e:
        print("wget failed:", e)

    # Finally try requests stream download
    try:
        stream_download(url, out_path)
        return True
    except Exception as e:
        print(f"stream download failed for {url}: {e}")
        return False

# --- main function -------------------------------------------------------

def main(args):
    outdir = args.outdir
    safe_mkdir(outdir)

    print("Discovering candidate download links on project pages...")
    discovered = discover_download_links()

    # print summary for user to inspect
    total = 0
    for page, links in discovered.items():
        print("\n---\nFrom page:", page)
        if not links:
            print("  (no candidate download links found)")
            continue
        for link in links:
            print("  ", link)
            total += 1

    if total == 0:
        print("\nNo direct download links discovered automatically. Please visit the official project page and follow instructions:")
        for p in PROJECT_PAGES:
            print("  -", p)
        print("\nIf you have a Google Drive link or direct URL, you can re-run this script with --direct <url>")
        return

    if args.dry_run:
        print("\nDry run complete. Use --download to attempt downloads.")
        return

    # Attempt downloads
    print("\nAttempting to download discovered candidate links...\n")
    for page, links in discovered.items():
        for link in links:
            print(f"\n[*] Trying {link}")
            ok = try_download_link(link, outdir)
            print(" ->", "OK" if ok else "FAILED")
            # be polite and wait a bit to avoid hammering servers
            time.sleep(1)

    print("\nDone. Check", outdir, "for downloaded files or error messages above.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Discover & download Celeb-DF dataset links (best-effort).")
    parser.add_argument("--outdir", default="./downloads", help="Output directory for downloads")
    parser.add_argument("--dry-run", action="store_true", help="Only discover and list links; do not download")
    parser.add_argument("--direct", nargs='*', help="Optional direct URLs to download (skips discovery)")
    args = parser.parse_args()

    if args.direct:
        # If direct URLs provided, try to download them
        for url in args.direct:
            print("Attempting direct download:", url)
            try:
                ok = try_download_link(url, args.outdir)
                print(" ->", "OK" if ok else "FAILED")
            except Exception as e:
                print("Direct download error:", e)
        sys.exit(0)

    main(args)
