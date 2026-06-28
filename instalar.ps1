# =====================================================================
#  Instalador Automatizado - FFmpeg Converter
# =====================================================================

# 1. Definindo os caminhos dinâmicos
$ScriptDir = $PSScriptRoot
$InstallDir = Join-Path -Path $env:USERPROFILE -ChildPath ".ffconverter"

Write-Host "Iniciando a instalação do FFConverter..." -ForegroundColor Cyan

# 2. Criando o diretório de destino (se não existir)
if (-Not (Test-Path -Path $InstallDir)) {
    Write-Host "-> Criando diretório em: $InstallDir"
    New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
}

# 3. Copiando os arquivos do repositório para o diretório de destino
Write-Host "-> Copiando arquivos..."
Copy-Item -Path "$ScriptDir\*" -Destination $InstallDir -Recurse -Force

# 4. Criando o arquivo .bat no destino dinamicamente
Write-Host "-> Configurando o executável (.bat)..."
$BatPath = Join-Path -Path $InstallDir -ChildPath "ffconverter.bat"
$BatContent = "@echo off`npython `"$InstallDir\converter.py`" %*"
Set-Content -Path $BatPath -Value $BatContent

# 5. Gerando o arquivo .reg dinamicamente
# O Windows Registry exige que os caminhos tenham barras duplas (\\)
Write-Host "-> Gerando chaves de registro..."
$EscapedInstallDir = $InstallDir -replace '\\', '\\'
$RegPath = Join-Path -Path $InstallDir -ChildPath "instalar_menu.reg"

# Usando HKEY_CURRENT_USER\Software\Classes para não exigir permissão de Administrador
$RegContent = @"
Windows Registry Editor Version 5.00

[HKEY_CURRENT_USER\Software\Classes\*\shell\FFConverter]
@="Converter Mídia (FFmpeg)"
"Icon"="cmd.exe"

[HKEY_CURRENT_USER\Software\Classes\*\shell\FFConverter\command]
@="\"$EscapedInstallDir\\ffconverter.bat\" \"%1\""
"@

Set-Content -Path $RegPath -Value $RegContent

# 6. Executando o arquivo .reg silenciosamente
Write-Host "-> Inserindo opção no menu de contexto..."
Start-Process -FilePath "reg.exe" -ArgumentList "import `"$RegPath`"" -Wait -NoNewWindow

Write-Host "`nInstalação concluída com sucesso! 🎉" -ForegroundColor Green
Write-Host "Você já pode clicar com o botão direito em qualquer mídia para testar." -ForegroundColor Yellow