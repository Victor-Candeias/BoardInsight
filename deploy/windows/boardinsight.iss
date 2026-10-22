; BoardInsight — instalador Windows (Inno Setup 6). Gerado em Linux por deploy/windows/build-installer.sh:
;   ISCC /DAppVersion=0.1.0 /DStageDir=<stage> /O<saída> boardinsight.iss
; Programa em {autopf}\BoardInsight; dados (.env, MongoDB, exportações, logs) em %ProgramData%\BoardInsight,
; acessíveis só a SYSTEM e Administradores e preservados em atualizações e desinstalação.
; Instalação silenciosa: /VERYSILENT /URL= /BOARD= /PORT= (e /TASKS="" para não abrir a firewall). A API key vem da
; variável de ambiente BOARDINSIGHT_SETUP_API_KEY e nunca da linha de comandos (o Inno regista-a no log).

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef StageDir
  #error "Definir StageDir (pasta preparada pelo build-installer.sh)"
#endif

#define AppName "BoardInsight"
#define DataDir "{commonappdata}\BoardInsight"
#define DefaultUrl "https://cttv8.kanbanize.com"
#define DefaultBoard "96"
#define DefaultPort "8080"

[Setup]
AppId={{8C1B6E2A-4F3D-4B7E-9A51-3D2C7E9F1A60}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppName}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Windows 10 1809 / Server 2019 ou superior (requisito do MongoDB 8.0).
MinVersion=10.0.17763
PrivilegesRequired=admin
OutputBaseFilename=BoardInsight-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
LZMAUseSeparateProcess=yes
WizardStyle=modern
SetupLogging=yes
TimeStampsInUTC=yes
CloseApplications=no
UninstallDisplayName={#AppName}

[Languages]
Name: "pt"; MessagesFile: "compiler:Languages\Portuguese.isl"

[Tasks]
Name: "firewall"; Description: "Permitir o acesso ao site a partir da rede local (regra de firewall, só sub-rede local)"

[Dirs]
Name: "{#DataDir}"; Flags: uninsneveruninstall
Name: "{#DataDir}\mongodb"; Flags: uninsneveruninstall
Name: "{#DataDir}\exports"; Flags: uninsneveruninstall
Name: "{#DataDir}\logs"; Flags: uninsneveruninstall

[Files]
Source: "{#StageDir}\app\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#StageDir}\winsw\WinSW-x64.exe"; DestDir: "{app}"; DestName: "boardinsight-mongodb.exe"; Flags: ignoreversion
Source: "{#StageDir}\winsw\WinSW-x64.exe"; DestDir: "{app}"; DestName: "boardinsight-api.exe"; Flags: ignoreversion
Source: "{#StageDir}\winsw\WinSW-x64.exe"; DestDir: "{app}"; DestName: "boardinsight-worker.exe"; Flags: ignoreversion
Source: "{#StageDir}\redist\vc_redist.x64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[INI]
Filename: "{group}\Abrir o BoardInsight.url"; Section: "InternetShortcut"; Key: "URL"; String: "http://localhost:{code:GetPort}/"

[Icons]
Name: "{group}\Logs do BoardInsight"; Filename: "{#DataDir}\logs"
Name: "{group}\Desinstalar o BoardInsight"; Filename: "{uninstallexe}"

[Run]
Filename: "http://localhost:{code:GetPort}/"; Description: "Abrir o BoardInsight no browser"; Flags: postinstall shellexec nowait skipifsilent

[UninstallDelete]
Type: files; Name: "{group}\Abrir o BoardInsight.url"
Type: filesandordirs; Name: "{app}\backend"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\mongodb"
Type: dirifempty; Name: "{app}"

[Code]
const
  ApiKeyEnv = 'BOARDINSIGHT_SETUP_API_KEY';
  FirewallRule = 'BoardInsight';
  SyncTask = 'BoardInsight\Sync';

var
  ConfigPage: TInputQueryWizardPage;
  HasExistingKey: Boolean;

function SetEnvironmentVariable(lpName: String; lpValue: String): BOOL;
  external 'SetEnvironmentVariableW@kernel32.dll stdcall';

function DataDir: String;
begin
  Result := ExpandConstant('{#DataDir}');
end;

function EnvFile: String;
begin
  Result := DataDir + '\.env';
end;

function ReadEnvValue(const Key: String): String;
var
  Lines: TArrayOfString;
  I: Integer;
  Line, Prefix: String;
begin
  Result := '';
  if not LoadStringsFromFile(EnvFile, Lines) then
    Exit;
  Prefix := Key + '=';
  for I := 0 to GetArrayLength(Lines) - 1 do
  begin
    Line := Trim(Lines[I]);
    if Pos(Prefix, Line) = 1 then
    begin
      Result := Trim(Copy(Line, Length(Prefix) + 1, MaxInt));
      Exit;
    end;
  end;
end;

{ Valor inicial: parâmetro da linha de comandos > .env existente > omissão. }
function Initial(const Param, EnvKey, Default: String): String;
begin
  Result := ExpandConstant('{param:' + Param + '|}');
  if Result = '' then
    Result := ReadEnvValue(EnvKey);
  if Result = '' then
    Result := Default;
end;

function InstanceUrl: String;
begin
  Result := Trim(ConfigPage.Values[0]);
  while (Length(Result) > 0) and (Result[Length(Result)] = '/') do
    SetLength(Result, Length(Result) - 1);
end;

function ApiKey: String;
begin
  Result := Trim(ConfigPage.Values[1]);
end;

function BoardId: String;
begin
  Result := Trim(ConfigPage.Values[2]);
end;

function GetPort(Param: String): String;
begin
  Result := Trim(ConfigPage.Values[3]);
end;

function RunQuiet(const FileName, Params: String): Integer;
var
  Code: Integer;
begin
  { Nunca passar a API key em Params: os comandos ficam no log de instalação. }
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, Code) then
    Code := -1;
  Log(Format('exec: %s %s -> %d', [FileName, Params, Code]));
  Result := Code;
