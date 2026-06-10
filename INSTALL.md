# Installing MRT2 Studio

The short version: **download the release ZIP, unzip, double-click `Setup-MRT2.bat`.**
This page is the friendly long version, including what to do if you've never heard of
"WSL."

## What you need

- A **Windows 10 or 11** PC.
- An **NVIDIA** graphics card (GeForce / RTX) with a recent driver.
- About **6 GB** of free disk space and an internet connection (first-time setup only).

## Step 1: Download

Open the project's **[Releases](../../releases/latest)** page and download
**`MRT2-Studio.zip`**. Unzip it anywhere (Desktop is fine).

> Don't use the green **Code → Download ZIP** button on the main page. It leaves out a
> component. Use the **release ZIP**.

## Step 2: Run Setup

Double-click **`Setup-MRT2.bat`**. A window opens and checks your PC. It will:

- List what (if anything) needs to be installed, and how big the downloads are.
- **Download nothing until you say yes.**
- Install the music engine and model, then verify they work on your GPU.

## "What is WSL, and what if I don't have it?"

WSL is a free Microsoft feature that lets Windows run the Linux-based music engine. **The
installer turns it on for you.** If WSL isn't installed yet, Setup will:

1. Ask for permission (click **Yes**), install WSL2 + Ubuntu, and ask you to **restart**.
2. After the restart, a black **Ubuntu** window opens once and asks you to create a
   **username and password**. Type any simple ones you'll remember, then close it.
3. Double-click **`Setup-MRT2.bat`** again to finish.

Prefer to do that part yourself first? Either works:

- **Microsoft Store:** open it, search **Ubuntu**, click **Get**.
- **Windows Features:** open Settings, search **"Windows features"**, tick **Windows
  Subsystem for Linux** and **Virtual Machine Platform**, click OK, and restart.

## Step 3: Make music

When setup finishes, the Studio opens in your browser. Type a vibe, set the length, press
**Generate**. Tracks are saved to `app\output\`.

Next time, skip Setup. Just double-click **`MRT2-Studio.bat`** in the main folder.

## If something goes wrong

`Setup-MRT2.bat` is **always safe to run again**. It skips finished steps and resumes
interrupted downloads.

- **"No NVIDIA GPU detected"**: install or update your driver from
  [nvidia.com/Download](https://www.nvidia.com/Download/index.aspx), then re-run Setup.
- **Setup stopped partway**: an internet or disk hiccup. Re-run `Setup-MRT2.bat`.
- **The page says "server offline" / "Waking up the musician…"**: on the first launch,
  give the model a minute to load onto the GPU.
- **No sound**: click the ▶ on the player once (browsers require a click before audio).
