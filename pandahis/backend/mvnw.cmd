@REM ----------------------------------------------------------------------------
@REM Maven Wrapper startup batch script, Windows
@REM ----------------------------------------------------------------------------
@echo off
setlocal

set WRAPPER_DIR=%~dp0.mvn\wrapper
set WRAPPER_JAR=%WRAPPER_DIR%\maven-wrapper.jar
set WRAPPER_PROPS=%WRAPPER_DIR%\maven-wrapper.properties

if not exist "%WRAPPER_JAR%" (
  echo Maven wrapper jar not found, downloading...
  set WRAPPER_URL=https://repo.maven.apache.org/maven2/org/apache/maven/wrapper/maven-wrapper/3.3.2/maven-wrapper-3.3.2.jar
  powershell -NoProfile -ExecutionPolicy Bypass -Command ^
    "$p='%WRAPPER_JAR%'; $u='https://repo.maven.apache.org/maven2/org/apache/maven/wrapper/maven-wrapper/3.3.2/maven-wrapper-3.3.2.jar'; New-Item -ItemType Directory -Force -Path (Split-Path -Parent $p) | Out-Null; Invoke-WebRequest -UseBasicParsing -Uri $u -OutFile $p"
  if errorlevel 1 (
    echo Failed to download Maven wrapper jar.
    exit /b 1
  )
)

set JAVA_EXE=java
if defined JAVA_HOME set JAVA_EXE=%JAVA_HOME%\bin\java.exe

"%JAVA_EXE%" -Dmaven.multiModuleProjectDirectory=%~dp0 -classpath "%WRAPPER_JAR%" org.apache.maven.wrapper.MavenWrapperMain %*

endlocal

