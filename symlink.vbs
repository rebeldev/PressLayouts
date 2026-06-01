Option Explicit

Dim shell, cmd, linkPath, targetPath

linkPath = "C:\PressLayouts"
targetPath = "C:\Users\bradb\Gannett Company, Incorporated\Gastonia CTP - Documents\General\Python\Press Layouts"

' /J = junction (no admin required)
cmd = "cmd.exe /c mklink /J """ & linkPath & """ """ & targetPath & """"

Set shell = CreateObject("WScript.Shell")
shell.Run cmd, 0, True

WScript.Echo "Junction created:" & vbCrLf & linkPath & " -> " & targetPath