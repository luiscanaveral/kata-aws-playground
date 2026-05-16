"""Deploy CDK stacks to Floci via CloudFormation."""
import json
import os
import subprocess
import sys
from pathlib import Path

import boto3


def _client(service: str):
    return boto3.client(
        service,
        endpoint_url=os.getenv("AWS_ENDPOINT_URL", "http://localhost:4566"),
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID", "test"),
        aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY", "test"),
    )


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


def synth():
    print("=== Synthesizing CDK stacks ===")
    root = _project_root()
    subprocess.run(
        [
            sys.executable, "-m", "aws_cdk",
            "synth",
            "--app", "python3 infrastructure/app.py",
            "--output", "infrastructure/cdk.out",
        ],
        check=True,
        cwd=str(root),
    )


def deploy_assets():
    manifest_path = _project_root() / "infrastructure" / "cdk.out" / "manifest.json"
    if not manifest_path.exists():
        print("No manifest.json found, skipping asset upload")
        return

    manifest = json.loads(manifest_path.read_text())
    s3 = _client("s3")
    out_dir = _project_root() / "infrastructure" / "cdk.out"

    for stack_name, stack_data in manifest.get("stacks", {}).items():
        for asset_hash, asset_info in stack_data.get("assets", {}).items():
            for dest_info in asset_info.get("destinations", {}).values():
                bucket_name = dest_info["bucketName"]
                object_key = dest_info["objectKey"]
                source_path = asset_info["source"]["path"]

                source_abs = (out_dir / source_path).resolve()
                if not source_abs.exists():
                    source_abs = (_project_root() / source_path).resolve()

                if not source_abs.exists():
                    print(f"  WARNING: Asset source not found: {source_abs}")
                    continue

                try:
                    s3.create_bucket(Bucket=bucket_name)
                    print(f"  Bucket ready: {bucket_name}")
                except Exception as e:
                    if "BucketAlready" not in str(e):
                        print(f"  Bucket note: {e}")

                import io
                import zipfile

                buf = io.BytesIO()
                if source_abs.is_dir():
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        for file_path in sorted(source_abs.rglob("*")):
                            if file_path.is_file():
                                arcname = str(file_path.relative_to(source_abs))
                                zf.write(str(file_path), arcname)
                else:
                    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                        zf.write(str(source_abs), source_abs.name)

                buf.seek(0)
                s3.put_object(
                    Bucket=bucket_name,
                    Key=object_key,
                    Body=buf.getvalue(),
                )
                print(f"  Uploaded {object_key} → s3://{bucket_name}/")

                _patch_template_s3_ref(
                    out_dir / f"{stack_name}.template.json",
                    bucket_name,
                    object_key,
                )


def _patch_template_s3_ref(template_path: Path, bucket: str, key: str):
    if not template_path.exists():
        return
    template = json.loads(template_path.read_text())
    modified = False

    def _walk(obj):
        nonlocal modified
        if isinstance(obj, dict):
            if "S3Bucket" in obj and "Fn::Sub" in obj["S3Bucket"]:
                obj["S3Bucket"] = bucket
                modified = True
            for v in obj.values():
                _walk(v)
        elif isinstance(obj, list):
            for item in obj:
                _walk(item)

    _walk(template)
    if modified:
        template_path.write_text(json.dumps(template, indent=2))
        print(f"  Patched S3 references in {template_path.name}")


def deploy_stacks(stack_filter: str | None = None):
    cf = _client("cloudformation")
    out_dir = _project_root() / "infrastructure" / "cdk.out"

    for template_file in sorted(out_dir.glob("*.template.json")):
        stack_name = template_file.stem.replace(".template", "")
        if stack_filter and stack_name != stack_filter:
            continue

        template = json.loads(template_file.read_text())

        try:
            try:
                cf.create_stack(
                    StackName=stack_name,
                    TemplateBody=json.dumps(template),
                )
                print(f"  Created stack: {stack_name}")
            except cf.exceptions.AlreadyExistsException:
                try:
                    cf.update_stack(
                        StackName=stack_name,
                        TemplateBody=json.dumps(template),
                    )
                    print(f"  Updated stack: {stack_name}")
                except cf.exceptions.NoUpdateIsRequiredException:
                    print(f"  No update needed: {stack_name}")
        except Exception as e:
            if "No updates are to be performed" in str(e):
                print(f"  No changes: {stack_name}")
            else:
                print(f"  WARNING: {stack_name} deploy failed: {e}")


def main():
    stack_filter = sys.argv[1] if len(sys.argv) > 1 else None
    synth()
    deploy_assets()
    deploy_stacks(stack_filter)


if __name__ == "__main__":
    main()
