function Set-PowerShellUtf8Interop {
    [CmdletBinding()]
    param()

    # Windows PowerShell 5.1 defaults $OutputEncoding to US-ASCII for pipes
    # to external programs, which turns Korean text into question marks.
    $utf8NoBom = [System.Text.UTF8Encoding]::new($false)

    [Console]::InputEncoding = $utf8NoBom
    [Console]::OutputEncoding = $utf8NoBom
    $global:OutputEncoding = $utf8NoBom

    # Python reads stdin/stdout through these encodings when used via
    # `python -` or other piped workflows.
    $env:PYTHONIOENCODING = "utf-8"
}

Set-PowerShellUtf8Interop
