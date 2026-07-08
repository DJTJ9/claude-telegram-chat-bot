$ErrorActionPreference = "Stop"
$lockFile = "$env:TEMP\voice_input.lock"
$audioFile = "$env:TEMP\voice_input.wav"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

if (Test-Path $lockFile) {
    $recPid = Get-Content $lockFile
    Stop-Process -Id $recPid -Force -ErrorAction SilentlyContinue
    Remove-Item $lockFile
    Write-Host "`e[33m● Transkribiere...`e[0m"
    $text = & python "$scriptDir\voice_transcribe.py" $audioFile
    Set-Clipboard -Value $text
    Add-Type -AssemblyName System.Windows.Forms
    [System.Windows.Forms.SendKeys]::SendWait("^v")
    Write-Host "`e[0m"
} else {
    Write-Host "`e[31m● REC`e[0m"
    $proc = Start-Process -FilePath "ffmpeg" -ArgumentList "-f dshow -i audio=`"Mikrofon (3- Razer Barracuda X)`" -y `"$audioFile`"" -PassThru -WindowStyle Hidden -RedirectStandardError "$env:TEMP\voice_ffmpeg_err.log"
    $proc.Id | Out-File $lockFile
}
