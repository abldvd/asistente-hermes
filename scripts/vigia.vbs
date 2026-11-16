' Arranca el vigía de juegos sin ventana (lo copia aplicar.ps1 a la carpeta Inicio).
Set sh = CreateObject("WScript.Shell")
sh.CurrentDirectory = "E:\asistente-hermes"
sh.Run """E:\asistente-hermes\.venv\Scripts\pythonw.exe"" -m asistente.vigia", 0, False
