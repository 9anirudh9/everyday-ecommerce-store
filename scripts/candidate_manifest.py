"""Create a deterministic local source archive without committing or pushing."""
import hashlib
import argparse
import json
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--output-dir',type=Path,default=ROOT/'outputs/p0-01-release')
parser.add_argument('--name',default='p0-01-candidate-source.zip')
args=parser.parse_args()
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=True)


def git_paths(*args):
    data = subprocess.check_output(["git", *args, "-z"], cwd=ROOT)
    return {Path(item.decode("utf-8")) for item in data.split(b"\0") if item}


paths = sorted(git_paths("ls-files", "--cached", "--others", "--exclude-standard"))
changed = sorted(git_paths("diff", "--name-only", "HEAD"))
untracked = sorted(git_paths("ls-files", "--others", "--exclude-standard"))
entries = []
archive_path = OUT / args.name
with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
    for path in paths:
        data = (ROOT / path).read_bytes()
        name = path.as_posix()
        info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
        info.compress_type = zipfile.ZIP_DEFLATED
        info.external_attr = 0o644 << 16
        archive.writestr(info, data)
        entries.append({"path": name, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})

manifest = {
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                    text=True).strip(),
    "branch": subprocess.check_output(["git", "branch", "--show-current"], cwd=ROOT,
                                      text=True).strip(),
    "changed_tracked": [path.as_posix() for path in changed],
    "untracked": [path.as_posix() for path in untracked],
    "files": entries,
    "archive": archive_path.name,
    "archive_sha256": hashlib.sha256(archive_path.read_bytes()).hexdigest(),
    "archive_bytes": archive_path.stat().st_size,
}
(OUT / "candidate-manifest.json").write_text(
    json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
print("files", len(entries), "changed tracked", len(changed), "untracked", len(untracked))
print("archive sha256", manifest["archive_sha256"])
