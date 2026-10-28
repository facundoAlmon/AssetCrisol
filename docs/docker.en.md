# AssetCrisol in Docker

[Español](docker.md)

The image ships ComfyUI (with its node packs), TRELLIS.2 (with its compiled extensions) and Blender 5.1, installed
with `instalar.sh`. **It ships no models**: they go in a volume you fill once. The assets you generate stay in a folder
of yours.

## Requirements

- Linux with a 16 GB NVIDIA card (Ampere, Ada or Hopper: RTX 30/40, A-series; RTX 50 cards are untested) and driver
  560 or newer.
- Docker with the [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)
  (`docker run --rm --gpus all ubuntu nvidia-smi` must show the card).
- Disk: ~23 GB for the image and ~90-135 GB for the models (see README > Detailed requirements). If
  `/var/lib/docker` lives on a small disk, move Docker's storage (`data-root` in `/etc/docker/daemon.json`).

## Usage

```bash
docker build -t assetcrisol .            # ~20 min (not published on GHCR yet)

# an alias to avoid repeating: GPU, models in a volume, assets in ./assets
mkdir -p assets
alias crisol='docker run --rm -it --gpus all -v crisol-modelos:/modelos -v "$PWD/assets":/datos assetcrisol'

crisol modelos                  # downloads the models into the volume (full level; --nivel minimo, --flux2)
crisol doctor                   # checks everything
crisol nuevo bandido            # and every other step, same as without Docker
crisol todo bandido
```

- **Gated models** (DINOv3 and FLUX.2 Klein): accept their terms on Hugging Face with your account. `crisol modelos`
  asks for a read token (or pass it with `-e HF_TOKEN=hf_...`); it is stored in the volume.
- Generated files belong to the owner of the folder mounted at `/datos`.
- To try it without generating anything: `cp -r ejemplos/* assets/` and `crisol blender cris && crisol sprites cris`.
- A shell inside: `crisol bash`.

## Publishing (maintainers)

`docker/publicar.sh <version>` builds it here and pushes it (23 GB: too big for GitHub's free runners). GHCR by
default (`ghcr.io/facundoalmon/assetcrisol`; the first one will be `0.1.0-alpha.1`); for another registry,
`REGISTRO=docker.io/<user>` or `registry.gitlab.com/<user>/<project>`. Run `docker login` first. On GHCR the package
starts private: the first time, make it public on its GitHub page.

## Notes

- Each `docker run` starts its own ComfyUI when a step needs it: the first image step takes longer (it loads the
  models).
- **One generation at a time on the GPU**: do not run an image or mesh step while another program uses it (another
  ComfyUI, a game). With 16 GB, two at once run out of memory.
- Kimodo and Godot are not in the image (optional; see the README).
- Blender and UltraTex's baking use EGL (OpenGL without a display): the image already requests the driver's graphics
  capabilities (`NVIDIA_DRIVER_CAPABILITIES=all`).
