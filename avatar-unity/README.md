# Avatar Unity

Unity client for the research avatar agent. It displays a local VRM avatar and
will connect the avatar presentation layer to the FastAPI server.

## Environment

- Unity: 6000.3.15f1 (Unity 6.3 LTS)
- UniVRM: 0.131.0
- Primary avatar format: VRM 1.0
- Target platform for the first demo: Windows Editor

## Project Structure

- `Assets/Scripts/`: shared C# code tracked by Git
- `Assets/Scenes/`: shared Unity scenes tracked by Git
- `Assets/Models/`: local VRM files and generated imports, ignored by Git
- `Packages/`: dependency declarations tracked by Git
- `ProjectSettings/`: shared Unity project settings tracked by Git
- `Library/`, `Temp/`, `Logs/`: generated Unity data ignored by Git

Unity `.meta` files provide stable GUIDs for assets. Commit them together with
tracked scripts and scenes. Model `.meta` files remain ignored with the models.

## Local Setup

1. Open this directory as a project from Unity Hub.
2. Confirm that a valid Unity Personal license is active.
3. Copy a permitted VRM model to `Assets/Models/`.
4. Use VRM 1.0 when possible.
5. Do not commit local models unless their license explicitly permits it.

The current loader expects `Assets/Models/male1.vrm` by default. The file name
will be configurable from the Unity Inspector after the loader is added to a
shared scene.

## Git Dependency Rules

Keep `Packages/manifest.json` and `Packages/packages-lock.json` in Git. They are
similar to Go's `go.mod` and `go.sum`: another computer uses them to restore
UniVRM. Downloaded package contents live in `Library/PackageCache` and are not
committed.

## Current Development Order

1. Load a local VRM model without a scene-level model reference.
2. Add a model-independent avatar controller.
3. Map server emotion values to VRM expression weights.
4. Connect Unity to `POST /api/v1/unity/chat`.
5. Add script-driven teaching actions and lip sync.

The local `AvatarDemo` scene currently references `male1` directly and is
ignored. A shared scene will replace it after runtime loading is verified.
