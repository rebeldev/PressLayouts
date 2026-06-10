Option Explicit

Dim shell, fso, scriptDir, logFile, pythonCmd, rc, cmd, summary
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
scriptDir = fso.GetParentFolderName(WScript.ScriptFullName)
logFile = scriptDir & "\\install_press_layout_modules.log"

Sub LogLine(msg)
    Dim ts
    If fso.FileExists(logFile) Then
        Set ts = fso.OpenTextFile(logFile, 8, True)
    Else
        Set ts = fso.CreateTextFile(logFile, True)
    End If
    ts.WriteLine Now & " - " & msg
    ts.Close
End Sub

Function RunAndLog(command)
    LogLine("RUN: " & command)
    RunAndLog = shell.Run("cmd /c " & Chr(34) & command & " >> " & Chr(34) & logFile & Chr(34) & " 2>&1" & Chr(34), 1, True)
    LogLine("EXIT CODE: " & CStr(RunAndLog))
End Function

Function CommandExists(commandText)
    Dim testCmd, rcLocal
    testCmd = "where " & commandText & " >nul 2>&1"
    rcLocal = shell.Run("cmd /c " & Chr(34) & testCmd & Chr(34), 0, True)
    CommandExists = (rcLocal = 0)
End Function

Function FindPythonCommand()
    If CommandExists("py") Then
        FindPythonCommand = "py -3"
        Exit Function
    End If
    If CommandExists("python") Then
        FindPythonCommand = "python"
        Exit Function
    End If
    If CommandExists("python3") Then
        FindPythonCommand = "python3"
        Exit Function
    End If
    FindPythonCommand = ""
End Function

pythonCmd = FindPythonCommand()

LogLine String(70, "=")
LogLine "Starting Press Layout dependency install"
LogLine "Script path: " & WScript.ScriptFullName

If pythonCmd = "" Then
    LogLine "Python was not found in PATH."
    MsgBox "Python was not found on this PC." & vbCrLf & vbCrLf & _
           "Install Python first (preferably from python.org or the Microsoft Store), then run this script again.", _
           vbCritical + vbOKOnly, "Press Layout Installer"
    WScript.Quit 1
End If

LogLine "Using Python command: " & pythonCmd

' Make sure pip exists for this Python install
rc = RunAndLog(pythonCmd & " -m pip --version")
If rc <> 0 Then
    LogLine "pip not found; attempting ensurepip."
    rc = RunAndLog(pythonCmd & " -m ensurepip --upgrade")
    If rc <> 0 Then
        MsgBox "Could not enable pip for this Python installation." & vbCrLf & _
               "See log file:" & vbCrLf & logFile, vbCritical + vbOKOnly, "Press Layout Installer"
        WScript.Quit rc
    End If
End If

' Optional but helpful: update pip in the current user profile only
rc = RunAndLog(pythonCmd & " -m pip install --user --upgrade pip")
If rc <> 0 Then
    LogLine "pip upgrade returned a non-zero code; continuing anyway."
End If

' Install only the non-standard modules detected from the source files:
'   PIL       -> Pillow
'   win32api / win32con / win32print / win32ui -> pywin32
rc = RunAndLog(pythonCmd & " -m pip install --user --upgrade Pillow pywin32")
If rc <> 0 Then
    MsgBox "Module installation failed." & vbCrLf & vbCrLf & _
           "Check the log file for details:" & vbCrLf & logFile, _
           vbCritical + vbOKOnly, "Press Layout Installer"
    WScript.Quit rc
End If

summary = "Installed/updated the required Python packages for Press Layout:" & vbCrLf & vbCrLf & _
          "  - Pillow" & vbCrLf & _
          "  - pywin32" & vbCrLf & vbCrLf & _
          "Install scope: current Windows user only (--user)" & vbCrLf & _
          "No admin rights required." & vbCrLf & vbCrLf & _
          "Log file:" & vbCrLf & logFile

LogLine "Install completed successfully."
MsgBox summary, vbInformation + vbOKOnly, "Press Layout Installer"
WScript.Quit 0
