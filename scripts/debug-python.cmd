@echo off
REM Run project venv Python in isolated mode (-I) so Windows registry
REM PythonPath entries do not inject a second stdlib into sys.path.
"%~dp0..\.venv\Scripts\python.exe" -I %*
