$regPath='Registry::HKEY_LOCAL_MACHINE\System\CurrentControlSet\Control\Session Manager\Environment'

Write-Output 'Installing Icarus Verilog...'
Invoke-WebRequest -Uri http://bleyer.org/icarus/iverilog-10.1.1-x64_setup.exe -OutFile iverilog-10.1.1-x64_setup.exe
Start-Process .\iverilog-10.1.1-x64_setup -ArgumentList '/VERYSILENT' -Wait

$oldPath=(Get-ItemProperty -Path $regPath -Name PATH).Path
$newPath=$oldPath+";C:\iverilog\bin"
Set-ItemProperty -Path $regPath -Name PATH -Value $newPath

Write-Output 'Installing Miniconda ...'
Invoke-WebRequest -outfile miniconda3.exe https://repo.continuum.io/miniconda/Miniconda3-latest-Windows-x86_64.exe
Start-Process .\miniconda3.exe -ArgumentList '/S /D=C:\miniconda3' -Wait
$condaPath = "C:\miniconda3;C:\miniconda3\Library\mingw-w64\bin;C:\miniconda3\Library\usr\bin;C:\miniconda3\Library\bin;C:\miniconda3\Scripts;C:\miniconda3\bin;C:\miniconda3\condabin;"

$env:Path = $condaPath + $env:Path
conda config --set ssl_verify no
conda install --yes -c msys2 m2-base m2-make m2w64-toolchain
conda install --yes libpython

$oldPath=(Get-ItemProperty -Path $regPath -Name PATH).Path
$newPath=$condaPath+$oldPath
Set-ItemProperty -Path $regPath -Name PATH -Value $newPath

pip install tox

tox -e py37
