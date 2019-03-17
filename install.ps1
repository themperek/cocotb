Write-Output 'Installing Icarus Verilog...'
Invoke-WebRequest -Uri http://bleyer.org/icarus/iverilog-10.1.1-x64_setup.exe -OutFile iverilog-10.1.1-x64_setup.exe
Start-Process .\iverilog-10.1.1-x64_setup -ArgumentList '/VERYSILENT' -Wait
$env:Path = $env:Path + ";C:\iverilog\bin"

Write-Output 'Installing Miniconda ...'
Invoke-WebRequest -outfile miniconda3.exe https://repo.continuum.io/miniconda/Miniconda3-latest-Windows-x86_64.exe
Start-Process .\miniconda3.exe -ArgumentList '/S /D=C:\miniconda3' -Wait
$condaPath = "C:\miniconda3;C:\miniconda3\Library\mingw-w64\bin;C:\miniconda3\Library\usr\bin;C:\miniconda3\Library\bin;C:\miniconda3\Scripts;C:\miniconda3\bin;C:\miniconda3\condabin;"



$env:Path = $condaPath + $env:Path
conda config --set ssl_verify no
conda install --yes -c msys2 m2-base m2-make m2w64-toolchain
conda install --yes libpython

pip install tox

[Environment]::SetEnvironmentVariable("Path", $env:Path, [System.EnvironmentVariableTarget]::Machine)
[System.Environment]::SetEnvironmentVariable("Path", $env:Path, "Machine")

echo $env:Path

tox -e py37
