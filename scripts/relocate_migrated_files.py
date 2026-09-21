"""Copy migrated originals into stable storage, verify hashes, then update DB paths."""

import argparse
import hashlib
import os
import shutil
from pathlib import Path

import psycopg


def digest(path):
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.digest()


def relocate(source_dir, target_dir, url):
    source_dir, target_dir = source_dir.resolve(), target_dir.resolve()
    if source_dir == target_dir:
        raise SystemExit("원본과 대상 디렉터리가 같습니다.")
    with psycopg.connect(url) as db:
        rows = db.execute("SELECT id,file_path FROM documents ORDER BY id").fetchall()
        staged = []
        for document_id, file_path in rows:
            source = Path(file_path).resolve()
            if source.parent != source_dir or not source.is_file():
                raise SystemExit(f"문서 {document_id}의 원본 경로가 예상과 다릅니다.")
            target = target_dir / source.name
            if target.exists() and (not target.is_file() or digest(source) != digest(target)):
                raise SystemExit(f"대상 파일 충돌: {target.name}")
            staged.append((document_id, source, target))
        target_dir.mkdir(parents=True, exist_ok=True)
        for _, source, target in staged:
            if not target.exists():
                shutil.copy2(source, target)
            if digest(source) != digest(target):
                raise SystemExit(f"복사 검증 실패: {target.name}")
        for document_id, _, target in staged:
            db.execute("UPDATE documents SET file_path=%s WHERE id=%s", (str(target), document_id))
    print(f"원본 {len(staged)}개 복사·해시 검증 및 경로 갱신 완료. 이전 원본은 보존했습니다.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source_dir", type=Path)
    parser.add_argument("target_dir", type=Path)
    parser.add_argument("--url", default=os.getenv("DATABASE_URL", "postgresql://docraft:docraft@127.0.0.1:5433/docraft"))
    args = parser.parse_args()
    relocate(args.source_dir, args.target_dir, args.url)
