# Running CreatorForge on a normal Windows laptop (Docker)

You don't need to install Python or anything technical. If the laptop
can run Docker, it can run CreatorForge. Two paths: **Docker Desktop**
(easiest) or **WSL2 + Docker** (for tinkerers). Both end at the same
place: the dashboard in your browser.

## Path A — Docker Desktop (recommended)

1. **Install Docker Desktop for Windows**
   - Download from [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop) and run the installer.
   - When it asks, keep **"Use WSL 2 instead of Hyper-V"** checked. Let it
     restart the laptop if it asks.
   - Open Docker Desktop once and wait until it says "running" (green).

2. **Get CreatorForge**
   - Download the repo zip from GitHub
     (`nave433-blip/creator-forge` → green **Code** button → Download ZIP),
     or `git clone https://github.com/nave433-blip/creator-forge.git`.
   - Unzip it somewhere simple, like `C:\creator-forge`.

3. **Start it**
   - Open **PowerShell**, go to the folder:
     ```powershell
     cd C:\creator-forge
     docker compose up -d --build
     ```
   - First start takes a few minutes (it downloads Python and the app's
     pieces). After that it's seconds.

4. **Open it** — go to [http://localhost:8765](http://localhost:8765) in
   your browser. That's the dashboard: catalog, chat approvals, word
   bank, payments, everything.

5. **Use the terminal commands** (optional) — anything from the docs
   works inside the container:
   ```powershell
   docker compose run --rm forge menu
   docker compose run --rm forge chat lexicon-list
   docker compose run --rm forge catalog scan /content
   ```

6. **Stop it** — `docker compose down`. Your data is safe: it lives in
   the `forge-data` and `identity-packs` folders next to the app, not
   inside the container.

## Path B — WSL2 (Ubuntu) + Docker

1. In PowerShell (as admin): `wsl --install` → restart → open the
   Ubuntu app and make your Linux username/password.
2. Inside Ubuntu:
   ```bash
   sudo apt update && sudo apt install -y docker.io docker-compose-plugin git
   sudo usermod -aG docker $USER
   ```
   Close and reopen the Ubuntu terminal.
3. Then it's the same as Path A from step 2:
   ```bash
   git clone https://github.com/nave433-blip/creator-forge.git
   cd creator-forge
   docker compose up -d --build
   ```
   Dashboard at [http://localhost:8765](http://localhost:8765).

## Your content folder (both paths)

To scan your photos/videos, mount the folder in `docker-compose.yml` —
uncomment the `/content` line and point it at your folder:

```yaml
- C:/Users/you/Pictures/content:/content:ro   # Windows path style
```

Then: `docker compose run --rm forge catalog scan /content`

## What Docker does NOT change (honest notes)

- **AI video training still needs a real GPU.** The Docker image runs
  the catalog, chat, vault, dashboard, and API-based generation
  (Replicate etc.) perfectly on a normal laptop. *Training* your personal
  AI model needs an NVIDIA GPU — on Windows that means the WSL2 backend
  with NVIDIA's container support, or just training on a rented cloud
  GPU / paid API instead. `docs/VIDEO.md` covers the options.
- **The Linux desktop app (`forge gui`) isn't in the Docker image.**
  Docker is headless — use the web dashboard instead, it does the same
  things. Run `forge gui` natively on Linux if you want the desktop app.
- **Live avatar / streaming** (`forge live`, `forge stream`) needs OBS
  on the *host* machine (Windows), not in Docker. The app prepares
  everything; OBS does the actual streaming. See `docs/STREAMING.md`.
- **Keep Docker Desktop updated** and give it at least 4 GB RAM in
  Settings → Resources if the laptop allows it.

## Updating

```powershell
cd C:\creator-forge
git pull
docker compose up -d --build
```

Your `forge-data` folder is untouched by updates.
