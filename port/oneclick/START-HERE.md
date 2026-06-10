# MRT2 Studio: Start Here

Type a prompt, press Generate, and an original track plays in your browser.

## Use it

1. Double-click `MRT2-Studio.bat` (or `studio\MRT2-Studio.vbs`).
2. The browser opens to the MRT2 Studio page. The first launch loads the model and shows
   "Waking up the musician…" for about a minute.
3. Type what you want, set the **Length**, and press **▶ Generate**.
4. The track plays, a visualizer reacts to it, and it appears in **History**. Every track
   is saved to `studio\output\`.

## The knobs

| Control | What it does |
|---|---|
| **Prompt** | The vibe, in words. |
| **Length** | Track length, 4 seconds to 3 minutes. |
| **Temperature** | Higher is more adventurous, lower is steadier. |
| **Top-k** | How many options it weighs at each step. |
| **Style strength** | How closely it follows the prompt. |
| **Melody strength** | How much it leans on melodic structure. |

Click an example chip under the prompt box to load a vibe instantly.

## How it runs

Generation runs on your NVIDIA GPU inside WSL2. The browser page talks to a local server
at `http://localhost:8777`. The model is `mrt2_small`. First-time WSL2 setup is in
[../wsl/README.md](../wsl/README.md).

## The larger model

`mrt2_base` runs on a rented cloud GPU through RunPod. See [README.md](README.md).

## If something seems off

- The status line at the top shows what the engine is doing. On first launch, give the
  model a minute to load.
- Click **▶** on the player once if you hear nothing. Browsers require a click before audio.
- Click **⏻ Quit** to stop the engine.
