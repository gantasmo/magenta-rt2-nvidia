@echo off
rem ===========================================================================
rem  MRT2 Studio (Windows launcher)
rem  Hands off to app\MRT2-Studio.vbs, which starts the music engine in WSL2
rem  and opens your browser to the Studio.
rem  For the larger mrt2_base model, see the RunPod cloud path in README.md.
rem ===========================================================================
echo Starting MRT2 Studio... your browser will open in a moment.
start "" "%~dp0app\MRT2-Studio.vbs"
