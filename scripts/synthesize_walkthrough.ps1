param([Parameter(Mandatory=$true)][string]$Directory)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Speech
$taskNarrator = New-Object System.Speech.Synthesis.SpeechSynthesizer
try {
    $taskNarrator.SelectVoice('Microsoft Zira Desktop')
    $taskNarrator.Rate = 0
    $taskNarrator.Volume = 100
    $taskSlides = Get-Content -LiteralPath (Join-Path $Directory 'slides.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    for ($taskSlideIndex = 0; $taskSlideIndex -lt $taskSlides.Count; $taskSlideIndex++) {
        $taskAudioPath = Join-Path $Directory ('{0:D2}.wav' -f $taskSlideIndex)
        $taskNarrator.SetOutputToWaveFile($taskAudioPath)
        $taskNarrator.Speak([string]$taskSlides[$taskSlideIndex].narration)
        $taskNarrator.SetOutputToNull()
        Write-Output ('Narrated slide ' + ($taskSlideIndex + 1))
    }
} finally {
    $taskNarrator.Dispose()
}
