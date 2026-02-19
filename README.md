# comfyui-cloud-storage

Cloud storage nodes for ComfyUI. Save images, video, and audio to any S3-compatible provider. Download and cache models from cloud storage. Works with Backblaze B2, AWS S3, Cloudflare R2, MinIO, Wasabi, DigitalOcean Spaces, and Google Cloud Storage.

> Upload generated content and manage AI models across machines using a single set of ComfyUI nodes and one `boto3` dependency.

## What Is comfyui-cloud-storage?

comfyui-cloud-storage is a custom node package for [ComfyUI](https://github.com/comfyanonymous/ComfyUI) that adds cloud storage support to any workflow. It uses the S3-compatible API shared by all major object storage providers, so a single installation covers B2, S3, R2, and more. Configure your credentials once and wire the profile to any number of save, load, or browse nodes.

### Problem

ComfyUI stores everything on the local filesystem. Generated outputs pile up on one machine with no backup. Sharing models across machines means re-downloading multi-gigabyte files from HuggingFace on each one. There is no built-in way to upload results to cloud storage or distribute models from a central bucket.

### Solution

This package adds 8 nodes that plug directly into the ComfyUI graph. Save nodes upload generated images, video, and audio to your bucket. Load nodes download and cache models locally with ETag-based invalidation and progress bars. Browse nodes list bucket contents and generate presigned sharing URLs. All nodes use the same credential profile, resolved from environment variables or a JSON config file -- secrets never appear in workflow JSON.

### Who Should Use This

- ComfyUI users who want automated cloud backup of generated content
- Teams sharing a model library across multiple machines
- Anyone who wants to serve generated images via presigned URLs or CDN

## Key Features

- **Multi-provider** -- Built-in presets for Backblaze B2, AWS S3, Cloudflare R2, MinIO, Wasabi, DigitalOcean Spaces, and GCS. Any S3-compatible endpoint works via the Custom provider.
- **Configure once** -- The Cloud Storage Profile node outputs a connection that wires to every other node. No repeated credential entry.
- **Save images, video, audio** -- Upload directly from the pipeline in PNG, JPG, WebP, MP4, WebM, FLAC, MP3, or WAV.
- **Download and cache models** -- Pull checkpoints, LoRAs, VAEs, and other model files from a bucket to the correct local `models/` directory. Skips re-download when the remote file hasn't changed (ETag comparison).
- **Browse and share** -- List bucket contents and generate time-limited presigned URLs from within a workflow.
- **Secure credentials** -- Resolved from environment variables or a server-side JSON file stored in ComfyUI's HTTP-inaccessible system directory. Never embedded in shareable workflows.
- **Progress tracking** -- Model downloads show a progress bar in the ComfyUI UI via `comfy.utils.ProgressBar`.
- **Lazy loading** -- `boto3` is only imported when a cloud storage node actually executes, so there's no startup penalty.

## Architecture

```
[Cloud Storage Profile]
        |
        | S3_PROFILE (provider, bucket, credentials)
        |
   +---------+---------+---------+
   |         |         |         |
   v         v         v         v
[Save     [Save     [Load     [Load
 Image]    Video]    Image]    Model]   ...
   |         |         |         |
   v         v         v         v
  boto3 --> S3-compatible API --> Your Bucket
```

| Component | Description | File |
|-----------|-------------|------|
| Provider presets | Endpoint URLs and defaults for each provider | `providers.py` |
| Profile resolver | 3-layer credential resolution (env vars, JSON profiles, node overrides) | `profile.py` |
| Profile node | Source node that outputs `S3_PROFILE` to wire into other nodes | `nodes_profile.py` |
| Save nodes | Upload images (PNG/JPG/WebP), video, and audio to a bucket | `nodes_save.py` |
| Load nodes | Download images into the pipeline; download and cache model files | `nodes_load.py` |
| Browse nodes | List bucket contents; generate presigned sharing URLs | `nodes_browse.py` |

### Nodes

| Node | Category | Inputs | Outputs |
|------|----------|--------|---------|
| **Cloud Storage Profile** | `cloud_storage` | profile, provider, bucket, path_prefix | `S3_PROFILE` |
| **Save Image to Cloud** | `cloud_storage/save` | images, key_prefix, filename, format, quality, profile | UI text |
| **Save Video to Cloud** | `cloud_storage/save` | video, key_prefix, filename, format, codec, profile | UI text |
| **Save Audio to Cloud** | `cloud_storage/save` | audio, key_prefix, filename, format, profile | UI text |
| **Load Image from Cloud** | `cloud_storage/load` | key, profile | IMAGE, MASK |
| **Download Model from Cloud** | `cloud_storage/models` | model_type, key, force_redownload, profile | model_filename (STRING) |
| **List Bucket Contents** | `cloud_storage/browse` | prefix, max_results, profile | file_list (STRING) |
| **Generate Sharing URL** | `cloud_storage/browse` | key, expires_hours, profile | url (STRING) |

## Quick Start

Prerequisites:

- ComfyUI installed and running
- Python >= 3.10
- A bucket on any S3-compatible provider (B2, S3, R2, MinIO, etc.)
- Access key and secret key for that provider

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/backblaze-b2-samples/comfyui-cloud-storage
pip install -r comfyui-cloud-storage/requirements.txt
```

Set your credentials and restart ComfyUI:

```bash
export COMFY_S3_PROVIDER="Backblaze B2"
export COMFY_S3_ACCESS_KEY="your_key_id"
export COMFY_S3_SECRET_KEY="your_application_key"
export COMFY_S3_BUCKET="your-bucket-name"
export COMFY_S3_REGION="us-west-004"
```

The nodes appear under `cloud_storage/` in the node menu.

## Step-by-Step Setup

### 1. Install the Package

**Option A** -- Clone into custom_nodes:

```bash
cd ComfyUI/custom_nodes
git clone https://github.com/backblaze-b2-samples/comfyui-cloud-storage
pip install -r comfyui-cloud-storage/requirements.txt
```

**Option B** -- Symlink for development:

```bash
git clone https://github.com/backblaze-b2-samples/comfyui-cloud-storage ~/projects/comfyui-cloud-storage
ln -s ~/projects/comfyui-cloud-storage ComfyUI/custom_nodes/comfyui-cloud-storage
pip install boto3
```

### 2. Create a Bucket

Create a bucket with your provider. For Backblaze B2:

1. Log in to [B2 Cloud Storage](https://secure.backblaze.com/b2_buckets.htm)
2. Create a bucket (private is recommended)
3. Create an application key scoped to that bucket
4. Note the **keyID**, **applicationKey**, **bucket name**, and **endpoint** (e.g. `s3.us-west-004.backblazeb2.com`)

### 3. Configure Credentials

**Option A** -- Environment variables (simplest):

```bash
export COMFY_S3_PROVIDER="Backblaze B2"
export COMFY_S3_ACCESS_KEY="<keyID>"
export COMFY_S3_SECRET_KEY="<applicationKey>"
export COMFY_S3_BUCKET="<bucket-name>"
export COMFY_S3_REGION="us-west-004"
```

**Option B** -- Named profiles (multiple accounts or providers):

Create `ComfyUI/user/__cloud_storage/profiles.json`:

```json
{
  "profiles": {
    "b2-outputs": {
      "provider": "Backblaze B2",
      "access_key": "<keyID>",
      "secret_key": "<applicationKey>",
      "bucket": "my-comfyui-outputs",
      "region": "us-west-004"
    },
    "s3-models": {
      "provider": "AWS S3",
      "access_key": "<AWS_ACCESS_KEY_ID>",
      "secret_key": "<AWS_SECRET_ACCESS_KEY>",
      "bucket": "my-model-archive",
      "region": "us-east-1"
    }
  }
}
```

This file is stored in ComfyUI's system user directory (`__` prefix) and is not accessible via the HTTP API.

### 4. Use in a Workflow

1. Add a **Cloud Storage Profile** node (or skip it to use env vars)
2. Add a **Save Image to Cloud** node after your VAE Decode
3. Wire the profile output to the save node's profile input
4. Set your key prefix (e.g. `comfyui/images/2024-02/`)
5. Queue the prompt -- images upload to your bucket automatically

### 5. Verify

Check your bucket via the provider console or use the **List Bucket Contents** node to browse from within ComfyUI.

## Configuration

### Environment Variables

| Variable | Description | Default | Required |
|----------|-------------|---------|----------|
| `COMFY_S3_PROVIDER` | Provider name (see supported list below) | `AWS S3` | No |
| `COMFY_S3_ACCESS_KEY` | Access key / key ID | -- | Yes |
| `COMFY_S3_SECRET_KEY` | Secret key / application key | -- | Yes |
| `COMFY_S3_BUCKET` | Bucket name | -- | Yes |
| `COMFY_S3_REGION` | Region identifier | Provider default | No |
| `COMFY_S3_ENDPOINT_URL` | Custom endpoint URL (overrides provider preset) | -- | No |
| `COMFY_S3_ACCOUNT_ID` | Account ID (required for Cloudflare R2) | -- | R2 only |
| `COMFY_S3_PATH_PREFIX` | Default key prefix for all operations | -- | No |

### Supported Providers

| Provider | `COMFY_S3_PROVIDER` value | Default region | Notes |
|----------|--------------------------|----------------|-------|
| Backblaze B2 | `Backblaze B2` | `us-west-004` | Free 10 GB storage |
| AWS S3 | `AWS S3` | `us-east-1` | |
| Cloudflare R2 | `Cloudflare R2` | `auto` | Requires `COMFY_S3_ACCOUNT_ID` |
| MinIO | `MinIO` | `us-east-1` | Uses path-style addressing |
| Wasabi | `Wasabi` | `us-east-1` | |
| DigitalOcean Spaces | `DigitalOcean Spaces` | `nyc3` | |
| GCS (S3 interop) | `GCS (S3 interop)` | `auto` | Uses HMAC keys |
| Custom | `Custom` | -- | Set `COMFY_S3_ENDPOINT_URL` |

### Profile JSON

Stored at `ComfyUI/user/__cloud_storage/profiles.json`:

```json
{
  "profiles": {
    "<profile-name>": {
      "provider": "<provider name>",
      "access_key": "<key>",
      "secret_key": "<secret>",
      "bucket": "<bucket>",
      "region": "<region>",
      "endpoint_url": "<optional override>",
      "account_id": "<optional, for R2>",
      "path_prefix": "<optional default prefix>"
    }
  }
}
```

Credentials are resolved in order: environment variables -> named profile -> per-node widget overrides. Later layers override earlier ones. Widget overrides only apply to `bucket` and `path_prefix` -- credentials always come from env vars or the profile file.

## Testing

```bash
pip install pytest boto3
cd comfyui-cloud-storage
python -m pytest tests/ -v
```

Tests mock boto3 and ComfyUI internals so they run standalone without a ComfyUI installation. The `test_user_agent.py` test spins up a local HTTP server to verify the `b2ai-comfyui` user agent string appears in actual HTTP requests.

## Troubleshooting

| Symptom | Fix |
|---------|-----|
| Nodes don't appear in menu | Verify the package is in `custom_nodes/` and `boto3` is installed. Check ComfyUI startup logs for import errors. |
| "Cloud storage access key not configured" | Set `COMFY_S3_ACCESS_KEY` / `COMFY_S3_SECRET_KEY` env vars or create a profiles.json. |
| "Bucket not found" | Check the bucket name and region. For B2, the region is in the endpoint (e.g. `us-west-004`). |
| "Access denied" | Verify your key has read/write permissions on the bucket. For B2, check the application key's bucket scope. |
| Model download stalls | Check network connectivity. The download uses a temp file (`.download` suffix) and cleans up on failure. |
| "boto3 not installed" warning on startup | Run `pip install boto3` in the same Python environment as ComfyUI. |

## Contributing

- Branching: `main` + feature branches
- Tests: `python -m pytest tests/ -v` -- all tests must pass
- PR checklist:
  - [ ] Tests added or updated
  - [ ] New nodes registered in `__init__.py`
  - [ ] Provider presets validated against real endpoints

## Security

- **Credentials are never stored in workflow JSON.** The Cloud Storage Profile node only stores the profile name as a widget value. Actual keys are resolved server-side from environment variables or the profiles.json file.
- **profiles.json is HTTP-inaccessible.** It lives in ComfyUI's `user/__cloud_storage/` directory, which uses the `__` system prefix convention that blocks HTTP endpoint access.
- **Never commit profiles.json or `.env` files.** Use a secret manager or environment variables in production.
- To report security issues, open a GitHub issue or contact the maintainers directly.

## License

MIT -- See LICENSE for details.
