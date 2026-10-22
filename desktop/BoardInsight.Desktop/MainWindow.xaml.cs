using System;
using System.Diagnostics;
using System.IO;
using System.Net.Http;
using System.Threading;
using System.Threading.Tasks;
using System.Windows;
using Microsoft.Web.WebView2.Core;

namespace BoardInsight.Desktop
{
    public partial class MainWindow : Window
    {
        private const string WebView2DownloadUrl = "https://developer.microsoft.com/microsoft-edge/webview2/";
        private static readonly TimeSpan ServerWaitTimeout = TimeSpan.FromMinutes(2);
        private static readonly TimeSpan ServerPollInterval = TimeSpan.FromSeconds(1);

        private readonly DesktopSettings _settings;
        private readonly HttpClient _http;
        private CancellationTokenSource? _startup;
        private bool _webViewReady;
        private bool _pageShown;
        private bool _browserProcessExited;

        public MainWindow(DesktopSettings settings)
        {
            _settings = settings;
            // O serviço é local (ou na LAN): nunca passar por um proxy corporativo.
            _http = new HttpClient(new HttpClientHandler { UseProxy = false }) { Timeout = TimeSpan.FromSeconds(5) };
            InitializeComponent();
            Loaded += async (_, _) => await StartAsync();
            Closed += (_, _) =>
            {
                _startup?.Cancel();
                _http.Dispose();
            };
        }

        private static string UserDataFolder =>
            Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "BoardInsight", "WebView2");

        private async Task StartAsync()
        {
            _startup?.Cancel();
            var startup = _startup = new CancellationTokenSource();
            ShowBusy("A abrir o BoardInsight…", "A preparar a janela.");

            if (!_webViewReady && !await InitializeWebViewAsync())
                return;

            ShowBusy("A ligar ao BoardInsight…", "À espera do serviço em " + _settings.BaseUrl + ".");
            if (!await WaitForServerAsync(startup.Token))
            {
                if (!startup.IsCancellationRequested)
                    ShowError("Não foi possível ligar ao BoardInsight",
                        "O serviço não respondeu em " + _settings.BaseUrl + ". Confirme que o serviço " +
                        "\"BoardInsight API e site\" (boardinsight-api) está a correr em services.msc e tente novamente.");
                return;
            }

            _pageShown = false;
            Browser.CoreWebView2.Navigate(_settings.BaseUrl.AbsoluteUri);
        }

        private async Task<bool> InitializeWebViewAsync()
        {
            try
            {
                var environment = await CoreWebView2Environment.CreateAsync(null, UserDataFolder);
                await Browser.EnsureCoreWebView2Async(environment);
            }
            catch (WebView2RuntimeNotFoundException)
            {
                ShowError("Falta o Microsoft Edge WebView2 Runtime",
                    "O BoardInsight precisa do WebView2 Runtime para mostrar o site dentro da janela. " +
                    "Instale-o (ou volte a correr o instalador do BoardInsight) ou abra o BoardInsight no browser.",
                    runtimeMissing: true);
                return false;
            }
            catch (Exception ex)
            {
                ShowError("Não foi possível iniciar o WebView2", ex.Message);
                return false;
            }

            var core = Browser.CoreWebView2;
            core.Settings.AreDevToolsEnabled = _settings.DevTools;
            core.Settings.IsStatusBarEnabled = false;
            core.Settings.IsPasswordAutosaveEnabled = false;
            core.Settings.IsGeneralAutofillEnabled = false;
            core.NavigationStarting += OnNavigationStarting;
            core.NavigationCompleted += OnNavigationCompleted;
            core.NewWindowRequested += OnNewWindowRequested;
            core.DocumentTitleChanged += (_, _) =>
                Title = string.IsNullOrWhiteSpace(core.DocumentTitle) ? "BoardInsight" : core.DocumentTitle;
            core.ProcessFailed += OnProcessFailed;
            _webViewReady = true;
            return true;
        }

        private async Task<bool> WaitForServerAsync(CancellationToken cancellation)
        {
            var started = Stopwatch.StartNew();
            while (!cancellation.IsCancellationRequested)
            {
                try
                {
                    using var response = await _http.GetAsync(_settings.HealthUrl, cancellation);
                    if (response.IsSuccessStatusCode)
                        return true;
                }
                catch (Exception) when (!cancellation.IsCancellationRequested)
                {
                    // Serviço ainda a arrancar (ex.: logo após ligar o PC): tentar outra vez.
                }
                catch (OperationCanceledException)
                {
                    return false;
                }

                if (started.Elapsed >= ServerWaitTimeout)
                    return false;
                if (started.Elapsed >= TimeSpan.FromSeconds(5))
                    StatusDetail.Text = "À espera do serviço em " + _settings.BaseUrl + " (" +
                        (int)started.Elapsed.TotalSeconds + " s). O serviço pode demorar a arrancar depois de ligar o PC.";
                try
                {
                    await Task.Delay(ServerPollInterval, cancellation);
                }
                catch (OperationCanceledException)
                {
                    return false;
                }
            }
            return false;
        }

