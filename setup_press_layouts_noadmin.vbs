Option Explicit

Dim fso, shell, scriptDir, targetPath, linkPath
Dim pythonCmd, rc, msg

Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
targetPath = scriptDir
linkPath = "C:\PressLayouts"
pythonCmd = DetectPythonCommand()

If pythonCmd = "" Then
    MsgBox "Python was not found on PATH. Please install Python first, then run this script again.", vbCritical, "Press Layout Setup"
    WScript.Quit 1
End If

' Create or validate the junction.
If fso.FolderExists(linkPath) Then
    If IsJunctionToTarget(linkPath, targetPath) Then
        ' Already correct.
    Else
        MsgBox "C:\PressLayouts already exists and is not the expected junction to:" & vbCrLf & targetPath & vbCrLf & vbCrLf & _
               "Please remove or rename the existing folder/link and run the script again.", vbCritical, "Press Layout Setup"
        WScript.Quit 1
    End If
ElseIf fso.FileExists(linkPath) Then
    MsgBox "C:\PressLayouts already exists as a file. Please remove or rename it and run the script again.", vbCritical, "Press Layout Setup"
    WScript.Quit 1
Else
    rc = RunHidden("cmd /c mklink /J " & Q(linkPath) & " " & Q(targetPath))
    If rc <> 0 Then
        MsgBox "Could not create junction:" & vbCrLf & linkPath & " -> " & targetPath & vbCrLf & vbCrLf & _
               "This script does not request elevation. If your account does not have permission to create items in C:\, Windows will block it.", _
               vbCritical, "Press Layout Setup"
        WScript.Quit 1
    End If
End If

' Upgrade pip (user scope) and install required packages for the press layout app.
rc = RunHidden(pythonCmd & " -m pip install --user --upgrade pip")
If rc <> 0 Then
    MsgBox "pip upgrade failed. Exit code: " & rc, vbCritical, "Press Layout Setup"
    WScript.Quit 1
End If

rc = RunHidden(pythonCmd & " -m pip install --user pillow pywin32")
If rc <> 0 Then
    MsgBox "Package install failed. Exit code: " & rc & vbCrLf & vbCrLf & _
           "Tried to install: pillow pywin32", vbCritical, "Press Layout Setup"
    WScript.Quit 1
End If

msg = "Setup completed successfully." & vbCrLf & vbCrLf & _
      "Junction:" & vbCrLf & "  " & linkPath & " -> " & targetPath & vbCrLf & vbCrLf & _
      "Python command:" & vbCrLf & "  " & pythonCmd & vbCrLf & vbCrLf & _
      "Installed packages:" & vbCrLf & "  pillow" & vbCrLf & "  pywin32"
MsgBox msg, vbInformation, "Press Layout Setup"

Function DetectPythonCommand()
    If CommandExists("py") Then
        DetectPythonCommand = "py"
        Exit Function
    End If
    If CommandExists("python") Then
        DetectPythonCommand = "python"
        Exit Function
    End If
    DetectPythonCommand = ""
End Function

Function CommandExists(cmdName)
    Dim execObj, output
    On Error Resume Next
    Set execObj = shell.Exec("cmd /c where " & cmdName)
    output = ""
    If Not execObj Is Nothing Then
        Do While execObj.Status = 0
            WScript.Sleep 50
        Loop
        output = Trim(execObj.StdOut.ReadAll)
        CommandExists = (execObj.ExitCode = 0 And output <> "")
    Else
        CommandExists = False
    End If
    On Error GoTo 0
End Function

Function IsJunctionToTarget(linkFolder, expectedTarget)
    Dim execObj, outText, normalizedExpected
    On Error Resume Next
    Set execObj = shell.Exec("cmd /c dir /AL " & Q(linkFolder))
    If execObj Is Nothing Then
        IsJunctionToTarget = False
        Exit Function
    End If
    Do While execObj.Status = 0
        WScript.Sleep 50
    Loop
    outText = execObj.StdOut.ReadAll
    normalizedExpected = LCase(Replace(expectedTarget, "/", "\\"))
    IsJunctionToTarget = (InStr(LCase(outText), "<junction>") > 0 And InStr(LCase(outText), normalizedExpected) > 0)
    On Error GoTo 0
End Function

Function RunHidden(cmd)
    RunHidden = shell.Run(cmd, 0, True)
End Function

Function Q(s)
    Q = Chr(34) & s & Chr(34)
End Function
