@echo off
setlocal
set "UTF8_SNIPPET=$utf8NoBom = [System.Text.UTF8Encoding]::new($false); [Console]::InputEncoding = $utf8NoBom; [Console]::OutputEncoding = $utf8NoBom; $global:OutputEncoding = $utf8NoBom; $env:PYTHONIOENCODING = 'utf-8'"
powershell.exe -NoLogo -NoExit -ExecutionPolicy Bypass -Command "%UTF8_SNIPPET%"
