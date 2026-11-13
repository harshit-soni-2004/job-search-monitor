param(
    [string]$Title = "Job Search Monitor",
    [string]$Message = "Daily monitor check completed."
)

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

$notification = New-Object System.Windows.Forms.NotifyIcon
$notification.Icon = [System.Drawing.SystemIcons]::Information
$notification.BalloonTipTitle = $Title
$notification.BalloonTipText = $Message
$notification.BalloonTipIcon = [System.Windows.Forms.ToolTipIcon]::Info
$notification.Visible = $True
$notification.ShowBalloonTip(7000)
Start-Sleep -Seconds 2
$notification.Dispose()

