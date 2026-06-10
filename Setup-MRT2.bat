@echo off
rem ===========================================================================
rem  MRT2 Studio - SETUP.  Double-click this ONCE to install everything.
rem  It checks your PC, shows what it needs, asks before downloading anything,
rem  and fixes common problems automatically.
rem ===========================================================================
title MRT2 Studio Setup
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0install\setup.ps1" %*
