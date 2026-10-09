# Open a document in Word, report what Word made of it, and always exit.
#
# Two things this has to get right, both learned the hard way:
#
#   * A fresh Word process per document. After one refusal, an instance will not
#     open anything else either, so every later result in the same instance is
#     meaningless -- including a file that is fine.
#   * `[ref]` on the arguments. `$doc.Open($path, $false, $true)` binds the
#     booleans as psobject and fails on a document Word would happily open, which
#     looks exactly like a corrupt file.
#
# Word is killed at the end whatever happens. `Quit()` on its own leaves
# WINWORD processes behind, and they contend with the next run.
param(
    [Parameter(Mandatory = $true)][string]$Path,
    [string]$TextOut
)

$word = $null
try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $doc = $word.Documents.Open($Path, [ref]$false, [ref]$true)
    Write-Output "paragraphs=$($doc.Paragraphs.Count)"
    if ($TextOut) {
        # Written to a file rather than to stdout: the console encoding turns
        # every Persian character into "?", which would make this assertion pass
        # or fail for reasons that have nothing to do with the document.
        [System.IO.File]::WriteAllText($TextOut, $doc.Content.Text, [System.Text.UTF8Encoding]::new($false))
    }
    $doc.Close([ref]$false)
    exit 0
} catch {
    # The message is the finding. "The file appears to be corrupted" means Word
    # rejected the package; anything else is a harness problem.
    Write-Output ("REFUSED: " + $_.Exception.Message)
    exit 1
} finally {
    if ($word) {
        try { $word.Quit([ref]$false) } catch { }
        [System.Runtime.InteropServices.Marshal]::ReleaseComObject($word) | Out-Null
    }
    Get-Process WINWORD -ErrorAction SilentlyContinue | Stop-Process -Force
}
