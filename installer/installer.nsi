; Muse Video Studio - NSIS installer script
; Build tren GitHub Actions: makensis installer\installer.nsi
; DISTDIR/OUTFILE truyen tu workflow bang /D (duong dan TUYET DOI) de tranh
; loi "no files found" khi makensis resolve duong dan tuong doi.
Unicode True
!include "MUI2.nsh"

!ifndef DISTDIR
  !define DISTDIR "dist\MuseVideoStudio"
!endif
!ifndef OUTFILE
  !define OUTFILE "MuseVideoStudio-Setup.exe"
!endif

Name "Muse Video Studio"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES\MuseVideoStudio"
InstallDirRegKey HKLM "Software\MuseVideoStudio" "InstallDir"
RequestExecutionLevel admin

; Icon cho installer + uninstaller (đường dẫn TUYỆT ĐỐI qua /DICONICO,
; vì makensis không resolve đúng đường dẫn tương đối từ repo root)
!ifndef ICONICO
  !define ICONICO "app\assets\icon.ico"
!endif
Icon "${ICONICO}"
UninstallIcon "${ICONICO}"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES

!insertmacro MUI_LANGUAGE "English"

Section "Install"
  ; Tat app cu dang chay (thuong nam duoi khay he thong) de ghi de file duoc.
  ; Diet ca tien trinh app cu SocialUploader neu van con (tuan chay song song).
  ; nsExec co san trong NSIS; taskkill co san tren Windows.
  nsExec::ExecToLog 'taskkill /F /IM MuseVideoStudio.exe'
  nsExec::ExecToLog 'taskkill /F /IM SocialUploader.exe'
  Sleep 1500

  SetOutPath "$INSTDIR"
  File /r "${DISTDIR}\*.*"

  WriteRegStr HKLM "Software\MuseVideoStudio" "InstallDir" "$INSTDIR"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Start Menu shortcuts
  CreateDirectory "$SMPROGRAMS\Muse Video Studio"
  CreateShortcut "$SMPROGRAMS\Muse Video Studio\Muse Video Studio.lnk" \
    "$INSTDIR\MuseVideoStudio.exe"
  CreateShortcut "$SMPROGRAMS\Muse Video Studio\Uninstall.lnk" \
    "$INSTDIR\Uninstall.exe"

  ; Desktop shortcut
  CreateShortcut "$DESKTOP\Muse Video Studio.lnk" \
    "$INSTDIR\MuseVideoStudio.exe"

  ; Add/Remove Programs entry
  WriteRegStr HKLM \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseVideoStudio" \
    "DisplayName" "Muse Video Studio"
  WriteRegStr HKLM \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseVideoStudio" \
    "UninstallString" "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  nsExec::ExecToLog 'taskkill /F /IM MuseVideoStudio.exe'
  Sleep 1500

  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR"

  DeleteRegKey HKLM "Software\MuseVideoStudio"
  DeleteRegKey HKLM \
    "Software\Microsoft\Windows\CurrentVersion\Uninstall\MuseVideoStudio"

  Delete "$SMPROGRAMS\Muse Video Studio\Muse Video Studio.lnk"
  Delete "$SMPROGRAMS\Muse Video Studio\Uninstall.lnk"
  RMDir "$SMPROGRAMS\Muse Video Studio"
  Delete "$DESKTOP\Muse Video Studio.lnk"
SectionEnd
