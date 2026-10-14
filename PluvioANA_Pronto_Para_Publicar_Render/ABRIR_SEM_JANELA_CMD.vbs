' Abre o PluvioANA no navegador sem exibir terminal (requer Python no Windows).
' Para encerrar o servidor oculto, feche o processo pythonw.exe/pyw.exe no Gerenciador de Tarefas.
Set shell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
folder = fso.GetParentFolderName(WScript.ScriptFullName)
shell.CurrentDirectory = folder
shell.Run "pyw -3 """ & folder & "\servidor.py"" --no-browser", 0, False
WScript.Sleep 1500
shell.Run "http://127.0.0.1:8765", 1, False
