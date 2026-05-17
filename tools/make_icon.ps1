# Regenerate assets/icon.ico for this project.
# Edit $Text / colors below and re-run.

param(
    [string]$Text = "DHCP",
    [int[]]$ColorFrom = @(80, 160, 255),
    [int[]]$ColorTo   = @(20, 60, 140),
    [string]$OutPath  = "$PSScriptRoot\..\assets\icon.ico"
)

Add-Type -AssemblyName System.Drawing

$outDir = Split-Path $OutPath -Parent
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir -Force | Out-Null }

$bgFrom = [System.Drawing.Color]::FromArgb(255, $ColorFrom[0], $ColorFrom[1], $ColorFrom[2])
$bgTo   = [System.Drawing.Color]::FromArgb(255, $ColorTo[0],   $ColorTo[1],   $ColorTo[2])

$sizes = 256, 128, 64, 48, 32, 16
$pngs = @()
foreach ($s in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap $s, $s
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = 'AntiAlias'
    $g.TextRenderingHint = 'AntiAliasGridFit'

    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $r = $s - 2
    $path.AddEllipse(1, 1, $r, $r)
    $brush = New-Object System.Drawing.Drawing2D.PathGradientBrush($path)
    $brush.CenterColor = $bgFrom
    $brush.SurroundColors = @($bgTo)
    $g.FillEllipse($brush, 1, 1, $r, $r)

    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(60, 0, 0, 0)), ([float]($s/64))
    $g.DrawEllipse($pen, 1, 1, $r, $r)

    $fontSize = [float]($s * 0.32)
    $font = New-Object System.Drawing.Font "Segoe UI Black", $fontSize, ([System.Drawing.FontStyle]::Bold), ([System.Drawing.GraphicsUnit]::Pixel)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = 'Center'; $sf.LineAlignment = 'Center'
    $shadow = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(80, 0, 0, 0))
    $g.DrawString($Text, $font, $shadow, [float]($s/2 + $s*0.02), [float]($s/2 + $s*0.02), $sf)
    $g.DrawString($Text, $font, [System.Drawing.Brushes]::White, [float]($s/2), [float]($s/2), $sf)
    $g.Dispose()

    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngs += ,@{ size = $s; bytes = $ms.ToArray() }
    $ms.Dispose(); $bmp.Dispose()
}

$fs = [System.IO.File]::Create($OutPath)
$bw = New-Object System.IO.BinaryWriter $fs
$bw.Write([uint16]0)
$bw.Write([uint16]1)
$bw.Write([uint16]$pngs.Count)
$offset = 6 + 16 * $pngs.Count
foreach ($p in $pngs) {
    $w = if ($p.size -ge 256) { 0 } else { $p.size }
    $bw.Write([byte]$w); $bw.Write([byte]$w)
    $bw.Write([byte]0); $bw.Write([byte]0)
    $bw.Write([uint16]1); $bw.Write([uint16]32)
    $bw.Write([uint32]$p.bytes.Length); $bw.Write([uint32]$offset)
    $offset += $p.bytes.Length
}
foreach ($p in $pngs) { $bw.Write($p.bytes) }
$bw.Close(); $fs.Close()
Write-Host "Wrote $OutPath"
