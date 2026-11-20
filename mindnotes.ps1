[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$CommandArgs
)

& "$PSScriptRoot\.venv\Scripts\python.exe" -m mindnotes.cli @CommandArgs
