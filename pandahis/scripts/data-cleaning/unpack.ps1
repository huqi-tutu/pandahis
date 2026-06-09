Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::OpenRead(C:\Users\user\Desktop\历史图谱\pandahis\data\historiography-index.zip)
foreach($e in $zip.Entries) {
  if($e.FullName.Contains(001) -and $e.FullName.EndsWith(.json)) {
    $s = $e.Open()
    $r = (New-Object System.IO.StreamReader($s)).ReadToEnd()
    [IO.File]::WriteAllText(C:\Users\user\Desktop\历史图谱\pandahis\scripts\data-cleaning\_index.json, $r, [Text.Encoding]::UTF8)
    Write-Host Extracted: $e.FullName $r.Length
    break
  }
}
$zip.Dispose()
