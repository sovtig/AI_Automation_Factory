@echo off
setlocal

echo Running LM Studio connection test...
cd /d %~dp0

:: Set Node.js options
set NODE_OPTIONS=--experimental-vm-modules --no-warnings

:: Run the test
node --experimental-modules test-connection.js

if %ERRORLEVEL% NEQ 0 (
    echo Test failed with error code %ERRORLEVEL%
    exit /b %ERRORLEVEL%
)

echo Test completed successfully
endlocal
