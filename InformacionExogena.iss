; Inno Setup Script for "Informacion Exogena"
; Instala el EXE generado por PyInstaller y crea acceso directo.
; Incluye asistente de licenciamiento online (producto + licencia).

#define AppPeriodo "2025"
#define LicenseApiUrl "https://TODO-LICENSE-ENDPOINT/api/licenses/validate"
#define MockLicenseValidation "1"

[Setup]
AppName=Informacion Exogena
AppVersion=1.0.0
AppPublisher=ExogenaFlet
DefaultDirName={autopf}\InformacionExogena
DefaultGroupName=Informacion Exogena
DisableProgramGroupPage=yes
OutputDir=installer_output
OutputBaseFilename=setup_InformacionExogena
SetupIconFile=resources\images\icono.ico

PrivilegesRequired=admin
ArchitecturesInstallIn64BitMode=x64

[Files]
; Se asume que ya construiste PyInstaller y tienes dist\InformacionExogena.exe
Source: "dist\InformacionExogena.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Informacion Exogena"; Filename: "{app}\InformacionExogena.exe"; WorkingDir: "{app}"

; Nota: WorkingDir se usa para que la app cree archivos temporales en la carpeta instalada
Name: "{commondesktop}\Informacion Exogena"; Filename: "{app}\InformacionExogena.exe"; WorkingDir: "{app}"

[Run]
Filename: "{app}\InformacionExogena.exe"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent; Check: ShouldRunApp

[Code]
var
  ProductoPage: TInputOptionWizardPage;
  LicenciaPage: TInputQueryWizardPage;
  ProductoSeleccionado: string;
  LicenciaIngresada: string;
  LicenciaValidada: Boolean;

function EncryptExogena(const Value: string): string;
var
  I: Integer;
  Codigo: Integer;
begin
  Result := '';
  for I := Length(Value) downto 1 do
  begin
    Codigo := Ord(Value[I]);
    if (I mod 2) <> 0 then
      Result := Result + Chr(Codigo - I)
    else
      Result := Result + Chr(Codigo + I);
  end;
end;

function ValidateLicenseOnline(
  const Producto: string;
  const Licencia: string;
  var MensajeError: string
): Boolean;
var
  Http: Variant;
  Body: string;
  StatusCode: Integer;
begin
  Result := False;
  MensajeError := '';

  { Modo temporal para avanzar mientras se implementa el backend real de licencias. }
  if '{#MockLicenseValidation}' = '1' then
  begin
    Result := True;
    exit;
  end;

  try
    Http := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Http.Open('POST', '{#LicenseApiUrl}', False);
    Http.SetRequestHeader('Content-Type', 'application/json');

    { TODO: Ajustar el contrato JSON al servicio real de licencias. }
    Body :=
      '{' +
      '"producto":"' + Producto + '",' +
      '"licencia":"' + Licencia + '"' +
      '}';

    Http.Send(Body);
    StatusCode := Http.Status;

    { TODO: Cuando exista backend, validar cuerpo de respuesta además del status. }
    Result := (StatusCode = 200);
    if not Result then
      MensajeError :=
        'No fue posible validar la licencia online (HTTP ' + IntToStr(StatusCode) + ').';
  except
    MensajeError :=
      'Error de conectividad al validar la licencia. Verifique internet y el endpoint.';
  end;
end;

procedure GuardarLicenciaInstalada(const Producto: string; const Licencia: string);
var
  Llave: string;
  LicenciaCifrada: string;
begin
  Llave := 'Software\WOW6432Node\Helisa\Exogena\{#AppPeriodo}';
  LicenciaCifrada := EncryptExogena(Licencia);

  { Se reutiliza el mismo esquema de cifrado reversible del proyecto (fn_bd_helisa.py). }
  RegWriteStringValue(HKLM, Llave, 'ProductoLicenciado', Producto);
  RegWriteStringValue(HKLM, Llave, 'LicenciaExogena', LicenciaCifrada);
  RegWriteStringValue(HKLM, Llave, 'LicenciaValidadaEn', GetDateTimeString('yyyy-mm-dd hh:nn:ss', '-', ':'));
end;

procedure InitializeWizard;
begin
  LicenciaValidada := False;
  ProductoSeleccionado := '';
  LicenciaIngresada := '';

  { Exclusive=False: checkboxes (se puede marcar NI y PH al tiempo). }
  ProductoPage := CreateInputOptionPage(
    wpWelcome,
    'Identificación de producto',
    'Seleccione el Aplicativo Contable',
    'Marque el producto Helisa según la licencia adquirida.',
    False,
    False
  );
  ProductoPage.Add('Helisa Norma Internacional');
  ProductoPage.Add('Helisa Propiedad Horizontal');
  ProductoPage.Values[0] := True;

  LicenciaPage := CreateInputQueryPage(
    ProductoPage.ID,
    'Licencia de Información Exógena',
    'Ingrese la licencia adquirida',
    'El instalador validará en línea la licencia antes de finalizar.'
  );
  LicenciaPage.Add('Licencia de Información Exógena:', False);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  MensajeError: string;
begin
  Result := True;

  if CurPageID = ProductoPage.ID then
  begin
    ProductoSeleccionado := '';
    if ProductoPage.Values[0] then
      ProductoSeleccionado := 'NI';
    if ProductoPage.Values[1] then
    begin
      if ProductoSeleccionado = '' then
        ProductoSeleccionado := 'PH'
      else
        ProductoSeleccionado := ProductoSeleccionado + ',PH';
    end;
    if ProductoSeleccionado = '' then
    begin
      MsgBox(
        'Debe seleccionar al menos un producto (Norma Internacional y/o Propiedad Horizontal).',
        mbError,
        MB_OK
      );
      Result := False;
      exit;
    end;
  end;

  if CurPageID = LicenciaPage.ID then
  begin
    LicenciaIngresada := Trim(LicenciaPage.Values[0]);
    if LicenciaIngresada = '' then
    begin
      MsgBox('Debe ingresar la licencia de Información Exógena.', mbError, MB_OK);
      Result := False;
      exit;
    end;

    WizardForm.StatusLabel.Caption := 'Validando licencia online...';
    WizardForm.Update;

    if not ValidateLicenseOnline(ProductoSeleccionado, LicenciaIngresada, MensajeError) then
    begin
      MsgBox(MensajeError, mbError, MB_OK);
      LicenciaValidada := False;
      Result := False;
      exit;
    end;

    GuardarLicenciaInstalada(ProductoSeleccionado, LicenciaIngresada);
    LicenciaValidada := True;
    MsgBox('Licencia validada correctamente. La instalación continuará.', mbInformation, MB_OK);
  end;
end;

function InitializeSetup: Boolean;
begin
  if WizardSilent then
  begin
    MsgBox(
      'La instalación silenciosa no está disponible porque se requiere validación de licencia online.',
      mbError,
      MB_OK
    );
    Result := False;
    exit;
  end;
  Result := True;
end;

function ShouldRunApp: Boolean;
begin
  Result := LicenciaValidada;
end;

