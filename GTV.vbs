' GTV launcher - completely silent, no black console window.
' The app keeps running even after run.bat / this script has finished.
' GTV is for OFFLINE single-player games only.
Option Explicit

Dim Shell, FSO, here, pyw, pythonExe
Set Shell = CreateObject("WScript.Shell")
Set FSO   = CreateObject("Scripting.FileSystemObject")

here      = FSO.GetParentFolderName(WScript.ScriptFullName)
pyw       = here & "\.venv\Scripts\pythonw.exe"
pythonExe = here & "\.venv\Scripts\python.exe"

If Not FSO.FileExists(pyw) Then
    If Not FSO.FileExists(pythonExe) Then
        MsgBox "GTV is not installed yet." & vbCrLf & _
               "Please double-click run.bat once first.", vbExclamation, "GTV"
        WScript.Quit 1
    End If
    ' Fallback: no pythonw available, use python.exe (a console window will open)
    pyw = pythonExe
End If

Shell.CurrentDirectory = here
' Window style 0 = hidden, False = do not wait for the process to finish.
' The launched process is independent, so closing the console never kills GTV.
Shell.Run """" & pyw & """ -m gtv.boot", 0, False
