@echo off
rem E1 probe - the "application path" the Locate utility offers to ZBrush (stored as PATH in GoZ_Config.txt).
rem Mirai is a Python program, not an .exe: E1 records whether ZBrush accepts this path and whether it ever runs it.
echo %DATE% %TIME% PROBE_APP args=[%*] cwd=[%CD%]>> "%~dp0captures\commands_log.txt"
echo Mirai GoZ probe (E1): stand-in application path. Nothing to do here; the receiver is Edit.bat.
exit /b 0
