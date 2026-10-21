param([string]$Out = "$PSScriptRoot\img")
Add-Type -AssemblyName System.Drawing
New-Item -ItemType Directory -Force $Out | Out-Null
function C($hex, $a = 255) { $c = [Drawing.ColorTranslator]::FromHtml($hex); [Drawing.Color]::FromArgb($a, $c.R, $c.G, $c.B) }

# ---------- page background: dark header band (battery-cell motif) + light canvas ----------
$S = 2; $W = 1280 * $S; $H = 720 * $S; $band = 104 * $S
$bmp = New-Object Drawing.Bitmap $W, $H
$g = [Drawing.Graphics]::FromImage($bmp); $g.SmoothingMode = "AntiAlias"
# canvas
$body = New-Object Drawing.Drawing2D.LinearGradientBrush (New-Object Drawing.Rectangle 0, $band, $W, ($H - $band)), (C "#EEF1F5"), (C "#E3E8EE"), 90
$g.FillRectangle($body, 0, $band, $W, $H - $band)
# band
$bandBrush = New-Object Drawing.Drawing2D.LinearGradientBrush (New-Object Drawing.Rectangle 0, 0, $W, $band), (C "#07090C"), (C "#1E252D"), 0
$g.FillRectangle($bandBrush, 0, 0, $W, $band)
# cylindrical cell tops, fading in from the left
$g.SetClip((New-Object Drawing.Rectangle 0, 0, $W, ($band - 4 * $S)))
$r = 15 * $S; $dx = 2 * $r + 6 * $S; $dy = [int]($dx * 0.866)
for ($row = -1; $row -le [int]($band / $dy) + 1; $row++) {
  for ($x = 0; $x -lt $W + $dx; $x += $dx) {
    $cx = $x + $(if ($row % 2) { $dx / 2 } else { 0 }); $cy = $row * $dy + 8 * $S
    $t = [Math]::Max(0, [Math]::Min(1, ($cx / $W - 0.35) / 0.65))
    if ($t -le 0) { continue }
    $a = [int](70 * $t)
    $pen = New-Object Drawing.Pen (C "#9AA5B1" $a), (1.2 * $S)
    $g.DrawEllipse($pen, [float]($cx - $r), [float]($cy - $r), [float](2 * $r), [float](2 * $r))
    $g.DrawEllipse($pen, [float]($cx - $r * 0.45), [float]($cy - $r * 0.45), [float]($r * 0.9), [float]($r * 0.9))
    $g.FillEllipse((New-Object Drawing.SolidBrush (C "#E31937" ([int]($a * 0.5)))), [float]($cx - 2 * $S), [float]($cy - 2 * $S), [float](4 * $S), [float](4 * $S))
  }
}
# soft vignette so text on the left stays readable
$vig = New-Object Drawing.Drawing2D.LinearGradientBrush (New-Object Drawing.Rectangle 0, 0, ($W * 0.6), $band), (C "#07090C" 235), (C "#07090C" 0), 0
$vig.WrapMode = [Drawing.Drawing2D.WrapMode]::TileFlipX
$g.FillRectangle((New-Object Drawing.SolidBrush (C "#07090C" 0)), 0, 0, 1, 1)
$vb = New-Object Drawing.Drawing2D.LinearGradientBrush (New-Object Drawing.Rectangle -2, 0, ([int]($W * 0.62) + 4), $band), (C "#07090C" 235), (C "#07090C" 0), 0
$g.FillRectangle($vb, 0, 0, [int]($W * 0.62), $band)
$g.ResetClip()
# accent line
$g.FillRectangle((New-Object Drawing.SolidBrush (C "#E31937")), 0, $band - 4 * $S, $W, 4 * $S)
$bmp.Save("$Out\bg.png", [Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()

# ---------- placeholder logo (replace logo.png to use another logo) ----------
$LW = 600; $LH = 240
$bmp = New-Object Drawing.Bitmap $LW, $LH
$g = [Drawing.Graphics]::FromImage($bmp); $g.SmoothingMode = "AntiAlias"; $g.TextRenderingHint = "AntiAliasGridFit"
$g.Clear([Drawing.Color]::Transparent)
# battery outline with lightning bolt
$white = New-Object Drawing.Pen (C "#FFFFFF"), 10
$g.DrawRectangle($white, 20, 70, 150, 100); $g.FillRectangle((New-Object Drawing.SolidBrush (C "#FFFFFF")), 170, 100, 14, 40)
$bolt = [Drawing.PointF[]]@((New-Object Drawing.PointF 108, 80), (New-Object Drawing.PointF 70, 128), (New-Object Drawing.PointF 98, 128), (New-Object Drawing.PointF 84, 162), (New-Object Drawing.PointF 128, 110), (New-Object Drawing.PointF 100, 110), (New-Object Drawing.PointF 116, 80))
$g.FillPolygon((New-Object Drawing.SolidBrush (C "#E31937")), $bolt)
$f1 = New-Object Drawing.Font "Segoe UI", 62, ([Drawing.FontStyle]::Bold), ([Drawing.GraphicsUnit]::Pixel)
$f2 = New-Object Drawing.Font "Segoe UI", 26, ([Drawing.FontStyle]::Regular), ([Drawing.GraphicsUnit]::Pixel)
$g.DrawString("PACKRISK", $f1, (New-Object Drawing.SolidBrush (C "#FFFFFF")), 205, 62)
$g.DrawString("SUPPLY RISK ANALYTICS", $f2, (New-Object Drawing.SolidBrush (C "#A2AAAD")), 210, 138)
$bmp.Save("$Out\logo.png", [Drawing.Imaging.ImageFormat]::Png); $g.Dispose(); $bmp.Dispose()
Get-ChildItem $Out | Select-Object Name, Length