end;

function ServiceCmd(const Id, Command: String): Integer;
var
  Exe: String;
begin
  Exe := ExpandConstant('{app}\' + Id + '.exe');
  if FileExists(Exe) then
    Result := RunQuiet(Exe, Command)
  else
    Result := -1;
end;

procedure SetStatus(const Text: String);
begin
  WizardForm.StatusLabel.Caption := Text;
  Log(Text);
end;

procedure Warn(const Text: String);
begin
  Log('AVISO: ' + Text);
  SuppressibleMsgBox(Text, mbError, MB_OK, IDOK);
end;

function CheckBusinessmap(var Detail: String): Boolean;
var
  Request: Variant;
  Status: Integer;
  Body: String;
begin
  Result := False;
  try
    Request := CreateOleObject('WinHttp.WinHttpRequest.5.1');
    Request.SetTimeouts(10000, 10000, 20000, 20000);
    Request.Open('GET', InstanceUrl + '/api/v2/boards?board_ids=' + BoardId, False);
    Request.SetRequestHeader('apikey', ApiKey);
    Request.SetRequestHeader('Accept', 'application/json');
    Request.Send('');
    Status := Request.Status;
    Body := Request.ResponseText;
    if Status = 200 then
    begin
      Result := Pos('"board_id"', Body) > 0;
      if not Result then
        Detail := 'o board ' + BoardId + ' não existe ou a API key não tem acesso a ele';
    end
    else if (Status = 401) or (Status = 403) then
      Detail := 'API key recusada (HTTP ' + IntToStr(Status) + ')'
    else
      Detail := 'resposta HTTP ' + IntToStr(Status);
  except
    Detail := GetExceptionMessage;
  end;
end;

procedure InitializeWizard;
begin
  HasExistingKey := ReadEnvValue('BUSINESSMAP_API_KEY') <> '';
  ConfigPage := CreateInputQueryPage(wpSelectTasks,
    'Ligação ao Businessmap',
    'Instância, API key e board inicial.',
    'A API key fica só em ' + EnvFile + ' (acesso restrito a Administradores e ao sistema).');
  ConfigPage.Add('URL da instância:', False);
  if HasExistingKey then
    ConfigPage.Add('API key (vazio = manter a atual):', True)
  else
    ConfigPage.Add('API key:', True);
  ConfigPage.Add('Board inicial (ID):', False);
  ConfigPage.Add('Porta do site:', False);
  ConfigPage.Values[0] := Initial('URL', 'BUSINESSMAP_BASE_URL', '{#DefaultUrl}');
  ConfigPage.Values[1] := GetEnv(ApiKeyEnv);
  ConfigPage.Values[2] := Initial('BOARD', 'BUSINESSMAP_BOARD_ID', '{#DefaultBoard}');
  ConfigPage.Values[3] := Initial('PORT', 'APP_PORT', '{#DefaultPort}');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  Detail, Url: String;
  Port: Integer;
begin
  Result := True;
  if CurPageID <> ConfigPage.ID then
    Exit;
  Url := Lowercase(InstanceUrl);
  if (Pos('https://', Url) <> 1) and (Pos('http://', Url) <> 1) then
  begin
    SuppressibleMsgBox('O URL da instância tem de começar por https:// ou http://', mbError, MB_OK, IDOK);
    Result := False;
    Exit;
  end;
  if StrToIntDef(BoardId, 0) <= 0 then
  begin
    SuppressibleMsgBox('O board inicial tem de ser um número inteiro positivo.', mbError, MB_OK, IDOK);
    Result := False;
    Exit;
  end;
  Port := StrToIntDef(GetPort(''), 0);
  if (Port < 1) or (Port > 65535) then
  begin
    SuppressibleMsgBox('A porta do site tem de estar entre 1 e 65535.', mbError, MB_OK, IDOK);
    Result := False;
    Exit;
  end;
  if ApiKey = '' then
  begin
    if not HasExistingKey then
    begin
      SuppressibleMsgBox('Indique a API key do Businessmap.', mbError, MB_OK, IDOK);
      Result := False;
    end;
    Exit;
  end;
  WizardForm.NextButton.Enabled := False;
  try
    if not CheckBusinessmap(Detail) then
      Result := SuppressibleMsgBox('Não foi possível validar a ligação ao Businessmap:' + #13#10 + Detail + #13#10#13#10 +
        'Continuar mesmo assim?', mbConfirmation, MB_YESNO or MB_DEFBUTTON2, IDYES) = IDYES;
  finally
    WizardForm.NextButton.Enabled := True;
  end;
end;

function UpdateReadyMemo(Space, NewLine, MemoUserInfoInfo, MemoDirInfo, MemoTypeInfo, MemoComponentsInfo,
  MemoGroupInfo, MemoTasksInfo: String): String;
var
  KeyInfo: String;
begin
  if ApiKey <> '' then
    KeyInfo := 'nova (oculta)'
  else
    KeyInfo := 'manter a atual';
  Result := MemoDirInfo + NewLine + NewLine +
    'Businessmap:' + NewLine +
    Space + 'Instância: ' + InstanceUrl + NewLine +
    Space + 'API key: ' + KeyInfo + NewLine +
    Space + 'Board inicial: ' + BoardId + NewLine + NewLine +
    'Site: http://localhost:' + GetPort('') + '/' + NewLine +
    'Dados: ' + DataDir;
  if MemoTasksInfo <> '' then
    Result := Result + NewLine + NewLine + MemoTasksInfo;
end;

procedure StopEverything;
begin
  RunQuiet(ExpandConstant('{sys}\schtasks.exe'), '/End /TN "' + SyncTask + '"');
  ServiceCmd('boardinsight-api', 'stopwait');
  ServiceCmd('boardinsight-worker', 'stopwait');
  ServiceCmd('boardinsight-mongodb', 'stopwait');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  StopEverything;
end;

function InstallService(const Id: String): Boolean;
begin
  ServiceCmd(Id, 'uninstall');
  Result := ServiceCmd(Id, 'install') = 0;
  if not Result then
    Warn('Não foi possível instalar o serviço ' + Id + '. Ver ' + DataDir + '\logs.');
end;

procedure ConfigureFirewall;
var
  Netsh: String;
begin
  Netsh := ExpandConstant('{sys}\netsh.exe');
  RunQuiet(Netsh, 'advfirewall firewall delete rule name="' + FirewallRule + '"');
  if WizardIsTaskSelected('firewall') then
    if RunQuiet(Netsh, 'advfirewall firewall add rule name="' + FirewallRule + '" dir=in action=allow protocol=TCP localport=' +
      GetPort('') + ' profile=domain,private remoteip=localsubnet') <> 0 then
      Warn('Não foi possível criar a regra de firewall "' + FirewallRule + '".');
end;

procedure PostInstall;
var
  Code: Integer;
  Params: String;
begin
  SetStatus('A proteger a pasta de dados...');
  RunQuiet(ExpandConstant('{sys}\icacls.exe'), '"' + DataDir + '" /inheritance:r /grant:r *S-1-5-18:(OI)(CI)F *S-1-5-32-544:(OI)(CI)F /Q');

  SetStatus('A instalar o Microsoft Visual C++ Redistributable...');
  Code := RunQuiet(ExpandConstant('{tmp}\vc_redist.x64.exe'), '/install /quiet /norestart');
  if (Code <> 0) and (Code <> 1638) and (Code <> 3010) then
    Warn('O Visual C++ Redistributable devolveu o código ' + IntToStr(Code) + '; o MongoDB pode não arrancar.');

  SetStatus('A instalar os serviços...');
  InstallService('boardinsight-mongodb');
  InstallService('boardinsight-api');
  InstallService('boardinsight-worker');

  SetStatus('A iniciar o MongoDB...');
  ServiceCmd('boardinsight-mongodb', 'start');

  SetStatus('A configurar o MongoDB e o board inicial...');
  SetEnvironmentVariable(ApiKeyEnv, ApiKey);
  SetEnvironmentVariable('BOARDINSIGHT_ENV_FILE', EnvFile);
  Params := '-m app.ops.windows_setup' +
    ' --env "' + EnvFile + '"' +
    ' --template "' + ExpandConstant('{app}\config\env.windows') + '"' +
    ' --admin-secret "' + DataDir + '\mongodb-admin.secret"' +
    ' --url "' + InstanceUrl + '"' +
    ' --board ' + BoardId +
    ' --port ' + GetPort('') +
    ' --frontend-dist "' + ExpandConstant('{app}\frontend\dist') + '"' +
    ' --log "' + DataDir + '\logs\setup.log"';
  Code := RunQuiet(ExpandConstant('{app}\python\python.exe'), Params);
  SetEnvironmentVariable(ApiKeyEnv, '');
  if Code = 2 then
    Warn('O board ' + BoardId + ' não foi registado (ver ' + DataDir + '\logs\setup.log). ' +
      'Pode adicioná-lo depois na página Boards do BoardInsight.')
  else if Code <> 0 then
    Warn('Falhou a configuração do MongoDB (código ' + IntToStr(Code) + '). Ver ' + DataDir + '\logs\setup.log.');

  SetStatus('A iniciar a API e o worker...');
  ServiceCmd('boardinsight-api', 'start');
  ServiceCmd('boardinsight-worker', 'start');

  SetStatus('A agendar a sincronização...');
  if RunQuiet(ExpandConstant('{sys}\schtasks.exe'), '/Create /TN "' + SyncTask + '" /TR "\"' + ExpandConstant('{app}\sync.cmd') +
    '\"" /SC MINUTE /MO 30 /RU SYSTEM /RL HIGHEST /F') <> 0 then
    Warn('Não foi possível criar a tarefa agendada "' + SyncTask + '".');

  SetStatus('A configurar a firewall...');
  ConfigureFirewall;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    PostInstall;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
  begin
    RunQuiet(ExpandConstant('{sys}\schtasks.exe'), '/Delete /TN "' + SyncTask + '" /F');
    StopEverything;
    ServiceCmd('boardinsight-api', 'uninstall');
    ServiceCmd('boardinsight-worker', 'uninstall');
    ServiceCmd('boardinsight-mongodb', 'uninstall');
    RunQuiet(ExpandConstant('{sys}\netsh.exe'), 'advfirewall firewall delete rule name="' + FirewallRule + '"');
  end;
  if (CurUninstallStep = usPostUninstall) and (not UninstallSilent) and DirExists(DataDir) then
    if MsgBox('Apagar também os dados do BoardInsight (' + DataDir + '), incluindo a base de dados, a configuração e a API key?',
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES then
      DelTree(DataDir, True, True, True);
end;
