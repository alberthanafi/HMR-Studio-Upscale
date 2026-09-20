Set shell = CreateObject("WScript.Shell")
Set fs = CreateObject("Scripting.FileSystemObject")
root = fs.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = root
python = root & "\.venv\Scripts\pythonw.exe"
If Not fs.FileExists(python) Then
  MsgBox "Run Install.cmd first to install HMR Upscale.", 64, "HMR Upscale"
Else
  shell.Run Chr(34) & python & Chr(34) & " " & Chr(34) & root & "\app.py" & Chr(34), 1, False
End If