        private void OnNavigationStarting(object? sender, CoreWebView2NavigationStartingEventArgs e)
        {
            if (_settings.IsAppUri(e.Uri))
                return;
            e.Cancel = true;
            OpenExternally(e.Uri);
        }

        private void OnNewWindowRequested(object? sender, CoreWebView2NewWindowRequestedEventArgs e)
        {
            e.Handled = true;
            if (_settings.IsAppUri(e.Uri))
                Browser.CoreWebView2.Navigate(e.Uri);
            else
                OpenExternally(e.Uri);
        }

        private void OnNavigationCompleted(object? sender, CoreWebView2NavigationCompletedEventArgs e)
        {
            if (e.IsSuccess)
            {
                _pageShown = true;
                Browser.Visibility = Visibility.Visible;
                StatusPanel.Visibility = Visibility.Collapsed;
            }
            else if (!_pageShown && e.WebErrorStatus != CoreWebView2WebErrorStatus.OperationCanceled)
            {
                ShowError("Não foi possível abrir o BoardInsight",
                    "O site em " + _settings.BaseUrl + " não respondeu (" + e.WebErrorStatus + ").");
            }
        }

        private void OnProcessFailed(object? sender, CoreWebView2ProcessFailedEventArgs e)
        {
            if (e.ProcessFailedKind != CoreWebView2ProcessFailedKind.BrowserProcessExited &&
                e.ProcessFailedKind != CoreWebView2ProcessFailedKind.RenderProcessExited &&
                e.ProcessFailedKind != CoreWebView2ProcessFailedKind.RenderProcessUnresponsive)
                return;
            _browserProcessExited = e.ProcessFailedKind == CoreWebView2ProcessFailedKind.BrowserProcessExited;
            ShowError("A página do BoardInsight deixou de responder",
                _browserProcessExited
                    ? "O WebView2 terminou inesperadamente. Tentar novamente reinicia a janela."
                    : "Tentar novamente volta a carregar a página.");
        }

        private async void Retry_Click(object sender, RoutedEventArgs e)
        {
            if (_browserProcessExited)
            {
                RestartApplication();
                return;
            }
            await StartAsync();
        }

        private void InstallRuntime_Click(object sender, RoutedEventArgs e) => OpenExternally(WebView2DownloadUrl);

        private void OpenInBrowser_Click(object sender, RoutedEventArgs e) => OpenExternally(_settings.BaseUrl.AbsoluteUri);

        private void ShowBusy(string title, string detail)
        {
            Browser.Visibility = Visibility.Hidden;
            StatusPanel.Visibility = Visibility.Visible;
            StatusTitle.Text = title;
            StatusDetail.Text = detail;
            Progress.Visibility = Visibility.Visible;
            Actions.Visibility = Visibility.Collapsed;
        }

        private void ShowError(string title, string detail, bool runtimeMissing = false)
        {
            ShowBusy(title, detail);
            Progress.Visibility = Visibility.Collapsed;
            Actions.Visibility = Visibility.Visible;
            InstallRuntimeButton.Visibility = runtimeMissing ? Visibility.Visible : Visibility.Collapsed;
        }

        private static void OpenExternally(string? uri)
        {
            if (!DesktopSettings.CanOpenExternally(uri))
                return;
            try
            {
                Process.Start(new ProcessStartInfo(uri!) { UseShellExecute = true });
            }
            catch (Exception ex)
            {
                MessageBox.Show("Não foi possível abrir " + uri + ":\n\n" + ex.Message, "BoardInsight",
                    MessageBoxButton.OK, MessageBoxImage.Warning);
            }
        }

        private static void RestartApplication()
        {
            var exe = Process.GetCurrentProcess().MainModule?.FileName;
            if (exe != null)
            {
                var args = Environment.GetCommandLineArgs();
                var quoted = new string[Math.Max(0, args.Length - 1)];
                for (var i = 1; i < args.Length; i++)
                    quoted[i - 1] = "\"" + args[i].Replace("\"", "\\\"") + "\"";
                Process.Start(new ProcessStartInfo(exe, string.Join(" ", quoted)) { UseShellExecute = false });
            }
            Application.Current.Shutdown();
        }
    }
}
